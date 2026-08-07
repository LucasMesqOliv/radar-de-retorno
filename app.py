from datetime import date, datetime, timedelta, timezone
import hmac
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

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
) -> dict[str, str]:
    return {
        "cdi": "CDI",
        "ipca": f"IPCA + {taxa_ipca:.2f}%",
        "prefixado": f"Prefixado {taxa_prefixada:.2f}% a.a.",
        "sp500": "S&P 500 (USD, preço)",
        "sp500_ipca": "S&P 500 + IPCA",
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
    base["indice_sp500_ipca"] = (
        base["indice_sp500"] * base["indice_inflacao"] / 100
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


st.title("Radar de Retorno")
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

    usar_referencia = st.checkbox("Adicionar taxa de referência", value=False)
    taxa_referencia = 12.0
    if usar_referencia:
        taxa_referencia = st.number_input(
            "Taxa de referência (% a.a.)", 0.0, 30.0, 12.0, 0.25
        )

    prazo_anos = st.selectbox("Prazo da janela", [1, 3, 5, 10], index=2)
    historico_anos = st.selectbox("Histórico exibido", [5, 10, 15, 20], index=2)
    nomes = nomes_series(taxa_ipca, taxa_prefixada, taxa_referencia)
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

    st.divider()
    st.caption(
        "Criado por Lucas Mesquita | Economista e assessor de investimentos | "
        "Aprovado no CFA Level II"
    )

except Exception as erro:
    st.error("Não foi possível carregar ou calcular os dados.")
    st.exception(erro)
