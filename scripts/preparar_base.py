"""Prepara a base inicial do Radar com índices e caches locais de fundos."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys
import tempfile

import pandas as pd
import requests


RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from radar_database import (  # noqa: E402
    caminho_banco,
    registrar_periodo,
    salvar_cotas,
    salvar_serie_mercado,
)


def atualizar_bcb(codigo: int, ano_inicial: int = 2000) -> int:
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
    partes = []
    for ano in range(ano_inicial, date.today().year + 1):
        resposta = requests.get(
            url,
            params={
                "formato": "json",
                "dataInicial": f"01/01/{ano}",
                "dataFinal": f"31/12/{ano}",
            },
            headers={"User-Agent": "Radar-de-Retorno/1.0"},
            timeout=60,
        )
        resposta.raise_for_status()
        parte = pd.DataFrame(resposta.json())
        if not parte.empty:
            partes.append(parte)
    dados = pd.concat(partes, ignore_index=True)
    dados["data"] = pd.to_datetime(dados["data"], dayfirst=True)
    dados["valor"] = pd.to_numeric(
        dados["valor"].astype(str).str.replace(",", "."), errors="coerce"
    )
    dados = dados.dropna(subset=["data", "valor"])
    salvar_serie_mercado(f"BCB_{codigo}", dados)
    return len(dados)


def atualizar_sp500(ano_inicial: int = 2000) -> int:
    inicio = datetime(ano_inicial, 1, 1, tzinfo=timezone.utc)
    fim = datetime.now(timezone.utc) + timedelta(days=1)
    resposta = requests.get(
        "https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC",
        params={
            "period1": int(inicio.timestamp()),
            "period2": int(fim.timestamp()),
            "interval": "1mo",
            "events": "history",
            "includeAdjustedClose": "false",
        },
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=60,
    )
    resposta.raise_for_status()
    resultado = resposta.json()["chart"]["result"][0]
    dados = pd.DataFrame(
        {
            "data": pd.to_datetime(resultado["timestamp"], unit="s", utc=True)
            .tz_convert(None),
            "valor": resultado["indicators"]["quote"][0]["close"],
        }
    ).dropna()
    salvar_serie_mercado("YAHOO_GSPC_MENSAL", dados)
    return len(dados)


def importar_cache_fundos() -> tuple[int, int]:
    pasta = Path(tempfile.gettempdir()) / "radar_retorno_cvm" / "series_fundos"
    arquivos = sorted(pasta.glob("*.pkl"))
    linhas = 0
    for arquivo in arquivos:
        identificador, periodo = arquivo.stem.rsplit("_", 1)
        dados = pd.read_pickle(arquivo)
        salvar_cotas(dados)
        tipo = "ano" if len(periodo) == 4 else "mes"
        registrar_periodo(tipo, identificador, periodo, not dados.empty)
        linhas += len(dados)
    return len(arquivos), linhas


def main() -> None:
    arquivos, linhas = importar_cache_fundos()
    cdi = atualizar_bcb(12)
    ipca = atualizar_bcb(433)
    sp500 = atualizar_sp500()
    print(f"Banco: {caminho_banco()}")
    print(f"Fundos: {arquivos} arquivos e {linhas} observações")
    print(f"Índices: CDI {cdi}, IPCA {ipca}, S&P 500 {sp500} observações")


if __name__ == "__main__":
    main()
