"""Camada SQLite do Radar de Retorno.

O banco funciona como cache persistente e pode ser substituído no futuro por
PostgreSQL sem alterar as regras de cálculo da aplicação.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3

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


def caminho_banco() -> Path:
    configurado = os.environ.get("RADAR_DB_PATH", "").strip()
    if configurado:
        caminho = Path(configurado).expanduser()
    else:
        caminho = Path(__file__).resolve().parent / "data" / "radar_retorno.db"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    return caminho


@contextmanager
def conexao():
    banco = sqlite3.connect(caminho_banco(), timeout=30)
    try:
        banco.execute("PRAGMA journal_mode=WAL")
        banco.execute("PRAGMA synchronous=NORMAL")
        banco.execute("PRAGMA busy_timeout=30000")
        inicializar(banco)
        yield banco
        banco.commit()
    finally:
        banco.close()


def inicializar(banco: sqlite3.Connection) -> None:
    banco.execute(
        """
        CREATE TABLE IF NOT EXISTS series_mercado (
            codigo TEXT NOT NULL,
            data TEXT NOT NULL,
            valor REAL NOT NULL,
            atualizado_em TEXT NOT NULL,
            PRIMARY KEY (codigo, data)
        )
        """
    )
    banco.execute(
        """
        CREATE TABLE IF NOT EXISTS cotas_fundos (
            cnpj TEXT NOT NULL,
            data TEXT NOT NULL,
            cota REAL NOT NULL,
            patrimonio REAL,
            captacao_dia REAL,
            resgate_dia REAL,
            cotistas REAL,
            atualizado_em TEXT NOT NULL,
            PRIMARY KEY (cnpj, data)
        )
        """
    )
    # A chave primária composta já cria o índice usado nas consultas por fundo
    # e intervalo; um segundo índice idêntico só aumentaria o arquivo.
    banco.execute("DROP INDEX IF EXISTS idx_cotas_fundos_cnpj_data")
    banco.execute(
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
    )


def carregar_serie_mercado(codigo: str) -> pd.DataFrame:
    with conexao() as banco:
        dados = pd.read_sql_query(
            "SELECT data, valor FROM series_mercado WHERE codigo = ? ORDER BY data",
            banco,
            params=(codigo,),
        )
    if dados.empty:
        return pd.DataFrame(columns=["data", "valor"])
    dados["data"] = pd.to_datetime(dados["data"], errors="coerce")
    dados["valor"] = pd.to_numeric(dados["valor"], errors="coerce")
    return dados.dropna(subset=["data", "valor"])


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
        banco.executemany(
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
        resultado = banco.execute(
            "SELECT MAX(atualizado_em) FROM series_mercado WHERE codigo = ?",
            (codigo,),
        ).fetchone()
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
        dados = pd.read_sql_query(
            f"""
            SELECT cnpj, data, cota, patrimonio, captacao_dia, resgate_dia, cotistas
            FROM cotas_fundos
            WHERE cnpj IN ({marcadores}) AND data BETWEEN ? AND ?
            ORDER BY cnpj, data
            """,
            banco,
            params=parametros,
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
        banco.executemany(
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
        resultado = banco.execute(
            """
            SELECT consultado_em FROM periodos_consultados
            WHERE tipo = ? AND identificador = ? AND periodo = ?
            """,
            (tipo, identificador, periodo),
        ).fetchone()
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
        banco.execute(
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
        )


def otimizar() -> None:
    with conexao() as banco:
        banco.execute("PRAGMA optimize")
