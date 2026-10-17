"""Montagem de carteira: posição atual, proposta por classe e PDF."""
import copy
from datetime import date, datetime, timedelta, timezone
from html import escape
import json
import re
import unicodedata

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from carteira import (
    CLASSES,
    ORDEM_CLASSES,
    calcular_movimentacoes,
    chave_produto,
    fmt_compacto,
    fmt_pct,
    fmt_reais,
    normalizar_posicoes,
    numero_positivo,
    produtos_novos,
    resumo_por_classe,
    texto_limpo,
    total,
)

COLUNAS = {
    "classe": "Classe",
    "produto": "Produto",
    "valor": "Valor",
    "liquidez": "Liquidez / vencimento",
    "detalhe": "Detalhe",
}
COLUNAS_PONTOS = {"titulo": "Título", "texto": "Texto"}
TABELAS = ("mc_pontos",)
# As posições ficam em listas comuns da sessão (não em widgets), então
# sobrevivem à troca de página sem cuidado extra.
LISTAS = {"atual": "mc_lista_atual", "recomendada": "mc_lista_recomendada"}
PAGINAS = {
    "mc_pag_capa": "Capa",
    "mc_pag_atual": "Carteira atual",
    "mc_pag_movimentacoes": "Movimentações",
    "mc_pag_recomendada": "Carteira recomendada",
    "mc_pag_alocacao": "Gráfico de alocação",
    "mc_pag_pontos": "Pontos de atenção",
}
CAMPOS = {
    "mc_kicker": "Proposta de realocação",
    "mc_titulo": "Revisão da carteira de investimentos",
    "mc_subtitulo": "Carteira atual, movimentações propostas e carteira recomendada",
    "mc_cliente": "",
    "mc_assinatura": "Lucas Mesquita · Assessor de Investimentos",
    "mc_nota_atual": "Valores líquidos, arredondados ao real.",
    "mc_nota_recomendada": "Valores líquidos; valores e percentuais arredondados.",
    "mc_nota_movimentacoes": "",
    "mc_titulo_pontos": "Pontos de atenção",
    "mc_aviso": "",
    **{chave: True for chave in PAGINAS},
}


def _posicao(classe, produto, detalhe, valor, liquidez):
    return {"classe": classe, "produto": produto, "detalhe": detalhe,
            "valor": valor, "liquidez": liquidez}


# Carteira fictícia, só para mostrar como a página funciona.
EXEMPLO = {
    "atual": [
        _posicao("CDI", "CDB DI liquidez diária", "", 400_000, "D+0"),
        _posicao("CDI", "Previdência RF Referenciado DI",
                 "Previdência · CDI", 250_000, "Previdência"),
        _posicao("Inflação", "Debênture incentivada",
                 "IPCA + 6,5% a.a. (isenta de IR)", 50_000, "Secundário / Venc. 05/2032"),
        _posicao("Multimercado", "Fundo multimercado macro",
                 "Gestão ativa · multimercado", 120_000, "D+30"),
        _posicao("RV Brasil", "Fundo de ações Brasil", "Gestão ativa · ações",
                 60_000, "D+32"),
        _posicao("Alternativos", "Op. estruturada S&P 500 com piso",
                 "mín. 40% no período ou 100% do S&P 500", 80_000, "Venc. 03/2031"),
    ],
    "recomendada": [
        _posicao("CDI", "CDB DI liquidez diária", "", 210_000, "D+0"),
        _posicao("CDI", "Previdência RF Referenciado DI",
                 "Previdência · CDI", 250_000, "Previdência"),
        _posicao("CDI", "LCI pós-fixada", "90% do CDI (isenta de IR)",
                 60_000, "Prazo 12 meses"),
        _posicao("Prefixado", "CRI prefixado", "12,5% a.a. (isento de IR)",
                 40_000, "Secundário / prazo 6 anos"),
        _posicao("Inflação", "Debênture incentivada",
                 "IPCA + 6,5% a.a. (isenta de IR)", 50_000, "Secundário / Venc. 05/2032"),
        _posicao("Multimercado", "Fundo multimercado macro",
                 "Gestão ativa · multimercado", 120_000, "D+30"),
        _posicao("RV Brasil", "Fundo de ações Brasil", "Gestão ativa · ações",
                 60_000, "D+32"),
        _posicao("RV Exterior", "ETF de ações globais", "Bolsa global em reais",
                 40_000, "D+2"),
        _posicao("Alternativos", "Op. estruturada S&P 500 com piso",
                 "mín. 40% no período ou 100% do S&P 500", 80_000, "Venc. 03/2031"),
        _posicao("Alternativos", "Op. estruturada IPCA + S&P 500",
                 "IPCA + 100% da alta do S&P 500", 50_000, "Prazo 5 anos"),
    ],
    "pontos": [
        {"titulo": "Juros", "texto": "O ritmo de queda da Selic depende da inflação "
         "e do cenário fiscal. Acompanhamos cada decisão do Copom."},
        {"titulo": "Liquidez", "texto": "A parcela em CDI com resgate diário funciona "
         "como reserva e como caixa para aproveitar oportunidades."},
        {"titulo": "Inflação", "texto": "Uma inflação mais resistente pode limitar os "
         "cortes de juros e favorecer títulos atrelados ao IPCA."},
    ],
}
VAZIO = {"atual": [], "recomendada": [], "pontos": []}


def _hoje() -> date:
    return datetime.now(timezone(timedelta(hours=-3))).date()


def _df_pontos(cartoes) -> pd.DataFrame:
    return pd.DataFrame(
        [{rotulo: texto_limpo(cartao.get(campo)) for campo, rotulo in COLUNAS_PONTOS.items()}
         for cartao in cartoes],
        columns=list(COLUNAS_PONTOS.values()),
    )


def _linhas_do_df(df, colunas) -> list:
    limpo = df.astype(object).where(df.notna(), None)
    return [
        {campo: linha.get(rotulo) for campo, rotulo in colunas.items()}
        for linha in limpo.to_dict("records")
    ]


def _pontos_validos(df) -> list:
    cartoes = []
    for linha in _linhas_do_df(df, COLUNAS_PONTOS):
        titulo, texto = texto_limpo(linha["titulo"]), texto_limpo(linha["texto"])
        if titulo or texto:
            cartoes.append({"titulo": titulo, "texto": texto})
    return cartoes[:6]


# Estado da página ---------------------------------------------------------
# O Streamlit apaga o estado dos widgets que não aparecem na tela. Os valores
# ficam guardados em chaves próprias para sobreviver à troca de página.
def _chave_editor(nome: str) -> str:
    return f"{nome}_editor_{st.session_state.get(nome + '_versao', 0)}"


def _substituir_tabela(nome: str, df: pd.DataFrame):
    st.session_state[nome] = df
    st.session_state[nome + "_ultimo"] = df
    st.session_state[nome + "_versao"] = st.session_state.get(nome + "_versao", 0) + 1


def _carregar_dados(dados: dict):
    for chave, padrao in CAMPOS.items():
        valor = dados.get(chave.removeprefix("mc_"), padrao)
        st.session_state[chave] = bool(valor) if isinstance(padrao, bool) else texto_limpo(valor)
    try:
        data_base = date.fromisoformat(str(dados.get("data_base")))
    except ValueError:
        data_base = _hoje()
    st.session_state["mc_data_base"] = data_base
    st.session_state["mc_memoria"] = {
        chave: st.session_state[chave] for chave in [*CAMPOS, "mc_data_base"]
    }
    ignoradas = 0
    for carteira, nome in LISTAS.items():
        posicoes, fora = normalizar_posicoes(dados.get(carteira) or [])
        st.session_state[nome] = posicoes
        ignoradas += fora
    _substituir_tabela("mc_pontos", _df_pontos(dados.get("pontos") or []))
    st.session_state.pop("mc_pdf", None)
    return ignoradas


def _inicializar():
    if "mc_memoria" not in st.session_state:
        _carregar_dados(EXEMPLO)
    memoria = st.session_state["mc_memoria"]
    for chave in [*CAMPOS, "mc_data_base"]:
        if chave not in st.session_state:
            st.session_state[chave] = memoria.get(chave, CAMPOS.get(chave, _hoje()))
    for carteira, nome in LISTAS.items():
        if nome not in st.session_state:
            # Sessão aberta antes da troca das tabelas por cartões.
            antiga = st.session_state.get(f"mc_{carteira}_ultimo")
            linhas = _linhas_do_df(antiga, COLUNAS) if antiga is not None else []
            st.session_state[nome] = normalizar_posicoes(linhas)[0]
    for nome in TABELAS:
        if _chave_editor(nome) not in st.session_state:
            st.session_state[nome] = st.session_state[nome + "_ultimo"]


def _ao_enviar_arquivo():
    arquivo = st.session_state.get("mc_arquivo")
    if arquivo is None:
        return
    try:
        dados = json.loads(arquivo.getvalue().decode("utf-8"))
        if not isinstance(dados, dict) or not ({"atual", "recomendada"} & set(dados)):
            raise ValueError
    except (UnicodeDecodeError, ValueError):
        st.session_state["mc_mensagem"] = (
            "erro", "Arquivo inválido: abra um .json salvo por esta página.",
        )
        return
    ignoradas = _carregar_dados(dados)
    texto = f"Proposta {arquivo.name} carregada."
    if ignoradas:
        texto += (f" {ignoradas} linha(s) ficaram de fora por falta de classe, "
                  "produto ou valor.")
    st.session_state["mc_mensagem"] = ("ok", texto)


def _copiar_atual():
    st.session_state[LISTAS["recomendada"]] = copy.deepcopy(st.session_state[LISTAS["atual"]])


def _exportar(pontos_df) -> str:
    dados = {"tipo": "radar-de-retorno/proposta-carteira", "versao": 1}
    for chave in CAMPOS:
        dados[chave.removeprefix("mc_")] = st.session_state[chave]
    dados["data_base"] = st.session_state["mc_data_base"].isoformat()
    for carteira, nome in LISTAS.items():
        dados[carteira] = st.session_state[nome]
    dados["pontos"] = _pontos_validos(pontos_df)
    return json.dumps(dados, ensure_ascii=False, indent=2)


def _slug(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")


# Posições em cartões ----------------------------------------------------------
def _ler_valor(texto) -> float | None:
    """Aceita 250000, 250.000, 250.000,50 ou R$ 250.000."""
    limpo = str(texto or "").replace("R$", "").replace(" ", "").strip()
    if "," in limpo:
        limpo = limpo.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", limpo):
        limpo = limpo.replace(".", "")
    return numero_positivo(limpo)


def _valor_texto(valor: float) -> str:
    texto = f"{valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return texto.removesuffix(",00")


def _posicao_do_formulario(classe, produto, valor, liquidez, detalhe):
    numero = _ler_valor(valor)
    if not texto_limpo(produto) or numero is None:
        return None
    return {
        "classe": classe,
        "produto": texto_limpo(produto),
        "detalhe": texto_limpo(detalhe),
        "valor": numero,
        "liquidez": texto_limpo(liquidez),
    }


def _formulario_adicionar(carteira: str):
    with st.form(f"mc_form_{carteira}", clear_on_submit=True):
        st.markdown('<div class="mc-form-titulo">Adicionar posição</div>', unsafe_allow_html=True)
        coluna_1, coluna_2, coluna_3 = st.columns([1.3, 2.7, 1.3])
        classe = coluna_1.selectbox("Classe", ORDEM_CLASSES, key=f"mc_add_classe_{carteira}")
        produto = coluna_2.text_input("Produto", key=f"mc_add_produto_{carteira}",
                                      placeholder="Ex.: CDB DI liquidez diária")
        valor = coluna_3.text_input("Valor (R$)", key=f"mc_add_valor_{carteira}",
                                    placeholder="Ex.: 250.000")
        coluna_4, coluna_5, coluna_6 = st.columns([2, 2.5, 1.5], vertical_alignment="bottom")
        liquidez = coluna_4.text_input("Liquidez / vencimento", key=f"mc_add_liquidez_{carteira}",
                                       placeholder="Ex.: D+0 ou Venc. 05/2032")
        detalhe = coluna_5.text_input("Detalhe (opcional)", key=f"mc_add_detalhe_{carteira}",
                                      placeholder="Ex.: 90% do CDI (isenta de IR)")
        enviado = coluna_6.form_submit_button("Adicionar", type="primary", width="stretch")
    if enviado:
        posicao = _posicao_do_formulario(classe, produto, valor, liquidez, detalhe)
        if posicao is None:
            st.error("Preencha o produto e um valor maior que zero.")
        else:
            st.session_state[LISTAS[carteira]] = [*st.session_state[LISTAS[carteira]], posicao]


@st.dialog("Editar posição")
def _dialogo_editar(carteira: str, indice: int):
    posicoes = st.session_state[LISTAS[carteira]]
    if indice >= len(posicoes):
        st.rerun()
    item = posicoes[indice]
    with st.form("mc_form_editar", border=False):
        classe = st.selectbox("Classe", ORDEM_CLASSES, index=ORDEM_CLASSES.index(item["classe"]))
        produto = st.text_input("Produto", value=item["produto"])
        valor = st.text_input("Valor (R$)", value=_valor_texto(item["valor"]))
        liquidez = st.text_input("Liquidez / vencimento", value=item["liquidez"])
        detalhe = st.text_input("Detalhe (opcional)", value=item["detalhe"])
        salvar = st.form_submit_button("Salvar", type="primary", width="stretch")
    if salvar:
        posicao = _posicao_do_formulario(classe, produto, valor, liquidez, detalhe)
        if posicao is None:
            st.error("Preencha o produto e um valor maior que zero.")
        else:
            nova = list(posicoes)
            nova[indice] = posicao
            st.session_state[LISTAS[carteira]] = nova
            st.rerun()


def _remover(carteira: str, indice: int):
    nova = list(st.session_state[LISTAS[carteira]])
    if indice < len(nova):
        del nova[indice]
    st.session_state[LISTAS[carteira]] = nova


def _lista_posicoes(carteira: str, novos: set):
    posicoes = st.session_state[LISTAS[carteira]]
    if not posicoes:
        st.info("Nenhuma posição ainda. Use o formulário acima para adicionar.")
        return
    total_carteira = total(posicoes)
    for numero_classe, classe in enumerate(ORDEM_CLASSES):
        itens = [(indice, item) for indice, item in enumerate(posicoes) if item["classe"] == classe]
        if not itens:
            continue
        cor, _, cor_nome = CLASSES[classe]
        soma = sum(item["valor"] for _, item in itens)
        st.markdown(
            f'<div class="mc-grupo"><span class="mc-ponto" style="background:{cor}"></span>'
            f'<span class="mc-grupo-nome" style="color:{cor_nome}">{classe}</span>'
            f'<span class="mc-grupo-total">{fmt_reais(soma)} · {fmt_pct(soma / total_carteira)}</span></div>',
            unsafe_allow_html=True,
        )
        for indice, item in itens:
            with st.container(key=f"mc_l{numero_classe}_{carteira}_{indice}"):
                info, valor, liquidez, editar, remover = st.columns(
                    [4.6, 2, 2.6, 0.55, 0.55], vertical_alignment="center", gap="small",
                )
                selo = (' <span class="mc-novo">novo</span>'
                        if chave_produto(item["produto"]) in novos else "")
                detalhe = (f'<div class="mc-det">{escape(item["detalhe"])}</div>'
                           if item["detalhe"] else "")
                info.markdown(
                    f'<div class="mc-prod">{escape(item["produto"])}{selo}</div>{detalhe}',
                    unsafe_allow_html=True,
                )
                valor.markdown(
                    f'<div class="mc-val">{fmt_reais(item["valor"])}</div>'
                    f'<div class="mc-det">{fmt_pct(item["valor"] / total_carteira)}</div>',
                    unsafe_allow_html=True,
                )
                liquidez.markdown(
                    f'<div class="mc-liq">{escape(item["liquidez"]) or "—"}</div>',
                    unsafe_allow_html=True,
                )
                if editar.button(":material/edit:", key=f"mc_editar_{carteira}_{indice}",
                                 help="Editar"):
                    _dialogo_editar(carteira, indice)
                remover.button(":material/delete:", key=f"mc_remover_{carteira}_{indice}",
                               help="Remover", on_click=_remover, args=(carteira, indice))


ESTILO = """
<style>
.mc-secao { display:flex; align-items:center; gap:.65rem; margin:.1rem 0 .15rem; }
.mc-numero { display:inline-grid; place-items:center; width:1.75rem; height:1.75rem;
    border-radius:50%; background:#e8f1fe; color:var(--radar-blue); font-size:.85rem;
    font-weight:800; flex:none; }
.mc-titulo { color:var(--radar-ink); font-size:1.2rem; font-weight:780; letter-spacing:-.01em; }
.mc-texto { color:var(--radar-muted); font-size:.88rem; line-height:1.5; margin:0 0 .4rem 2.4rem; }
.mc-subtitulo { color:var(--radar-ink); font-size:1rem; font-weight:760; margin:.4rem 0 0; }
.mc-kpis { display:grid; grid-template-columns:repeat(auto-fit, minmax(13rem, 1fr));
    gap:.75rem; margin:.3rem 0 .5rem; }
.mc-kpi { padding:.75rem .9rem; border:1px solid #dce5f0; border-top:3px solid var(--radar-blue);
    border-radius:.78rem; background:white; box-shadow:0 5px 18px rgba(24,44,76,.05); }
.mc-kpi span { display:block; color:var(--radar-muted); font-size:.8rem; }
.mc-kpi strong { display:block; margin-top:.2rem; color:var(--radar-ink); font-size:1.5rem;
    font-weight:650; letter-spacing:-.02em; font-variant-numeric:tabular-nums; white-space:nowrap; }
.mc-legenda { display:grid; grid-template-columns:repeat(auto-fill, minmax(10.5rem, 1fr));
    gap:.6rem 1.4rem; margin:.1rem 0 .4rem; }
.mc-item { display:grid; grid-template-columns:.7rem 1fr auto; column-gap:.6rem; align-items:center; }
.mc-ponto { width:.7rem; height:.7rem; border-radius:50%; }
.mc-nome { color:#2b3a55; font-size:.9rem; line-height:1.2; white-space:nowrap; }
.mc-valor { display:block; color:var(--radar-muted); font-size:.74rem; }
.mc-pct { color:var(--radar-ink); font-size:.92rem; font-weight:760; font-variant-numeric:tabular-nums; }
.mc-mudancas { display:grid; grid-template-columns:repeat(auto-fill, minmax(19rem, 1fr));
    column-gap:2.2rem; margin-top:.2rem; }
.mc-mudanca { display:grid; grid-template-columns:.7rem 1fr auto auto; column-gap:.65rem;
    align-items:center; padding:.6rem 0; border-bottom:1px solid #edf1f6; }
.mc-de { color:var(--radar-muted); font-size:.9rem; font-variant-numeric:tabular-nums; white-space:nowrap; }
.mc-de b { color:var(--radar-ink); font-weight:760; }
.mc-delta { padding:.16rem .55rem; border-radius:99px; background:#eef2f7; color:#2b3a55;
    font-size:.76rem; font-weight:700; font-variant-numeric:tabular-nums; white-space:nowrap; }
.mc-form-titulo { color:var(--radar-ink); font-size:.95rem; font-weight:760; }
[data-testid="stFormSubmitButton"] button { border-radius:.58rem; border-color:var(--radar-blue);
    background:linear-gradient(100deg, var(--radar-blue), #0f8ee9); color:#fff; font-weight:700;
    white-space:nowrap; }
[data-testid="stFormSubmitButton"] button:hover { color:#fff; border-color:var(--radar-blue); filter:brightness(1.06); }
.mc-grupo { display:flex; align-items:center; gap:.55rem; margin:.9rem 0 .1rem; }
.mc-grupo-nome { font-size:1rem; font-weight:780; }
.mc-grupo-total { color:var(--radar-muted); font-size:.82rem; font-variant-numeric:tabular-nums; }
[class*="st-key-mc_l"] { background:#fff; border:1px solid #e3e9f2; border-left:4px solid #c8d3e0;
    border-radius:.65rem; padding:.55rem .55rem .55rem .95rem; gap:0;
    box-shadow:0 2px 8px rgba(24,44,76,.04); }
[class*="st-key-mc_l"] button { border:0; background:transparent; min-height:2rem; padding:.2rem .4rem; }
[class*="st-key-mc_l"] button:hover { background:#eef3fa; }
.mc-prod { color:var(--radar-ink); font-weight:700; font-size:.95rem; line-height:1.3; }
.mc-det { color:var(--radar-muted); font-size:.78rem; line-height:1.35; }
.mc-val { color:var(--radar-ink); font-weight:700; font-size:.95rem; font-variant-numeric:tabular-nums; white-space:nowrap; }
.mc-liq { color:#4a5266; font-size:.84rem; }
.mc-novo { display:inline-block; margin-left:.35rem; padding:.05rem .45rem; border-radius:.3rem;
    background:#c8642a; color:#fff; font-size:.68rem; font-weight:800; vertical-align:middle; }
</style>
"""
ESTILO_CLASSES = "<style>" + "".join(
    f'[class*="st-key-mc_l{indice}_"] {{ border-left-color:{CLASSES[classe][0]}; }}'
    for indice, classe in enumerate(ORDEM_CLASSES)
) + "</style>"


def _secao(numero: int, titulo: str, texto: str = ""):
    html = (
        f'<div class="mc-secao"><span class="mc-numero">{numero}</span>'
        f'<span class="mc-titulo">{titulo}</span></div>'
    )
    if texto:
        html += f'<div class="mc-texto">{texto}</div>'
    st.markdown(html, unsafe_allow_html=True)


def _grafico_rosca(soma: dict, total_carteira: float):
    classes = [classe for classe in ORDEM_CLASSES if soma[classe] > 0]
    figura = go.Figure(go.Pie(
        labels=classes,
        values=[soma[classe] for classe in classes],
        customdata=[fmt_reais(soma[classe]) for classe in classes],
        hole=0.66,
        sort=False,
        direction="clockwise",
        marker={"colors": [CLASSES[classe][0] for classe in classes],
                "line": {"color": "#ffffff", "width": 2}},
        textinfo="none",
        hovertemplate="<b>%{label}</b><br>%{customdata} · %{percent:.1%}<extra></extra>",
    ))
    figura.update_layout(
        height=220,
        margin={"l": 0, "r": 0, "t": 6, "b": 6},
        showlegend=False,
        separators=",.",
        paper_bgcolor="rgba(0,0,0,0)",
        annotations=[
            {"text": fmt_compacto(total_carteira), "x": 0.5, "y": 0.55, "showarrow": False,
             "font": {"size": 18, "color": "#14213d", "family": "Georgia, serif"}},
            {"text": "PATRIMÔNIO", "x": 0.5, "y": 0.41, "showarrow": False,
             "font": {"size": 10, "color": "#667085"}},
        ],
    )
    return figura


def _legenda(soma: dict, total_carteira: float) -> str:
    itens = []
    for classe in ORDEM_CLASSES:
        if soma[classe] <= 0:
            continue
        itens.append(
            f'<div class="mc-item"><span class="mc-ponto" style="background:{CLASSES[classe][0]}"></span>'
            f'<span class="mc-nome">{classe}<span class="mc-valor">{fmt_reais(soma[classe])}</span></span>'
            f'<span class="mc-pct">{fmt_pct(soma[classe] / total_carteira)}</span></div>'
        )
    return f'<div class="mc-legenda">{"".join(itens)}</div>'


def _mudancas(soma_atual, total_atual, soma_recomendada, total_recomendado) -> str:
    linhas = []
    for classe in ORDEM_CLASSES:
        if not soma_atual[classe] and not soma_recomendada[classe]:
            continue
        antes = soma_atual[classe] / total_atual
        depois = soma_recomendada[classe] / total_recomendado
        diferenca = (depois - antes) * 100
        if abs(diferenca) < 0.05:
            variacao = "sem mudança"
        else:
            seta = "▲" if diferenca > 0 else "▼"
            variacao = f"{seta} {abs(diferenca):.1f} p.p.".replace(".", ",", 1)
        linhas.append(
            f'<div class="mc-mudanca"><span class="mc-ponto" style="background:{CLASSES[classe][0]}"></span>'
            f'<span class="mc-nome">{classe}</span>'
            f'<span class="mc-de">{fmt_pct(antes)} → <b>{fmt_pct(depois)}</b></span>'
            f'<span class="mc-delta">{variacao}</span></div>'
        )
    return f'<div class="mc-mudancas">{"".join(linhas)}</div>'


def _carteira_visual(rotulo: str, posicoes):
    soma = resumo_por_classe(posicoes)
    total_carteira = total(posicoes)
    st.markdown(f'<div class="mc-subtitulo">{rotulo}</div>', unsafe_allow_html=True)
    st.plotly_chart(_grafico_rosca(soma, total_carteira),
                    config={"displayModeBar": False, "displaylogo": False})
    st.markdown(_legenda(soma, total_carteira), unsafe_allow_html=True)


def _resumo(atual, recomendada):
    total_atual, total_recomendado = total(atual), total(recomendada)
    mov = calcular_movimentacoes(atual, recomendada) if atual and recomendada else None
    rotulo_movimento = (
        "Valor movimentado" if mov and (mov["aporte"] or mov["saida"]) else "Valor realocado"
    )
    indicadores = [
        ("Patrimônio atual", fmt_reais(total_atual) if atual else "—"),
        ("Patrimônio recomendado", fmt_reais(total_recomendado) if recomendada else "—"),
        (rotulo_movimento, fmt_reais(mov["total_movimentado"]) if mov else "—"),
        ("Novas posições", str(mov["novas"] if mov else len(recomendada))),
    ]
    st.markdown(
        '<div class="mc-kpis">' + "".join(
            f'<div class="mc-kpi"><span>{rotulo}</span><strong>{valor}</strong></div>'
            for rotulo, valor in indicadores
        ) + "</div>",
        unsafe_allow_html=True,
    )

    carteiras = [
        (rotulo, posicoes)
        for rotulo, posicoes in (("Carteira atual", atual), ("Carteira recomendada", recomendada))
        if posicoes
    ]
    if not carteiras:
        st.info("Cadastre ao menos uma posição para ver a alocação por classe.")
        return
    for coluna, (rotulo, posicoes) in zip(st.columns(2), carteiras):
        with coluna:
            _carteira_visual(rotulo, posicoes)
    if atual and recomendada:
        st.markdown('<div class="mc-subtitulo">Mudança por classe</div>', unsafe_allow_html=True)
        st.markdown(
            _mudancas(resumo_por_classe(atual), total_atual,
                      resumo_por_classe(recomendada), total_recomendado),
            unsafe_allow_html=True,
        )
    if mov and mov["aporte"]:
        st.info(
            f"A carteira recomendada soma {fmt_reais(mov['aporte'])} a mais que a atual. "
            "No PDF, essa diferença aparece como novo aporte."
        )
    if mov and mov["saida"]:
        st.info(
            f"A carteira recomendada soma {fmt_reais(mov['saida'])} a menos que a atual. "
            "No PDF, essa diferença aparece como resgate sem reaplicação."
        )


def pagina_montagem_carteira():
    _inicializar()
    st.markdown(ESTILO + ESTILO_CLASSES, unsafe_allow_html=True)
    st.markdown(
        """
        <div class="radar-topbar">
            <span class="radar-section-label">Montagem de carteira</span>
            <span class="radar-live">Proposta em PDF</span>
        </div>
        <section class="radar-hero">
            <span class="radar-hero-kicker">MONTAGEM DE CARTEIRA</span>
            <h1>Monte a proposta por classe e gere o PDF.</h1>
            <p>
                Cadastre a carteira atual e a recomendada separando CDI,
                prefixados, inflação, multimercado, renda variável Brasil e
                exterior e alternativos.
                Percentuais, movimentações e posições novas são calculados
                automaticamente.
            </p>
        </section>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Abrir proposta salva ou recomeçar"):
        st.file_uploader(
            "Proposta salva (.json)", type=["json"], key="mc_arquivo",
            on_change=_ao_enviar_arquivo,
        )
        coluna_exemplo, coluna_vazio = st.columns(2)
        coluna_exemplo.button("Carregar exemplo", on_click=_carregar_dados,
                              args=(EXEMPLO,), width="stretch")
        coluna_vazio.button("Começar do zero", on_click=_carregar_dados,
                            args=(VAZIO,), width="stretch")
        st.caption(
            "Os dados ficam apenas nesta sessão do navegador. Para guardar a proposta, "
            "use Salvar proposta no fim da página."
        )
    mensagem = st.session_state.pop("mc_mensagem", None)
    if mensagem:
        (st.success if mensagem[0] == "ok" else st.error)(mensagem[1])

    with st.container(border=True):
        _secao(1, "Capa da proposta", "Título, cliente e assinatura que aparecem na primeira página.")
        coluna_1, coluna_2 = st.columns(2)
        with coluna_1:
            st.text_input("Título", key="mc_titulo")
            st.text_input("Subtítulo", key="mc_subtitulo")
            st.text_input("Chamada acima do título", key="mc_kicker")
        with coluna_2:
            st.text_input("Cliente (opcional)", key="mc_cliente",
                          help="Aparece na capa como Preparado para ...")
            st.text_input("Assinatura", key="mc_assinatura")
            st.date_input("Data base", key="mc_data_base", format="DD/MM/YYYY")

    with st.container(border=True):
        _secao(2, "Carteiras", "Adicione cada posição e escolha a classe. Use o lápis para editar.")
        aba_atual, aba_recomendada = st.tabs(["Carteira atual", "Carteira recomendada"])
        with aba_atual:
            st.caption(
                "Para um cliente novo, deixe a carteira atual vazia: o PDF mostra só a "
                "carteira recomendada."
            )
            _formulario_adicionar("atual")
            _lista_posicoes("atual", set())
        with aba_recomendada:
            if st.session_state[LISTAS["recomendada"]]:
                # Substituir apaga a proposta montada: só com confirmação.
                with st.popover("Copiar a carteira atual para cá"):
                    st.write("Isso substitui todas as posições da carteira recomendada "
                             "pelas da carteira atual.")
                    st.button("Substituir", type="primary", key="mc_copiar_confirmar",
                              on_click=_copiar_atual)
            else:
                st.button("Copiar a carteira atual para cá", key="mc_copiar",
                          on_click=_copiar_atual)
            st.caption(
                "A diferença em relação à carteira atual vira resgate ou aplicação, e produtos "
                "que não estão na atual recebem o selo novo. Use o mesmo nome do produto nas "
                "duas abas."
            )
            _formulario_adicionar("recomendada")
            _lista_posicoes(
                "recomendada",
                produtos_novos(st.session_state[LISTAS["atual"]],
                               st.session_state[LISTAS["recomendada"]])
                if st.session_state[LISTAS["atual"]] else set(),
            )
        atual = st.session_state[LISTAS["atual"]]
        recomendada = st.session_state[LISTAS["recomendada"]]

    with st.container(border=True):
        _secao(3, "Alocação por classe", "Atualiza a cada edição. Passe o mouse no gráfico para ver os valores.")
        _resumo(atual, recomendada)

    with st.container(border=True):
        _secao(4, "Textos e páginas do PDF", "Opcional: observações, comentários e quais páginas entram.")
        with st.expander("Editar textos e páginas"):
            st.text_input("Observação da carteira atual", key="mc_nota_atual",
                          help="Rodapé da página. A data base é acrescentada automaticamente.")
            st.text_input("Observação da carteira recomendada", key="mc_nota_recomendada")
            st.text_area("Comentários da página de movimentações", key="mc_nota_movimentacoes",
                         help="Aparece num quadro de comentários. Cada linha vira um tópico.",
                         placeholder="O CDB segue com R$ 200 mil em liquidez D+0.\n"
                                     "O prefixado trava a taxa caso os juros caiam.")
            st.text_input("Título da página de pontos de atenção", key="mc_titulo_pontos")
            st.caption("Quadros da página de pontos de atenção (até 6).")
            pontos_df = st.data_editor(
                st.session_state["mc_pontos"],
                key=_chave_editor("mc_pontos"),
                num_rows="dynamic",
                hide_index=True,
                width="stretch",
                column_config={
                    "Título": st.column_config.TextColumn("Título", max_chars=60, width="medium"),
                    "Texto": st.column_config.TextColumn("Texto", max_chars=400, width="large"),
                },
            )
            st.text_area("Aviso legal (opcional)", key="mc_aviso", height=110,
                         help="Se preenchido, aparece no fim da página de pontos de atenção.")
            st.markdown("**Páginas incluídas**")
            colunas_paginas = st.columns(3)
            for indice, (chave, rotulo) in enumerate(PAGINAS.items()):
                colunas_paginas[indice % 3].checkbox(rotulo, key=chave)

    data_base = st.session_state["mc_data_base"]
    proposta = {
        chave.removeprefix("mc_"): st.session_state[chave]
        for chave in CAMPOS if not chave.startswith("mc_pag_")
    }
    proposta.update({
        "data_base": data_base,
        "atual": atual,
        "recomendada": recomendada,
        "pontos": _pontos_validos(pontos_df),
        "paginas": {
            chave.removeprefix("mc_pag_"): st.session_state[chave] for chave in PAGINAS
        },
    })
    configuracao = json.dumps(proposta, ensure_ascii=False, sort_keys=True, default=str)
    nome_arquivo = "proposta-carteira-" + (
        _slug(st.session_state["mc_cliente"]) or data_base.isoformat()
    )

    caixa_final = st.container(border=True)
    with caixa_final:
        _secao(5, "Gerar a proposta", "O PDF usa tudo o que está acima. Salve o arquivo .json para continuar outro dia.")
    coluna_pdf, coluna_json = caixa_final.columns(2)
    with coluna_pdf:
        if st.button("Preparar PDF da proposta", type="primary", width="stretch",
                     disabled=not (atual or recomendada)):
            try:
                from carteira_pdf import gerar_pdf_carteira

                with st.spinner("Montando a proposta..."):
                    st.session_state["mc_pdf"] = gerar_pdf_carteira(proposta)
                    st.session_state["mc_pdf_config"] = configuracao
            except ImportError:
                st.error("A biblioteca de geração de PDF não está instalada.")
            except ValueError as erro:
                st.error(str(erro))
        if (
            st.session_state.get("mc_pdf")
            and st.session_state.get("mc_pdf_config") == configuracao
        ):
            st.download_button(
                "Baixar proposta (.pdf)",
                data=st.session_state["mc_pdf"],
                file_name=f"{nome_arquivo}.pdf",
                mime="application/pdf",
                on_click="ignore",
                width="stretch",
            )
        elif st.session_state.get("mc_pdf"):
            st.caption("Os dados mudaram depois do último PDF. Prepare de novo para baixar.")
    with coluna_json:
        st.download_button(
            "Salvar proposta (.json)",
            data=_exportar(pontos_df),
            file_name=f"{nome_arquivo}.json",
            mime="application/json",
            on_click="ignore",
            width="stretch",
        )
        st.caption("Guarde o arquivo no seu computador e abra-o aqui para continuar depois.")

    st.session_state["mc_memoria"] = {
        chave: st.session_state[chave] for chave in [*CAMPOS, "mc_data_base"]
    }
    st.session_state["mc_pontos_ultimo"] = pontos_df
