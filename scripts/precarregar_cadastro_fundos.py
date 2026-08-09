"""Atualiza no banco permanente o cadastro de fundos e classes da CVM."""

from __future__ import annotations

import io
import os
from pathlib import Path
import re
import sys
import zipfile

import pandas as pd
import requests


RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from radar_database import fechar_conexoes, salvar_cadastro_fundos  # noqa: E402


URL = "https://dados.cvm.gov.br/dados/FI/CAD/DADOS/registro_fundo_classe.zip"


def normalizar_cnpj(valor) -> str:
    return re.sub(r"\D", "", "" if pd.isna(valor) else str(valor)).zfill(14)


def baixar_cadastro() -> bytes:
    resposta = requests.get(
        URL,
        headers={"User-Agent": "Radar-de-Retorno/1.0"},
        timeout=(15, 180),
    )
    resposta.raise_for_status()
    return resposta.content


def montar_cadastro(conteudo: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(conteudo)) as pacote:
        with pacote.open("registro_classe.csv") as arquivo:
            classes = pd.read_csv(
                arquivo,
                sep=";",
                encoding="latin1",
                dtype=str,
                usecols=[
                    "ID_Registro_Fundo",
                    "CNPJ_Classe",
                    "Data_Constituicao",
                    "Denominacao_Social",
                    "Situacao",
                    "Tipo_Classe",
                    "Classificacao",
                    "Classificacao_Anbima",
                    "Indicador_Desempenho",
                    "Publico_Alvo",
                    "Patrimonio_Liquido",
                    "Data_Patrimonio_Liquido",
                ],
            )
        with pacote.open("registro_fundo.csv") as arquivo:
            fundos = pd.read_csv(
                arquivo,
                sep=";",
                encoding="latin1",
                dtype=str,
                usecols=[
                    "ID_Registro_Fundo",
                    "CNPJ_Fundo",
                    "Data_Constituicao",
                    "Denominacao_Social",
                    "Situacao",
                    "Tipo_Fundo",
                    "Patrimonio_Liquido",
                    "Data_Patrimonio_Liquido",
                    "Administrador",
                    "Gestor",
                ],
            )

    metadados = fundos[
        ["ID_Registro_Fundo", "Administrador", "Gestor", "CNPJ_Fundo"]
    ].drop_duplicates("ID_Registro_Fundo")
    classes = classes.merge(metadados, on="ID_Registro_Fundo", how="left")
    classes = classes.rename(
        columns={
            "CNPJ_Classe": "cnpj",
            "Data_Constituicao": "data_constituicao",
            "Denominacao_Social": "nome",
            "Situacao": "situacao",
            "Tipo_Classe": "tipo",
            "Classificacao": "classificacao",
            "Classificacao_Anbima": "classificacao_anbima",
            "Indicador_Desempenho": "indicador_desempenho",
            "Publico_Alvo": "publico_alvo",
            "Patrimonio_Liquido": "patrimonio_cadastral",
            "Data_Patrimonio_Liquido": "data_patrimonio_cadastral",
            "Administrador": "administrador",
            "Gestor": "gestor",
        }
    )

    cnpjs_classes = set(classes["cnpj"].dropna().map(normalizar_cnpj))
    adicionais = fundos[
        ~fundos["CNPJ_Fundo"].map(normalizar_cnpj).isin(cnpjs_classes)
    ].copy()
    adicionais = adicionais.rename(
        columns={
            "CNPJ_Fundo": "cnpj",
            "Data_Constituicao": "data_constituicao",
            "Denominacao_Social": "nome",
            "Situacao": "situacao",
            "Tipo_Fundo": "tipo",
            "Patrimonio_Liquido": "patrimonio_cadastral",
            "Data_Patrimonio_Liquido": "data_patrimonio_cadastral",
            "Administrador": "administrador",
            "Gestor": "gestor",
        }
    )
    for coluna in (
        "classificacao",
        "classificacao_anbima",
        "indicador_desempenho",
        "publico_alvo",
    ):
        adicionais[coluna] = ""

    colunas = [
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
    ]
    cadastro = pd.concat([classes[colunas], adicionais[colunas]], ignore_index=True)
    cadastro["cnpj"] = cadastro["cnpj"].map(normalizar_cnpj)
    cadastro = cadastro[
        cadastro["cnpj"].str.fullmatch(r"\d{14}")
        & cadastro["cnpj"].ne("00000000000000")
    ]
    cadastro["nome"] = cadastro["nome"].fillna("Fundo sem denominação")
    cadastro["patrimonio_cadastral"] = pd.to_numeric(
        cadastro["patrimonio_cadastral"], errors="coerce"
    )
    cadastro["data_constituicao"] = pd.to_datetime(
        cadastro["data_constituicao"], errors="coerce"
    )
    cadastro["data_patrimonio_cadastral"] = pd.to_datetime(
        cadastro["data_patrimonio_cadastral"], errors="coerce"
    )
    cadastro["em_funcionamento"] = cadastro["situacao"].fillna("").str.contains(
        "Funcionamento Normal", case=False
    )
    return cadastro.sort_values(
        ["em_funcionamento", "patrimonio_cadastral"],
        ascending=[False, False],
        na_position="last",
    ).drop_duplicates("cnpj")


def main() -> None:
    if not os.environ.get("DATABASE_URL", "").strip():
        raise SystemExit("DATABASE_URL não configurada.")
    cadastro = montar_cadastro(baixar_cadastro())
    salvar_cadastro_fundos(cadastro)
    ativos = int(cadastro["em_funcionamento"].sum())
    print(f"Cadastro atualizado: {len(cadastro)} registros, {ativos} em funcionamento.")
    fechar_conexoes()


if __name__ == "__main__":
    main()
