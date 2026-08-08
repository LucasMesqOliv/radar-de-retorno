from datetime import date, datetime, timedelta, timezone
import hmac
import importlib.util
import io
import json
from pathlib import Path
import re
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


def baixar_arquivo_cvm(url: str, nome: str) -> Path:
    pasta_cache = Path(tempfile.gettempdir()) / "radar_retorno_cvm"
    pasta_cache.mkdir(parents=True, exist_ok=True)
    arquivo = pasta_cache / nome
    atualizado = (
        arquivo.exists()
        and arquivo.stat().st_size > 1_000
        and time.time() - arquivo.stat().st_mtime < 86_400
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

    if not zipfile.is_zipfile(caminho_temporario):
        caminho_temporario.unlink(missing_ok=True)
        raise RuntimeError("A CVM retornou um arquivo inválido.")
    caminho_temporario.replace(arquivo)
    return arquivo


@st.cache_data(ttl=86_400, show_spinner=False)
def carregar_cadastro_fundos_cvm() -> pd.DataFrame:
    arquivo = baixar_arquivo_cvm(
        URL_CADASTRO_FUNDOS_CVM,
        "registro_fundo_classe.zip",
    )
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
                    "Denominacao_Social",
                    "Situacao",
                    "Tipo_Classe",
                    "Classificacao",
                    "Classificacao_Anbima",
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
            "Denominacao_Social": "nome",
            "Situacao": "situacao",
            "Tipo_Classe": "tipo",
            "Classificacao": "classificacao",
            "Classificacao_Anbima": "classificacao_anbima",
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
            "Denominacao_Social": "nome",
            "Situacao": "situacao",
            "Tipo_Fundo": "tipo",
            "Patrimonio_Liquido": "patrimonio_cadastral",
            "Data_Patrimonio_Liquido": "data_patrimonio_cadastral",
            "Administrador": "administrador",
            "Gestor": "gestor",
        }
    )
    for coluna in ["classificacao", "classificacao_anbima", "publico_alvo"]:
        fundos_adicionais[coluna] = ""

    colunas = [
        "cnpj",
        "nome",
        "situacao",
        "tipo",
        "classificacao",
        "classificacao_anbima",
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
    cadastro["cnpj"] = cadastro["cnpj"].map(normalizar_cnpj)
    cadastro = cadastro[
        cadastro["cnpj"].str.fullmatch(r"\d{14}")
        & cadastro["cnpj"].ne("00000000000000")
    ]
    cadastro["nome"] = cadastro["nome"].fillna("Fundo sem denominação")
    cadastro["patrimonio_cadastral"] = pd.to_numeric(
        cadastro["patrimonio_cadastral"], errors="coerce"
    )
    cadastro["em_funcionamento"] = cadastro["situacao"].fillna("").str.contains(
        "Funcionamento Normal", case=False
    )
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


def buscar_fundos_cvm(
    cadastro: pd.DataFrame,
    termo: str,
    limite: int = 30,
) -> pd.DataFrame:
    termo_normalizado = normalizar_busca(termo).strip()
    digitos = re.sub(r"\D", "", termo)
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
    nome_zip = f"inf_diario_fi_{mes}.zip"
    arquivo = baixar_arquivo_cvm(
        URL_INFORME_DIARIO_CVM.format(mes=mes),
        nome_zip,
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
        with pacote.open(nome_csv) as dados_arquivo:
            dados = pd.read_csv(
                dados_arquivo,
                sep=";",
                encoding="latin1",
                dtype={coluna_cnpj: str},
                usecols=colunas_existentes,
            )

    dados["cnpj"] = dados[coluna_cnpj].map(normalizar_cnpj)
    dados = dados[dados["cnpj"].isin(set(cnpjs))].copy()
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
    return dados[
        [
            "cnpj",
            "data",
            "cota",
            "patrimonio",
            "captacao_dia",
            "resgate_dia",
            "cotistas",
        ]
    ].sort_values(["cnpj", "data"])


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
    cadastro: pd.DataFrame,
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


def pagina_fundos():
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
    """Baixa uma série do SGS/BCB em blocos anuais."""
    partes = []
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"

    for ano in range(ano_inicial, date.today().year + 1):
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
                    raise
                time.sleep(2 ** tentativa)

        parte = pd.DataFrame(resposta.json())
        if not parte.empty:
            partes.append(parte)

    if not partes:
        raise RuntimeError("O Banco Central não retornou dados para a série.")

    dados = pd.concat(partes, ignore_index=True)
    dados["data"] = pd.to_datetime(dados["data"], dayfirst=True)
    dados["valor"] = pd.to_numeric(
        dados["valor"].astype(str).str.replace(",", "."),
        errors="coerce",
    )
    return dados.dropna(subset=["valor"]).sort_values("data")


@st.cache_data(ttl=86_400, show_spinner=False)
def baixar_sp500(ano_inicial: int) -> pd.DataFrame:
    """Baixa o índice de preços S&P 500 (^GSPC), em USD e sem dividendos."""
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
        timeout=30,
    )
    resposta.raise_for_status()
    resultado = resposta.json()["chart"]["result"][0]
    fechamentos = resultado["indicators"]["quote"][0]["close"]
    dados = pd.DataFrame(
        {
            "data": pd.to_datetime(resultado["timestamp"], unit="s", utc=True)
            .tz_convert(None),
            "indice_sp500": fechamentos,
        }
    ).dropna()
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
                    "%{x|%m/%Y}<br>Retorno anualizado: %{y:.2f}%<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        title={
            "text": f"Retornos anualizados em janelas móveis de {prazo_anos} anos",
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
        title_text="Retorno anualizado",
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
) -> pd.DataFrame:
    linhas = []
    for codigo in series_escolhidas:
        serie = analise[codigo]
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

    with tempfile.TemporaryDirectory(prefix="radar_retorno_") as temporaria:
        entrada = Path(temporaria) / "dados.json"
        saida = Path(temporaria) / "radar-de-retorno.pdf"
        entrada.write_text(dados_json, encoding="utf-8")
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


cabecalho_contextual("Análise de índices")
st.title("Análise de índices")
st.caption(
    "Compare diferentes referências em janelas móveis mensais. Cada ponto "
    "representa o retorno anualizado na janela encerrada naquele mês."
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

    st.plotly_chart(
        criar_grafico(analise, series_escolhidas, nomes, prazo_anos),
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
        "Os retornos são anualizados. As datas indicam o mês de encerramento "
        "de cada janela."
    )
    st.dataframe(
        criar_tabela_estatisticas(analise, series_escolhidas, nomes),
        hide_index=True,
        width=1050,
        height=min(190, 48 + 32 * len(series_escolhidas)),
        row_height=32,
        column_config={
            "Referência": st.column_config.TextColumn(width="medium"),
            "Pior retorno": st.column_config.TextColumn(width="small"),
            "Final da pior janela": st.column_config.TextColumn(width="medium"),
            "Retorno mediano": st.column_config.TextColumn(width="small"),
            "Melhor retorno": st.column_config.TextColumn(width="small"),
            "Final da melhor janela": st.column_config.TextColumn(width="medium"),
        },
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
