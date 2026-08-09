from datetime import date, datetime, timedelta, timezone
import base64
import hmac
from html import escape
import importlib.util
import io
import json
from pathlib import Path
import re
import runpy
import subprocess
import sys
import tempfile
import time
import unicodedata
import zipfile

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

from radar_database import (
    cadastro_fundos_atualizado_recentemente,
    buscar_cadastro_fundos,
    carregar_cadastro_fundos,
    carregar_cadastro_fundos_por_cnpj,
    carregar_cotas,
    carregar_serie_mercado,
    contar_cadastro_fundos,
    periodo_foi_consultado,
    registrar_periodo,
    salvar_cadastro_fundos,
    salvar_cotas,
    salvar_serie_mercado,
    serie_mercado_atualizada_recentemente,
)


st.set_page_config(
    page_title="Radar de Retorno",
    page_icon="📈",
    layout="wide",
)


def exigir_senha():
    if st.session_state.get("acesso_autorizado"):
        return

    st.title("Radar de Retorno")
    st.caption("Acesso restrito")
    with st.form("formulario_acesso"):
        senha_digitada = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("Entrar", type="primary")

    if entrar:
        senha_correta = str(st.secrets.get("APP_PASSWORD", ""))
        if senha_correta and hmac.compare_digest(senha_digitada, senha_correta):
            st.session_state["acesso_autorizado"] = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
    st.stop()


exigir_senha()


def aplicar_identidade_visual():
    """Aplica a identidade visual do Radar sem depender de imagens externas."""
    st.markdown(
        """
        <style>
        :root {
            --radar-navy: #06162f;
            --radar-blue: #1769e0;
            --radar-cyan: #19c2d8;
            --radar-coral: #ff6b4a;
            --radar-ink: #14213d;
            --radar-muted: #667085;
            --radar-surface: #ffffff;
            --radar-bg: #f4f7fb;
        }

        .stApp {
            background:
                radial-gradient(circle at 92% 2%, rgba(25, 194, 216, .10), transparent 24rem),
                var(--radar-bg);
            color: var(--radar-ink);
        }

        html, body, [class*="css"] {
            font-family: Inter, "Segoe UI", Arial, sans-serif;
        }

        [data-testid="stHeader"] {
            background: rgba(244, 247, 251, .88);
            backdrop-filter: blur(10px);
        }

        [data-testid="stSidebar"] {
            background: var(--radar-navy);
            border-right: 1px solid rgba(255,255,255,.08);
        }

        [data-testid="stSidebar"] * {
            color: #eef5ff;
        }

        [data-testid="stSidebar"] [data-baseweb="select"] > div,
        [data-testid="stSidebar"] input,
        [data-testid="stSidebar"] [data-baseweb="input"] > div {
            background: rgba(255,255,255,.09) !important;
            border-color: rgba(255,255,255,.20) !important;
        }

        [data-testid="stSidebar"] input,
        [data-testid="stSidebar"] input[type="number"] {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            caret-color: #72e6f3 !important;
            font-weight: 700 !important;
            opacity: 1 !important;
        }

        [data-testid="stSidebar"] input::placeholder {
            color: #b9c8dc !important;
            -webkit-text-fill-color: #b9c8dc !important;
            opacity: 1 !important;
        }

        [data-testid="stSidebar"] [data-testid="stNumberInput"]
        [data-baseweb="input"] > div {
            background: #ffffff !important;
            border-color: #c8d5e6 !important;
        }

        [data-testid="stSidebar"] [data-testid="stNumberInput"] input {
            color: #071d39 !important;
            -webkit-text-fill-color: #071d39 !important;
            caret-color: var(--radar-blue) !important;
            font-weight: 750 !important;
            opacity: 1 !important;
        }

        [data-testid="stSidebar"] [data-testid="stNumberInput"] button,
        [data-testid="stSidebar"] [data-testid="stNumberInput"] button * {
            color: #36506d !important;
            fill: #36506d !important;
        }

        [data-testid="stSidebar"] [role="radiogroup"] label {
            padding: .55rem .65rem;
            margin: .12rem 0;
            border-radius: .55rem;
            transition: background .15s ease;
        }

        [data-testid="stSidebar"] [role="radiogroup"] label:hover {
            background: rgba(255,255,255,.08);
        }

        .radar-sidebar-brand {
            display: flex;
            align-items: center;
            gap: .75rem;
            padding: .45rem 0 1rem;
            border-bottom: 1px solid rgba(255,255,255,.12);
            margin-bottom: .9rem;
        }

        .radar-mark {
            display: grid;
            place-items: center;
            width: 2.35rem;
            height: 2.35rem;
            border-radius: .72rem;
            background: linear-gradient(135deg, var(--radar-cyan), var(--radar-blue));
            color: white;
            font-weight: 800;
            box-shadow: 0 8px 24px rgba(25,194,216,.24);
        }

        .radar-brand-name { font-weight: 760; letter-spacing: -.02em; }
        .radar-brand-sub { color: #9eb1cc !important; font-size: .75rem; }

        .radar-topbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            margin: -.2rem 0 1.15rem;
            padding: .2rem .15rem;
        }

        .radar-section-label {
            color: var(--radar-blue);
            font-size: .76rem;
            font-weight: 800;
            letter-spacing: .12em;
            text-transform: uppercase;
        }

        .radar-live {
            display: inline-flex;
            align-items: center;
            gap: .45rem;
            padding: .38rem .7rem;
            border: 1px solid #d7e1ef;
            border-radius: 99px;
            background: white;
            color: var(--radar-muted);
            font-size: .78rem;
            white-space: nowrap;
        }

        .radar-live::before {
            content: "";
            width: .48rem;
            height: .48rem;
            border-radius: 50%;
            background: #20b486;
            box-shadow: 0 0 0 4px rgba(32,180,134,.12);
        }

        .radar-hero {
            position: relative;
            overflow: hidden;
            padding: clamp(2rem, 5vw, 4.4rem);
            margin-bottom: 1.25rem;
            border-radius: 1.15rem;
            background:
                linear-gradient(110deg, rgba(6,22,47,.98), rgba(18,75,155,.94)),
                var(--radar-navy);
            box-shadow: 0 18px 50px rgba(6,22,47,.15);
            color: white;
        }

        .radar-hero::after {
            content: "";
            position: absolute;
            width: 24rem;
            height: 24rem;
            right: -7rem;
            top: -10rem;
            border-radius: 50%;
            border: 4rem solid rgba(25,194,216,.16);
        }

        .radar-hero-kicker {
            color: #72e6f3;
            font-weight: 800;
            font-size: .76rem;
            letter-spacing: .15em;
        }

        .radar-hero h1 {
            position: relative;
            z-index: 1;
            max-width: 760px;
            margin: .75rem 0 .65rem;
            color: white;
            font-size: clamp(2rem, 4vw, 3.45rem);
            line-height: 1.04;
            letter-spacing: -.045em;
        }

        .radar-hero p {
            position: relative;
            z-index: 1;
            max-width: 690px;
            margin: 0;
            color: #c9d8eb;
            font-size: 1rem;
        }

        .radar-search-label {
            margin: 1.4rem 0 .2rem;
            color: var(--radar-ink);
            font-size: 1.15rem;
            font-weight: 760;
        }

        div[data-testid="stTextInput"] input {
            min-height: 3.15rem;
            border-radius: .72rem;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-color: #dce5f0;
            border-radius: .85rem;
            background: rgba(255,255,255,.88);
            box-shadow: 0 5px 18px rgba(24,44,76,.045);
        }

        div[data-testid="stMetric"] {
            padding: 1rem 1.05rem;
            border: 1px solid #dce5f0;
            border-top: 3px solid var(--radar-blue);
            border-radius: .78rem;
            background: white;
            box-shadow: 0 5px 18px rgba(24,44,76,.05);
        }

        .stButton > button, .stDownloadButton > button {
            border-radius: .58rem;
            border-color: var(--radar-blue);
            font-weight: 700;
        }

        .stButton > button[kind="primary"],
        .stDownloadButton > button[kind="primary"] {
            background: linear-gradient(100deg, var(--radar-blue), #0f8ee9);
        }

        .radar-card-kicker {
            color: var(--radar-blue);
            font-size: .73rem;
            font-weight: 800;
            letter-spacing: .09em;
            text-transform: uppercase;
        }

        .radar-card-title {
            margin: .25rem 0 .45rem;
            color: var(--radar-ink);
            font-size: 1.2rem;
            font-weight: 780;
        }

        .radar-card-copy {
            min-height: 3.1rem;
            color: var(--radar-muted);
            font-size: .88rem;
            line-height: 1.5;
        }

        .radar-coming {
            display: inline-block;
            margin-bottom: .75rem;
            padding: .24rem .55rem;
            border-radius: 99px;
            background: #fff0ec;
            color: #ca4f34;
            font-size: .7rem;
            font-weight: 800;
            letter-spacing: .05em;
            text-transform: uppercase;
        }

        .radar-footer {
            margin-top: 2.5rem;
            padding: 1.35rem 0 .35rem;
            border-top: 1px solid #d8e1ec;
            color: var(--radar-muted);
            font-size: .78rem;
        }

        @media (max-width: 700px) {
            .radar-hero { padding: 1.7rem 1.25rem; border-radius: .85rem; }
            .radar-hero::after { opacity: .55; }
            .radar-live { display: none; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def navegar_para(destino: str):
    st.session_state["pagina_radar"] = destino


def cabecalho_contextual(secao: str, status: str = "Dados de mercado"):
    st.markdown(
        f"""
        <div class="radar-topbar">
            <span class="radar-section-label">{secao}</span>
            <span class="radar-live">{status}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def rodape_radar():
    st.markdown(
        """
        <div class="radar-footer">
            Criado por Lucas Mesquita &nbsp;·&nbsp; Economista e assessor de
            investimentos &nbsp;·&nbsp; Aprovado no CFA Level II
        </div>
        """,
        unsafe_allow_html=True,
    )


def pagina_inicial():
    cabecalho_contextual("Visão geral", "Plataforma de análises")
    st.markdown(
        """
        <section class="radar-hero">
            <span class="radar-hero-kicker">RADAR DE RETORNO</span>
            <h1>Encontre contexto antes de comparar retornos.</h1>
            <p>
                Explore índices, consistência histórica e, em breve, fundos de
                investimento em uma experiência única, clara e orientada a decisões.
            </p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="radar-search-label">O que você deseja analisar?</div>',
        unsafe_allow_html=True,
    )
    busca = st.text_input(
        "Pesquisar ferramentas",
        placeholder="Busque por índices, janelas móveis, CDI, IPCA ou fundos...",
        label_visibility="collapsed",
        key="busca_inicio",
    )

    modulos = [
        {
            "pagina": "Análise de índices",
            "kicker": "Disponível agora",
            "titulo": "Análise de índices",
            "texto": (
                "Compare CDI, IPCA+, prefixado e S&P 500 em janelas móveis "
                "e períodos personalizados."
            ),
            "termos": "índices indice janelas móveis cdi ipca prefixado sp 500",
        },
        {
            "pagina": "Fundos",
            "kicker": "Nova área",
            "titulo": "Pesquisa e comparação de fundos",
            "texto": (
                "Área separada para localizar fundos por nome ou CNPJ e preparar "
                "comparações lado a lado."
            ),
            "termos": "fundos fundo cnpj pesquisa comparação previdência prev",
        },
    ]
    termo = busca.strip().casefold()
    exibidos = [
        modulo for modulo in modulos
        if not termo or termo in (modulo["titulo"] + " " + modulo["termos"]).casefold()
    ]

    if not exibidos:
        st.info("Nenhuma ferramenta encontrada. Tente pesquisar por CDI, IPCA ou fundos.")
    else:
        colunas = st.columns(len(exibidos))
        for coluna, modulo in zip(colunas, exibidos):
            with coluna:
                with st.container(border=True):
                    st.markdown(
                        f"""
                        <div class="radar-card-kicker">{modulo['kicker']}</div>
                        <div class="radar-card-title">{modulo['titulo']}</div>
                        <div class="radar-card-copy">{modulo['texto']}</div>
                        """,
                        unsafe_allow_html=True,
                    )
                    st.button(
                        "Acessar análise",
                        key=f"abrir_{modulo['pagina']}",
                        type="primary" if modulo["pagina"] == "Análise de índices" else "secondary",
                        width="stretch",
                        on_click=navegar_para,
                        args=(modulo["pagina"],),
                    )

    st.markdown("### Uma plataforma, diferentes leituras")
    coluna_1, coluna_2, coluna_3 = st.columns(3)
    destaques = [
        (coluna_1, "Consistência", "Veja como cada estratégia se comportou em vários pontos de entrada."),
        (coluna_2, "Comparação", "Coloque referências diferentes sob o mesmo prazo e metodologia."),
        (coluna_3, "Comunicação", "Transforme a análise selecionada em um relatório simples para o cliente."),
    ]
    for coluna, titulo, texto in destaques:
        with coluna:
            with st.container(border=True):
                st.markdown(f"**{titulo}**")
                st.caption(texto)
    rodape_radar()


URL_CADASTRO_FUNDOS_CVM = (
    "https://dados.cvm.gov.br/dados/FI/CAD/DADOS/registro_fundo_classe.zip"
)
URL_INFORME_DIARIO_CVM = (
    "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/"
    "inf_diario_fi_{mes}.zip"
)
URL_INFORME_HISTORICO_CVM = (
    "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/HIST/"
    "inf_diario_fi_{ano}.zip"
)
URL_EXTRATO_FUNDOS_CVM = (
    "https://dados.cvm.gov.br/dados/FI/DOC/EXTRATO/DADOS/extrato_fi.csv"
)
URL_HISTORICO_INDICE_B3 = (
    "https://sistemaswebb3-listados.b3.com.br/"
    "indexStatisticsProxy/IndexCall/GetDownloadPortfolioDay/{parametros}"
)


def normalizar_cnpj(valor) -> str:
    return re.sub(r"\D", "", str(valor or "")).zfill(14)


def formatar_cnpj(valor) -> str:
    cnpj = normalizar_cnpj(valor)
    return (
        f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/"
        f"{cnpj[8:12]}-{cnpj[12:]}"
    )


def normalizar_busca(valor) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    return "".join(letra for letra in texto if not unicodedata.combining(letra)).casefold()


def formatar_reais(valor) -> str:
    if pd.isna(valor):
        return "—"
    numero = float(valor)
    if abs(numero) >= 1_000_000_000:
        return f"R$ {numero / 1_000_000_000:.2f} bi".replace(".", ",")
    if abs(numero) >= 1_000_000:
        return f"R$ {numero / 1_000_000:.1f} mi".replace(".", ",")
    return f"R$ {numero:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


def baixar_arquivo_cvm(
    url: str,
    nome: str,
    validade_segundos: int = 86_400,
    validar_zip: bool = True,
) -> Path:
    pasta_cache = Path(tempfile.gettempdir()) / "radar_retorno_cvm"
    pasta_cache.mkdir(parents=True, exist_ok=True)
    arquivo = pasta_cache / nome
    atualizado = (
        arquivo.exists()
        and arquivo.stat().st_size > 1_000
        and time.time() - arquivo.stat().st_mtime < validade_segundos
    )
    if atualizado:
        return arquivo

    resposta = requests.get(
        url,
        headers={"User-Agent": "Radar-de-Retorno/1.0"},
        timeout=(15, 180),
        stream=True,
    )
    resposta.raise_for_status()
    with tempfile.NamedTemporaryFile(
        mode="wb", dir=pasta_cache, prefix=f"{nome}.", suffix=".part", delete=False
    ) as temporario:
        for bloco in resposta.iter_content(chunk_size=1024 * 1024):
            if bloco:
                temporario.write(bloco)
        caminho_temporario = Path(temporario.name)

    if validar_zip and not zipfile.is_zipfile(caminho_temporario):
        caminho_temporario.unlink(missing_ok=True)
        raise RuntimeError("A CVM retornou um arquivo inválido.")
    caminho_temporario.replace(arquivo)
    return arquivo


def preparar_cadastro_fundos(cadastro: pd.DataFrame) -> pd.DataFrame:
    cadastro = cadastro.copy()
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
    if "em_funcionamento" not in cadastro:
        cadastro["em_funcionamento"] = cadastro["situacao"].fillna("").str.contains(
            "Funcionamento Normal", case=False
        )
    else:
        cadastro["em_funcionamento"] = cadastro["em_funcionamento"].fillna(False).astype(bool)
    cadastro["_busca"] = (
        cadastro["nome"].fillna("")
        + " " + cadastro["cnpj"].fillna("")
        + " " + cadastro["administrador"].fillna("")
        + " " + cadastro["gestor"].fillna("")
    ).map(normalizar_busca)
    cadastro = cadastro.sort_values(
        ["em_funcionamento", "patrimonio_cadastral"],
        ascending=[False, False],
        na_position="last",
    ).drop_duplicates("cnpj")
    return cadastro.reset_index(drop=True)


@st.cache_data(ttl=86_400, show_spinner=False)
def carregar_cadastro_fundos_cvm() -> pd.DataFrame:
    if cadastro_fundos_atualizado_recentemente():
        armazenado = carregar_cadastro_fundos()
        if not armazenado.empty:
            return preparar_cadastro_fundos(armazenado)

    try:
        arquivo = baixar_arquivo_cvm(
            URL_CADASTRO_FUNDOS_CVM,
            "registro_fundo_classe.zip",
        )
    except Exception:
        armazenado = carregar_cadastro_fundos()
        if not armazenado.empty:
            return preparar_cadastro_fundos(armazenado)
        raise
    with zipfile.ZipFile(arquivo) as pacote:
        with pacote.open("registro_classe.csv") as dados_classe:
            classes = pd.read_csv(
                dados_classe,
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
        with pacote.open("registro_fundo.csv") as dados_fundo:
            fundos = pd.read_csv(
                dados_fundo,
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

    metadados_fundo = fundos[
        ["ID_Registro_Fundo", "Administrador", "Gestor", "CNPJ_Fundo"]
    ].drop_duplicates("ID_Registro_Fundo")
    classes = classes.merge(metadados_fundo, on="ID_Registro_Fundo", how="left")
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
    fundos_adicionais = fundos[
        ~fundos["CNPJ_Fundo"].map(normalizar_cnpj).isin(cnpjs_classes)
    ].copy()
    fundos_adicionais = fundos_adicionais.rename(
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
    for coluna in [
        "classificacao",
        "classificacao_anbima",
        "indicador_desempenho",
        "publico_alvo",
    ]:
        fundos_adicionais[coluna] = ""

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
    cadastro = pd.concat(
        [classes[colunas], fundos_adicionais[colunas]],
        ignore_index=True,
    )
    cadastro = preparar_cadastro_fundos(cadastro)
    salvar_cadastro_fundos(cadastro)
    return cadastro


def buscar_fundos_cvm(
    cadastro: pd.DataFrame | None,
    termo: str,
    limite: int = 30,
) -> pd.DataFrame:
    termo_normalizado = normalizar_busca(termo).strip()
    digitos = re.sub(r"\D", "", termo)
    if cadastro is None:
        return buscar_cadastro_fundos(
            termo_normalizado,
            digitos if len(digitos) >= 6 else "",
            limite,
        )
    if len(digitos) >= 6:
        mascara = cadastro["cnpj"].str.contains(digitos, regex=False)
    else:
        palavras = [palavra for palavra in termo_normalizado.split() if palavra]
        mascara = pd.Series(True, index=cadastro.index)
        for palavra in palavras:
            mascara &= cadastro["_busca"].str.contains(palavra, regex=False)
    return cadastro[mascara].head(limite).copy()


@st.cache_data(ttl=86_400, show_spinner=False)
def carregar_informe_mes_cvm(mes: str, cnpjs: tuple[str, ...]) -> pd.DataFrame:
    colunas_saida = [
        "cnpj",
        "data",
        "cota",
        "patrimonio",
        "captacao_dia",
        "resgate_dia",
        "cotistas",
    ]
    nome_zip = f"inf_diario_fi_{mes}.zip"
    periodo_arquivo = pd.Period(mes, freq="M")
    idade_meses = pd.Period(date.today(), freq="M").ordinal - periodo_arquivo.ordinal
    if idade_meses <= 1:
        validade = 86_400
    elif idade_meses <= 12:
        validade = 604_800
    else:
        validade = 31_536_000

    inicio_periodo = periodo_arquivo.start_time.strftime("%Y-%m-%d")
    fim_periodo = periodo_arquivo.end_time.strftime("%Y-%m-%d")
    validade_consulta = validade if idade_meses <= 1 else None
    if all(
        periodo_foi_consultado(
            "mes", cnpj, mes, validade_segundos=validade_consulta
        )
        for cnpj in cnpjs
    ):
        return carregar_cotas(cnpjs, inicio_periodo, fim_periodo)

    pasta_series = Path(tempfile.gettempdir()) / "radar_retorno_cvm" / "series_fundos"
    pasta_series.mkdir(parents=True, exist_ok=True)
    arquivos_series = {
        cnpj: pasta_series / f"{cnpj}_{mes}.pkl"
        for cnpj in cnpjs
    }
    faltantes = []
    for cnpj, arquivo_serie in arquivos_series.items():
        cache_valido = arquivo_serie.exists()
        if cache_valido and idade_meses <= 1:
            cache_valido = time.time() - arquivo_serie.stat().st_mtime < validade
        if not cache_valido:
            faltantes.append(cnpj)

    if not faltantes:
        partes_cache = [pd.read_pickle(arquivos_series[cnpj]) for cnpj in cnpjs]
        resultado = pd.concat(partes_cache, ignore_index=True).sort_values(
            ["cnpj", "data"]
        )
        salvar_cotas(resultado)
        for cnpj in cnpjs:
            registrar_periodo(
                "mes", cnpj, mes, not resultado[resultado["cnpj"].eq(cnpj)].empty
            )
        return resultado

    arquivo = baixar_arquivo_cvm(
        URL_INFORME_DIARIO_CVM.format(mes=mes),
        nome_zip,
        validade_segundos=validade,
    )
    with zipfile.ZipFile(arquivo) as pacote:
        nome_csv = next(
            nome for nome in pacote.namelist() if nome.lower().endswith(".csv")
        )
        with pacote.open(nome_csv) as cabecalho_arquivo:
            cabecalho = pd.read_csv(
                cabecalho_arquivo,
                sep=";",
                encoding="latin1",
                nrows=0,
            ).columns.tolist()

        coluna_cnpj = (
            "CNPJ_FUNDO_CLASSE"
            if "CNPJ_FUNDO_CLASSE" in cabecalho
            else "CNPJ_FUNDO"
        )
        colunas_desejadas = [
            coluna_cnpj,
            "DT_COMPTC",
            "VL_QUOTA",
            "VL_PATRIM_LIQ",
            "CAPTC_DIA",
            "RESG_DIA",
            "NR_COTST",
        ]
        colunas_existentes = [
            coluna for coluna in colunas_desejadas if coluna in cabecalho
        ]
        partes_filtradas = []
        with pacote.open(nome_csv) as dados_arquivo:
            for parte in pd.read_csv(
                dados_arquivo,
                sep=";",
                encoding="latin1",
                dtype={coluna_cnpj: str},
                usecols=colunas_existentes,
                chunksize=100_000,
            ):
                parte["cnpj"] = parte[coluna_cnpj].map(normalizar_cnpj)
                parte = parte[parte["cnpj"].isin(set(faltantes))]
                if not parte.empty:
                    partes_filtradas.append(parte.copy())

    if idade_meses > 1:
        arquivo.unlink(missing_ok=True)
    if partes_filtradas:
        dados = pd.concat(partes_filtradas, ignore_index=True)
    else:
        dados = pd.DataFrame(columns=[*colunas_existentes, "cnpj"])

    dados["data"] = pd.to_datetime(dados["DT_COMPTC"], errors="coerce")
    renomear = {
        "VL_QUOTA": "cota",
        "VL_PATRIM_LIQ": "patrimonio",
        "CAPTC_DIA": "captacao_dia",
        "RESG_DIA": "resgate_dia",
        "NR_COTST": "cotistas",
    }
    dados = dados.rename(columns=renomear)
    for coluna in renomear.values():
        if coluna not in dados:
            dados[coluna] = pd.NA
        dados[coluna] = pd.to_numeric(dados[coluna], errors="coerce")
    dados = dados[colunas_saida].sort_values(["cnpj", "data"])

    for cnpj in faltantes:
        serie_fundo = dados[dados["cnpj"].eq(cnpj)].copy()
        temporario = arquivos_series[cnpj].with_suffix(".tmp")
        serie_fundo.to_pickle(temporario)
        temporario.replace(arquivos_series[cnpj])

    partes_cache = [pd.read_pickle(arquivos_series[cnpj]) for cnpj in cnpjs]
    resultado = pd.concat(partes_cache, ignore_index=True).sort_values(["cnpj", "data"])
    salvar_cotas(resultado)
    for cnpj in cnpjs:
        registrar_periodo(
            "mes", cnpj, mes, not resultado[resultado["cnpj"].eq(cnpj)].empty
        )
    return resultado


@st.cache_data(ttl=86_400, show_spinner=False)
def carregar_extrato_fundos_cvm(cnpjs: tuple[str, ...]) -> pd.DataFrame:
    arquivo = baixar_arquivo_cvm(
        URL_EXTRATO_FUNDOS_CVM,
        "extrato_fi.csv",
        validar_zip=False,
    )
    cabecalho = pd.read_csv(
        arquivo,
        sep=";",
        encoding="latin1",
        nrows=0,
    ).columns.tolist()
    coluna_cnpj = (
        "CNPJ_FUNDO_CLASSE"
        if "CNPJ_FUNDO_CLASSE" in cabecalho
        else "CNPJ_FUNDO"
    )
    desejadas = [
        coluna_cnpj,
        "DT_COMPTC",
        "CONDOM",
        "PUBLICO_ALVO",
        "CLASSE_ANBIMA",
        "DISTRIB",
        "APLIC_MIN",
        "ATUALIZ_DIARIA_COTA",
        "QT_DIA_CONVERSAO_COTA",
        "QT_DIA_RESGATE_COTAS",
        "QT_DIA_PAGTO_RESGATE",
        "TP_DIA_PAGTO_RESGATE",
        "TAXA_ADM",
        "EXISTE_TAXA_PERFM",
        "TAXA_PERFM",
        "PARAM_TAXA_PERFM",
        "PR_INDICE_REFER_TAXA_PERFM",
    ]
    usecols = [coluna for coluna in desejadas if coluna in cabecalho]
    partes = []
    for parte in pd.read_csv(
        arquivo,
        sep=";",
        encoding="latin1",
        dtype=str,
        usecols=usecols,
        chunksize=50_000,
    ):
        parte["cnpj"] = parte[coluna_cnpj].map(normalizar_cnpj)
        filtrada = parte[parte["cnpj"].isin(set(cnpjs))]
        if not filtrada.empty:
            partes.append(filtrada.copy())
    if not partes:
        return pd.DataFrame(columns=["cnpj"] + usecols)
    extrato = pd.concat(partes, ignore_index=True)
    extrato["DT_COMPTC"] = pd.to_datetime(extrato["DT_COMPTC"], errors="coerce")
    extrato = (
        extrato.sort_values("DT_COMPTC")
        .groupby("cnpj", as_index=False)
        .last()
    )
    for coluna in [
        "APLIC_MIN",
        "QT_DIA_CONVERSAO_COTA",
        "QT_DIA_RESGATE_COTAS",
        "QT_DIA_PAGTO_RESGATE",
        "TAXA_ADM",
        "TAXA_PERFM",
        "PR_INDICE_REFER_TAXA_PERFM",
    ]:
        if coluna in extrato:
            extrato[coluna] = pd.to_numeric(extrato[coluna], errors="coerce")
    return extrato


@st.cache_data(show_spinner=False)
def carregar_informe_ano_cvm(ano: int, cnpjs: tuple[str, ...]) -> pd.DataFrame:
    colunas_saida = [
        "cnpj", "data", "cota", "patrimonio",
        "captacao_dia", "resgate_dia", "cotistas",
    ]
    if all(periodo_foi_consultado("ano", cnpj, str(ano)) for cnpj in cnpjs):
        return carregar_cotas(cnpjs, f"{ano}-01-01", f"{ano}-12-31")
    pasta_series = Path(tempfile.gettempdir()) / "radar_retorno_cvm" / "series_fundos"
    pasta_series.mkdir(parents=True, exist_ok=True)
    arquivos_series = {
        cnpj: pasta_series / f"{cnpj}_{ano}.pkl" for cnpj in cnpjs
    }
    faltantes = [cnpj for cnpj, caminho in arquivos_series.items() if not caminho.exists()]
    if faltantes:
        arquivo = baixar_arquivo_cvm(
            URL_INFORME_HISTORICO_CVM.format(ano=ano),
            f"inf_diario_fi_{ano}.zip",
            validade_segundos=31_536_000,
        )
        partes_filtradas = []
        with zipfile.ZipFile(arquivo) as pacote:
            for nome_csv in pacote.namelist():
                if not nome_csv.lower().endswith(".csv"):
                    continue
                with pacote.open(nome_csv) as cabecalho_arquivo:
                    cabecalho = pd.read_csv(
                        cabecalho_arquivo, sep=";", encoding="latin1", nrows=0
                    ).columns.tolist()
                coluna_cnpj = (
                    "CNPJ_FUNDO_CLASSE"
                    if "CNPJ_FUNDO_CLASSE" in cabecalho
                    else "CNPJ_FUNDO"
                )
                desejadas = [
                    coluna_cnpj, "DT_COMPTC", "VL_QUOTA", "VL_PATRIM_LIQ",
                    "CAPTC_DIA", "RESG_DIA", "NR_COTST",
                ]
                existentes = [coluna for coluna in desejadas if coluna in cabecalho]
                with pacote.open(nome_csv) as dados_arquivo:
                    for parte in pd.read_csv(
                        dados_arquivo,
                        sep=";",
                        encoding="latin1",
                        dtype={coluna_cnpj: str},
                        usecols=existentes,
                        chunksize=100_000,
                    ):
                        parte["cnpj"] = parte[coluna_cnpj].map(normalizar_cnpj)
                        parte = parte[parte["cnpj"].isin(set(faltantes))]
                        if not parte.empty:
                            partes_filtradas.append(parte.copy())
        arquivo.unlink(missing_ok=True)
        if partes_filtradas:
            dados = pd.concat(partes_filtradas, ignore_index=True)
        else:
            dados = pd.DataFrame(columns=["cnpj", "DT_COMPTC", "VL_QUOTA"])
        dados["data"] = pd.to_datetime(dados["DT_COMPTC"], errors="coerce")
        dados = dados.rename(
            columns={
                "VL_QUOTA": "cota",
                "VL_PATRIM_LIQ": "patrimonio",
                "CAPTC_DIA": "captacao_dia",
                "RESG_DIA": "resgate_dia",
                "NR_COTST": "cotistas",
            }
        )
        for coluna in colunas_saida[2:]:
            if coluna not in dados:
                dados[coluna] = pd.NA
            dados[coluna] = pd.to_numeric(dados[coluna], errors="coerce")
        dados = dados[colunas_saida].sort_values(["cnpj", "data"])
        for cnpj in faltantes:
            serie_fundo = dados[dados["cnpj"].eq(cnpj)].copy()
            temporario = arquivos_series[cnpj].with_suffix(".tmp")
            serie_fundo.to_pickle(temporario)
            temporario.replace(arquivos_series[cnpj])

    partes_cache = [pd.read_pickle(arquivos_series[cnpj]) for cnpj in cnpjs]
    resultado = pd.concat(partes_cache, ignore_index=True).sort_values(["cnpj", "data"])
    salvar_cotas(resultado)
    for cnpj in cnpjs:
        registrar_periodo(
            "ano", cnpj, str(ano), not resultado[resultado["cnpj"].eq(cnpj)].empty
        )
    return resultado


@st.cache_data(ttl=86_400, show_spinner=False)
def carregar_historico_fundos_cvm(
    cnpjs: tuple[str, ...],
    meses: int | None,
    data_inicio: str | None = None,
) -> pd.DataFrame:
    periodo_final = pd.Period(date.today(), freq="M")
    if meses is None:
        inicio = pd.Timestamp(data_inicio) if data_inicio else pd.Timestamp("2000-01-01")
        periodo_inicial = inicio.to_period("M")
    else:
        periodo_inicial = periodo_final - meses
    partes = []
    primeiro_ano_mensal = 2021
    ultimo_ano_historico = min(periodo_final.year, primeiro_ano_mensal - 1)
    for ano in range(periodo_inicial.year, ultimo_ano_historico + 1):
        try:
            parte = carregar_informe_ano_cvm(ano, cnpjs)
        except requests.HTTPError as erro:
            if erro.response is not None and erro.response.status_code == 404:
                continue
            raise
        if not parte.empty:
            partes.append(parte)

    inicio_mensal = max(
        periodo_inicial,
        pd.Period(f"{primeiro_ano_mensal}-01", freq="M"),
    )
    for periodo in pd.period_range(inicio_mensal, periodo_final, freq="M"):
        try:
            parte = carregar_informe_mes_cvm(periodo.strftime("%Y%m"), cnpjs)
        except requests.HTTPError as erro:
            if erro.response is not None and erro.response.status_code == 404:
                continue
            raise
        if not parte.empty:
            partes.append(parte)
    if not partes:
        raise RuntimeError("A CVM não retornou histórico para os fundos selecionados.")
    historico = pd.concat(partes, ignore_index=True)
    historico = historico[historico["data"] >= periodo_inicial.start_time]
    return (
        historico.dropna(subset=["data", "cota"])
        .drop_duplicates(["cnpj", "data"], keep="last")
        .sort_values(["cnpj", "data"])
    )


@st.cache_data(ttl=86_400, show_spinner=False)
def carregar_cdi_para_fundos(ano_inicial: int) -> pd.Series:
    partes = []
    url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados"
    for ano in range(ano_inicial, date.today().year + 1):
        resposta = requests.get(
            url,
            params={
                "formato": "json",
                "dataInicial": f"01/01/{ano}",
                "dataFinal": f"31/12/{ano}",
            },
            headers={"User-Agent": "Radar-de-Retorno/1.0"},
            timeout=30,
        )
        resposta.raise_for_status()
        parte = pd.DataFrame(resposta.json())
        if not parte.empty:
            partes.append(parte)
    if not partes:
        raise RuntimeError("O Banco Central não retornou a série do CDI.")
    dados = pd.concat(partes, ignore_index=True)
    dados["data"] = pd.to_datetime(dados["data"], dayfirst=True)
    dados["taxa"] = pd.to_numeric(
        dados["valor"].astype(str).str.replace(",", "."),
        errors="coerce",
    ) / 100
    dados = dados.dropna(subset=["data", "taxa"]).sort_values("data")
    indice = (1 + dados["taxa"]).cumprod()
    return pd.Series(indice.values, index=dados["data"], name="CDI")


@st.cache_data(ttl=86_400, show_spinner=False)
def carregar_indice_b3(codigo: str, ano_inicial: int) -> pd.Series:
    meses = {
        "Jan": 1,
        "Fev": 2,
        "Mar": 3,
        "Abr": 4,
        "Mai": 5,
        "Jun": 6,
        "Jul": 7,
        "Ago": 8,
        "Set": 9,
        "Out": 10,
        "Nov": 11,
        "Dez": 12,
    }
    registros = []
    for ano in range(ano_inicial, date.today().year + 1):
        parametros = base64.b64encode(
            json.dumps(
                {"index": codigo, "language": "pt-br", "year": str(ano)},
                separators=(",", ":"),
            ).encode("utf-8")
        ).decode("ascii")
        resposta = requests.get(
            URL_HISTORICO_INDICE_B3.format(parametros=parametros),
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": (
                    "https://sistemaswebb3-listados.b3.com.br/"
                    f"indexStatisticsPage/daily-evolution/{codigo}?language=pt-br"
                ),
            },
            timeout=30,
        )
        resposta.raise_for_status()
        conteudo = base64.b64decode(resposta.text.strip()).decode("latin1")
        tabela = pd.read_csv(io.StringIO(conteudo), sep=";", skiprows=1, dtype=str)
        coluna_dia = tabela.columns[0]
        for _, linha in tabela.iterrows():
            try:
                dia = int(linha[coluna_dia])
            except (TypeError, ValueError):
                continue
            for coluna_mes, numero_mes in meses.items():
                if coluna_mes not in tabela.columns or pd.isna(linha[coluna_mes]):
                    continue
                texto = str(linha[coluna_mes]).strip()
                if not texto:
                    continue
                valor = pd.to_numeric(
                    texto.replace(".", "").replace(",", "."),
                    errors="coerce",
                )
                if pd.isna(valor):
                    continue
                try:
                    data_registro = pd.Timestamp(ano, numero_mes, dia)
                except ValueError:
                    continue
                registros.append((data_registro, float(valor)))
    if not registros:
        raise RuntimeError(f"A B3 não retornou a série {codigo}.")
    serie = pd.Series(
        [valor for _, valor in registros],
        index=[data_registro for data_registro, _ in registros],
        name=codigo,
    )
    return serie[~serie.index.duplicated(keep="last")].sort_index()


def obter_series_analise_fundos(
    historico: pd.DataFrame,
    cadastro: pd.DataFrame,
    cnpjs: tuple[str, ...],
    benchmarks: list[str],
) -> dict[str, pd.Series]:
    series = {}
    for cnpj in cnpjs:
        nome = cadastro.loc[cadastro["cnpj"].eq(cnpj), "nome"].iloc[0]
        rotulo = nome
        if rotulo in series:
            rotulo = f"{nome} · {formatar_cnpj(cnpj)}"
        dados_fundo = historico[historico["cnpj"].eq(cnpj)]
        serie = pd.Series(
            dados_fundo["cota"].values,
            index=pd.DatetimeIndex(dados_fundo["data"]),
            name=rotulo,
        )
        series[rotulo] = serie[~serie.index.duplicated(keep="last")].sort_index()

    primeira_data = min(serie.index.min() for serie in series.values())
    if "CDI" in benchmarks:
        series["CDI"] = carregar_cdi_para_fundos(primeira_data.year)
    if "Ibovespa" in benchmarks:
        series["Ibovespa"] = carregar_indice_b3("IBOV", primeira_data.year)
    if "IDIV" in benchmarks:
        series["IDIV"] = carregar_indice_b3("IDIV", primeira_data.year)
    primeira_data_comum = max(serie.dropna().index.min() for serie in series.values())
    ultima_data_comum = min(serie.dropna().index.max() for serie in series.values())
    return {
        nome: serie[
            (serie.index >= primeira_data_comum) & (serie.index <= ultima_data_comum)
        ]
        for nome, serie in series.items()
    }


def valor_mais_proximo(serie: pd.Series, data_alvo: pd.Timestamp):
    serie = serie.dropna().sort_index()
    if serie.empty:
        return None
    posicao = (serie.index - data_alvo).to_series(index=serie.index).abs().idxmin()
    return float(serie.loc[posicao]), pd.Timestamp(posicao)


def calcular_retorno_serie(
    serie: pd.Series,
    meses: int | None = None,
    inicio_calendario: str | None = None,
):
    serie = serie.dropna().sort_index()
    if len(serie) < 2:
        return None
    data_final = pd.Timestamp(serie.index.max())
    valor_final = float(serie.iloc[-1])
    if inicio_calendario == "mes":
        data_alvo = data_final.to_period("M").start_time - pd.Timedelta(days=1)
    elif inicio_calendario == "ano":
        data_alvo = pd.Timestamp(data_final.year, 1, 1) - pd.Timedelta(days=1)
    else:
        data_alvo = data_final - pd.DateOffset(months=meses or 0)
    if data_alvo < serie.index.min():
        return None
    inicial = valor_mais_proximo(serie, data_alvo)
    if inicial is None:
        return None
    valor_inicial, data_inicial = inicial
    if valor_inicial <= 0 or data_inicial >= data_final:
        return None
    retorno = valor_final / valor_inicial - 1
    dias = (data_final - data_inicial).days
    anualizado = (1 + retorno) ** (365.25 / dias) - 1 if dias > 0 else None
    return {
        "retorno": retorno,
        "anualizado": anualizado,
        "data_inicial": data_inicial,
        "data_final": data_final,
    }


def criar_tabela_periodos_fundos(series: dict[str, pd.Series]) -> pd.DataFrame:
    periodos = [
        ("Mês", None, "mes"),
        ("Ano", None, "ano"),
        ("1 mês", 1, None),
        ("6 meses", 6, None),
        ("12 meses", 12, None),
        ("24 meses", 24, None),
        ("36 meses", 36, None),
        ("60 meses", 60, None),
    ]
    linhas = []
    for nome, serie in series.items():
        linha = {"Ativo": nome}
        for rotulo, meses, calendario in periodos:
            resultado = calcular_retorno_serie(serie, meses, calendario)
            linha[rotulo] = "—" if resultado is None else f"{resultado['retorno']:.2%}"
        linhas.append(linha)
    return pd.DataFrame(linhas)


def calcular_metricas_risco_fundos(
    series: dict[str, pd.Series],
) -> pd.DataFrame:
    retornos_cdi = series.get("CDI", pd.Series(dtype=float)).pct_change().dropna()
    linhas = []
    for nome, serie in series.items():
        retornos = serie.pct_change()
        retornos = retornos[retornos.map(lambda valor: pd.notna(valor) and abs(valor) != float("inf"))]
        if retornos.empty:
            continue
        volatilidade = retornos.std() * (252 ** 0.5)
        acumulado = (1 + retornos).cumprod()
        drawdown = acumulado / acumulado.cummax() - 1
        sharpe = None
        if nome != "CDI" and not retornos_cdi.empty:
            alinhados = pd.concat([retornos, retornos_cdi], axis=1, join="inner").dropna()
            if len(alinhados) > 2:
                excesso = alinhados.iloc[:, 0] - alinhados.iloc[:, 1]
                desvio_excesso = excesso.std()
                if desvio_excesso and not pd.isna(desvio_excesso):
                    sharpe = excesso.mean() / desvio_excesso * (252 ** 0.5)
        linhas.append(
            {
                "Ativo": nome,
                "Volatilidade a.a.": volatilidade,
                "Sharpe vs. CDI": sharpe,
                "Maior queda": drawdown.min(),
                "Dias positivos": (retornos > 0).mean(),
                "Melhor dia": retornos.max(),
                "Pior dia": retornos.min(),
            }
        )
    return pd.DataFrame(linhas)


def criar_grafico_volatilidade_fundos(series: dict[str, pd.Series]):
    cores = ["#1769e0", "#19c2d8", "#ff6b4a", "#7656d6", "#0f9d78", "#e2a126", "#64748b"]
    fig = go.Figure()
    for (nome, serie), cor in zip(series.items(), cores):
        retornos = serie.dropna().sort_index().pct_change()
        volatilidade = retornos.rolling(63, min_periods=32).std() * (252 ** 0.5) * 100
        volatilidade = volatilidade.dropna()
        fig.add_trace(
            go.Scatter(
                x=volatilidade.index,
                y=volatilidade.values,
                mode="lines",
                name=nome,
                line={"width": 2.2, "color": cor},
                hovertemplate=(
                    "%{x|%d/%m/%Y}<br>Volatilidade: %{y:.2f}% a.a."
                    f"<extra>{nome}</extra>"
                ),
            )
        )
    fig.update_layout(
        title="Volatilidade anualizada ao longo do tempo",
        height=430,
        margin={"l": 25, "r": 20, "t": 65, "b": 85},
        hovermode="x unified",
        dragmode=False,
        legend={"orientation": "h", "y": -0.18, "x": 0.5, "xanchor": "center"},
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    fig.update_xaxes(showgrid=False, fixedrange=True)
    fig.update_yaxes(ticksuffix="%", gridcolor="#e2e8f0", fixedrange=True)
    return fig


def criar_grafico_drawdown_fundos(series: dict[str, pd.Series]):
    cores = ["#1769e0", "#19c2d8", "#ff6b4a", "#7656d6", "#0f9d78", "#e2a126", "#64748b"]
    preenchimentos = [
        "rgba(23,105,224,0.10)",
        "rgba(25,194,216,0.10)",
        "rgba(255,107,74,0.10)",
        "rgba(118,86,214,0.10)",
        "rgba(15,157,120,0.10)",
        "rgba(226,161,38,0.10)",
        "rgba(100,116,139,0.10)",
    ]
    fig = go.Figure()
    for (nome, serie), cor, preenchimento in zip(series.items(), cores, preenchimentos):
        serie = serie.dropna().sort_index()
        drawdown = (serie / serie.cummax() - 1) * 100
        fig.add_trace(
            go.Scatter(
                x=drawdown.index,
                y=drawdown.values,
                mode="lines",
                name=nome,
                fill="tozeroy",
                fillcolor=preenchimento,
                line={"width": 1.9, "color": cor},
                hovertemplate="%{x|%d/%m/%Y}<br>Queda: %{y:.2f}%<extra></extra>",
            )
        )
    fig.update_layout(
        title="Quedas em relação ao maior valor anterior · drawdown",
        height=430,
        margin={"l": 25, "r": 20, "t": 65, "b": 85},
        hovermode="x unified",
        dragmode=False,
        legend={"orientation": "h", "y": -0.18, "x": 0.5, "xanchor": "center"},
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    fig.update_xaxes(showgrid=False, fixedrange=True)
    fig.update_yaxes(ticksuffix="%", gridcolor="#e2e8f0", fixedrange=True)
    return fig


def calcular_frequencia_vitorias_janelas(
    dados_janelas: dict[str, pd.Series],
    principal: str,
):
    linhas = []
    serie_principal = dados_janelas.get(principal, pd.Series(dtype=float))
    for comparativo, serie_comparativa in dados_janelas.items():
        if comparativo == principal:
            continue
        alinhadas = pd.concat(
            [serie_principal.rename("principal"), serie_comparativa.rename("comparativo")],
            axis=1,
            join="inner",
        ).dropna()
        if alinhadas.empty:
            continue
        diferenca = alinhadas["principal"] - alinhadas["comparativo"]
        vitorias = int((diferenca > 1e-10).sum())
        empates = int((diferenca.abs() <= 1e-10).sum())
        derrotas = len(alinhadas) - vitorias - empates
        linhas.append(
            {
                "Comparativo": comparativo,
                "Principal venceu": vitorias,
                "Empates": empates,
                "Comparativo venceu": derrotas,
                "Janelas": len(alinhadas),
                "% de vitória do principal": vitorias / len(alinhadas),
            }
        )
    return pd.DataFrame(linhas)


def criar_grafico_frequencia_vitorias(tabela: pd.DataFrame, principal: str):
    fig = go.Figure(
        go.Bar(
            x=tabela["% de vitória do principal"] * 100,
            y=tabela["Comparativo"],
            orientation="h",
            marker_color="#1769e0",
            text=[f"{valor:.1%}" for valor in tabela["% de vitória do principal"]],
            textposition="inside",
            hovertemplate="%{y}<br>Vitórias: %{x:.1f}%<extra></extra>",
        )
    )
    fig.update_layout(
        title="Percentual de janelas em que o fundo principal venceu",
        height=max(240, 90 + 54 * len(tabela)),
        margin={"l": 25, "r": 25, "t": 65, "b": 35},
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
    )
    fig.update_xaxes(range=[0, 100], ticksuffix="%", gridcolor="#e2e8f0", fixedrange=True)
    fig.update_yaxes(fixedrange=True)
    return fig


def criar_grafico_evolucao_fundos(series: dict[str, pd.Series]):
    cores = ["#1769e0", "#19c2d8", "#ff6b4a", "#7656d6", "#0f9d78", "#e2a126", "#64748b"]
    fig = go.Figure()
    for (nome, serie), cor in zip(series.items(), cores):
        serie = serie.dropna().sort_index()
        retorno_acumulado = (serie / serie.iloc[0] - 1) * 100
        fig.add_trace(
            go.Scatter(
                x=retorno_acumulado.index,
                y=retorno_acumulado.values,
                mode="lines",
                name=nome,
                line={"width": 2.4, "color": cor},
                hovertemplate="%{x|%d/%m/%Y}<br>Retorno: %{y:.2f}%<extra></extra>",
            )
        )
    fig.update_layout(
        title="Rentabilidade acumulada · início em 0%",
        height=500,
        margin={"l": 25, "r": 20, "t": 65, "b": 85},
        hovermode="x unified",
        dragmode=False,
        legend={"orientation": "h", "y": -0.18, "x": 0.5, "xanchor": "center"},
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    fig.update_xaxes(showgrid=False, fixedrange=True)
    fig.update_yaxes(ticksuffix="%", gridcolor="#e2e8f0", fixedrange=True)
    return fig


def criar_janelas_moveis_fundos(
    series: dict[str, pd.Series],
    meses_janela: int,
):
    cores = ["#1769e0", "#19c2d8", "#ff6b4a", "#7656d6", "#0f9d78", "#e2a126", "#64748b"]
    fig = go.Figure()
    dados_janelas = {}
    for (nome, serie), cor in zip(series.items(), cores):
        mensal = serie.dropna().sort_index().resample("ME").last()
        hoje = pd.Timestamp(date.today())
        if hoje.day < hoje.days_in_month:
            mensal = mensal[mensal.index.to_period("M") < hoje.to_period("M")]
        retorno = mensal.pct_change(meses_janela)
        if meses_janela >= 12:
            retorno = (1 + retorno) ** (12 / meses_janela) - 1
        retorno = retorno.dropna()
        dados_janelas[nome] = retorno
        fig.add_trace(
            go.Scatter(
                x=retorno.index,
                y=retorno.values * 100,
                mode="lines",
                name=nome,
                line={"width": 2.2, "color": cor},
                hovertemplate="%{x|%m/%Y}<br>Retorno: %{y:.2f}%<extra></extra>",
            )
        )
    tipo = "anualizado" if meses_janela >= 12 else "acumulado"
    fig.update_layout(
        title=f"Janelas móveis de {meses_janela} meses · retorno {tipo}",
        height=470,
        margin={"l": 25, "r": 20, "t": 65, "b": 85},
        hovermode="x unified",
        dragmode=False,
        legend={"orientation": "h", "y": -0.18, "x": 0.5, "xanchor": "center"},
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    fig.update_xaxes(showgrid=False, fixedrange=True)
    fig.update_yaxes(ticksuffix="%", gridcolor="#e2e8f0", fixedrange=True)
    return fig, dados_janelas


def carregar_mes_recente_fundos(cnpjs: tuple[str, ...]):
    periodo_atual = pd.Period(date.today(), freq="M")
    ultimo_erro = None
    for recuo in range(4):
        periodo = periodo_atual - recuo
        try:
            dados = carregar_informe_mes_cvm(periodo.strftime("%Y%m"), cnpjs)
            if not dados.empty:
                return periodo, dados
        except requests.HTTPError as erro:
            ultimo_erro = erro
            if erro.response is None or erro.response.status_code != 404:
                raise
    if ultimo_erro:
        raise RuntimeError("Não foram encontrados informes recentes para o fundo.") from ultimo_erro
    raise RuntimeError("O fundo selecionado não possui informes recentes na CVM.")


def ultimo_registro_por_fundo(dados: pd.DataFrame) -> pd.DataFrame:
    return (
        dados.dropna(subset=["data"])
        .sort_values("data")
        .groupby("cnpj", as_index=False)
        .last()
    )


def montar_resumo_comparacao_fundos(
    cadastro: pd.DataFrame,
    cnpjs: tuple[str, ...],
    meses: int,
):
    mes_final, dados_finais = carregar_mes_recente_fundos(cnpjs)
    mes_inicial = mes_final - meses
    dados_iniciais = carregar_informe_mes_cvm(
        mes_inicial.strftime("%Y%m"),
        cnpjs,
    )
    finais = ultimo_registro_por_fundo(dados_finais).rename(
        columns={
            "data": "data_final",
            "cota": "cota_final",
            "patrimonio": "patrimonio_atual",
            "cotistas": "cotistas_atuais",
        }
    )
    alvos = finais[["cnpj", "data_final"]].copy()
    alvos["data_alvo"] = alvos["data_final"] - pd.DateOffset(months=meses)
    iniciais = dados_iniciais.merge(
        alvos[["cnpj", "data_alvo"]],
        on="cnpj",
        how="inner",
    )
    iniciais["distancia_data"] = (
        iniciais["data"] - iniciais["data_alvo"]
    ).abs()
    iniciais = (
        iniciais.sort_values(["cnpj", "distancia_data", "data"])
        .groupby("cnpj", as_index=False)
        .first()
        .rename(columns={"data": "data_inicial", "cota": "cota_inicial"})
    )
    resumo = finais.merge(
        iniciais[["cnpj", "data_inicial", "cota_inicial"]],
        on="cnpj",
        how="left",
    )
    resumo["cota_inicial"] = resumo["cota_inicial"].where(
        resumo["cota_inicial"] > 0
    )
    resumo["retorno"] = resumo["cota_final"] / resumo["cota_inicial"] - 1
    resumo["dias_periodo"] = (
        resumo["data_final"] - resumo["data_inicial"]
    ).dt.days
    resumo["retorno_anualizado"] = (
        (1 + resumo["retorno"]) ** (365.25 / resumo["dias_periodo"]) - 1
    )
    resumo = resumo.merge(
        cadastro[["cnpj", "nome", "administrador", "gestor"]],
        on="cnpj",
        how="left",
    )
    return resumo, mes_inicial, mes_final


def rotulo_fundo(registro: pd.Series) -> str:
    nome = str(registro.get("nome", "Fundo sem denominação"))
    return f"{nome} · {formatar_cnpj(registro.get('cnpj'))}"


def seletor_fundo_cvm(
    cadastro: pd.DataFrame | None,
    titulo: str,
    chave: str,
):
    termo = st.text_input(
        titulo,
        placeholder="Digite ao menos 3 letras ou parte do CNPJ",
        key=f"{chave}_busca",
    )
    if len(termo.strip()) < 3:
        return None
    resultados = buscar_fundos_cvm(cadastro, termo)
    if resultados.empty:
        st.caption("Nenhum fundo encontrado.")
        return None
    mapa = resultados.set_index("cnpj").to_dict("index")
    return st.selectbox(
        f"Resultados para {titulo.lower()}",
        options=resultados["cnpj"].tolist(),
        format_func=lambda cnpj: rotulo_fundo(pd.Series(mapa[cnpj] | {"cnpj": cnpj})),
        key=f"{chave}_resultado",
    )


def _pagina_fundos_legada():
    cabecalho_contextual("Fundos de investimento", "Dados oficiais da CVM")
    st.markdown(
        """
        <section class="radar-hero">
            <span class="radar-hero-kicker">PESQUISA E COMPARAÇÃO</span>
            <h1>Fundos no mesmo radar.</h1>
            <p>
                Pesquise fundos e classes registrados na CVM e compare seus
                retornos a partir das cotas informadas pelos administradores.
            </p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    try:
        with st.spinner("Atualizando o cadastro oficial de fundos..."):
            cadastro = carregar_cadastro_fundos_cvm()
    except Exception as erro:
        st.error("Não foi possível acessar o cadastro de fundos da CVM agora.")
        st.caption(str(erro))
        rodape_radar()
        return

    st.caption(
        f"{len(cadastro):,} fundos e classes disponíveis no cadastro da CVM. "
        "A pesquisa também considera administrador e gestor."
    )
    aba_pesquisa, aba_comparacao = st.tabs(["Pesquisar fundos", "Comparar fundos"])

    with aba_pesquisa:
        termo = st.text_input(
            "Nome ou CNPJ do fundo",
            placeholder="Ex.: fundo DI, previdência ou 00.000.000/0001-00",
            key="pesquisa_fundo",
        )
        if len(termo.strip()) < 3:
            st.info("Digite ao menos 3 letras do nome ou parte do CNPJ para pesquisar.")
        else:
            resultados = buscar_fundos_cvm(cadastro, termo)
            if resultados.empty:
                st.warning("Nenhum fundo foi encontrado com esse termo.")
            else:
                mapa_resultados = resultados.set_index("cnpj").to_dict("index")
                cnpj_escolhido = st.selectbox(
                    "Resultados encontrados",
                    options=resultados["cnpj"].tolist(),
                    format_func=lambda cnpj: rotulo_fundo(
                        pd.Series(mapa_resultados[cnpj] | {"cnpj": cnpj})
                    ),
                    key="fundo_pesquisa_resultado",
                )
                fundo = cadastro[cadastro["cnpj"] == cnpj_escolhido].iloc[0]
                st.markdown(f"### {fundo['nome']}")
                st.caption(formatar_cnpj(cnpj_escolhido))
                coluna_status, coluna_tipo, coluna_pl = st.columns(3)
                coluna_status.metric("Situação", fundo.get("situacao") or "Não informada")
                coluna_tipo.metric("Tipo", fundo.get("tipo") or "Não informado")
                coluna_pl.metric(
                    "Patrimônio cadastral",
                    formatar_reais(fundo.get("patrimonio_cadastral")),
                )
                detalhes = pd.DataFrame(
                    {
                        "Campo": [
                            "Administrador",
                            "Gestor",
                            "Classificação",
                            "Classificação ANBIMA",
                            "Público-alvo",
                        ],
                        "Informação": [
                            fundo.get("administrador") or "—",
                            fundo.get("gestor") or "—",
                            fundo.get("classificacao") or "—",
                            fundo.get("classificacao_anbima") or "—",
                            fundo.get("publico_alvo") or "—",
                        ],
                    }
                )
                st.dataframe(detalhes, hide_index=True, width="stretch")

                if st.button("Carregar último informe diário", type="primary"):
                    st.session_state["detalhe_fundo_cvm"] = cnpj_escolhido
                if st.session_state.get("detalhe_fundo_cvm") == cnpj_escolhido:
                    try:
                        with st.spinner("Consultando o informe diário na CVM..."):
                            _, dados_recentes = carregar_mes_recente_fundos(
                                (cnpj_escolhido,)
                            )
                        atual = ultimo_registro_por_fundo(dados_recentes).iloc[0]
                        st.markdown("#### Última informação disponível")
                        coluna_data, coluna_cota, coluna_pl_atual, coluna_cotistas = st.columns(4)
                        coluna_data.metric("Data", atual["data"].strftime("%d/%m/%Y"))
                        coluna_cota.metric("Cota", f"{atual['cota']:.6f}")
                        coluna_pl_atual.metric(
                            "Patrimônio líquido", formatar_reais(atual["patrimonio"])
                        )
                        coluna_cotistas.metric(
                            "Cotistas",
                            f"{atual['cotistas']:,.0f}".replace(",", "."),
                        )
                    except Exception as erro:
                        st.warning("Não foi encontrado um informe diário recente para este fundo.")
                        st.caption(str(erro))

    with aba_comparacao:
        st.write(
            "Pesquise dois fundos. O retorno é calculado pela variação das cotas "
            "entre os fechamentos mensais disponíveis."
        )
        coluna_a, coluna_b = st.columns(2)
        with coluna_a:
            cnpj_a = seletor_fundo_cvm(cadastro, "Fundo principal", "fundo_a")
        with coluna_b:
            cnpj_b = seletor_fundo_cvm(cadastro, "Fundo de comparação", "fundo_b")

        opcoes_prazo = {
            "6 meses": 6,
            "12 meses": 12,
            "2 anos": 24,
            "3 anos": 36,
            "5 anos": 60,
        }
        prazo_fundos = st.selectbox(
            "Período da comparação",
            options=list(opcoes_prazo),
            index=1,
        )
        cnpjs_validos = tuple(
            dict.fromkeys(cnpj for cnpj in [cnpj_a, cnpj_b] if cnpj)
        )
        comparar = st.button(
            "Comparar fundos",
            type="primary",
            width="stretch",
            disabled=len(cnpjs_validos) != 2,
        )
        if comparar:
            st.session_state["comparacao_fundos_cvm"] = (
                cnpjs_validos,
                opcoes_prazo[prazo_fundos],
            )

        configuracao = st.session_state.get("comparacao_fundos_cvm")
        if configuracao and configuracao == (
            cnpjs_validos,
            opcoes_prazo[prazo_fundos],
        ):
            try:
                with st.spinner(
                    "Baixando os dois fechamentos necessários e calculando os retornos..."
                ):
                    resumo, mes_inicial, mes_final = montar_resumo_comparacao_fundos(
                        cadastro,
                        cnpjs_validos,
                        opcoes_prazo[prazo_fundos],
                    )
                if resumo["retorno"].isna().any():
                    st.warning(
                        "Um dos fundos não possui cota nos dois extremos do período "
                        "selecionado. Tente um prazo menor."
                    )
                else:
                    colunas_retorno = st.columns(len(resumo))
                    for coluna, (_, linha) in zip(colunas_retorno, resumo.iterrows()):
                        coluna.metric(
                            linha["nome"],
                            f"{linha['retorno']:.2%}",
                            f"{linha['retorno_anualizado']:.2%} a.a.",
                            delta_color="off",
                        )

                    grafico = go.Figure(
                        go.Bar(
                            x=resumo["nome"],
                            y=resumo["retorno"] * 100,
                            marker_color=["#1769e0", "#19c2d8"],
                            text=[f"{valor:.2%}" for valor in resumo["retorno"]],
                            textposition="outside",
                            hovertemplate="%{x}<br>Retorno: %{y:.2f}%<extra></extra>",
                        )
                    )
                    grafico.update_layout(
                        title=f"Retorno acumulado · {prazo_fundos}",
                        height=420,
                        margin={"l": 20, "r": 20, "t": 65, "b": 110},
                        plot_bgcolor="white",
                        paper_bgcolor="white",
                        showlegend=False,
                    )
                    grafico.update_yaxes(ticksuffix="%", gridcolor="#e2e8f0")
                    grafico.update_xaxes(tickangle=-10)
                    st.plotly_chart(
                        grafico,
                        width="stretch",
                        config={"displayModeBar": False, "displaylogo": False},
                    )

                    tabela = resumo[
                        [
                            "nome",
                            "data_inicial",
                            "data_final",
                            "retorno",
                            "retorno_anualizado",
                            "patrimonio_atual",
                            "cotistas_atuais",
                        ]
                    ].copy()
                    tabela.columns = [
                        "Fundo",
                        "Data inicial",
                        "Data final",
                        "Retorno acumulado",
                        "Retorno anualizado",
                        "Patrimônio atual",
                        "Cotistas",
                    ]
                    st.dataframe(
                        tabela,
                        hide_index=True,
                        width="stretch",
                        column_config={
                            "Data inicial": st.column_config.DateColumn(format="DD/MM/YYYY"),
                            "Data final": st.column_config.DateColumn(format="DD/MM/YYYY"),
                            "Retorno acumulado": st.column_config.NumberColumn(format="percent"),
                            "Retorno anualizado": st.column_config.NumberColumn(format="percent"),
                            "Patrimônio atual": st.column_config.NumberColumn(format="R$ %.2f"),
                            "Cotistas": st.column_config.NumberColumn(format="localized"),
                        },
                    )
                    st.caption(
                        f"Período de referência: {mes_inicial.strftime('%m/%Y')} a "
                        f"{mes_final.strftime('%m/%Y')}. Retorno pela variação da cota, "
                        "sem impostos ou custos individuais do cotista."
                    )
            except requests.HTTPError as erro:
                st.error("A CVM não disponibilizou um dos meses necessários agora.")
                st.caption(str(erro))
            except Exception as erro:
                st.error("Não foi possível concluir a comparação dos fundos.")
                st.caption(str(erro))

    st.markdown(
        "Fonte: [Portal de Dados Abertos da CVM]"
        "(https://dados.cvm.gov.br/dataset/fi-doc-inf_diario). "
        "As informações são reportadas pelos administradores dos fundos."
    )
    rodape_radar()


def texto_extrato(valor, padrao="Não informado"):
    if valor is None or pd.isna(valor) or not str(valor).strip():
        return padrao
    return str(valor).strip()


def prazo_dias_extrato(valor, tipo_dia=""):
    if valor is None or pd.isna(valor):
        return "Não informado"
    sufixo = f" {str(tipo_dia).lower()}" if texto_extrato(tipo_dia, "") else " dias"
    return f"D+{int(float(valor))}{sufixo}"


def renderizar_fichas_fundos(cadastro, cnpjs, extrato, historico):
    st.markdown(
        """
        <style>
        .fundo-ficha {
            width: 100%;
            max-width: 480px;
            margin: 0 0 0.75rem 0;
            overflow: hidden;
            border: 1px solid #cfdae8;
            border-radius: 12px;
            background: #ffffff;
            box-shadow: 0 5px 18px rgba(8, 38, 75, 0.06);
        }
        .fundo-ficha-cabecalho {
            padding: 0.72rem 0.85rem;
            border-bottom: 3px solid #19c2d8;
            background: linear-gradient(110deg, #08264c, #1555a0);
            color: #ffffff;
        }
        .fundo-ficha-nome {
            font-size: 0.86rem;
            font-weight: 800;
            line-height: 1.25;
            text-transform: uppercase;
        }
        .fundo-ficha-ref {
            margin-top: 0.2rem;
            color: #cceaf6;
            font-size: 0.66rem;
        }
        .fundo-ficha-linha {
            display: grid;
            grid-template-columns: minmax(120px, 46%) minmax(0, 54%);
            align-items: center;
            gap: 0.5rem;
            min-height: 29px;
            padding: 0.31rem 0.72rem;
            border-bottom: 1px solid #e4ebf3;
            font-size: 0.73rem;
            line-height: 1.15;
        }
        .fundo-ficha-linha:nth-child(even) { background: #edf6ff; }
        .fundo-ficha-linha:nth-child(odd) { background: #ffffff; }
        .fundo-ficha-linha:last-child { border-bottom: 0; }
        .fundo-ficha-chave { color: #36506d; }
        .fundo-ficha-valor {
            color: #071d39;
            font-weight: 650;
            overflow-wrap: anywhere;
            text-align: right;
        }
        @media (max-width: 700px) {
            .fundo-ficha { max-width: 100%; }
            .fundo-ficha-linha { grid-template-columns: 43% 57%; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Informações dos fundos", expanded=True):
        colunas = st.columns(min(2, len(cnpjs)))
        for indice, cnpj in enumerate(cnpjs):
            fundo = cadastro[cadastro["cnpj"].eq(cnpj)].iloc[0]
            linha_extrato = extrato[extrato["cnpj"].eq(cnpj)]
            ext = linha_extrato.iloc[0] if not linha_extrato.empty else pd.Series(dtype=object)
            dados_recentes = historico[historico["cnpj"].eq(cnpj)].dropna(subset=["data"])
            atual = (
                dados_recentes.sort_values("data").iloc[-1]
                if not dados_recentes.empty
                else pd.Series(dtype=object)
            )
            benchmark = texto_extrato(fundo.get("indicador_desempenho"), "")
            if not benchmark:
                benchmark = texto_extrato(ext.get("PARAM_TAXA_PERFM"))
            taxa_adm = ext.get("TAXA_ADM")
            taxa_adm_texto = "Não informada" if pd.isna(taxa_adm) else f"{taxa_adm:.2f}% a.a."
            taxa_perf = ext.get("TAXA_PERFM")
            taxa_perf_texto = "Não informada" if pd.isna(taxa_perf) else f"{taxa_perf:.2f}%"
            aplicacao = ext.get("APLIC_MIN")
            aplicacao_texto = "Não informada" if pd.isna(aplicacao) else formatar_reais(aplicacao)
            data_extrato = ext.get("DT_COMPTC")
            referencia = (
                pd.Timestamp(data_extrato).strftime("%d/%m/%Y")
                if pd.notna(data_extrato)
                else "não disponível"
            )
            cotistas = atual.get("cotistas")
            cotistas_texto = (
                "Não informado"
                if pd.isna(cotistas)
                else f"{cotistas:,.0f}".replace(",", ".")
            )
            linhas = [
                ("Tipo de ativo", texto_extrato(fundo.get("tipo"))),
                ("CNPJ", formatar_cnpj(cnpj)),
                ("Situação", texto_extrato(fundo.get("situacao"))),
                ("Administrador", texto_extrato(fundo.get("administrador"))),
                ("Gestão", texto_extrato(fundo.get("gestor"))),
                ("Classificação", texto_extrato(ext.get("CLASSE_ANBIMA"), texto_extrato(fundo.get("classificacao")))),
                ("Benchmark", benchmark),
                ("Condomínio", texto_extrato(ext.get("CONDOM"))),
                ("Captação", "Não informada pela CVM"),
                ("Público-alvo", texto_extrato(ext.get("PUBLICO_ALVO"), texto_extrato(fundo.get("publico_alvo")))),
                ("Taxa de administração", taxa_adm_texto),
                ("Taxa de performance", taxa_perf_texto),
                ("Aplicação mínima", aplicacao_texto),
                ("Conversão da aplicação", prazo_dias_extrato(ext.get("QT_DIA_CONVERSAO_COTA"))),
                ("Conversão do resgate", prazo_dias_extrato(ext.get("QT_DIA_RESGATE_COTAS"))),
                ("Pagamento do resgate", prazo_dias_extrato(ext.get("QT_DIA_PAGTO_RESGATE"), ext.get("TP_DIA_PAGTO_RESGATE"))),
                ("Última cota", "Não informada" if pd.isna(atual.get("cota")) else f"{atual['cota']:.6f}"),
                ("Patrimônio líquido", formatar_reais(atual.get("patrimonio"))),
                ("Cotistas", cotistas_texto),
                ("Data da posição", "Não informada" if pd.isna(atual.get("data")) else atual["data"].strftime("%d/%m/%Y")),
            ]
            corpo = "".join(
                '<div class="fundo-ficha-linha">'
                f'<span class="fundo-ficha-chave">{escape(chave)}</span>'
                f'<span class="fundo-ficha-valor">{escape(str(valor))}</span>'
                "</div>"
                for chave, valor in linhas
            )
            ficha = (
                '<div class="fundo-ficha">'
                '<div class="fundo-ficha-cabecalho">'
                f'<div class="fundo-ficha-nome">{escape(str(fundo["nome"]))}</div>'
                f'<div class="fundo-ficha-ref">Extrato CVM declarado em {escape(referencia)}</div>'
                "</div>"
                f"<div>{corpo}</div>"
                "</div>"
            )
            with colunas[indice % len(colunas)]:
                st.markdown(ficha, unsafe_allow_html=True)


def renderizar_analise_completa_fundos(
    cadastro,
    cnpjs,
    benchmarks,
    meses_historico,
    rotulo_historico,
):
    data_inicio_comum = None
    if meses_historico is None:
        datas_constituicao = cadastro.loc[
            cadastro["cnpj"].isin(cnpjs), "data_constituicao"
        ].dropna()
        if not datas_constituicao.empty:
            data_inicio_comum = datas_constituicao.max().strftime("%Y-%m-%d")
    with st.spinner(
        "Montando o histórico. No primeiro acesso, a consulta de vários anos pode levar alguns minutos..."
    ):
        extrato = carregar_extrato_fundos_cvm(tuple(cnpjs))
        try:
            historico = carregar_historico_fundos_cvm(
                tuple(cnpjs),
                meses_historico,
                data_inicio_comum,
            )
        except RuntimeError as erro:
            if "não retornou histórico" not in str(erro).lower():
                raise
            historico_vazio = pd.DataFrame(
                columns=[
                    "cnpj",
                    "data",
                    "cota",
                    "patrimonio",
                    "captacao_dia",
                    "resgate_dia",
                    "cotistas",
                ]
            )
            renderizar_fichas_fundos(cadastro, cnpjs, extrato, historico_vazio)
            st.warning(
                "A base pública de Informe Diário da CVM não disponibilizou cotas "
                f"para este fundo no período “{rotulo_historico}”. Isso não significa que o fundo "
                "não possua histórico em outras bases. Tente ampliar o período; sem "
                "cotas públicas no intervalo, os gráficos não podem ser calculados."
            )
            return
        benchmarks_internos = list(dict.fromkeys([*benchmarks, "CDI"]))
        series_completas = obter_series_analise_fundos(
            historico, cadastro, tuple(cnpjs), benchmarks_internos
        )

    nomes_fundos = list(series_completas)[: len(cnpjs)]
    series_exibidas = {
        nome: serie
        for nome, serie in series_completas.items()
        if nome in nomes_fundos or nome in benchmarks
    }
    if not series_exibidas or any(serie.empty for serie in series_exibidas.values()):
        st.warning("Não há histórico comum suficiente para a seleção realizada.")
        return

    fundos_com_serie_interrompida = []
    limite_recencia = pd.Timestamp(date.today()) - pd.Timedelta(days=45)
    for cnpj in cnpjs:
        dados_fundo = historico[historico["cnpj"].eq(cnpj)].dropna(subset=["data"])
        if dados_fundo.empty:
            continue
        ultima_data = pd.Timestamp(dados_fundo["data"].max())
        if ultima_data < limite_recencia:
            nome = cadastro.loc[cadastro["cnpj"].eq(cnpj), "nome"].iloc[0]
            fundos_com_serie_interrompida.append((nome, ultima_data))

    renderizar_fichas_fundos(cadastro, cnpjs, extrato, historico)
    if fundos_com_serie_interrompida:
        detalhes_interrupcao = "; ".join(
            f"{nome}: último registro em {ultima_data:%d/%m/%Y}"
            for nome, ultima_data in fundos_com_serie_interrompida
        )
        st.warning(
            "A base pública de Informe Diário da CVM não possui cotas recentes para "
            f"a seguinte seleção: {detalhes_interrupcao}. O fundo pode continuar ativo "
            "e possuir histórico em outras bases. Os cálculos abaixo consideram somente "
            "o trecho efetivamente disponibilizado pela CVM."
        )

    with st.expander("Rentabilidade", expanded=True):
        st.plotly_chart(
            criar_grafico_evolucao_fundos(series_exibidas),
            width="stretch",
            config={"displayModeBar": False, "displaylogo": False},
        )
        st.markdown("#### Retornos por período")
        st.dataframe(
            criar_tabela_periodos_fundos(series_exibidas),
            hide_index=True,
            width="stretch",
        )
        data_inicial = max(serie.index.min() for serie in series_exibidas.values())
        data_final = min(serie.index.max() for serie in series_exibidas.values())
        st.caption(
            f"Séries comparadas em uma base comum, de {data_inicial:%d/%m/%Y} a "
            f"{data_final:%d/%m/%Y}. O retorno acumulado começa em 0%."
        )

    with st.expander("Análise de risco", expanded=False):
        st.markdown("#### Volatilidade e índice de Sharpe")
        metricas = calcular_metricas_risco_fundos(series_completas)
        if "CDI" not in benchmarks:
            metricas = metricas[metricas["Ativo"].ne("CDI")]
        st.dataframe(
            metricas,
            hide_index=True,
            width="stretch",
            column_config={
                "Volatilidade a.a.": st.column_config.NumberColumn(format="percent"),
                "Sharpe vs. CDI": st.column_config.NumberColumn(format="%.2f"),
                "Maior queda": st.column_config.NumberColumn(format="percent"),
                "Dias positivos": st.column_config.NumberColumn(format="percent"),
                "Melhor dia": st.column_config.NumberColumn(format="percent"),
                "Pior dia": st.column_config.NumberColumn(format="percent"),
            },
        )
        st.caption(
            f"Período analisado: {data_inicial:%d/%m/%Y} a {data_final:%d/%m/%Y}. "
            "Volatilidade e Sharpe anualizados com 252 dias úteis. O Sharpe considera "
            "o excesso de retorno diário sobre o CDI; maior queda é o drawdown máximo."
        )
        aba_volatilidade, aba_drawdown = st.tabs(["Volatilidade", "Drawdown"])
        with aba_volatilidade:
            st.plotly_chart(
                criar_grafico_volatilidade_fundos(series_exibidas),
                width="stretch",
                config={"displayModeBar": False, "displaylogo": False},
            )
            st.caption(
                "Volatilidade anualizada calculada em intervalos de 63 dias úteis, "
                "sem seletor adicional."
            )
        with aba_drawdown:
            st.plotly_chart(
                criar_grafico_drawdown_fundos(series_exibidas),
                width="stretch",
                config={"displayModeBar": False, "displaylogo": False},
            )

    with st.expander("Janelas móveis", expanded=False):
        st.caption(
            f"Intervalo histórico usado: {data_inicial:%d/%m/%Y} a {data_final:%d/%m/%Y} "
            f"({rotulo_historico} selecionado no topo). "
            "Cada ponto representa uma entrada no fechamento de um mês."
        )
        opcoes_janela = {
            "1 mês": 1,
            "3 meses": 3,
            "6 meses": 6,
            "12 meses": 12,
            "2 anos": 24,
            "3 anos": 36,
            "5 anos": 60,
        }
        if meses_historico is not None and meses_historico <= 3:
            indice_janela_padrao = 0
        elif meses_historico is not None and meses_historico <= 6:
            indice_janela_padrao = 1
        else:
            indice_janela_padrao = 3
        janela_escolhida = st.selectbox(
            "Tamanho de cada janela",
            list(opcoes_janela),
            index=indice_janela_padrao,
            key=f"janela_fundos_{'_'.join(cnpjs)}",
        )
        meses_janela = opcoes_janela[janela_escolhida]
        grafico_janelas, janelas = criar_janelas_moveis_fundos(
            series_exibidas, meses_janela
        )
        if not any(not serie.empty for serie in janelas.values()):
            st.info("Escolha uma janela menor ou um período histórico maior.")
        else:
            st.plotly_chart(
                grafico_janelas,
                width="stretch",
                config={"displayModeBar": False, "displaylogo": False},
            )
            resumo = []
            for nome, serie in janelas.items():
                if serie.empty:
                    continue
                resumo.append(
                    {
                        "Ativo": nome,
                        "Pior janela": serie.min(),
                        "Janela mediana": serie.median(),
                        "Melhor janela": serie.max(),
                        "Janelas analisadas": len(serie),
                    }
                )
            st.dataframe(
                pd.DataFrame(resumo),
                hide_index=True,
                width="stretch",
                column_config={
                    "Pior janela": st.column_config.NumberColumn(format="percent"),
                    "Janela mediana": st.column_config.NumberColumn(format="percent"),
                    "Melhor janela": st.column_config.NumberColumn(format="percent"),
                },
            )
            principal = nomes_fundos[0]
            frequencia = calcular_frequencia_vitorias_janelas(janelas, principal)
            if frequencia.empty:
                st.info(
                    "Adicione ao menos um benchmark ou outro fundo para calcular "
                    "a frequência histórica de vitória."
                )
            else:
                st.markdown("#### Quantas vezes o fundo principal venceu?")
                st.caption(
                    f"Série principal: {principal}. As janelas são mensais e sobrepostas, "
                    "como na análise de índices."
                )
                for _, linha in frequencia.iterrows():
                    st.markdown(
                        f"**Fundo principal × {linha['Comparativo']}:** o principal venceu "
                        f"**{int(linha['Principal venceu'])} de {int(linha['Janelas'])} janelas "
                        f"({linha['% de vitória do principal']:.1%})**; o comparativo venceu "
                        f"{int(linha['Comparativo venceu'])}."
                    )
                if frequencia["Janelas"].min() < 12:
                    st.warning(
                        "A amostra possui menos de 12 janelas comparáveis. Percentuais "
                        "calculados com poucas observações devem ser interpretados com cautela."
                    )
                st.plotly_chart(
                    criar_grafico_frequencia_vitorias(frequencia, principal),
                    width="stretch",
                    config={"displayModeBar": False, "displaylogo": False},
                )
                st.dataframe(
                    frequencia,
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "% de vitória do principal": st.column_config.NumberColumn(format="percent"),
                    },
                )


def pagina_fundos():
    cabecalho_contextual("Fundos de investimento", "Dados oficiais da CVM")
    st.markdown(
        """
        <section class="radar-hero">
            <span class="radar-hero-kicker">PESQUISA, COMPARAÇÃO E RISCO</span>
            <h1>Fundos no mesmo radar.</h1>
            <p>Compare rentabilidade, risco e consistência histórica em uma leitura única e intuitiva.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    try:
        cadastro = None
        if not cadastro_fundos_atualizado_recentemente():
            with st.spinner("Atualizando o cadastro oficial de fundos..."):
                cadastro = carregar_cadastro_fundos_cvm()
                total_cadastro = len(cadastro)
        else:
            total_cadastro = contar_cadastro_fundos()
    except Exception as erro:
        st.error("Não foi possível acessar o cadastro de fundos da CVM agora.")
        st.caption(str(erro))
        rodape_radar()
        return

    st.caption(
        f"{total_cadastro:,} fundos e classes no cadastro da CVM. "
        "A pesquisa considera nome, CNPJ, administrador e gestor."
    )
    aba_pesquisa, aba_comparacao = st.tabs(["Analisar um fundo", "Comparar fundos"])
    opcoes_periodo = {
        "3 meses": 3,
        "6 meses": 6,
        "1 ano": 12,
        "2 anos": 24,
        "3 anos": 36,
        "5 anos": 60,
        "Desde o início comum": None,
    }
    opcoes_benchmark = ["CDI", "Ibovespa", "IDIV"]

    with aba_pesquisa:
        cnpj = seletor_fundo_cvm(cadastro, "Pesquise por nome ou CNPJ", "analise_individual")
        coluna_periodo, coluna_benchmark = st.columns([1, 2])
        with coluna_periodo:
            periodo = st.selectbox(
                "Histórico do gráfico", list(opcoes_periodo), index=2, key="periodo_fundo_individual"
            )
        with coluna_benchmark:
            benchmarks = st.multiselect(
                "Comparar também com", opcoes_benchmark, default=["CDI"], key="bench_individual"
            )
        analisar = st.button(
            "Gerar análise completa",
            type="primary",
            width="stretch",
            disabled=cnpj is None,
            key="analisar_fundo_individual",
        )
        if analisar:
            st.session_state["analise_fundo_individual"] = (
                cnpj, tuple(benchmarks), opcoes_periodo[periodo]
            )
        configuracao = st.session_state.get("analise_fundo_individual")
        if configuracao == (cnpj, tuple(benchmarks), opcoes_periodo[periodo]):
            try:
                cadastro_selecionado = (
                    cadastro[cadastro["cnpj"].eq(cnpj)].copy()
                    if cadastro is not None
                    else carregar_cadastro_fundos_por_cnpj((cnpj,))
                )
                renderizar_analise_completa_fundos(
                    cadastro_selecionado,
                    [cnpj],
                    benchmarks,
                    opcoes_periodo[periodo],
                    periodo,
                )
            except Exception as erro:
                st.error("Não foi possível montar a análise completa deste fundo.")
                st.caption(str(erro))

    with aba_comparacao:
        st.write("Selecione de um a quatro fundos e acrescente os benchmarks desejados.")
        quantidade = st.select_slider(
            "Quantidade de fundos", options=[1, 2, 3, 4], value=2, key="quantidade_fundos"
        )
        selecionados = []
        colunas = st.columns(2)
        for indice in range(quantidade):
            with colunas[indice % 2]:
                selecionados.append(
                    seletor_fundo_cvm(
                        cadastro, f"Fundo {indice + 1}", f"comparacao_fundo_{indice + 1}"
                    )
                )
        cnpjs = list(dict.fromkeys(cnpj for cnpj in selecionados if cnpj))
        if len(cnpjs) < len([cnpj for cnpj in selecionados if cnpj]):
            st.warning("Um fundo repetido será considerado apenas uma vez.")
        coluna_periodo, coluna_benchmark = st.columns([1, 2])
        with coluna_periodo:
            periodo = st.selectbox(
                "Histórico do gráfico", list(opcoes_periodo), index=2, key="periodo_comparacao_fundos"
            )
        with coluna_benchmark:
            benchmarks = st.multiselect(
                "Benchmarks", opcoes_benchmark, default=["CDI"], key="bench_comparacao_fundos"
            )
        comparar = st.button(
            "Comparar seleção",
            type="primary",
            width="stretch",
            disabled=not cnpjs,
            key="comparar_selecao_fundos",
        )
        if comparar:
            st.session_state["analise_comparacao_fundos"] = (
                tuple(cnpjs), tuple(benchmarks), opcoes_periodo[periodo]
            )
        configuracao = st.session_state.get("analise_comparacao_fundos")
        if configuracao == (tuple(cnpjs), tuple(benchmarks), opcoes_periodo[periodo]):
            try:
                cadastro_selecionado = (
                    cadastro[cadastro["cnpj"].isin(cnpjs)].copy()
                    if cadastro is not None
                    else carregar_cadastro_fundos_por_cnpj(tuple(cnpjs))
                )
                renderizar_analise_completa_fundos(
                    cadastro_selecionado,
                    cnpjs,
                    benchmarks,
                    opcoes_periodo[periodo],
                    periodo,
                )
            except Exception as erro:
                st.error("Não foi possível concluir a comparação dos fundos.")
                st.caption(str(erro))

    st.info(
        "IHFA: a integração está preparada, mas a série oficial da ANBIMA exige "
        "credenciais de acesso ao ANBIMA Feed. CDI, Ibovespa e IDIV já estão disponíveis."
    )
    st.markdown(
        "Fontes: [CVM — informes diários](https://dados.cvm.gov.br/dataset/fi-doc-inf_diario), "
        "[CVM — extrato](https://dados.cvm.gov.br/dataset/fi-doc-extrato), "
        "Banco Central do Brasil e B3. Dados reportados pelos administradores; "
        "retornos brutos pela variação das cotas."
    )
    rodape_radar()


aplicar_identidade_visual()

with st.sidebar:
    st.markdown(
        """
        <div class="radar-sidebar-brand">
            <div class="radar-mark">R</div>
            <div>
                <div class="radar-brand-name">Radar de Retorno</div>
                <div class="radar-brand-sub">Inteligência de investimentos</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    pagina_atual = st.radio(
        "Navegação",
        ["Início", "Análise de índices", "Fundos"],
        key="pagina_radar",
    )

if pagina_atual == "Início":
    pagina_inicial()
    st.stop()

if pagina_atual == "Fundos":
    pagina_fundos()
    st.stop()


@st.cache_data(ttl=86_400, show_spinner=False)
def baixar_serie_bcb(codigo: int, ano_inicial: int) -> pd.DataFrame:
    """Lê o SGS do banco local e busca no BCB somente o trecho novo."""
    codigo_banco = f"BCB_{codigo}"
    armazenados = carregar_serie_mercado(codigo_banco)
    if not armazenados.empty and serie_mercado_atualizada_recentemente(codigo_banco):
        return armazenados.sort_values("data")
    primeiro_ano = (
        ano_inicial
        if armazenados.empty
        else max(ano_inicial, armazenados["data"].max().year)
    )
    partes = []
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"

    for ano in range(primeiro_ano, date.today().year + 1):
        for tentativa in range(5):
            try:
                resposta = requests.get(
                    url,
                    params={
                        "formato": "json",
                        "dataInicial": f"01/01/{ano}",
                        "dataFinal": f"31/12/{ano}",
                    },
                    headers={"User-Agent": "Radar-de-Retorno/1.0"},
                    timeout=30,
                )
                resposta.raise_for_status()
                break
            except requests.RequestException:
                if tentativa == 4:
                    if not armazenados.empty:
                        return armazenados.sort_values("data")
                    raise
                time.sleep(2 ** tentativa)

        parte = pd.DataFrame(resposta.json())
        if not parte.empty:
            partes.append(parte)

    if not partes and armazenados.empty:
        raise RuntimeError("O Banco Central não retornou dados para a série.")
    if partes:
        novos = pd.concat(partes, ignore_index=True)
        novos["data"] = pd.to_datetime(novos["data"], dayfirst=True)
        novos["valor"] = pd.to_numeric(
            novos["valor"].astype(str).str.replace(",", "."),
            errors="coerce",
        )
        novos = novos.dropna(subset=["data", "valor"])
        salvar_serie_mercado(codigo_banco, novos)
    return carregar_serie_mercado(codigo_banco).sort_values("data")


@st.cache_data(ttl=86_400, show_spinner=False)
def baixar_sp500(ano_inicial: int) -> pd.DataFrame:
    """Lê o S&P 500 local e atualiza somente os meses mais recentes."""
    codigo_banco = "YAHOO_GSPC_MENSAL"
    armazenados = carregar_serie_mercado(codigo_banco)
    if not armazenados.empty and serie_mercado_atualizada_recentemente(codigo_banco):
        dados = armazenados.rename(columns={"valor": "indice_sp500"})
        dados["mes"] = dados["data"].dt.to_period("M")
        return dados.groupby("mes", as_index=False).last()
    if armazenados.empty:
        inicio = datetime(ano_inicial, 1, 1, tzinfo=timezone.utc)
    else:
        inicio = (
            armazenados["data"].max() - pd.DateOffset(months=2)
        ).to_pydatetime().replace(tzinfo=timezone.utc)
    fim = datetime.now(timezone.utc) + timedelta(days=1)
    try:
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
            timeout=30,
        )
        resposta.raise_for_status()
    except requests.RequestException:
        if armazenados.empty:
            raise
        dados = armazenados.rename(columns={"valor": "indice_sp500"})
        dados["mes"] = dados["data"].dt.to_period("M")
        return dados.groupby("mes", as_index=False).last()
    resultado = resposta.json()["chart"]["result"][0]
    fechamentos = resultado["indicators"]["quote"][0]["close"]
    novos = pd.DataFrame(
        {
            "data": pd.to_datetime(resultado["timestamp"], unit="s", utc=True)
            .tz_convert(None),
            "valor": fechamentos,
        }
    ).dropna()
    salvar_serie_mercado(codigo_banco, novos)
    dados = carregar_serie_mercado(codigo_banco).rename(
        columns={"valor": "indice_sp500"}
    )
    dados["mes"] = dados["data"].dt.to_period("M")
    return dados.groupby("mes", as_index=False).last()


@st.cache_data(ttl=86_400, show_spinner=False)
def preparar_dados(ano_inicial: int = 2000):
    # SGS 12: CDI diário em percentual ao dia.
    cdi = baixar_serie_bcb(12, ano_inicial)
    cdi["taxa_cdi_dia"] = cdi["valor"] / 100
    cdi["indice_cdi"] = (1 + cdi["taxa_cdi_dia"]).cumprod() * 100
    cdi["mes"] = cdi["data"].dt.to_period("M")
    cdi_mensal = cdi.groupby("mes", as_index=False).last()

    # SGS 433: IPCA cheio, variação percentual mensal.
    ipca = baixar_serie_bcb(433, ano_inicial)
    ipca["ipca_mes"] = ipca["valor"] / 100
    ipca["mes"] = ipca["data"].dt.to_period("M")

    sp500 = baixar_sp500(ano_inicial)
    return cdi_mensal, ipca, sp500


def nomes_series(
    taxa_ipca: float,
    taxa_prefixada: float,
    taxa_referencia: float,
    participacao_sp500: float,
) -> dict[str, str]:
    return {
        "cdi": "CDI",
        "ipca": f"IPCA + {taxa_ipca:.2f}%",
        "prefixado": f"Prefixado {taxa_prefixada:.2f}% a.a.",
        "sp500": (
            f"S&P 500 ({participacao_sp500:.0f}% de participação, USD, preço)"
        ),
        "sp500_ipca": f"S&P 500 ({participacao_sp500:.0f}%) + IPCA",
        "referencia": f"Referência {taxa_referencia:.2f}% a.a.",
    }


COLUNAS_INDICES = {
    "cdi": "indice_cdi",
    "ipca": "indice_ipca",
    "prefixado": "indice_prefixado",
    "sp500": "indice_sp500",
    "sp500_ipca": "indice_sp500_ipca",
    "referencia": "indice_referencia",
}


def construir_indices(
    cdi_mensal: pd.DataFrame,
    ipca: pd.DataFrame,
    sp500: pd.DataFrame,
    taxa_ipca: float,
    taxa_prefixada: float,
    taxa_referencia: float,
    participacao_sp500: float,
) -> pd.DataFrame:
    taxa_real_mensal = (1 + taxa_ipca / 100) ** (1 / 12) - 1
    taxa_prefixada_mensal = (1 + taxa_prefixada / 100) ** (1 / 12) - 1
    taxa_referencia_mensal = (1 + taxa_referencia / 100) ** (1 / 12) - 1

    ipca_calculo = ipca[["mes", "ipca_mes"]].copy()
    ipca_calculo["indice_ipca"] = (
        1 + ((1 + ipca_calculo["ipca_mes"]) * (1 + taxa_real_mensal) - 1)
    ).cumprod() * 100
    ipca_calculo["indice_inflacao"] = (1 + ipca_calculo["ipca_mes"]).cumprod() * 100

    base = pd.merge(
        cdi_mensal[["mes", "indice_cdi"]],
        ipca_calculo[["mes", "indice_ipca", "indice_inflacao"]],
        on="mes",
        how="inner",
    )
    base = pd.merge(
        base,
        sp500[["mes", "indice_sp500"]],
        on="mes",
        how="inner",
    ).sort_values("mes")

    base["indice_prefixado"] = (
        (1 + taxa_prefixada_mensal) ** pd.Series(range(len(base)), index=base.index)
    ) * 100
    base["indice_referencia"] = (
        (1 + taxa_referencia_mensal) ** pd.Series(range(len(base)), index=base.index)
    ) * 100
    retorno_sp500 = base["indice_sp500"].pct_change().fillna(0)
    base["indice_sp500"] = (
        1 + retorno_sp500 * participacao_sp500 / 100
    ).cumprod() * 100
    indice_inflacao_rebaseado = (
        base["indice_inflacao"] / base["indice_inflacao"].iloc[0] * 100
    )
    base["indice_sp500_ipca"] = (
        base["indice_sp500"] * indice_inflacao_rebaseado / 100
    )
    base["data"] = base["mes"].dt.to_timestamp("M")
    return base


def analisar_janelas(
    cdi_mensal: pd.DataFrame,
    ipca: pd.DataFrame,
    sp500: pd.DataFrame,
    taxa_ipca: float,
    taxa_prefixada: float,
    taxa_referencia: float,
    participacao_sp500: float,
    prazo_anos: int,
    historico_anos: int,
) -> pd.DataFrame:
    numero_meses = prazo_anos * 12
    base = construir_indices(
        cdi_mensal,
        ipca,
        sp500,
        taxa_ipca,
        taxa_prefixada,
        taxa_referencia,
        participacao_sp500,
    )

    for codigo, coluna_indice in COLUNAS_INDICES.items():
        acumulado = base[coluna_indice].pct_change(numero_meses)
        base[f"{codigo}_acumulado"] = acumulado
        base[codigo] = (1 + acumulado) ** (1 / prazo_anos) - 1

    base["data_final"] = base["mes"].dt.to_timestamp("M")
    base = base.dropna(subset=list(COLUNAS_INDICES))
    ultima_data = base["data_final"].max()
    return base[
        base["data_final"] >= ultima_data - pd.DateOffset(years=historico_anos)
    ].copy()


def criar_grafico(
    analise: pd.DataFrame,
    series_escolhidas: list[str],
    nomes: dict[str, str],
    prazo_anos: int,
    visualizacao: str = "Anualizado em linhas",
):
    cores = {
        "cdi": "#174A7E",
        "ipca": "#1B7F5A",
        "prefixado": "#C43D3D",
        "sp500": "#7A4EAB",
        "sp500_ipca": "#D47A22",
        "referencia": "#555555",
    }
    estilos = {"prefixado": "dash", "referencia": "dot"}
    fig = go.Figure()
    exibir_acumulado = visualizacao == "Acumulado em linhas"

    for codigo in series_escolhidas:
        if exibir_acumulado:
            fig.add_trace(
                go.Scatter(
                    x=analise["data_final"],
                    y=analise[f"{codigo}_acumulado"] * 100,
                    mode="lines",
                    name=nomes[codigo],
                    line={
                        "color": cores[codigo],
                        "width": 2.5,
                        "dash": estilos.get(codigo, "solid"),
                    },
                    hovertemplate=(
                        f"<b>{nomes[codigo]}</b><br>"
                        "%{x|%m/%Y}<br>Retorno acumulado da janela: "
                        "%{y:.2f}%<extra></extra>"
                    ),
                )
            )
        else:
            fig.add_trace(
                go.Scatter(
                    x=analise["data_final"],
                    y=analise[codigo] * 100,
                    mode="lines",
                    name=nomes[codigo],
                    line={
                        "color": cores[codigo],
                        "width": 2.5,
                        "dash": estilos.get(codigo, "solid"),
                    },
                    hovertemplate=(
                        f"<b>{nomes[codigo]}</b><br>"
                        "%{x|%m/%Y}<br>Retorno anualizado: "
                        "%{y:.2f}%<extra></extra>"
                    ),
                )
            )

    fig.update_layout(
        title={
            "text": (
                f"Retornos acumulados em janelas móveis de {prazo_anos} anos"
                if exibir_acumulado
                else f"Retornos anualizados em janelas móveis de {prazo_anos} anos"
            ),
            "x": 0,
            "xanchor": "left",
            "font": {"size": 22},
        },
        autosize=False,
        width=1100,
        height=520,
        margin={"l": 25, "r": 20, "t": 75, "b": 80},
        hovermode="x unified",
        dragmode=False,
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.16,
            "xanchor": "center",
            "x": 0.5,
        },
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    fig.update_xaxes(
        title_text="Data final da janela",
        showgrid=False,
        dtick="M24",
        tickformat="%Y",
        automargin=True,
        fixedrange=True,
    )
    fig.update_yaxes(
        title_text="Retorno acumulado da janela" if exibir_acumulado else "Retorno anualizado",
        ticksuffix="%",
        gridcolor="#E2E2E2",
        zerolinecolor="#BBBBBB",
        automargin=True,
        fixedrange=True,
    )
    return fig


def calcular_desempenho_periodo(
    indices: pd.DataFrame,
    series_escolhidas: list[str],
    data_inicial,
    data_final,
):
    inicio = pd.Timestamp(data_inicial).to_period("M")
    fim = pd.Timestamp(data_final).to_period("M")
    periodo = indices[
        (indices["mes"] >= inicio) & (indices["mes"] <= fim)
    ].copy()

    if len(periodo) < 2:
        raise ValueError("O período precisa conter pelo menos dois fechamentos mensais.")

    primeiro_mes = periodo["mes"].iloc[0]
    ultimo_mes = periodo["mes"].iloc[-1]
    meses = (
        (ultimo_mes.year - primeiro_mes.year) * 12
        + ultimo_mes.month
        - primeiro_mes.month
    )
    if meses < 1:
        raise ValueError("O período selecionado é muito curto para o cálculo.")

    resultados = {}
    for codigo in series_escolhidas:
        coluna = COLUNAS_INDICES[codigo]
        valor_inicial = periodo[coluna].iloc[0]
        valor_final = periodo[coluna].iloc[-1]
        acumulado = valor_final / valor_inicial - 1
        anualizado = (1 + acumulado) ** (12 / meses) - 1
        periodo[f"normalizado_{codigo}"] = periodo[coluna] / valor_inicial * 100
        resultados[codigo] = {
            "acumulado": acumulado,
            "anualizado": anualizado,
        }

    return periodo, resultados, meses


def criar_grafico_periodo(
    periodo: pd.DataFrame,
    series_escolhidas: list[str],
    nomes: dict[str, str],
):
    cores = {
        "cdi": "#174A7E",
        "ipca": "#1B7F5A",
        "prefixado": "#C43D3D",
        "sp500": "#7A4EAB",
        "sp500_ipca": "#D47A22",
        "referencia": "#555555",
    }
    estilos = {"prefixado": "dash", "referencia": "dot"}
    fig = go.Figure()

    for codigo in series_escolhidas:
        fig.add_trace(
            go.Scatter(
                x=periodo["data"],
                y=periodo[f"normalizado_{codigo}"],
                mode="lines",
                name=nomes[codigo],
                line={
                    "color": cores[codigo],
                    "width": 2.5,
                    "dash": estilos.get(codigo, "solid"),
                },
                hovertemplate=(
                    f"<b>{nomes[codigo]}</b><br>"
                    "%{x|%m/%Y}<br>Valor do índice: %{y:.2f}<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        title={
            "text": "Evolução no período - índices iniciados em 100",
            "x": 0,
            "xanchor": "left",
            "font": {"size": 22},
        },
        autosize=False,
        width=1100,
        height=480,
        margin={"l": 25, "r": 20, "t": 75, "b": 80},
        hovermode="x unified",
        dragmode=False,
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.16,
            "xanchor": "center",
            "x": 0.5,
        },
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    fig.update_xaxes(
        title_text="Mês",
        showgrid=False,
        tickformat="%m/%Y",
        automargin=True,
        fixedrange=True,
    )
    fig.update_yaxes(
        title_text="Índice (início = 100)",
        gridcolor="#E2E2E2",
        automargin=True,
        fixedrange=True,
    )
    return fig


def criar_tabela_estatisticas(
    analise: pd.DataFrame,
    series_escolhidas: list[str],
    nomes: dict[str, str],
    acumulado: bool = False,
) -> pd.DataFrame:
    linhas = []
    for codigo in series_escolhidas:
        coluna_retorno = f"{codigo}_acumulado" if acumulado else codigo
        serie = analise[coluna_retorno]
        indice_pior = serie.idxmin()
        indice_melhor = serie.idxmax()
        constante = serie.nunique() == 1
        linhas.append(
            {
                "Referência": nomes[codigo],
                "Pior retorno": f"{serie.min():.2%}",
                "Final da pior janela": (
                    "Todas" if constante else analise.loc[indice_pior, "data_final"].strftime("%m/%Y")
                ),
                "Retorno mediano": f"{serie.median():.2%}",
                "Melhor retorno": f"{serie.max():.2%}",
                "Final da melhor janela": (
                    "Todas" if constante else analise.loc[indice_melhor, "data_final"].strftime("%m/%Y")
                ),
            }
        )
    return pd.DataFrame(linhas)


def exibir_tabela_estatisticas(
    analise: pd.DataFrame,
    series_escolhidas: list[str],
    nomes: dict[str, str],
    prazo_anos: int,
    acumulado: bool = False,
    compacta: bool = False,
) -> None:
    titulo = "Retornos acumulados" if acumulado else "Retornos anualizados"
    st.markdown(f"**{titulo}**")
    st.caption(
        (
            f"Retorno total obtido ao longo de cada janela de {prazo_anos} anos, "
            "sem anualização."
        )
        if acumulado
        else "Taxa equivalente anual de cada janela analisada."
    )

    tabela = criar_tabela_estatisticas(
        analise,
        series_escolhidas,
        nomes,
        acumulado=acumulado,
    )
    if compacta:
        tabela = tabela.rename(
            columns={
                "Pior retorno": "Pior",
                "Final da pior janela": "Fim pior",
                "Retorno mediano": "Mediana",
                "Melhor retorno": "Melhor",
                "Final da melhor janela": "Fim melhor",
            }
        )

    st.dataframe(
        tabela,
        hide_index=True,
        width="stretch" if compacta else 1050,
        height=min(190, 48 + 32 * len(series_escolhidas)),
        row_height=32,
        column_config={
            "Referência": st.column_config.TextColumn(width="medium"),
            "Pior retorno": st.column_config.TextColumn(width="small"),
            "Final da pior janela": st.column_config.TextColumn(width="medium"),
            "Retorno mediano": st.column_config.TextColumn(width="small"),
            "Melhor retorno": st.column_config.TextColumn(width="small"),
            "Final da melhor janela": st.column_config.TextColumn(width="medium"),
            "Pior": st.column_config.TextColumn(width="small"),
            "Fim pior": st.column_config.TextColumn(width="small"),
            "Mediana": st.column_config.TextColumn(width="small"),
            "Melhor": st.column_config.TextColumn(width="small"),
            "Fim melhor": st.column_config.TextColumn(width="small"),
        },
    )


def formatar_percentual(valor: float, casas: int = 1) -> str:
    return f"{valor:.{casas}%}".replace(".", ",")


def montar_dados_apresentacao(
    analise: pd.DataFrame,
    periodo: pd.DataFrame,
    resultados_periodo: dict,
    rotulo_periodo: str,
    serie_principal: str,
    series_comparativas: list[str],
    series_escolhidas: list[str],
    nomes: dict[str, str],
    prazo_anos: int,
    historico_anos: int,
) -> dict:
    passo = max(1, len(analise) // 60)
    amostra = analise.iloc[::passo].copy()
    if amostra.index[-1] != analise.index[-1]:
        amostra = pd.concat([amostra, analise.iloc[[-1]]])
    passo_periodo = max(1, len(periodo) // 60)
    amostra_periodo = periodo.iloc[::passo_periodo].copy()
    if amostra_periodo.index[-1] != periodo.index[-1]:
        amostra_periodo = pd.concat([amostra_periodo, periodo.iloc[[-1]]])

    meses = [
        "janeiro", "fevereiro", "março", "abril", "maio", "junho",
        "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
    ]
    hoje = date.today()

    comparacoes = []
    for comparativa in series_comparativas:
        frequencia = (analise[serie_principal] > analise[comparativa]).mean()
        comparacoes.append({
            "value": formatar_percentual(frequencia),
            "label": f"{nomes[serie_principal]} venceu {nomes[comparativa]}",
        })

    estatisticas = []
    for codigo in series_escolhidas:
        serie = analise[codigo]
        estatisticas.append({
            "name": nomes[codigo],
            "periodReturn": formatar_percentual(
                resultados_periodo[codigo]["acumulado"]
            ),
            "periodAnnual": formatar_percentual(
                resultados_periodo[codigo]["anualizado"]
            ),
            "worst": formatar_percentual(serie.min()),
            "median": formatar_percentual(serie.median()),
            "best": formatar_percentual(serie.max()),
        })

    return {
        "generatedAt": f"{meses[hoje.month - 1].capitalize()} de {hoje.year}",
        "summaryTitle": f"{nomes[serie_principal]} em perspectiva histórica",
        "summarySubtitle": (
            f"Comparação em janelas mensais de {prazo_anos} anos, com "
            f"{historico_anos} anos de histórico exibido."
        ),
        "comparisons": comparacoes,
        "chartTitle": "O retorno anualizado variou ao longo do tempo",
        "chart": {
            "categories": [data.strftime("%m/%Y") for data in amostra["data_final"]],
            "series": [
                {
                    "name": nomes[codigo],
                    "values": [float(valor) for valor in amostra[codigo]],
                    "dashed": codigo in {"prefixado", "referencia"},
                }
                for codigo in series_escolhidas
            ],
        },
        "periodLabel": rotulo_periodo,
        "periodChart": {
            "categories": [
                data.strftime("%m/%Y") for data in amostra_periodo["data"]
            ],
            "series": [
                {
                    "name": nomes[codigo],
                    "values": [
                        float(valor)
                        for valor in amostra_periodo[f"normalizado_{codigo}"]
                    ],
                    "dashed": codigo in {"prefixado", "referencia"},
                }
                for codigo in series_escolhidas
            ],
        },
        "statistics": estatisticas,
        "parameters": {
            "windowYears": prazo_anos,
            "historyYears": historico_anos,
        },
    }


@st.cache_data(show_spinner=False)
def gerar_pdf(dados_json: str) -> bytes:
    pasta_projeto = Path(__file__).resolve().parent
    runtime = pasta_projeto / "presentation_runtime"
    gerador = runtime / "generate_pdf.py"
    python_bundled = (
        Path.home()
        / ".cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"
    )
    python_pdf = Path(sys.executable)
    if importlib.util.find_spec("reportlab") is None and python_bundled.exists():
        python_pdf = python_bundled
    if importlib.util.find_spec("reportlab") is None and not python_bundled.exists():
        raise RuntimeError("A biblioteca de geração de PDF não está instalada.")

    pasta_temporaria_pdf = Path(__file__).resolve().parent / ".radar_runtime" / "pdf"
    pasta_temporaria_pdf.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        prefix="radar_retorno_",
        suffix=".json",
        dir=pasta_temporaria_pdf,
        delete=False,
        encoding="utf-8",
    ) as arquivo_entrada:
        arquivo_entrada.write(dados_json)
        entrada = Path(arquivo_entrada.name)
    saida = entrada.with_suffix(".pdf")

    try:
        # No Streamlit Cloud, o ReportLab já está instalado e o gerador pode
        # rodar no mesmo processo, evitando a abertura de outro Python.
        if importlib.util.find_spec("reportlab") is not None:
            argumentos_originais = sys.argv[:]
            try:
                sys.argv = [str(gerador), str(entrada), str(saida)]
                runpy.run_path(str(gerador), run_name="__main__")
            finally:
                sys.argv = argumentos_originais
            if not saida.exists():
                raise RuntimeError("Não foi possível gerar o PDF.")
            return saida.read_bytes()

        # No Anaconda local, enquanto o ReportLab não estiver instalado,
        # preservamos o runtime auxiliar que já funcionava no projeto.
        processo = subprocess.run(
            [str(python_pdf), str(gerador), str(entrada), str(saida)],
            cwd=runtime,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if processo.returncode != 0 or not saida.exists():
            detalhe = processo.stderr.strip().splitlines()[-1] if processo.stderr else ""
            raise RuntimeError(f"Não foi possível gerar o PDF. {detalhe}")
        return saida.read_bytes()
    finally:
        for arquivo_temporario in (entrada, saida):
            try:
                arquivo_temporario.unlink(missing_ok=True)
            except OSError:
                # O Windows pode manter o arquivo bloqueado por alguns
                # instantes; isso não deve impedir o download já concluído.
                pass


cabecalho_contextual("Análise de índices")
st.title("Análise de índices")
st.caption(
    "Compare diferentes referências em janelas móveis mensais. Cada mês "
    "representa uma janela encerrada naquela data; você pode visualizar a "
    "taxa anualizada ou o retorno total acumulado, ambos em linhas."
)

with st.container(border=True):
    st.markdown("#### Por que olhar janelas móveis?")
    st.write(
        "Uma rentabilidade calculada entre apenas duas datas é uma fotografia: "
        "ela pode parecer muito boa ou ruim por causa do momento escolhido. "
        "As janelas móveis repetem a mesma análise em todos os fechamentos "
        "mensais disponíveis."
    )
    st.write(
        "Assim, conseguimos avaliar se o resultado foi consistente em vários "
        "meses de entrada e saída, quanto ele dependeu do momento da aplicação "
        "e com que frequência uma referência superou as demais."
    )

with st.sidebar:
    st.divider()
    st.header("Parâmetros")
    rotulos_selecao = {
        "cdi": "CDI",
        "ipca": "IPCA + taxa",
        "prefixado": "Taxa prefixada",
        "sp500": "S&P 500 (USD, preço)",
        "sp500_ipca": "S&P 500 + IPCA",
    }
    codigos = list(rotulos_selecao)

    serie_principal = st.selectbox(
        "Série principal",
        codigos,
        index=1,
        format_func=lambda codigo: rotulos_selecao[codigo],
    )
    opcoes_comparacao = [codigo for codigo in codigos if codigo != serie_principal]
    padrao_comparacao = [
        codigo for codigo in ["cdi", "prefixado"] if codigo in opcoes_comparacao
    ]
    series_comparativas = st.multiselect(
        "Comparar com",
        opcoes_comparacao,
        default=padrao_comparacao,
        format_func=lambda codigo: rotulos_selecao[codigo],
    )

    selecoes = [serie_principal] + series_comparativas
    taxa_ipca = 6.8
    taxa_prefixada = 12.0
    if "ipca" in selecoes:
        taxa_ipca = st.number_input(
            "Taxa real do IPCA+ (% a.a.)", 0.0, 20.0, 6.8, 0.1
        )
    if "prefixado" in selecoes:
        taxa_prefixada = st.number_input(
            "Taxa prefixada (% a.a.)", 0.0, 30.0, 12.0, 0.25
        )
    participacao_sp500 = 100.0
    if any(codigo in selecoes for codigo in {"sp500", "sp500_ipca"}):
        participacao_sp500 = st.number_input(
            "Participação no S&P 500 (%)",
            min_value=0.0,
            max_value=300.0,
            value=100.0,
            step=10.0,
            help=(
                "Multiplica cada retorno mensal do S&P 500. Exemplo: com "
                "participação de 120%, um mês de +5% vira +6% e um mês de "
                "-5% vira -6%."
            ),
        )

    usar_referencia = st.checkbox("Adicionar taxa de referência", value=False)
    taxa_referencia = 12.0
    if usar_referencia:
        taxa_referencia = st.number_input(
            "Taxa de referência (% a.a.)", 0.0, 30.0, 12.0, 0.25
        )

    prazo_anos = st.selectbox("Prazo da janela", [1, 3, 5, 10], index=2)
    historico_anos = st.selectbox("Histórico exibido", [5, 10, 15, 20], index=2)
    nomes = nomes_series(
        taxa_ipca,
        taxa_prefixada,
        taxa_referencia,
        participacao_sp500,
    )
    st.caption("CDI e IPCA: BCB. S&P 500: Yahoo Finance (^GSPC).")

series_comparativas_finais = series_comparativas.copy()
if usar_referencia:
    series_comparativas_finais.append("referencia")

if not series_comparativas_finais:
    st.warning("Escolha ao menos uma série em ‘Comparar com’.")
    st.stop()

try:
    with st.spinner("Atualizando séries históricas..."):
        cdi_mensal, ipca, sp500 = preparar_dados(2000)
        analise = analisar_janelas(
            cdi_mensal,
            ipca,
            sp500,
            taxa_ipca,
            taxa_prefixada,
            taxa_referencia,
            participacao_sp500,
            prazo_anos,
            historico_anos,
        )
        indices = construir_indices(
            cdi_mensal,
            ipca,
            sp500,
            taxa_ipca,
            taxa_prefixada,
            taxa_referencia,
            participacao_sp500,
        )

    series_escolhidas = [serie_principal] + series_comparativas_finais

    st.subheader("Frequência histórica")
    colunas = st.columns(len(series_comparativas_finais))
    for coluna, comparativa in zip(colunas, series_comparativas_finais):
        frequencia = (analise[serie_principal] > analise[comparativa]).mean()
        coluna.metric(
            f"{nomes[serie_principal]} venceu {nomes[comparativa]}",
            f"{frequencia:.1%}",
        )

    visualizacao_janelas = st.radio(
        "Visualização das janelas móveis",
        ["Anualizado em linhas", "Acumulado em linhas"],
        horizontal=True,
        key="visualizacao_janelas_indices",
    )
    if visualizacao_janelas == "Acumulado em linhas":
        st.caption(
            "Cada ponto representa o retorno total da janela encerrada naquele mês, "
            "sem transformar o resultado em uma taxa anual."
        )

    st.plotly_chart(
        criar_grafico(
            analise,
            series_escolhidas,
            nomes,
            prazo_anos,
            visualizacao_janelas,
        ),
        width=1100,
        config={
            "responsive": False,
            "displaylogo": False,
            "displayModeBar": False,
            "scrollZoom": False,
        },
    )
    st.caption(
        f"Análise de {len(analise)} janelas mensais sobrepostas, de "
        f"{analise['data_final'].min():%m/%Y} a {analise['data_final'].max():%m/%Y}. "
        "Retornos brutos, sem impostos, taxas ou custos."
    )

    st.subheader("Melhores e piores janelas")
    st.caption(
        "Escolha a leitura desejada. As datas indicam o mês de encerramento "
        "de cada janela."
    )
    visualizacao_tabelas = st.radio(
        "Visualização das tabelas",
        ["Anualizado", "Acumulado", "Ambos"],
        horizontal=True,
        key="visualizacao_tabelas_indices",
    )

    if visualizacao_tabelas == "Ambos":
        coluna_anualizada, coluna_acumulada = st.columns(2, gap="medium")
        with coluna_anualizada:
            exibir_tabela_estatisticas(
                analise,
                series_escolhidas,
                nomes,
                prazo_anos,
                acumulado=False,
                compacta=True,
            )
        with coluna_acumulada:
            exibir_tabela_estatisticas(
                analise,
                series_escolhidas,
                nomes,
                prazo_anos,
                acumulado=True,
                compacta=True,
            )
    else:
        exibir_tabela_estatisticas(
            analise,
            series_escolhidas,
            nomes,
            prazo_anos,
            acumulado=visualizacao_tabelas == "Acumulado",
        )

    st.subheader("Desempenho no período")
    st.caption(
        "Escolha um intervalo para comparar a evolução e o retorno acumulado "
        "das referências selecionadas."
    )
    opcoes_periodo = {
        "Últimos 6 meses": 6,
        "Últimos 12 meses": 12,
        "Últimos 2 anos": 24,
        "Últimos 3 anos": 36,
        "Últimos 4 anos": 48,
        "Últimos 5 anos": 60,
        "Últimos 10 anos": 120,
        "Período personalizado": None,
    }
    periodo_escolhido = st.selectbox(
        "Período de desempenho",
        list(opcoes_periodo),
        index=5,
    )
    ultima_data_disponivel = indices["data"].max()
    primeira_data_disponivel = indices["data"].min()

    if opcoes_periodo[periodo_escolhido] is None:
        coluna_inicio, coluna_fim = st.columns(2)
        data_inicial_periodo = coluna_inicio.date_input(
            "Data inicial",
            value=max(
                primeira_data_disponivel.date(),
                (ultima_data_disponivel - pd.DateOffset(years=5)).date(),
            ),
            min_value=primeira_data_disponivel.date(),
            max_value=ultima_data_disponivel.date(),
        )
        data_final_periodo = coluna_fim.date_input(
            "Data final",
            value=ultima_data_disponivel.date(),
            min_value=primeira_data_disponivel.date(),
            max_value=ultima_data_disponivel.date(),
        )
        rotulo_periodo = (
            f"{pd.Timestamp(data_inicial_periodo):%m/%Y} a "
            f"{pd.Timestamp(data_final_periodo):%m/%Y}"
        )
    else:
        meses_periodo = opcoes_periodo[periodo_escolhido]
        data_final_periodo = ultima_data_disponivel
        data_inicial_periodo = ultima_data_disponivel - pd.DateOffset(
            months=meses_periodo
        )
        rotulo_periodo = periodo_escolhido

    if pd.Timestamp(data_inicial_periodo) >= pd.Timestamp(data_final_periodo):
        st.warning("A data inicial deve ser anterior à data final.")
        st.stop()

    periodo, resultados_periodo, meses_efetivos = calcular_desempenho_periodo(
        indices,
        series_escolhidas,
        data_inicial_periodo,
        data_final_periodo,
    )

    colunas_periodo = st.columns(len(series_escolhidas))
    for coluna, codigo in zip(colunas_periodo, series_escolhidas):
        resultado = resultados_periodo[codigo]
        coluna.metric(
            nomes[codigo],
            f"{resultado['acumulado']:.1%}",
            f"Equivalente anual: {resultado['anualizado']:.2%} a.a.",
            delta_color="off",
        )

    st.plotly_chart(
        criar_grafico_periodo(periodo, series_escolhidas, nomes),
        width=1100,
        config={
            "responsive": False,
            "displaylogo": False,
            "displayModeBar": False,
            "scrollZoom": False,
        },
    )
    st.caption(
        f"Período efetivamente utilizado: {periodo['data'].min():%m/%Y} a "
        f"{periodo['data'].max():%m/%Y} ({meses_efetivos} meses). "
        "Todos os índices começam em 100 para facilitar a comparação."
    )

    st.subheader("Relatório para o cliente")
    st.caption(
        "Gere um PDF com os filtros atuais, os principais resultados, o "
        "gráfico, a tabela e as premissas metodológicas."
    )
    dados_apresentacao = montar_dados_apresentacao(
        analise,
        periodo,
        resultados_periodo,
        rotulo_periodo,
        serie_principal,
        series_comparativas_finais,
        series_escolhidas,
        nomes,
        prazo_anos,
        historico_anos,
    )
    dados_json = json.dumps(dados_apresentacao, ensure_ascii=False, sort_keys=True)

    if st.button("Preparar PDF", type="primary"):
        with st.spinner("Montando o relatório em PDF..."):
            st.session_state["pdf_radar"] = gerar_pdf(dados_json)
            st.session_state["pdf_configuracao"] = dados_json

    if (
        st.session_state.get("pdf_radar")
        and st.session_state.get("pdf_configuracao") == dados_json
    ):
        st.download_button(
            "Baixar relatório (.pdf)",
            data=st.session_state["pdf_radar"],
            file_name="radar-de-retorno.pdf",
            mime="application/pdf",
            on_click="ignore",
        )

    rodape_radar()

except Exception as erro:
    st.error("Não foi possível carregar ou calcular os dados.")
    st.exception(erro)
