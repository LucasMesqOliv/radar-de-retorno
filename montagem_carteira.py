"""Montagem de carteira: posição atual, proposta por classe e PDF."""
from datetime import date, datetime, timedelta, timezone
import json
import re
import unicodedata

import pandas as pd
import streamlit as st

from carteira import (
    AVISO_PADRAO,
    ORDEM_CLASSES,
    calcular_movimentacoes,
    fmt_pct,
    fmt_reais,
    normalizar_posicoes,
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
TABELAS = ("mc_atual", "mc_recomendada", "mc_pontos")
PAGINAS = {
    "mc_pag_capa": "Capa",
    "mc_pag_atual": "Carteira atual",
    "mc_pag_movimentacoes": "Movimentações",
    "mc_pag_recomendada": "Carteira recomendada",
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
    "mc_aviso": AVISO_PADRAO,
    **{chave: True for chave in PAGINAS},
}


def _posicao(classe, produto, detalhe, valor, liquidez):
    return {"classe": classe, "produto": produto, "detalhe": detalhe,
            "valor": valor, "liquidez": liquidez}


# Carteira fictícia, só para mostrar como a página funciona.
EXEMPLO = {
    "atual": [
        _posicao("CDI e Pós-fixados", "CDB DI liquidez diária", "", 400_000, "D+0"),
        _posicao("CDI e Pós-fixados", "Previdência RF Referenciado DI",
                 "Previdência · CDI", 250_000, "Previdência"),
        _posicao("Multimercado", "Fundo multimercado macro",
                 "Gestão ativa · multimercado", 120_000, "D+30"),
        _posicao("IPCA+", "Debênture incentivada",
                 "IPCA + 6,5% a.a. (isenta de IR)", 50_000, "Secundário / Venc. 05/2032"),
        _posicao("Alternativos", "Op. estruturada S&P 500 com piso",
                 "mín. 40% no período ou 100% do S&P 500", 80_000, "Venc. 03/2031"),
    ],
    "recomendada": [
        _posicao("CDI e Pós-fixados", "CDB DI liquidez diária", "", 250_000, "D+0"),
        _posicao("CDI e Pós-fixados", "Previdência RF Referenciado DI",
                 "Previdência · CDI", 250_000, "Previdência"),
        _posicao("CDI e Pós-fixados", "LCI pós-fixada", "90% do CDI (isenta de IR)",
                 60_000, "Prazo 12 meses"),
        _posicao("Multimercado", "Fundo multimercado macro",
                 "Gestão ativa · multimercado", 120_000, "D+30"),
        _posicao("Prefixado", "CRI prefixado", "12,5% a.a. (isento de IR)",
                 40_000, "Secundário / prazo 6 anos"),
        _posicao("IPCA+", "Debênture incentivada",
                 "IPCA + 6,5% a.a. (isenta de IR)", 50_000, "Secundário / Venc. 05/2032"),
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


def _df_posicoes(linhas) -> pd.DataFrame:
    df = pd.DataFrame(
        [{rotulo: linha.get(campo) for campo, rotulo in COLUNAS.items()} for linha in linhas],
        columns=list(COLUNAS.values()),
    )
    for rotulo in COLUNAS.values():
        if rotulo == "Valor":
            df[rotulo] = pd.to_numeric(df[rotulo], errors="coerce").astype(float)
        else:
            df[rotulo] = df[rotulo].map(texto_limpo).astype(object)
    return df


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
    _substituir_tabela("mc_atual", _df_posicoes(dados.get("atual") or []))
    _substituir_tabela("mc_recomendada", _df_posicoes(dados.get("recomendada") or []))
    _substituir_tabela("mc_pontos", _df_pontos(dados.get("pontos") or []))
    st.session_state.pop("mc_pdf", None)


def _inicializar():
    if "mc_memoria" not in st.session_state:
        _carregar_dados(EXEMPLO)
    memoria = st.session_state["mc_memoria"]
    for chave in [*CAMPOS, "mc_data_base"]:
        if chave not in st.session_state:
            st.session_state[chave] = memoria.get(chave, CAMPOS.get(chave, _hoje()))
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
    _carregar_dados(dados)
    st.session_state["mc_mensagem"] = ("ok", f"Proposta {arquivo.name} carregada.")


def _copiar_atual():
    atual = st.session_state["mc_atual_ultimo"].copy()
    _substituir_tabela("mc_recomendada", atual)


def _exportar(atual_df, recomendada_df, pontos_df) -> str:
    dados = {"tipo": "radar-de-retorno/proposta-carteira", "versao": 1}
    for chave in CAMPOS:
        dados[chave.removeprefix("mc_")] = st.session_state[chave]
    dados["data_base"] = st.session_state["mc_data_base"].isoformat()
    dados["atual"] = _linhas_do_df(atual_df, COLUNAS)
    dados["recomendada"] = _linhas_do_df(recomendada_df, COLUNAS)
    dados["pontos"] = _pontos_validos(pontos_df)
    return json.dumps(dados, ensure_ascii=False, indent=2)


def _slug(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")


# Componentes ----------------------------------------------------------------
def _editor_posicoes(nome: str) -> pd.DataFrame:
    return st.data_editor(
        st.session_state[nome],
        key=_chave_editor(nome),
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        column_config={
            "Classe": st.column_config.SelectboxColumn(
                "Classe", options=ORDEM_CLASSES, required=True,
                default=ORDEM_CLASSES[0], width=150,
            ),
            "Produto": st.column_config.TextColumn("Produto", required=True, width=280),
            "Valor": st.column_config.NumberColumn(
                "Valor (R$)", min_value=0.0, step=1.0, format="localized",
                required=True, width=115,
            ),
            "Liquidez / vencimento": st.column_config.TextColumn(
                "Liquidez / vencimento", width=190,
            ),
            "Detalhe": st.column_config.TextColumn(
                "Detalhe", width=330,
                help="Linha menor abaixo do produto. Ex.: Previdência · CDI",
            ),
        },
    )


def _resumo(atual, recomendada):
    total_atual, total_recomendado = total(atual), total(recomendada)
    mov = calcular_movimentacoes(atual, recomendada) if atual and recomendada else None
    colunas = st.columns(4)
    colunas[0].metric("Patrimônio atual", fmt_reais(total_atual) if atual else "—")
    colunas[1].metric("Patrimônio recomendado", fmt_reais(total_recomendado) if recomendada else "—")
    rotulo_movimento = (
        "Valor movimentado" if mov and (mov["aporte"] or mov["saida"]) else "Valor realocado"
    )
    colunas[2].metric(rotulo_movimento, fmt_reais(mov["total_movimentado"]) if mov else "—")
    colunas[3].metric("Novas posições", mov["novas"] if mov else len(recomendada))

    soma_atual, soma_recomendada = resumo_por_classe(atual), resumo_por_classe(recomendada)
    linhas = []
    for classe in ORDEM_CLASSES:
        if not soma_atual[classe] and not soma_recomendada[classe]:
            continue
        linhas.append({
            "Classe": classe,
            "Atual": fmt_reais(soma_atual[classe]),
            "% atual": fmt_pct(soma_atual[classe] / total_atual) if total_atual else "—",
            "Recomendada": fmt_reais(soma_recomendada[classe]),
            "% recomendada": (
                fmt_pct(soma_recomendada[classe] / total_recomendado)
                if total_recomendado else "—"
            ),
        })
    if linhas:
        st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
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
                Cadastre a carteira atual e a recomendada separando CDI e
                pós-fixados, prefixados, IPCA+, multimercado e alternativos.
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

    st.markdown("#### Capa")
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

    st.markdown("#### Carteira atual")
    st.caption(
        "Uma linha por posição. Para um cliente novo, deixe esta tabela vazia: "
        "o PDF mostra só a carteira recomendada."
    )
    atual_df = _editor_posicoes("mc_atual")

    st.markdown("#### Carteira recomendada")
    st.button("Copiar a carteira atual para cá", on_click=_copiar_atual)
    st.caption(
        "Edite os valores e inclua os produtos novos. A diferença em relação à carteira "
        "atual vira resgate ou aplicação, e produtos que não estão na atual recebem o "
        "selo novo no PDF. Use o mesmo nome do produto nas duas tabelas."
    )
    recomendada_df = _editor_posicoes("mc_recomendada")

    atual, ignoradas_atual = normalizar_posicoes(_linhas_do_df(atual_df, COLUNAS))
    recomendada, ignoradas_recomendada = normalizar_posicoes(
        _linhas_do_df(recomendada_df, COLUNAS)
    )
    if ignoradas_atual or ignoradas_recomendada:
        st.warning(
            f"{ignoradas_atual + ignoradas_recomendada} linha(s) ficaram fora do resumo e "
            "do PDF: toda posição precisa de classe, produto e valor maior que zero."
        )

    st.markdown("#### Resumo por classe")
    _resumo(atual, recomendada)

    with st.expander("Textos e páginas do PDF"):
        st.text_input("Observação da carteira atual", key="mc_nota_atual",
                      help="Rodapé da página. A data base é acrescentada automaticamente.")
        st.text_input("Observação da carteira recomendada", key="mc_nota_recomendada")
        st.text_area("Comentário das movimentações (opcional)", key="mc_nota_movimentacoes",
                     help="Aparece abaixo da mudança por classe. Ex.: o CDB segue com "
                          "R$ 200 mil em liquidez D+0.")
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
        st.text_area("Aviso legal", key="mc_aviso", height=110)
        st.markdown("**Páginas incluídas**")
        colunas_paginas = st.columns(len(PAGINAS))
        for coluna, (chave, rotulo) in zip(colunas_paginas, PAGINAS.items()):
            coluna.checkbox(rotulo, key=chave)

    st.markdown("#### Gerar a proposta")
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

    coluna_pdf, coluna_json = st.columns(2)
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
            data=_exportar(atual_df, recomendada_df, pontos_df),
            file_name=f"{nome_arquivo}.json",
            mime="application/json",
            on_click="ignore",
            width="stretch",
        )
        st.caption("Guarde o arquivo no seu computador e abra-o aqui para continuar depois.")

    st.session_state["mc_memoria"] = {
        chave: st.session_state[chave] for chave in [*CAMPOS, "mc_data_base"]
    }
    st.session_state["mc_atual_ultimo"] = atual_df
    st.session_state["mc_recomendada_ultimo"] = recomendada_df
    st.session_state["mc_pontos_ultimo"] = pontos_df
