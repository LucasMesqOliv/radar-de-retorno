"""Camada de dados do Radar de Retorno.

Usa PostgreSQL quando ``DATABASE_URL`` está configurada e mantém o SQLite
local como fallback. Assim, o site continua funcionando localmente e passa a
preservar novos dados entre reinicializações quando conectado ao banco online.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
from threading import Lock
import unicodedata

import pandas as pd


COLUNAS_COTAS = [
    "cnpj",
    "data",
    "cota",
    "patrimonio",
    "captacao_dia",
    "resgate_dia",
    "cotistas",
]

COLUNAS_CADASTRO_FUNDOS = [
    "cnpj",
    "nome",
    "data_constituicao",
    "situacao",
    "tipo",
    "classificacao",
    "classificacao_anbima",
    "indicador_desempenho",
    "publico_alvo",
    "patrimonio_cadastral",
    "data_patrimonio_cadastral",
    "administrador",
    "gestor",
    "em_funcionamento",
]

_POOL_POSTGRES = None
_LOCK_POOL = Lock()
_LOCK_SCHEMA = Lock()
_SCHEMAS_INICIALIZADOS: set[str] = set()


def url_banco_remoto() -> str:
    return os.environ.get("DATABASE_URL", "").strip()


def backend_banco() -> str:
    return "postgresql" if url_banco_remoto() else "sqlite"


def caminho_banco() -> Path:
    configurado = os.environ.get("RADAR_DB_PATH", "").strip()
    if configurado:
        caminho = Path(configurado).expanduser()
    else:
        caminho = Path(__file__).resolve().parent / "data" / "radar_retorno.db"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    return caminho


def _pool_postgres():
    global _POOL_POSTGRES
    if _POOL_POSTGRES is None:
        with _LOCK_POOL:
            if _POOL_POSTGRES is None:
                from psycopg_pool import ConnectionPool

                _POOL_POSTGRES = ConnectionPool(
                    conninfo=url_banco_remoto(),
                    min_size=1,
                    max_size=5,
                    timeout=30,
                    kwargs={"connect_timeout": 15},
                )
    return _POOL_POSTGRES


def _sql(comando: str) -> str:
    return comando.replace("?", "%s") if backend_banco() == "postgresql" else comando


def _executar(banco, comando: str, parametros=()):
    cursor = banco.cursor()
    cursor.execute(_sql(comando), parametros)
    return cursor


def _executar_muitos(banco, comando: str, linhas) -> None:
    cursor = banco.cursor()
    try:
        cursor.executemany(_sql(comando), linhas)
    finally:
        cursor.close()


def _ler_dataframe(banco, comando: str, parametros, colunas: list[str]) -> pd.DataFrame:
    cursor = _executar(banco, comando, parametros)
    try:
        return pd.DataFrame(cursor.fetchall(), columns=colunas)
    finally:
        cursor.close()


def _garantir_schema(banco) -> None:
    backend = backend_banco()
    if backend in _SCHEMAS_INICIALIZADOS:
        return
    with _LOCK_SCHEMA:
        if backend not in _SCHEMAS_INICIALIZADOS:
            inicializar(banco)
            banco.commit()
            _SCHEMAS_INICIALIZADOS.add(backend)


@contextmanager
def conexao():
    if backend_banco() == "postgresql":
        with _pool_postgres().connection() as banco:
            _garantir_schema(banco)
            try:
                yield banco
                banco.commit()
            except Exception:
                banco.rollback()
                raise
        return

    banco = sqlite3.connect(caminho_banco(), timeout=30)
    try:
        banco.execute("PRAGMA journal_mode=WAL")
        banco.execute("PRAGMA synchronous=NORMAL")
        banco.execute("PRAGMA busy_timeout=30000")
        _garantir_schema(banco)
        yield banco
        banco.commit()
    except Exception:
        banco.rollback()
        raise
    finally:
        banco.close()


def inicializar(banco) -> None:
    if backend_banco() == "postgresql":
        _executar(banco, "CREATE EXTENSION IF NOT EXISTS unaccent").close()
        _executar(banco, "CREATE EXTENSION IF NOT EXISTS pg_trgm").close()
    _executar(
        banco,
        """
        CREATE TABLE IF NOT EXISTS series_mercado (
            codigo TEXT NOT NULL,
            data TEXT NOT NULL,
            valor DOUBLE PRECISION NOT NULL,
            atualizado_em TEXT NOT NULL,
            PRIMARY KEY (codigo, data)
        )
        """
    ).close()
    _executar(
        banco,
        """
        CREATE TABLE IF NOT EXISTS cadastro_fundos (
            cnpj TEXT NOT NULL PRIMARY KEY,
            nome TEXT NOT NULL,
            data_constituicao TEXT,
            situacao TEXT,
            tipo TEXT,
            classificacao TEXT,
            classificacao_anbima TEXT,
            indicador_desempenho TEXT,
            publico_alvo TEXT,
            patrimonio_cadastral DOUBLE PRECISION,
            data_patrimonio_cadastral TEXT,
            administrador TEXT,
            gestor TEXT,
            em_funcionamento INTEGER NOT NULL,
            busca TEXT NOT NULL DEFAULT '',
            atualizado_em TEXT NOT NULL
        )
        """
    ).close()
    _executar(
        banco,
        "ALTER TABLE cadastro_fundos ADD COLUMN IF NOT EXISTS busca TEXT NOT NULL DEFAULT ''",
    ).close()
    if backend_banco() == "postgresql":
        _executar(
            banco,
            """
            CREATE INDEX IF NOT EXISTS cadastro_fundos_busca_trgm_idx
            ON cadastro_fundos USING gin (busca gin_trgm_ops)
            """,
        ).close()
    _executar(
        banco,
        """
        CREATE TABLE IF NOT EXISTS cotas_fundos (
            cnpj TEXT NOT NULL,
            data TEXT NOT NULL,
            cota DOUBLE PRECISION NOT NULL,
            patrimonio DOUBLE PRECISION,
            captacao_dia DOUBLE PRECISION,
            resgate_dia DOUBLE PRECISION,
            cotistas DOUBLE PRECISION,
            atualizado_em TEXT NOT NULL,
            PRIMARY KEY (cnpj, data)
        )
        """
    ).close()
    # A chave primária composta já cria o índice usado nas consultas por fundo
    # e intervalo; um segundo índice idêntico só aumentaria o arquivo.
    _executar(banco, "DROP INDEX IF EXISTS idx_cotas_fundos_cnpj_data").close()
    _executar(
        banco,
        """
        CREATE TABLE IF NOT EXISTS periodos_consultados (
            tipo TEXT NOT NULL,
            identificador TEXT NOT NULL,
            periodo TEXT NOT NULL,
            possui_dados INTEGER NOT NULL,
            consultado_em TEXT NOT NULL,
            PRIMARY KEY (tipo, identificador, periodo)
        )
        """
    ).close()


def carregar_serie_mercado(codigo: str) -> pd.DataFrame:
    with conexao() as banco:
        dados = _ler_dataframe(
            banco,
            "SELECT data, valor FROM series_mercado WHERE codigo = ? ORDER BY data",
            (codigo,),
            ["data", "valor"],
        )
    if dados.empty:
        return pd.DataFrame(columns=["data", "valor"])
    dados["data"] = pd.to_datetime(dados["data"], errors="coerce")
    dados["valor"] = pd.to_numeric(dados["valor"], errors="coerce")
    return dados.dropna(subset=["data", "valor"])


def carregar_cadastro_fundos() -> pd.DataFrame:
    with conexao() as banco:
        dados = _ler_dataframe(
            banco,
            """
            SELECT cnpj, nome, data_constituicao, situacao, tipo, classificacao,
                   classificacao_anbima, indicador_desempenho, publico_alvo,
                   patrimonio_cadastral, data_patrimonio_cadastral,
                   administrador, gestor, em_funcionamento
            FROM cadastro_fundos
            ORDER BY em_funcionamento DESC, patrimonio_cadastral DESC
            """,
            (),
            COLUNAS_CADASTRO_FUNDOS,
        )
    return _normalizar_dataframe_cadastro(dados)


def fechar_conexoes() -> None:
    global _POOL_POSTGRES
    if _POOL_POSTGRES is not None:
        _POOL_POSTGRES.close()
        _POOL_POSTGRES = None


def contar_cadastro_fundos() -> int:
    with conexao() as banco:
        cursor = _executar(banco, "SELECT COUNT(*) FROM cadastro_fundos")
        resultado = cursor.fetchone()
        cursor.close()
    return int(resultado[0]) if resultado else 0


def buscar_cadastro_fundos(
    termo: str,
    digitos: str = "",
    limite: int = 30,
) -> pd.DataFrame:
    if digitos:
        filtro = "cnpj LIKE ?"
        parametros = (f"%{digitos}%", limite)
    else:
        palavras = [palavra for palavra in termo.lower().split() if palavra]
        if not palavras:
            return pd.DataFrame(columns=COLUNAS_CADASTRO_FUNDOS)
        filtro = " AND ".join("busca LIKE ?" for _ in palavras)
        parametros = (*[f"%{palavra}%" for palavra in palavras], limite)

    with conexao() as banco:
        dados = _ler_dataframe(
            banco,
            f"""
            SELECT cnpj, nome, data_constituicao, situacao, tipo, classificacao,
                   classificacao_anbima, indicador_desempenho, publico_alvo,
                   patrimonio_cadastral, data_patrimonio_cadastral,
                   administrador, gestor, em_funcionamento
            FROM cadastro_fundos
            WHERE {filtro}
            ORDER BY em_funcionamento DESC, patrimonio_cadastral DESC
            LIMIT ?
            """,
            parametros,
            COLUNAS_CADASTRO_FUNDOS,
        )
    return _normalizar_dataframe_cadastro(dados)


def carregar_cadastro_fundos_por_cnpj(cnpjs: tuple[str, ...]) -> pd.DataFrame:
    if not cnpjs:
        return pd.DataFrame(columns=COLUNAS_CADASTRO_FUNDOS)
    marcadores = ",".join("?" for _ in cnpjs)
    with conexao() as banco:
        dados = _ler_dataframe(
            banco,
            f"""
            SELECT cnpj, nome, data_constituicao, situacao, tipo, classificacao,
                   classificacao_anbima, indicador_desempenho, publico_alvo,
                   patrimonio_cadastral, data_patrimonio_cadastral,
                   administrador, gestor, em_funcionamento
            FROM cadastro_fundos
            WHERE cnpj IN ({marcadores})
            """,
            cnpjs,
            COLUNAS_CADASTRO_FUNDOS,
        )
    return _normalizar_dataframe_cadastro(dados)


def _normalizar_dataframe_cadastro(dados: pd.DataFrame) -> pd.DataFrame:
    if dados.empty:
        return pd.DataFrame(columns=COLUNAS_CADASTRO_FUNDOS)
    dados["data_constituicao"] = pd.to_datetime(
        dados["data_constituicao"], errors="coerce"
    )
    dados["data_patrimonio_cadastral"] = pd.to_datetime(
        dados["data_patrimonio_cadastral"], errors="coerce"
    )
    dados["patrimonio_cadastral"] = pd.to_numeric(
        dados["patrimonio_cadastral"], errors="coerce"
    )
    dados["em_funcionamento"] = dados["em_funcionamento"].astype(bool)
    return dados


def cadastro_fundos_atualizado_recentemente(
    validade_segundos: int = 86_400,
) -> bool:
    with conexao() as banco:
        cursor = _executar(banco, "SELECT MAX(atualizado_em) FROM cadastro_fundos")
        resultado = cursor.fetchone()
        cursor.close()
    if not resultado or not resultado[0]:
        return False
    atualizado_em = datetime.fromisoformat(resultado[0])
    idade = datetime.now(timezone.utc) - atualizado_em
    return idade.total_seconds() < validade_segundos


def salvar_cadastro_fundos(dados: pd.DataFrame) -> None:
    if dados.empty:
        return
    normalizados = dados.copy()
    for coluna in COLUNAS_CADASTRO_FUNDOS:
        if coluna not in normalizados:
            normalizados[coluna] = pd.NA
    agora = datetime.now(timezone.utc).isoformat()

    def texto_ou_nulo(valor):
        if pd.isna(valor):
            return None
        texto = str(valor).strip()
        return texto or None

    def data_ou_nulo(valor):
        if pd.isna(valor):
            return None
        return pd.Timestamp(valor).strftime("%Y-%m-%d")

    def numero_ou_nulo(valor):
        return None if pd.isna(valor) else float(valor)

    def texto_busca(*valores) -> str:
        texto = " ".join("" if pd.isna(valor) else str(valor) for valor in valores)
        texto = unicodedata.normalize("NFKD", texto)
        texto = "".join(caractere for caractere in texto if not unicodedata.combining(caractere))
        return " ".join(texto.lower().split())

    linhas = []
    for linha in normalizados[COLUNAS_CADASTRO_FUNDOS].itertuples(
        index=False, name=None
    ):
        (
            cnpj,
            nome,
            data_constituicao,
            situacao,
            tipo,
            classificacao,
            classificacao_anbima,
            indicador_desempenho,
            publico_alvo,
            patrimonio,
            data_patrimonio,
            administrador,
            gestor,
            em_funcionamento,
        ) = linha
        if pd.isna(cnpj) or pd.isna(nome):
            continue
        linhas.append(
            (
                str(cnpj),
                str(nome),
                data_ou_nulo(data_constituicao),
                texto_ou_nulo(situacao),
                texto_ou_nulo(tipo),
                texto_ou_nulo(classificacao),
                texto_ou_nulo(classificacao_anbima),
                texto_ou_nulo(indicador_desempenho),
                texto_ou_nulo(publico_alvo),
                numero_ou_nulo(patrimonio),
                data_ou_nulo(data_patrimonio),
                texto_ou_nulo(administrador),
                texto_ou_nulo(gestor),
                int(bool(em_funcionamento)),
                texto_busca(nome, cnpj, administrador, gestor),
                agora,
            )
        )

    with conexao() as banco:
        if backend_banco() == "postgresql":
            cursor = banco.cursor()
            cursor.execute(
                """
                CREATE TEMP TABLE cadastro_fundos_carga
                (LIKE cadastro_fundos INCLUDING DEFAULTS) ON COMMIT DROP
                """
            )
            with cursor.copy(
                """
                COPY cadastro_fundos_carga (
                    cnpj, nome, data_constituicao, situacao, tipo, classificacao,
                    classificacao_anbima, indicador_desempenho, publico_alvo,
                    patrimonio_cadastral, data_patrimonio_cadastral,
                    administrador, gestor, em_funcionamento, busca, atualizado_em
                ) FROM STDIN
                """
            ) as copia:
                for linha in linhas:
                    copia.write_row(linha)
            cursor.execute(
                """
                INSERT INTO cadastro_fundos (
                    cnpj, nome, data_constituicao, situacao, tipo, classificacao,
                    classificacao_anbima, indicador_desempenho, publico_alvo,
                    patrimonio_cadastral, data_patrimonio_cadastral,
                    administrador, gestor, em_funcionamento, busca, atualizado_em
                )
                SELECT cnpj, nome, data_constituicao, situacao, tipo, classificacao,
                       classificacao_anbima, indicador_desempenho, publico_alvo,
                       patrimonio_cadastral, data_patrimonio_cadastral,
                       administrador, gestor, em_funcionamento, busca, atualizado_em
                FROM cadastro_fundos_carga
                ON CONFLICT(cnpj) DO UPDATE SET
                    nome = excluded.nome,
                    data_constituicao = excluded.data_constituicao,
                    situacao = excluded.situacao,
                    tipo = excluded.tipo,
                    classificacao = excluded.classificacao,
                    classificacao_anbima = excluded.classificacao_anbima,
                    indicador_desempenho = excluded.indicador_desempenho,
                    publico_alvo = excluded.publico_alvo,
                    patrimonio_cadastral = excluded.patrimonio_cadastral,
                    data_patrimonio_cadastral = excluded.data_patrimonio_cadastral,
                    administrador = excluded.administrador,
                    gestor = excluded.gestor,
                    em_funcionamento = excluded.em_funcionamento,
                    busca = excluded.busca,
                    atualizado_em = excluded.atualizado_em
                """
            )
            cursor.close()
        else:
            _executar_muitos(
                banco,
                """
                INSERT INTO cadastro_fundos (
                    cnpj, nome, data_constituicao, situacao, tipo, classificacao,
                    classificacao_anbima, indicador_desempenho, publico_alvo,
                    patrimonio_cadastral, data_patrimonio_cadastral,
                    administrador, gestor, em_funcionamento, busca, atualizado_em
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cnpj) DO UPDATE SET
                    nome = excluded.nome,
                    data_constituicao = excluded.data_constituicao,
                    situacao = excluded.situacao,
                    tipo = excluded.tipo,
                    classificacao = excluded.classificacao,
                    classificacao_anbima = excluded.classificacao_anbima,
                    indicador_desempenho = excluded.indicador_desempenho,
                    publico_alvo = excluded.publico_alvo,
                    patrimonio_cadastral = excluded.patrimonio_cadastral,
                    data_patrimonio_cadastral = excluded.data_patrimonio_cadastral,
                    administrador = excluded.administrador,
                    gestor = excluded.gestor,
                    em_funcionamento = excluded.em_funcionamento,
                    busca = excluded.busca,
                    atualizado_em = excluded.atualizado_em
                """,
                linhas,
            )


def salvar_serie_mercado(codigo: str, dados: pd.DataFrame) -> None:
    if dados.empty:
        return
    agora = datetime.now(timezone.utc).isoformat()
    linhas = [
        (codigo, pd.Timestamp(data).strftime("%Y-%m-%d"), float(valor), agora)
        for data, valor in dados[["data", "valor"]].itertuples(index=False, name=None)
        if pd.notna(data) and pd.notna(valor)
    ]
    with conexao() as banco:
        _executar_muitos(
            banco,
            """
            INSERT INTO series_mercado (codigo, data, valor, atualizado_em)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(codigo, data) DO UPDATE SET
                valor = excluded.valor,
                atualizado_em = excluded.atualizado_em
            """,
            linhas,
        )


def serie_mercado_atualizada_recentemente(
    codigo: str, validade_segundos: int = 86_400
) -> bool:
    with conexao() as banco:
        cursor = _executar(
            banco,
            "SELECT MAX(atualizado_em) FROM series_mercado WHERE codigo = ?",
            (codigo,),
        )
        resultado = cursor.fetchone()
        cursor.close()
    if not resultado or not resultado[0]:
        return False
    atualizado_em = datetime.fromisoformat(resultado[0])
    idade = datetime.now(timezone.utc) - atualizado_em
    return idade.total_seconds() < validade_segundos


def carregar_cotas(
    cnpjs: tuple[str, ...], data_inicial: str, data_final: str
) -> pd.DataFrame:
    if not cnpjs:
        return pd.DataFrame(columns=COLUNAS_COTAS)
    marcadores = ",".join("?" for _ in cnpjs)
    parametros = (*cnpjs, data_inicial, data_final)
    with conexao() as banco:
        dados = _ler_dataframe(
            banco,
            f"""
            SELECT cnpj, data, cota, patrimonio, captacao_dia, resgate_dia, cotistas
            FROM cotas_fundos
            WHERE cnpj IN ({marcadores}) AND data BETWEEN ? AND ?
            ORDER BY cnpj, data
            """,
            parametros,
            COLUNAS_COTAS,
        )
    if dados.empty:
        return pd.DataFrame(columns=COLUNAS_COTAS)
    dados["data"] = pd.to_datetime(dados["data"], errors="coerce")
    return dados.dropna(subset=["data", "cota"])


def salvar_cotas(dados: pd.DataFrame) -> None:
    if dados.empty:
        return
    normalizados = dados.copy()
    for coluna in COLUNAS_COTAS:
        if coluna not in normalizados:
            normalizados[coluna] = pd.NA
    agora = datetime.now(timezone.utc).isoformat()

    def numero_ou_nulo(valor):
        return None if pd.isna(valor) else float(valor)

    linhas = []
    for linha in normalizados[COLUNAS_COTAS].itertuples(index=False, name=None):
        cnpj, data, cota, patrimonio, captacao, resgate, cotistas = linha
        if pd.isna(data) or pd.isna(cota):
            continue
        linhas.append(
            (
                str(cnpj),
                pd.Timestamp(data).strftime("%Y-%m-%d"),
                float(cota),
                numero_ou_nulo(patrimonio),
                numero_ou_nulo(captacao),
                numero_ou_nulo(resgate),
                numero_ou_nulo(cotistas),
                agora,
            )
        )
    with conexao() as banco:
        _executar_muitos(
            banco,
            """
            INSERT INTO cotas_fundos (
                cnpj, data, cota, patrimonio, captacao_dia, resgate_dia,
                cotistas, atualizado_em
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cnpj, data) DO UPDATE SET
                cota = excluded.cota,
                patrimonio = excluded.patrimonio,
                captacao_dia = excluded.captacao_dia,
                resgate_dia = excluded.resgate_dia,
                cotistas = excluded.cotistas,
                atualizado_em = excluded.atualizado_em
            """,
            linhas,
        )


def periodo_foi_consultado(
    tipo: str,
    identificador: str,
    periodo: str,
    validade_segundos: int | None = None,
) -> bool:
    with conexao() as banco:
        cursor = _executar(
            banco,
            """
            SELECT consultado_em FROM periodos_consultados
            WHERE tipo = ? AND identificador = ? AND periodo = ?
            """,
            (tipo, identificador, periodo),
        )
        resultado = cursor.fetchone()
        cursor.close()
    if resultado is None:
        return False
    if validade_segundos is None:
        return True
    consultado_em = datetime.fromisoformat(resultado[0])
    idade = datetime.now(timezone.utc) - consultado_em
    return idade.total_seconds() < validade_segundos


def registrar_periodo(
    tipo: str, identificador: str, periodo: str, possui_dados: bool
) -> None:
    with conexao() as banco:
        _executar(
            banco,
            """
            INSERT INTO periodos_consultados (
                tipo, identificador, periodo, possui_dados, consultado_em
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(tipo, identificador, periodo) DO UPDATE SET
                possui_dados = excluded.possui_dados,
                consultado_em = excluded.consultado_em
            """,
            (
                tipo,
                identificador,
                periodo,
                int(possui_dados),
                datetime.now(timezone.utc).isoformat(),
            ),
        ).close()


def otimizar() -> None:
    if backend_banco() == "sqlite":
        with conexao() as banco:
            _executar(banco, "PRAGMA optimize").close()
