"""Desenha a proposta de carteira em PDF, em páginas 16:9 agrupadas por classe."""
from datetime import date
import io

from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from carteira import (
    CLASSES,
    ORDEM_CLASSES,
    agrupar,
    calcular_movimentacoes,
    chave_produto,
    fmt_compacto,
    fmt_pct,
    fmt_reais,
    mes_extenso,
    plural,
    produtos_novos,
    resumo_por_classe,
    total,
)

W, H = 960, 540
M = 40
NAVY = HexColor("#1F2D5C")
FUNDO = HexColor("#F6F7FB")
LARANJA = HexColor("#C8642A")
AZUL = HexColor("#3B5EA6")
CINZA = HexColor("#6B7385")
GRAFITE = HexColor("#4A5266")
LINHA = HexColor("#D9DEE8")
FUNDO_CABECALHO = HexColor("#EEF0F6")
CLARO_CAPA = HexColor("#C5CCE3")
SERIF = "Times-Bold"
SANS = "Helvetica"
SANS_B = "Helvetica-Bold"

# Colunas das tabelas de carteira.
X_PRODUTO = 200
X_VALOR = 650
X_PCT = 722
X_LIQUIDEZ = 742
X_FIM = W - M
LARGURA_PRODUTO = 560 - (X_PRODUTO + 10)
LARGURA_LIQUIDEZ = X_FIM - X_LIQUIDEZ - 10
LIMITE_INFERIOR = 46
# A linha TOTAL pode descer mais que as posições, até encostar no rodapé.
LIMITE_TOTAL = 54
ALTURA_MIN_GRUPO = 32
ESPACO_GRUPOS = 4
CORES_CARTOES = [AZUL, HexColor("#3B7A57"), LARANJA, HexColor("#6A50A7"), HexColor("#97781C"), NAVY]


def _cortar(texto, fonte, tamanho, largura):
    if stringWidth(texto, fonte, tamanho) <= largura:
        return texto
    while texto and stringWidth(texto + "…", fonte, tamanho) > largura:
        texto = texto[:-1]
    return texto.rstrip() + "…"


def _linhas(texto, fonte, tamanho, largura, maximo=2):
    if not texto:
        return []
    linhas = simpleSplit(texto, fonte, tamanho, largura)
    if len(linhas) > maximo:
        restante = " ".join(linhas[maximo - 1:])
        linhas = linhas[:maximo - 1] + [_cortar(restante, fonte, tamanho, largura)]
    return linhas


class _Proposta:
    def __init__(self, proposta: dict):
        self.p = proposta
        self.buffer = io.BytesIO()
        self.c = canvas.Canvas(self.buffer, pagesize=(W, H))
        self.c.setTitle(proposta.get("titulo") or "Proposta de carteira")
        self.c.setAuthor(proposta.get("assinatura") or "Radar de Retorno")
        self.assinatura = proposta.get("assinatura", "")
        self.paginas = 0

    # Primitivas -----------------------------------------------------------
    def texto(self, valor, x, y, fonte=SANS, tamanho=9.5, cor=NAVY,
              alinhar="esquerda", espacamento=0.0):
        c = self.c
        c.setFillColor(cor)
        if espacamento:
            # O espaçamento entre letras fica no estado gráfico do PDF;
            # salvar e restaurar evita que ele vaze para os próximos textos.
            c.saveState()
            objeto = c.beginText(x, y)
            objeto.setFont(fonte, tamanho)
            objeto.setCharSpace(espacamento)
            objeto.textOut(valor)
            c.drawText(objeto)
            c.restoreState()
            return
        c.setFont(fonte, tamanho)
        if alinhar == "direita":
            c.drawRightString(x, y, valor)
        else:
            c.drawString(x, y, valor)

    def fundo(self, cor=FUNDO):
        self.c.setFillColor(cor)
        self.c.rect(0, 0, W, H, fill=1, stroke=0)

    def cabecalho(self, kicker, titulo, subtitulo=""):
        self.fundo()
        self.texto(kicker.upper(), M, H - 34, SANS_B, 8.5, LARANJA, espacamento=0.6)
        self.texto(_cortar(titulo, SERIF, 27, W - 2 * M), M, H - 64, SERIF, 27, NAVY)
        if subtitulo:
            self.texto(subtitulo, M, H - 82, SANS, 10, AZUL)
        self.c.setStrokeColor(NAVY)
        self.c.setLineWidth(2.4)
        self.c.line(M, H - 92, W - M, H - 92)

    def rodape(self, nota=""):
        linhas = simpleSplit(nota, SANS, 6.8, W - 2 * M - 200) if nota else []
        y = 16 + 9 * (len(linhas) - 1)
        for linha in linhas:
            self.texto(linha, M, y, SANS, 6.8, CINZA)
            y -= 9
        if self.assinatura:
            self.texto(self.assinatura, W - M, 16, SANS, 6.8, CINZA, "direita")
        self.c.showPage()
        self.paginas += 1

    def seta(self, x_fim, y_base):
        c = self.c
        y = y_base + 3.2
        c.setStrokeColor(NAVY)
        c.setLineWidth(0.9)
        c.line(x_fim - 11, y, x_fim, y)
        c.line(x_fim - 3.2, y + 2.6, x_fim, y)
        c.line(x_fim - 3.2, y - 2.6, x_fim, y)

    def selo_novo(self, x, y_base):
        largura = stringWidth("novo", SANS_B, 7) + 8
        self.c.setFillColor(LARANJA)
        self.c.roundRect(x, y_base - 2.5, largura, 11, 2, fill=1, stroke=0)
        self.texto("novo", x + 4, y_base, SANS_B, 7, white)

    # Capa -----------------------------------------------------------------
    def capa(self):
        p = self.p
        self.fundo(NAVY)
        faixas = ["CDI", "Prefixado", "Inflação", "Alternativos"]
        altura = H / len(faixas)
        for indice, classe in enumerate(faixas):
            self.c.setFillColor(HexColor(CLASSES[classe][0]))
            self.c.rect(W - 14, H - (indice + 1) * altura, 14, altura, fill=1, stroke=0)
        x, y = 50, 338
        if p.get("kicker"):
            self.texto(p["kicker"].upper(), x, y, SANS_B, 9, LARANJA, espacamento=0.7)
        y -= 50
        for linha in _linhas(p.get("titulo", ""), SERIF, 40, 600, 3):
            self.texto(linha, x, y, SERIF, 40, white)
            y -= 46
        y += 16
        for linha in _linhas(p.get("subtitulo", ""), SANS, 13, 600, 2):
            self.texto(linha, x, y, SANS, 13, CLARO_CAPA)
            y -= 17
        if p.get("cliente"):
            self.texto(f"Preparado para {p['cliente']}", x, 92, SANS_B, 10.5, white)
        if self.assinatura:
            self.texto(self.assinatura, x, 70, SANS, 9.5, CLARO_CAPA)
        self.texto(mes_extenso(p["data_base"]), x, 52, SANS, 9.5, CLARO_CAPA)
        self.c.showPage()
        self.paginas += 1

    # Tabelas de carteira -------------------------------------------------
    def cabecalho_tabela(self):
        y = H - 112
        colunas = [
            ("Classe / Estratégia", M + 16, "esquerda"),
            ("Produto", X_PRODUTO + 10, "esquerda"),
            ("Valor", X_VALOR, "direita"),
            ("%", X_PCT, "direita"),
            ("Liquidez / Vencimento", X_LIQUIDEZ + 10, "esquerda"),
        ]
        for rotulo, x, alinhar in colunas:
            self.texto(rotulo, x, y, SANS_B, 8, NAVY, alinhar)
        self.c.setStrokeColor(NAVY)
        self.c.setLineWidth(1.2)
        self.c.line(M, y - 7, X_FIM, y - 7)
        return y - 8

    def medir_linha(self, posicao, novo):
        largura_produto = LARGURA_PRODUTO - (34 if novo else 0)
        produto = _linhas(posicao["produto"], SANS_B, 9.5, largura_produto)
        detalhe = _linhas(posicao["detalhe"], SANS, 7.8, LARGURA_PRODUTO)
        liquidez = _linhas(posicao["liquidez"], SANS, 8, LARGURA_LIQUIDEZ)
        bloco = 9.5 + 11.5 * (len(produto) - 1) + 10.5 * len(detalhe)
        bloco_liquidez = 8 + 10 * (len(liquidez) - 1) if liquidez else 0
        return {
            "posicao": posicao,
            "novo": novo,
            "produto": produto,
            "detalhe": detalhe,
            "liquidez": liquidez,
            "bloco": bloco,
            "bloco_liquidez": bloco_liquidez,
            "altura": max(22, bloco + 11, bloco_liquidez + 11),
        }

    def desenhar_linha(self, linha, topo, total_carteira):
        centro = topo - linha["altura"] / 2
        y = centro + linha["bloco"] / 2 - 7
        for indice, texto in enumerate(linha["produto"]):
            self.texto(texto, X_PRODUTO + 10, y, SANS_B, 9.5, NAVY)
            if linha["novo"] and indice == len(linha["produto"]) - 1:
                self.selo_novo(X_PRODUTO + 15 + stringWidth(texto, SANS_B, 9.5), y)
            y -= 11.5
        y += 1
        for texto in linha["detalhe"]:
            self.texto(texto, X_PRODUTO + 10, y, SANS, 7.8, CINZA)
            y -= 10.5
        valor = linha["posicao"]["valor"]
        base = centro - 3.3
        self.texto(fmt_reais(valor), X_VALOR, base, SANS, 9.5, NAVY, "direita")
        self.texto(fmt_pct(valor / total_carteira), X_PCT, base, SANS_B, 9.5, NAVY, "direita")
        y = centro + linha["bloco_liquidez"] / 2 - 5.8
        for texto in linha["liquidez"]:
            self.texto(texto, X_LIQUIDEZ + 10, y, SANS, 8, GRAFITE)
            y -= 10

    def desenhar_grupo(self, topo, classe, linhas, soma, total_carteira):
        cor, fundo, cor_nome = (HexColor(valor) for valor in CLASSES[classe])
        altura = sum(linha["altura"] for linha in linhas)
        if altura < ALTURA_MIN_GRUPO:
            linhas[-1]["altura"] += ALTURA_MIN_GRUPO - altura
            altura = ALTURA_MIN_GRUPO
        c = self.c
        c.setFillColor(fundo)
        c.rect(M, topo - altura, X_FIM - M, altura, fill=1, stroke=0)
        c.setFillColor(cor)
        c.rect(M, topo - altura, 4, altura, fill=1, stroke=0)
        centro = topo - altura / 2
        self.texto(classe, M + 16, centro + 2, SERIF, 14, cor_nome)
        self.texto(f"{fmt_reais(soma)} · {fmt_pct(soma / total_carteira)}",
                   M + 16, centro - 11, SANS, 8, CINZA)
        y = topo
        for indice, linha in enumerate(linhas):
            if indice:
                c.setStrokeColor(white)
                c.setLineWidth(1.4)
                c.line(X_PRODUTO, y, X_FIM, y)
            self.desenhar_linha(linha, y, total_carteira)
            y -= linha["altura"]
        return topo - altura

    def linha_total(self, topo, total_carteira):
        c = self.c
        c.setStrokeColor(NAVY)
        c.setLineWidth(1.4)
        c.line(M, topo, X_FIM, topo)
        base = topo - 18
        self.texto("TOTAL", M + 16, base, SERIF, 12.5, NAVY)
        self.texto(fmt_reais(total_carteira), X_VALOR, base, SERIF, 12.5, NAVY, "direita")
        self.texto("100%", X_PCT, base, SANS_B, 11, NAVY, "direita")
        self.texto("—", X_LIQUIDEZ + 10, base, SANS_B, 11, NAVY)
        c.setStrokeColor(LINHA)
        c.setLineWidth(0.8)
        c.line(M, topo - 28, X_FIM, topo - 28)

    def pagina_carteira(self, kicker, titulo, posicoes, nota, novos):
        total_carteira = total(posicoes)
        grupos = agrupar(posicoes)
        subtitulo = "  •  ".join([
            f"Patrimônio líquido {fmt_reais(total_carteira)}",
            plural(len(grupos), "classe de estratégia", "classes de estratégia"),
            plural(len(posicoes), "posição", "posições"),
        ])

        def abrir(continuacao):
            self.cabecalho(kicker, titulo + (" (continuação)" if continuacao else ""), subtitulo)
            return self.cabecalho_tabela()

        y = abrir(False)
        for classe, itens in grupos:
            soma = total(itens)
            bloco = []
            for posicao in itens:
                linha = self.medir_linha(posicao, chave_produto(posicao["produto"]) in novos)
                ocupado = sum(item["altura"] for item in bloco)
                if y - max(ocupado + linha["altura"], ALTURA_MIN_GRUPO) < LIMITE_INFERIOR:
                    if bloco:
                        self.desenhar_grupo(y, classe, bloco, soma, total_carteira)
                    self.rodape(nota)
                    y = abrir(True)
                    bloco = []
                bloco.append(linha)
            y = self.desenhar_grupo(y, classe, bloco, soma, total_carteira) - ESPACO_GRUPOS
        if y + 1 < LIMITE_TOTAL:
            self.rodape(nota)
            y = abrir(True)
        self.linha_total(y + 1, total_carteira)
        self.rodape(nota)

    # Movimentações -------------------------------------------------------
    def pagina_movimentacoes(self, atual, recomendada, mov, nota):
        total_atual, total_recomendado = total(atual), total(recomendada)
        sem_fluxo = not mov["aporte"] and not mov["saida"]
        if mov["aporte"]:
            fluxo = f"novo aporte de {fmt_compacto(mov['aporte'])}"
        elif mov["saida"]:
            fluxo = f"resgate líquido de {fmt_compacto(mov['saida'])}"
        else:
            fluxo = "sem novo aporte"
        novas = (
            plural(mov["novas"], "nova posição", "novas posições")
            if mov["novas"] else "nenhuma posição nova"
        )
        verbo = "realocados" if sem_fluxo else "movimentados"
        subtitulo = "  •  ".join(
            [f"{fmt_compacto(mov['total_movimentado'])} {verbo}", novas, fluxo]
        )
        self.cabecalho("Movimentações propostas", "De onde vem e para onde vai", subtitulo)

        origem = [
            (f"Resgate {'total' if item['total'] else 'parcial'}: {item['produto']}", -item["valor"])
            for item in mov["resgates"]
        ]
        if mov["aporte"]:
            origem.append(("Novo aporte", mov["aporte"]))
        destino = []
        for item in mov["aplicacoes"]:
            if item["novo"]:
                rotulo = item["produto"] + (f" · {item['detalhe']}" if item["detalhe"] else "")
            else:
                rotulo = f"Aporte adicional: {item['produto']}"
            destino.append((rotulo, item["valor"]))
        if mov["saida"]:
            destino.append(("Resgate sem reaplicação", mov["saida"]))

        topo = H - 108
        disponivel = topo - 50
        maximo_itens = int(disponivel // 17) - 3
        origem = self._resumir(origem, max(1, maximo_itens // 2), "Outros resgates")
        destino = self._resumir(destino, max(1, maximo_itens - len(origem)), "Outras aplicações")
        quantidade = len(origem) + len(destino) + 3
        altura_linha = max(17, min(31, disponivel / quantidade))

        x, largura = M, 470
        c = self.c
        c.setFillColor(white)
        c.setStrokeColor(LINHA)
        c.setLineWidth(0.8)
        c.rect(x, topo - quantidade * altura_linha, largura, quantidade * altura_linha, fill=1, stroke=1)
        y = topo

        def secao(rotulo):
            nonlocal y
            c.setFillColor(FUNDO_CABECALHO)
            c.rect(x, y - altura_linha, largura, altura_linha, fill=1, stroke=0)
            self.texto(rotulo, x + 16, y - altura_linha / 2 - 3.3, SANS_B, 9.5, NAVY)
            y -= altura_linha

        def item(rotulo, valor, fonte=SANS):
            nonlocal y
            base = y - altura_linha / 2 - 3.3
            self.texto(_cortar(rotulo, fonte, 9.5, largura - 32 - 95), x + 16, base, fonte, 9.5, NAVY)
            texto_valor = ("– " if valor < 0 else "") + fmt_reais(abs(valor))
            self.texto(texto_valor, x + largura - 16, base, fonte, 9.5,
                       LARANJA if valor < 0 else NAVY, "direita")
            y -= altura_linha
            c.setStrokeColor(LINHA)
            c.setLineWidth(0.6)
            c.line(x, y, x + largura, y)

        secao("Origem dos recursos")
        for rotulo, valor in origem:
            item(rotulo, valor)
        secao("Aplicações")
        for rotulo, valor in destino:
            item(rotulo, valor)
        item("Total realocado" if sem_fluxo else "Total movimentado",
             mov["total_movimentado"], SANS_B)

        x2 = M + largura + 28
        largura2 = X_FIM - x2
        altura_patrimonio = 74
        c.setFillColor(white)
        c.setStrokeColor(LINHA)
        c.rect(x2, topo - altura_patrimonio, largura2, altura_patrimonio, fill=1, stroke=1)
        c.setFillColor(NAVY)
        c.rect(x2, topo - altura_patrimonio, 5, altura_patrimonio, fill=1, stroke=0)
        self.texto(fmt_reais(total_recomendado), x2 + 24, topo - 38, SERIF, 30, NAVY)
        if sem_fluxo:
            legenda = "Patrimônio inalterado: a realocação usa apenas recursos já investidos."
        else:
            motivo = "o novo aporte" if mov["aporte"] else "o resgate líquido"
            legenda = (
                f"Patrimônio passa de {fmt_reais(total_atual)} para "
                f"{fmt_reais(total_recomendado)} com {motivo}."
            )
        yl = topo - 56
        for linha in _linhas(legenda, SANS, 8.5, largura2 - 48):
            self.texto(linha, x2 + 24, yl, SANS, 8.5, CINZA)
            yl -= 11

        resumo_atual = resumo_por_classe(atual)
        resumo_recomendado = resumo_por_classe(recomendada)
        classes = [
            classe for classe in ORDEM_CLASSES
            if resumo_atual[classe] or resumo_recomendado[classe]
        ]
        topo_classes = topo - altura_patrimonio - 16
        altura_classes = 48 + 19.5 * len(classes)
        c.setFillColor(white)
        c.setStrokeColor(LINHA)
        c.rect(x2, topo_classes - altura_classes, largura2, altura_classes, fill=1, stroke=1)
        self.texto("Mudança por classe", x2 + 22, topo_classes - 25, SERIF, 13.5, NAVY)
        yc = topo_classes - 46
        direita = x2 + largura2 - 18
        for classe in classes:
            antes = fmt_pct(resumo_atual[classe] / total_atual) if total_atual else "0,0%"
            depois = fmt_pct(resumo_recomendado[classe] / total_recomendado) if total_recomendado else "0,0%"
            self.ponto(x2 + 26, yc, classe)
            self.texto(classe, x2 + 36, yc, SANS, 9.5, GRAFITE)
            self.texto(depois, direita, yc, SANS_B, 9.5, NAVY, "direita")
            largura_depois = stringWidth(depois, SANS_B, 9.5)
            self.seta(direita - largura_depois - 5, yc)
            self.texto(antes, direita - largura_depois - 21, yc, SANS, 9.5, GRAFITE, "direita")
            yc -= 19.5

        if nota:
            fim_esquerda = topo - quantidade * altura_linha
            fim_direita = topo_classes - altura_classes
            self.quadro_comentario(nota, min(fim_esquerda, fim_direita) - 16)
        self.rodape(f"Valores líquidos. Data base: {self.p['data_base']:%d/%m/%Y}.")

    def quadro_comentario(self, nota, topo):
        """Comentário livre em quadro de largura total; cada linha vira um tópico."""
        linhas_digitadas = [linha.strip() for linha in nota.splitlines() if linha.strip()]
        marcadas = any(linha[:1] in "-•*" for linha in linhas_digitadas)
        itens = [linha.lstrip("-•* ").strip() for linha in linhas_digitadas]
        topicos = len(itens) > 1 or marcadas
        largura = X_FIM - M
        recuo = 14 if topicos else 0
        maximo = int((topo - 40 - 54) // 14)
        if maximo < 1:
            return
        blocos = []
        for item in itens:
            for indice, linha in enumerate(simpleSplit(item, SANS, 10, largura - 48 - recuo)):
                blocos.append((indice == 0 and topicos, linha))
        if len(blocos) > maximo:
            blocos = blocos[:maximo]
            marcador, ultima = blocos[-1]
            blocos[-1] = (marcador, _cortar(ultima + "…", SANS, 10, largura - 48 - recuo))
        altura = 54 + 14 * len(blocos)
        c = self.c
        c.setFillColor(white)
        c.setStrokeColor(LINHA)
        c.setLineWidth(0.8)
        c.rect(M, topo - altura, largura, altura, fill=1, stroke=1)
        c.setFillColor(LARANJA)
        c.rect(M, topo - altura, 4, altura, fill=1, stroke=0)
        self.texto("COMENTÁRIOS", M + 24, topo - 22, SANS_B, 7.5, LARANJA, espacamento=0.6)
        y = topo - 42
        for marcador, linha in blocos:
            if marcador:
                self.texto("•", M + 24, y, SANS_B, 10, LARANJA)
            self.texto(linha, M + 24 + recuo, y, SANS, 10, GRAFITE)
            y -= 14

    def ponto(self, x, y_base, classe):
        self.c.setFillColor(HexColor(CLASSES[classe][0]))
        self.c.circle(x, y_base + 3.3, 3.6, fill=1, stroke=0)

    # Alocação por classe ---------------------------------------------------
    def pagina_alocacao(self, atual, recomendada):
        carteiras = [
            (rotulo, posicoes)
            for rotulo, posicoes in (("Carteira atual", atual), ("Carteira recomendada", recomendada))
            if posicoes
        ]
        subtitulo = (
            "Carteira atual e carteira recomendada  •  percentual do patrimônio de cada carteira"
            if len(carteiras) == 2 else "Percentual do patrimônio em cada classe"
        )
        self.cabecalho("Diversificação", "Alocação por classe", subtitulo)
        espaco = 24
        largura = (W - 2 * M - espaco) / 2
        inicio = M if len(carteiras) == 2 else M + (W - 2 * M - largura) / 2
        for indice, (rotulo, posicoes) in enumerate(carteiras):
            self.rosca(inicio + indice * (largura + espaco), H - 112, largura, rotulo, posicoes)
        self.rodape(f"Valores líquidos. Data base: {self.p['data_base']:%d/%m/%Y}.")

    def rosca(self, x, topo, largura, rotulo, posicoes):
        c = self.c
        altura = 284
        c.setFillColor(white)
        c.setStrokeColor(LINHA)
        c.setLineWidth(0.8)
        c.rect(x, topo - altura, largura, altura, fill=1, stroke=1)
        self.texto(rotulo, x + 24, topo - 32, SERIF, 15, NAVY)

        soma = resumo_por_classe(posicoes)
        total_carteira = total(posicoes)
        classes = [classe for classe in ORDEM_CLASSES if soma[classe] > 0]
        raio, furo = 88, 56
        cx, cy = x + 24 + raio, topo - 60 - raio
        if len(classes) == 1:
            c.setFillColor(HexColor(CLASSES[classes[0]][0]))
            c.circle(cx, cy, raio, fill=1, stroke=0)
        else:
            inicio = 90.0
            c.setStrokeColor(white)
            c.setLineWidth(2)
            for classe in classes:
                extensao = 360 * soma[classe] / total_carteira
                c.setFillColor(HexColor(CLASSES[classe][0]))
                c.wedge(cx - raio, cy - raio, cx + raio, cy + raio,
                        inicio - extensao, extensao, stroke=1, fill=1)
                inicio -= extensao
        c.setFillColor(white)
        c.circle(cx, cy, furo, fill=1, stroke=0)
        valor = fmt_compacto(total_carteira)
        self.texto(valor, cx - stringWidth(valor, SERIF, 16) / 2, cy + 1, SERIF, 16, NAVY)
        legenda = "PATRIMÔNIO"
        largura_legenda = stringWidth(legenda, SANS_B, 6.5) + 0.6 * (len(legenda) - 1)
        self.texto(legenda, cx - largura_legenda / 2, cy - 13, SANS_B, 6.5, CINZA, espacamento=0.6)

        x_legenda = cx + raio + 26
        direita = x + largura - 22
        y = topo - 72
        passo = min(30, 210 / max(1, len(classes)))
        for classe in classes:
            self.ponto(x_legenda + 4, y, classe)
            self.texto(classe, x_legenda + 14, y, SANS, 9.5, GRAFITE)
            self.texto(fmt_pct(soma[classe] / total_carteira), direita, y, SANS_B, 9.5, NAVY, "direita")
            self.texto(fmt_reais(soma[classe]), x_legenda + 14, y - 11, SANS, 7.5, CINZA)
            y -= passo

    @staticmethod
    def _resumir(itens, maximo, rotulo):
        if len(itens) <= maximo:
            return itens
        manter = itens[:maximo - 1]
        resto = itens[maximo - 1:]
        return manter + [(f"{rotulo} ({len(resto)})", sum(valor for _, valor in resto))]

    # Pontos de atenção --------------------------------------------------
    def pagina_pontos(self, titulo, cartoes, aviso):
        self.cabecalho("Pontos que acompanhamos", titulo or "Pontos de atenção")
        c = self.c
        y = H - 110
        colunas = min(3, max(1, len(cartoes)))
        espaco = 16
        largura = (W - 2 * M - espaco * (colunas - 1)) / colunas
        for inicio in range(0, len(cartoes), colunas):
            fileira = cartoes[inicio:inicio + colunas]
            textos = [_linhas(cartao["texto"], SANS, 9.5, largura - 44, 9) for cartao in fileira]
            altura = 62 + 14 * max(len(linhas) for linhas in textos)
            for indice, (cartao, linhas) in enumerate(zip(fileira, textos)):
                x = M + indice * (largura + espaco)
                c.setFillColor(white)
                c.setStrokeColor(LINHA)
                c.setLineWidth(0.8)
                c.rect(x, y - altura, largura, altura, fill=1, stroke=1)
                c.setFillColor(CORES_CARTOES[(inicio + indice) % len(CORES_CARTOES)])
                c.rect(x, y - altura, 4, altura, fill=1, stroke=0)
                self.texto(_cortar(cartao["titulo"], SERIF, 13.5, largura - 44),
                           x + 22, y - 28, SERIF, 13.5, NAVY)
                yt = y - 50
                for linha in linhas:
                    self.texto(linha, x + 22, yt, SANS, 9.5, GRAFITE)
                    yt -= 14
            y -= altura + 16
        if aviso:
            tamanho = 7.8 if cartoes else 9.5
            entrelinha = 10.5 if cartoes else 13.5
            for linha in simpleSplit(aviso, SANS, tamanho, W - 2 * M):
                self.texto(linha, M, y - 4, SANS, tamanho, CINZA)
                y -= entrelinha
        self.rodape()

    # Montagem ------------------------------------------------------------
    def gerar(self) -> bytes:
        p = self.p
        paginas = p.get("paginas", {})
        atual = p.get("atual", [])
        recomendada = p.get("recomendada", [])
        data_base = p["data_base"]
        if paginas.get("capa", True):
            self.capa()
        if atual and paginas.get("atual", True):
            nota = " ".join(filter(None, [p.get("nota_atual", ""), f"Data base: {data_base:%d/%m/%Y}."]))
            self.pagina_carteira("Posição consolidada", "Carteira Atual", atual, nota, set())
        if atual and recomendada and paginas.get("movimentacoes", True):
            mov = calcular_movimentacoes(atual, recomendada)
            if mov["resgates"] or mov["aplicacoes"]:
                self.pagina_movimentacoes(atual, recomendada, mov, p.get("nota_movimentacoes", ""))
        if recomendada and paginas.get("recomendada", True):
            novos = produtos_novos(atual, recomendada) if atual else set()
            self.pagina_carteira("Proposta de alocação", "Carteira Recomendada",
                                 recomendada, p.get("nota_recomendada", ""), novos)
        if (atual or recomendada) and paginas.get("alocacao", True):
            self.pagina_alocacao(atual, recomendada)
        cartoes = p.get("pontos", [])[:6]
        if paginas.get("pontos", True) and (cartoes or p.get("aviso")):
            self.pagina_pontos(p.get("titulo_pontos", ""), cartoes, p.get("aviso", ""))
        if not self.paginas:
            raise ValueError("Nenhuma página selecionada tem conteúdo para o PDF.")
        self.c.save()
        return self.buffer.getvalue()


def gerar_pdf_carteira(proposta: dict) -> bytes:
    """Recebe posições já normalizadas e devolve o PDF pronto."""
    dados = dict(proposta)
    if not isinstance(dados.get("data_base"), date):
        dados["data_base"] = date.today()
    return _Proposta(dados).gerar()
