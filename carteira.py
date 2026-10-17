"""Regras da montagem de carteira: classes, totais e movimentações."""
import math

CLASSES = {
    "CDI e Pós-fixados": ("#3B7A57", "#E8F1EB"),
    "Prefixado": ("#C0612B", "#FAEDE3"),
    "IPCA+": ("#3B5EA6", "#E6ECF6"),
    "Multimercado": ("#97781C", "#F5EFDB"),
    "Alternativos": ("#6A50A7", "#EEEAF6"),
}
ORDEM_CLASSES = list(CLASSES)

MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]

AVISO_PADRAO = (
    "Este material tem caráter informativo e não constitui oferta ou garantia de "
    "rentabilidade. Rentabilidade passada não é garantia de rentabilidade futura. "
    "Títulos de crédito privado estão sujeitos ao risco do emissor e a preços de "
    "mercado se vendidos antes do vencimento; operações estruturadas têm retorno "
    "definido no vencimento. Leia os documentos de cada oferta antes de investir."
)

# Diferenças abaixo de R$ 0,50 são arredondamento, não movimentação.
TOLERANCIA = 0.5


def texto_limpo(valor) -> str:
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return ""
    return " ".join(str(valor).split())


def numero_positivo(valor):
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numero) or numero <= 0:
        return None
    return numero


def normalizar_posicoes(linhas):
    """Devolve as posições válidas e quantas linhas preenchidas ficaram de fora."""
    posicoes, ignoradas = [], 0
    for linha in linhas or []:
        classe = texto_limpo(linha.get("classe"))
        produto = texto_limpo(linha.get("produto"))
        detalhe = texto_limpo(linha.get("detalhe"))
        liquidez = texto_limpo(linha.get("liquidez"))
        valor = numero_positivo(linha.get("valor"))
        if classe not in CLASSES or not produto or valor is None:
            if produto or detalhe or liquidez or valor is not None:
                ignoradas += 1
            continue
        posicoes.append({
            "classe": classe,
            "produto": produto,
            "detalhe": detalhe,
            "valor": valor,
            "liquidez": liquidez,
        })
    return posicoes, ignoradas


def chave_produto(produto: str) -> str:
    return " ".join(produto.casefold().split())


def total(posicoes) -> float:
    return sum(posicao["valor"] for posicao in posicoes)


def resumo_por_classe(posicoes) -> dict:
    soma = {classe: 0.0 for classe in ORDEM_CLASSES}
    for posicao in posicoes:
        soma[posicao["classe"]] += posicao["valor"]
    return soma


def agrupar(posicoes):
    """Agrupa na ordem fixa das classes, mantendo a ordem das linhas."""
    grupos = []
    for classe in ORDEM_CLASSES:
        itens = [posicao for posicao in posicoes if posicao["classe"] == classe]
        if itens:
            grupos.append((classe, itens))
    return grupos


def produtos_novos(atual, recomendada) -> set:
    existentes = {chave_produto(posicao["produto"]) for posicao in atual}
    return {
        chave_produto(posicao["produto"])
        for posicao in recomendada
        if chave_produto(posicao["produto"]) not in existentes
    }


def calcular_movimentacoes(atual, recomendada) -> dict:
    """Compara as carteiras pelo nome do produto.

    Valor menor na recomendada vira resgate; valor maior, ou produto novo,
    vira aplicação. A diferença entre aplicações e resgates é aporte novo
    (ou saída de recursos, quando negativa).
    """
    def somar(posicoes):
        valores, primeira = {}, {}
        for posicao in posicoes:
            chave = chave_produto(posicao["produto"])
            valores[chave] = valores.get(chave, 0.0) + posicao["valor"]
            primeira.setdefault(chave, posicao)
        return valores, primeira

    valores_atual, posicoes_atual = somar(atual)
    valores_recomendada, posicoes_recomendada = somar(recomendada)

    resgates = []
    for chave, valor in valores_atual.items():
        restante = valores_recomendada.get(chave, 0.0)
        if restante < valor - TOLERANCIA:
            resgates.append({
                "produto": posicoes_atual[chave]["produto"],
                "classe": posicoes_atual[chave]["classe"],
                "valor": valor - restante,
                "total": restante < TOLERANCIA,
            })

    aplicacoes = []
    for chave, valor in valores_recomendada.items():
        anterior = valores_atual.get(chave, 0.0)
        if valor > anterior + TOLERANCIA:
            aplicacoes.append({
                "produto": posicoes_recomendada[chave]["produto"],
                "detalhe": posicoes_recomendada[chave]["detalhe"],
                "classe": posicoes_recomendada[chave]["classe"],
                "valor": valor - anterior,
                "novo": chave not in valores_atual,
            })

    total_resgatado = sum(item["valor"] for item in resgates)
    total_aplicado = sum(item["valor"] for item in aplicacoes)
    diferenca = total_aplicado - total_resgatado
    aporte = diferenca if diferenca > TOLERANCIA else 0.0
    saida = -diferenca if diferenca < -TOLERANCIA else 0.0
    return {
        "resgates": resgates,
        "aplicacoes": aplicacoes,
        "total_resgatado": total_resgatado,
        "total_aplicado": total_aplicado,
        "aporte": aporte,
        "saida": saida,
        "total_movimentado": total_resgatado + aporte,
        "novas": sum(1 for item in aplicacoes if item["novo"]),
    }


def fmt_reais(valor: float) -> str:
    return "R$ " + f"{valor:,.0f}".replace(",", ".")


def fmt_pct(fracao: float) -> str:
    return f"{fracao * 100:.1f}%".replace(".", ",")


def fmt_compacto(valor: float) -> str:
    """R$ 250 mil, R$ 1,4 milhão."""
    if valor >= 999_500:
        milhoes = valor / 1_000_000
        texto = f"{milhoes:.1f}".replace(".", ",").removesuffix(",0")
        return f"R$ {texto} {'milhão' if milhoes < 2 else 'milhões'}"
    if valor >= 1_000:
        milhares = valor / 1_000
        if milhares >= 10:
            texto = f"{milhares:.0f}"
        else:
            texto = f"{milhares:.1f}".replace(".", ",").removesuffix(",0")
        return f"R$ {texto} mil"
    return fmt_reais(valor)


def plural(quantidade: int, singular: str, plural_: str) -> str:
    return f"{quantidade} {singular if quantidade == 1 else plural_}"


def mes_extenso(data) -> str:
    return f"{MESES[data.month - 1]} de {data.year}"
