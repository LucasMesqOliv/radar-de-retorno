"""Migra a base SQLite atual para o PostgreSQL configurado no projeto."""

from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import sys
import tomllib

import pandas as pd


RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))


def carregar_url_local() -> None:
    if os.environ.get("DATABASE_URL", "").strip():
        return
    arquivo = RAIZ / ".streamlit" / "secrets.toml"
    if arquivo.exists():
        with arquivo.open("rb") as segredo:
            configuracao = tomllib.load(segredo)
        url = str(configuracao.get("DATABASE_URL", "")).strip()
        if url:
            os.environ["DATABASE_URL"] = url


carregar_url_local()

from radar_database import (  # noqa: E402
    backend_banco,
    registrar_periodo,
    salvar_cotas,
    salvar_serie_mercado,
)


def main() -> None:
    if backend_banco() != "postgresql":
        raise SystemExit(
            "Configure DATABASE_URL em .streamlit/secrets.toml antes da migração."
        )

    origem = RAIZ / "data" / "radar_retorno.db"
    if not origem.exists():
        raise SystemExit(f"Base SQLite não encontrada: {origem}")

    with sqlite3.connect(origem) as sqlite:
        series = pd.read_sql_query(
            "SELECT codigo, data, valor FROM series_mercado ORDER BY codigo, data",
            sqlite,
        )
        cotas = pd.read_sql_query(
            """
            SELECT cnpj, data, cota, patrimonio, captacao_dia, resgate_dia, cotistas
            FROM cotas_fundos ORDER BY cnpj, data
            """,
            sqlite,
        )
        periodos = pd.read_sql_query(
            """
            SELECT tipo, identificador, periodo, possui_dados
            FROM periodos_consultados
            """,
            sqlite,
        )

    for codigo, parte in series.groupby("codigo", sort=False):
        salvar_serie_mercado(str(codigo), parte[["data", "valor"]])

    for inicio in range(0, len(cotas), 5_000):
        salvar_cotas(cotas.iloc[inicio : inicio + 5_000])

    for linha in periodos.itertuples(index=False):
        registrar_periodo(
            str(linha.tipo),
            str(linha.identificador),
            str(linha.periodo),
            bool(linha.possui_dados),
        )

    print("Migração concluída.")
    print(f"Séries de mercado: {len(series)} registros")
    print(f"Cotas de fundos: {len(cotas)} registros")
    print(f"Períodos consultados: {len(periodos)} registros")


if __name__ == "__main__":
    main()
