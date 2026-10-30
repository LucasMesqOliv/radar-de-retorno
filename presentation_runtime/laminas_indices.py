"""Lâminas 16:9 da Análise de índices (PDF).

Layout inspirado nas lâminas comerciais: fundo off-white, série principal em
vermelho, comparativos em cinza/grafite, manchete com a frequência de vitória
e painel lateral com os números que sustentam a mensagem.

Uso: render(canvas, dados) — dados no formato montado por
``montar_dados_apresentacao`` em app.py (reportVersion "indices-v6-laminas").
"""

from __future__ import annotations

import math
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont

W, H = 1440, 810
PAGE = (W, H)
ASSETS = Path(__file__).resolve().parent / "assets"

BG = colors.HexColor("#F6F5F2")
INK = colors.HexColor("#1F2329")
MUTED = colors.HexColor("#6B7280")
SOFT = colors.HexColor("#9CA3AF")
GRID = colors.HexColor("#E2E0DB")
LINE = colors.HexColor("#E8E6E1")
WHITE = colors.white
RED = colors.HexColor("#EC0000")
DARK_RED = colors.HexColor("#B4000A")
GREEN = colors.HexColor("#1E7B46")
GREEN_BG = colors.HexColor("#E3F1E7")
NEG_BG = colors.HexColor("#FBE4E4")

# Ordem das cores: principal, 1º comparativo, 2º, ...
SERIES_HEX = ["#EC0000", "#8E9AAB", "#1F2329", "#C08A1E", "#3F6FB5", "#2E8B6E", "#7A4EAB"]
VALUE_HEX = ["#B4000A", "#5F6B7A", "#1F2329", "#8A6212", "#2F5891", "#21684F", "#5C3A82"]

LEFT = 96
RIGHT = W - 96


# ---------------------------------------------------------------- fontes
def _registrar_fontes():
    nomes = {
        "regular": ("DMSans", "DMSans-Regular.ttf", "Helvetica"),
        "medium": ("DMSans-Medium", "DMSans-Medium.ttf", "Helvetica"),
        "bold": ("DMSans-Bold", "DMSans-Bold.ttf", "Helvetica-Bold"),
    }
    fontes = {}
    for chave, (nome, arquivo, reserva) in nomes.items():
        caminho = ASSETS / arquivo
        try:
            if nome not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(nome, str(caminho)))
            fontes[chave] = nome
        except Exception:
            fontes[chave] = reserva
    return fontes


F = _registrar_fontes()


# ---------------------------------------------------------------- helpers
def Y(top):
    """Converte distância a partir do topo em coordenada do ReportLab."""
    return H - top


def pct(valor, casas=1):
    if valor is None or (isinstance(valor, float) and math.isnan(valor)):
        return "–"
    return f"{valor * 100:.{casas}f}%".replace(".", ",")


def pp(valor):
    sinal = "+" if valor >= 0 else "−"
    return f"{sinal}{abs(valor) * 100:.0f}"


def pp2(valor):
    sinal = "+" if valor >= 0 else "−"
    return f"{sinal}{abs(valor) * 100:.2f}".replace(".", ",") + " p.p."


def frequencia(vitorias, total):
    return "100%" if vitorias == total else pct(vitorias / total)


def largura(texto, fonte, tamanho, espaco=0.0):
    return stringWidth(str(texto), fonte, tamanho) + espaco * max(0, len(str(texto)) - 1)


def escrever(c, texto, x, top, tamanho, fonte="regular", cor=INK, alinhar="left", espaco=0.0):
    nome = F[fonte]
    texto = str(texto)
    w = largura(texto, nome, tamanho, espaco)
    if alinhar == "right":
        x -= w
    elif alinhar == "center":
        x -= w / 2
    t = c.beginText()
    t.setTextOrigin(x, Y(top))
    t.setFont(nome, tamanho)
    t.setFillColor(cor)
    t.setCharSpace(espaco)
    t.textOut(texto)
    c.drawText(t)
    return w


def ajustar(texto, fonte, maximo, largura_max, minimo=18):
    tamanho = maximo
    while tamanho > minimo and largura(texto, F[fonte], tamanho) > largura_max:
        tamanho -= 1
    return tamanho


def encurtar(texto, fonte, tamanho, largura_max):
    texto = str(texto)
    if largura(texto, F[fonte], tamanho) <= largura_max:
        return texto
    while texto and largura(texto + "…", F[fonte], tamanho) > largura_max:
        texto = texto[:-1]
    return texto.rstrip() + "…"


def caixa(c, x, top, w, h, raio=14, preenchimento=WHITE, borda=LINE):
    c.setFillColor(preenchimento)
    c.setStrokeColor(borda)
    c.setLineWidth(0.8)
    c.roundRect(x, Y(top + h), w, h, raio, fill=1, stroke=1 if borda else 0)


def ticks_bonitos(vmin, vmax, alvo=5):
    """Escolhe o menor passo "bonito" que cobre o intervalo com até alvo+1 marcas."""
    if vmax <= vmin:
        vmax = vmin + 0.01
    melhor = None
    for expoente in range(-4, 3):
        for base in (1, 2, 2.5, 5):
            passo = base * 10 ** expoente
            inicio = math.floor(vmin / passo + 1e-9) * passo
            fim = math.ceil(vmax / passo - 1e-9) * passo
            n = round((fim - inicio) / passo) + 1
            if 3 <= n <= alvo + 1:
                melhor = (passo, inicio, n)
                break
        if melhor:
            break
    if not melhor:
        passo = (vmax - vmin) / max(1, alvo - 1)
        melhor = (passo, vmin, alvo)
    passo, inicio, n = melhor
    return [round(inicio + i * passo, 10) for i in range(n)]


def rotulo_tick(valor, passo, sufixo="%", escala=100):
    v = valor * escala
    passo_escala = passo * escala
    casas = 0 if abs(passo_escala - round(passo_escala)) < 1e-9 else 1
    return f"{v:.{casas}f}{sufixo}".replace(".", ",").replace("-", "−")


# ---------------------------------------------------------------- moldura
class Lamina:
    def __init__(self, c, dados):
        self.c = c
        self.d = dados
        self.logo = None
        if dados.get("brand", "santander") == "santander":
            caminho = ASSETS / "santander_logo.png"
            if caminho.exists():
                self.logo = ImageReader(str(caminho))

    def nova(self, eyebrow, titulo, tamanho_titulo=46, top_titulo=168):
        c = self.c
        c.setFillColor(BG)
        c.rect(0, 0, W, H, fill=1, stroke=0)
        if self.logo is not None:
            lw = 182
            iw, ih = self.logo.getSize()
            lh = lw * ih / iw
            c.drawImage(self.logo, RIGHT - lw, Y(36 + lh), lw, lh, mask="auto")
        else:
            escrever(c, "RADAR DE RETORNO", RIGHT, 60, 15, "bold", INK, "right", 2.2)
        escrever(c, eyebrow.upper(), LEFT, top_titulo - 66, 16, "medium", RED, espaco=2.6)
        tamanho = ajustar(titulo, "bold", tamanho_titulo, RIGHT - LEFT, 26)
        escrever(c, titulo, LEFT, top_titulo, tamanho, "bold", INK)

    def rodape(self, texto, destaque="Rentabilidade passada não é garantia de rentabilidade futura."):
        c = self.c
        tamanho = 14
        largura_total = largura(texto + " ", F["regular"], tamanho) + largura(destaque, F["medium"], tamanho)
        while largura_total > RIGHT - LEFT and tamanho > 10:
            tamanho -= 0.5
            largura_total = largura(texto + " ", F["regular"], tamanho) + largura(destaque, F["medium"], tamanho)
        w = escrever(c, texto + " ", LEFT, 760, tamanho, "regular", MUTED)
        if destaque:
            escrever(c, destaque, LEFT + w, 760, tamanho, "medium", INK)
        c.showPage()

    # ------------------------------------------------------------ legenda
    def legenda(self, itens, x, top, extra=None, tamanho=17, limite=None):
        c = self.c
        inicio = x
        limite = limite or RIGHT
        for nome, cor, tracejado in itens:
            largura_item = 40 + largura(nome, F["regular"], tamanho)
            if x > inicio and x + largura_item > limite:
                x = inicio
                top += tamanho + 10
            c.setStrokeColor(cor)
            c.setLineWidth(4)
            c.setLineCap(1)
            if tracejado:
                c.setDash(7, 5)
            c.line(x, Y(top - 6), x + 30, Y(top - 6))
            c.setDash()
            x += 40
            x += escrever(c, nome, x, top, tamanho, "regular", INK) + 30
        if extra:
            if x + largura(extra, F["regular"], tamanho) > limite:
                x = inicio - 6
                top += tamanho + 10
            escrever(c, extra, x + 6, top, tamanho, "regular", MUTED)

    # ------------------------------------------------------------ gráfico
    def linhas(self, x, top, w, h, categorias, series, zero_base=False, sufixo="%",
               escala=100, ticks_x=3, inferior_exato=False):
        """series: [(valores, cor, espessura, tracejado)]"""
        c = self.c
        valores = [v for s in series for v in s[0] if v is not None]
        if not valores:
            return
        vmin, vmax = min(valores), max(valores)
        if zero_base:
            vmin = min(0, vmin)
        folga = (vmax - vmin) * 0.06 or 0.01
        # folga abaixo da menor série (linha constante não cola no eixo)
        inferior = vmin - max((vmax - vmin) * 0.15, 0.01 if sufixo else 1)
        if zero_base and vmin >= 0:
            inferior = max(0, inferior)
        if inferior_exato:
            inferior = vmin
        ticks = ticks_bonitos(inferior, vmax + folga, 5)
        lo, hi = ticks[0], ticks[-1]
        passo = ticks[1] - ticks[0] if len(ticks) > 1 else 1
        base = Y(top + h)

        def py(v):
            return base + h * (v - lo) / max(1e-12, hi - lo)

        c.setLineWidth(1)
        for t in ticks:
            c.setStrokeColor(GRID)
            c.line(x, py(t), x + w, py(t))
            escrever(c, rotulo_tick(t, passo, sufixo, escala), x - 14, H - py(t) + 5, 15, "regular", MUTED, "right")

        n = max(1, len(categorias) - 1)
        for valores_serie, cor, espessura, tracejado in series:
            pontos = [(x + w * i / n, py(v)) for i, v in enumerate(valores_serie) if v is not None]
            if len(pontos) < 2:
                continue
            c.setStrokeColor(cor)
            c.setLineWidth(espessura)
            c.setLineJoin(1)
            c.setLineCap(1)
            if tracejado:
                c.setDash(8, 6)
            caminho = c.beginPath()
            caminho.moveTo(*pontos[0])
            for p in pontos[1:]:
                caminho.lineTo(*p)
            c.drawPath(caminho, stroke=1, fill=0)
            c.setDash()
        # pontos finais por último, para ficarem por cima das linhas
        for valores_serie, cor, espessura, _ in series:
            if valores_serie and valores_serie[-1] is not None:
                c.setFillColor(cor)
                c.setStrokeColor(BG)
                c.setLineWidth(2)
                c.circle(x + w, py(valores_serie[-1]), 6.5, fill=1, stroke=1)

        if categorias:
            posicoes = sorted({0, len(categorias) // 2, len(categorias) - 1}) if ticks_x == 3 else range(len(categorias))
            for i in posicoes:
                alinhar = "left" if i == 0 else ("right" if i == len(categorias) - 1 else "center")
                escrever(c, categorias[i], x + w * i / n, top + h + 30, 15, "regular", MUTED, alinhar)


# ---------------------------------------------------------------- lâminas
def _cor(i):
    return colors.HexColor(SERIES_HEX[i % len(SERIES_HEX)])


def _cor_valor(i):
    return colors.HexColor(VALUE_HEX[i % len(VALUE_HEX)])


def _artigo(serie):
    nome = serie["name"]
    if nome[:1].isdigit():
        return nome
    return ("a " if serie.get("feminine") else "o ") + nome


def lamina_anualizada(L, d, idx_comp):
    series = d["series"]
    principal, comp = series[0], series[idx_comp]
    cmp_info = d["comparisons"][idx_comp - 1]
    vit, tot = cmp_info["wins"], cmp_info["total"]
    if vit == tot:
        titulo = f"{principal['name']} bateu {_artigo(comp)} em {vit} de {tot} janelas"
    else:
        titulo = f"{principal['name']} bateu {_artigo(comp)} em {vit} de {tot} janelas ({frequencia(vit, tot)})"
    L.nova(f"Janelas móveis de {d['windowYears']} {'ano' if d['windowYears'] == 1 else 'anos'}", titulo)

    cor_p, cor_c = _cor(0), _cor(idx_comp)
    L.legenda(
        [(principal["name"], cor_p, False), (comp["name"], cor_c, comp.get("dashed"))],
        LEFT, 243, f"Retorno anualizado em cada janela de {d['windowYears']} anos",
    )
    graf = d["annualChart"]
    L.linhas(
        167, 274, 712, 342, graf["categories"],
        [
            (graf["values"][comp["code"]], cor_c, 4.2, comp.get("dashed")),
            (graf["values"][principal["code"]], cor_p, 4.6, principal.get("dashed")),
        ],
    )

    # painel lateral
    px, pw, ptop = 964, 380, 268
    sp, sc = d["stats"][principal["code"]], d["stats"][comp["code"]]
    linhas = [
        (d["periodLabel"], sp["period"], sc["period"]),
        ("Anualizado", sp["periodAnnual"], sc["periodAnnual"]),
        ("Pior janela", sp["worst"], sc["worst"]),
        ("Mediana", sp["median"], sc["median"]),
        ("Melhor janela", sp["best"], sc["best"]),
    ]
    altura_linha = 69
    col_p, col_c = px + pw - 112, px + pw - 22
    rotulo_p = principal["name"] if largura(principal["name"], F["bold"], 16) <= 170 else principal["short"]
    escrever(L.c, encurtar(rotulo_p, "bold", 16, 170), col_p, ptop - 14, 16, "bold", DARK_RED, "right")
    escrever(L.c, encurtar(comp["short"], "bold", 16, 82), col_c, ptop - 14, 16, "bold", SOFT, "right")
    caixa(L.c, px, ptop, pw, altura_linha * len(linhas), 14)
    for i, (rotulo, vp, vc) in enumerate(linhas):
        top = ptop + i * altura_linha
        if i % 2 == 1:
            L.c.setFillColor(BG)
            L.c.rect(px + 0.8, Y(top + altura_linha), pw - 1.6, altura_linha, fill=1, stroke=0)
        meio = top + altura_linha / 2 + 7
        escrever(L.c, encurtar(rotulo, "regular", 19, 150), px + 21, meio, 19, "regular", INK)
        escrever(L.c, pct(vp), col_p, meio + 3, 27, "bold", DARK_RED, "right")
        escrever(L.c, pct(vc), col_c, meio + 3, 24, "medium", _cor_valor(idx_comp) if idx_comp > 1 else MUTED, "right")

    L.rodape(f"Retornos brutos, até {d['asOf']}.")


def lamina_acumulada(L, d):
    series = d["series"]
    principal, comps = series[0], series[1:]
    janela = d["windowYears"]
    total = d["totalWindows"]
    primeira = d["comparisons"][0]
    if primeira["wins"] == primeira["total"]:
        titulo = f"Em qualquer mês de entrada, {principal['name']} superou {_artigo(comps[0])}"
    else:
        titulo = (f"{principal['name']} superou {_artigo(comps[0])} em "
                  f"{primeira['wins']} de {primeira['total']} meses de entrada")
    L.nova(
        f"Retorno acumulado · Janelas móveis de {janela} {'ano' if janela == 1 else 'anos'} · {total} janelas",
        titulo, 40, 160,
    )
    L.legenda([(s["name"], _cor(i), s.get("dashed")) for i, s in enumerate(series)], LEFT, 222,
              tamanho=17 if len(series) <= 3 else 15, limite=905)
    graf = d["accumChart"]
    desenho = [(graf["values"][s["code"]], _cor(i), 4.0 if i else 4.4, s.get("dashed"))
               for i, s in reversed(list(enumerate(series)))]
    L.linhas(159, 274, 746, 339, graf["categories"], desenho, zero_base=True)

    # cards de frequência
    c = L.c
    px, pw = 952, 392
    ncards = min(3, len(comps))
    altura_linha_tab = 44 if ncards < 3 else 40
    altura_tabela = 54 + 3 * altura_linha_tab
    topo, base = 201, 630 if ncards < 3 else 662
    disponivel = base - topo - altura_tabela - 18
    altura_card = min(118, (disponivel - (ncards - 1) * 16) / max(1, ncards))
    for i in range(ncards):
        info = d["comparisons"][i]
        top = topo + i * (altura_card + 16)
        caixa(c, px, top, pw, altura_card, 14)
        c.setFillColor(RED)
        c.roundRect(px, Y(top + 8), pw, 8, 4, fill=1, stroke=0)
        c.rect(px + 4, Y(top + 8), pw - 8, 4, fill=1, stroke=0)
        grande = 54 if altura_card >= 105 else (42 if altura_card >= 85 else 34)
        cor_num = RED if i == 0 else INK
        escrever(c, f"{info['wins']} de {info['total']}", px + 24, top + 16 + grande * 0.86, grande, "bold", cor_num)
        if i == 0:
            texto = f"janelas superaram {_artigo(comps[i])} ({frequencia(info['wins'], info['total'])})"
        else:
            texto = f"superaram {_artigo(comps[i])} ({frequencia(info['wins'], info['total'])})"
        tam = 17 if altura_card >= 85 else 14
        respiro = 12 if altura_card >= 85 else 7
        escrever(c, encurtar(texto, "regular", tam, pw - 48), px + 24, top + 14 + grande * 0.86 + tam + respiro, tam, "regular", MUTED)
    topo_tabela = topo + ncards * (altura_card + 16) + 2 if ncards else topo

    # tabela pior / mediana / melhor
    colunas = series[:4]
    caixa(c, px, topo_tabela, pw, altura_tabela, 14)
    rotulo_tabela = f"{janela} {'ANO' if janela == 1 else 'ANOS'}"
    if len(colunas) <= 3:
        rotulo_tabela = "EM " + rotulo_tabela
    escrever(c, rotulo_tabela, px + 24, topo_tabela + 34, 12.5, "medium", SOFT, espaco=1.6)
    rotulo_w = 96 if len(colunas) <= 3 else 76
    col_w = (pw - 24 - rotulo_w - 16) / len(colunas)
    tam_cab = 12.5 if len(colunas) <= 3 else 11
    tam_val = 20 if len(colunas) <= 3 else 17
    for j, s in enumerate(colunas):
        xr = px + 24 + rotulo_w + col_w * (j + 1)
        cor = DARK_RED if j == 0 else INK
        escrever(c, encurtar(s["short"], "bold", tam_cab, col_w - 4), xr, topo_tabela + 34, tam_cab, "bold", cor, "right")
    c.setStrokeColor(INK)
    c.setLineWidth(1.4)
    c.line(px + 24, Y(topo_tabela + 46), px + pw - 24, Y(topo_tabela + 46))
    for i, (rotulo, chave) in enumerate([("Pior", "worstAcc"), ("Mediana", "medianAcc"), ("Melhor", "bestAcc")]):
        top = topo_tabela + 54 + i * altura_linha_tab
        if i:
            c.setStrokeColor(LINE)
            c.setLineWidth(1)
            c.line(px + 24, Y(top), px + pw - 24, Y(top))
        escrever(c, rotulo, px + 24, top + altura_linha_tab * 0.66, 17, "regular", INK)
        for j, s in enumerate(colunas):
            xr = px + 24 + rotulo_w + col_w * (j + 1)
            cor = DARK_RED if j == 0 else (_cor_valor(j) if j > 1 else colors.HexColor("#4B5563"))
            escrever(c, pct(d["stats"][s["code"]][chave]), xr, top + altura_linha_tab * 0.68, tam_val, "bold" if j != 1 else "medium", cor, "right")

    nota = "S&P 500 em USD, índice de preço. " if d.get("hasSP500") else ""
    L.rodape(f"Fonte: Radar de Retorno, dados até {d['asOfShort']}. {nota}Retornos brutos e acumulados.",
             "Rentabilidade passada não garante rentabilidade futura.")


def lamina_calendario_barras(L, d):
    cal = d["calendar"]
    linhas = cal["rows"]
    principal = d["series"][0]
    comp = next(s for s in d["series"] if s["code"] == cal["comparative"])
    janela = d["windowYears"]
    venceu = sum(1 for r in linhas if r["values"][principal["code"]] > r["values"][comp["code"]])
    anos_txt = f"{janela} {'ano' if janela == 1 else 'anos'}"
    if venceu == len(linhas):
        titulo = f"Superou {_artigo(comp)} em todas as janelas de {anos_txt}"
    else:
        titulo = f"Superou {_artigo(comp)} em {venceu} de {len(linhas)} janelas de {anos_txt}"
    L.nova(
        f"{principal['short']} vs {comp['short']} · Retornos acumulados · {linhas[0]['startYear']} a {linhas[-1]['endYear']}",
        titulo, 40, 160,
    )
    c = L.c
    # legenda à direita
    for i, (nome, cor) in enumerate([(principal["name"], RED), (comp["name"], _cor(1))]):
        top = 205 + i * 30
        c.setFillColor(cor)
        c.roundRect(1082, Y(top + 18), 20, 20, 3, fill=1, stroke=0)
        escrever(c, encurtar(nome, "medium" if i == 0 else "regular", 17, 230), 1112, top + 15, 17,
                 "medium" if i == 0 else "regular", INK)

    x0, x1 = 175, RIGHT + 8
    top_area, base_top = 262, 580
    h = base_top - top_area
    vals = [r["values"][principal["code"]] for r in linhas] + [r["values"][comp["code"]] for r in linhas]
    vmax, vmin = max(vals + [0]), min(vals + [0])
    ticks = ticks_bonitos(vmin, vmax * 1.1 if vmax > 0 else vmax, 4)
    lo, hi = ticks[0], ticks[-1]
    passo = ticks[1] - ticks[0] if len(ticks) > 1 else 1

    escala_h = h / max(1e-12, hi - lo)
    zero_y = Y(base_top) + (-lo) * escala_h if lo < 0 else Y(base_top)

    def pyv(v):
        return zero_y + v * escala_h

    c.setDash(2, 4)
    for t in ticks:
        c.setStrokeColor(GRID)
        c.setLineWidth(0.8)
        c.line(x0, pyv(t), x1, pyv(t))
        escrever(c, rotulo_tick(t, passo), x0 - 14, H - pyv(t) + 5, 15, "regular", SOFT, "right")
    c.setDash()
    n = len(linhas)
    grupo = (x1 - x0) / n
    barra = min(50, grupo * 0.42)
    tam_rot = 15 if n <= 12 else (13 if n <= 16 else 11)
    for i, r in enumerate(linhas):
        gx = x0 + grupo * i + (grupo - 2 * barra - 4) / 2
        for k, (codigo, cor, cor_txt) in enumerate(
            [(principal["code"], RED, DARK_RED), (comp["code"], _cor(1), colors.HexColor("#4B5563"))]
        ):
            v = r["values"][codigo]
            bx = gx + k * (barra + 4)
            y_top = pyv(v)
            c.setFillColor(cor)
            c.rect(bx, min(zero_y, y_top), barra, abs(y_top - zero_y), fill=1, stroke=0)
            escrever(c, f"{v * 100:.0f}%", bx + barra / 2, H - max(zero_y, y_top) - 8, tam_rot, "bold", cor_txt, "center")
        escrever(c, r["label"], x0 + grupo * (i + 0.5), base_top + 30, 15 if n <= 12 else 12.5, "regular", INK, "center")
        dif = r["values"][principal["code"]] - r["values"][comp["code"]]
        pw_ = min(grupo - 10, 92)
        cx = x0 + grupo * (i + 0.5)
        c.setFillColor(GREEN_BG if dif >= 0 else NEG_BG)
        c.roundRect(cx - pw_ / 2, Y(base_top + 64), pw_, 23, 4, fill=1, stroke=0)
        escrever(c, pp(dif), cx, base_top + 58, 14 if n <= 12 else 12, "bold", GREEN if dif >= 0 else DARK_RED, "center")
    c.setStrokeColor(INK)
    c.setLineWidth(1.2)
    c.line(x0, zero_y, x1, zero_y)
    escrever(c, "p.p.", 100, base_top + 58, 15, "bold", GREEN)

    nota = "S&P 500 em USD, sem dividendos e sem câmbio. " if d.get("hasSP500") else ""
    L.rodape(f"Janelas de dezembro a dezembro. Em verde, ganho sobre {_artigo(comp)} (p.p.). {nota}Retornos brutos, sem impostos.", "")


def lamina_calendario_tabela(L, d):
    cal = d["calendar"]
    linhas = cal["rows"]
    principal = d["series"][0]
    comp = next(s for s in d["series"] if s["code"] == cal["comparative"])
    janela = d["windowYears"]
    L.nova(
        f"{principal['short']} vs {comp['short']} · Retornos acumulados · {linhas[0]['startYear']} a {linhas[-1]['endYear']}",
        f"Todas as janelas de {janela} {'ano' if janela == 1 else 'anos'}, lado a lado", 40, 160,
    )
    c = L.c
    cab = ["Período"] + [col["name"] for col in cal["components"]]
    cab += [s["short"] for s in d["series"]]
    cab += [f"Ganho s/ {comp['short']}"]
    ncol = len(cab)
    larg_total = RIGHT - LEFT
    w_periodo = 190
    w_col = (larg_total - w_periodo) / (ncol - 1)
    top = 203
    alt_cab = 39
    disponivel = 700 - top - alt_cab
    alt = min(40.5, disponivel / max(1, len(linhas)))
    tam = 17 if alt >= 36 else (15 if alt >= 30 else 12.5)
    c.setFillColor(INK)
    c.rect(LEFT, Y(top + alt_cab), larg_total, alt_cab, fill=1, stroke=0)
    for j, nome in enumerate(cab):
        if j == 0:
            escrever(c, nome, LEFT + 12, top + 26, 16, "bold", WHITE)
        else:
            xr = LEFT + w_periodo + w_col * j - 12
            escrever(c, encurtar(nome, "bold", 16, w_col - 14), xr, top + 26, 16, "bold", WHITE, "right")
    for i, r in enumerate(linhas):
        t = top + alt_cab + i * alt
        if i % 2 == 1:
            c.setFillColor(colors.HexColor("#EEECE7"))
            c.rect(LEFT, Y(t + alt), larg_total, alt, fill=1, stroke=0)
        c.setStrokeColor(LINE)
        c.setLineWidth(0.6)
        c.line(LEFT, Y(t + alt), RIGHT, Y(t + alt))
        meio = t + alt / 2 + tam * 0.36
        valores = [r["components"].get(col["code"]) for col in cal["components"]]
        valores += [r["values"][s["code"]] for s in d["series"]]
        escrever(c, r["labelLong"], LEFT + 12, meio, tam, "regular", INK)
        for j, v in enumerate(valores, start=1):
            xr = LEFT + w_periodo + w_col * j - 12
            principal_col = j == len(cal["components"]) + 1
            escrever(c, pct(v, 2), xr, meio, tam, "bold" if principal_col else "regular",
                     DARK_RED if principal_col else INK, "right")
        dif = r["values"][principal["code"]] - r["values"][comp["code"]]
        escrever(c, pp2(dif), RIGHT - 12, meio, tam, "bold", GREEN if dif >= 0 else DARK_RED, "right")

    nota = "S&P 500 em USD, sem dividendos e sem câmbio. " if d.get("hasSP500") else ""
    comp_txt = "Composto = (1 + S&P) × (1 + IPCA) − 1. " if cal["components"] else ""
    L.rodape(f"{nota}{comp_txt}Janelas de dezembro a dezembro.",
             "Rentabilidade passada não garante rentabilidade futura.")


def lamina_periodo(L, d):
    series = d["series"]
    principal = series[0]
    sp = d["stats"][principal["code"]]
    rotulo = d["periodLabel"]
    if rotulo.startswith("Últimos"):
        titulo = f"{principal['name']} acumulou {pct(sp['period'])} nos {rotulo[0].lower() + rotulo[1:]}"
    else:
        titulo = f"{principal['name']} acumulou {pct(sp['period'])} de {rotulo}"
    L.nova(f"Desempenho no período · {rotulo}", titulo, 44, 168)
    L.legenda([(s["name"], _cor(i), s.get("dashed")) for i, s in enumerate(series)], LEFT, 236,
              "Base 100 no início do período", tamanho=17 if len(series) <= 3 else 15, limite=905)
    graf = d["periodChart"]
    desenho = [([v / 100 for v in graf["values"][s["code"]]], _cor(i), 4.0 if i else 4.4, s.get("dashed"))
               for i, s in reversed(list(enumerate(series)))]
    L.linhas(167, 274, 712, 342, graf["categories"], desenho, sufixo="", escala=100,
             inferior_exato=True)

    c = L.c
    px, pw, ptop = 964, 380, 268
    escrever(c, "Acumulado", px + pw - 128, ptop - 14, 15, "bold", SOFT, "right")
    escrever(c, "Ao ano", px + pw - 22, ptop - 14, 15, "bold", SOFT, "right")
    alt = min(80, 345 / max(1, len(series)))
    caixa(c, px, ptop, pw, alt * len(series), 14)
    for i, s in enumerate(series):
        top = ptop + i * alt
        if i % 2 == 1:
            c.setFillColor(BG)
            c.rect(px + 0.8, Y(top + alt), pw - 1.6, alt, fill=1, stroke=0)
        st = d["stats"][s["code"]]
        meio = top + alt / 2 + 7
        c.setFillColor(_cor(i))
        c.circle(px + 24, Y(meio - 6), 5.5, fill=1, stroke=0)
        escrever(c, encurtar(s["short"], "regular", 17, 150), px + 38, meio, 17, "regular", INK)
        cor = DARK_RED if i == 0 else INK
        escrever(c, pct(st["period"]), px + pw - 128, meio + 2, 24, "bold", cor, "right")
        escrever(c, pct(st["periodAnnual"]), px + pw - 22, meio + 2, 19, "medium", MUTED, "right")
    L.rodape(f"Período efetivo: {d['periodRange']}. Retornos brutos.")


def lamina_premissas(L, d):
    L.nova("Premissas", "Como ler este material", 44, 168)
    itens = [
        ("Janelas móveis",
         f"Cada ponto é o retorno de uma janela de {d['windowYears']} {'ano' if d['windowYears'] == 1 else 'anos'} "
         "encerrada naquele mês. Repetir a conta em todos os meses mostra quanto o resultado depende do momento de entrada."),
        ("Frequência de vitória",
         "\"N de N janelas\" conta em quantos meses de entrada a série principal terminou a janela acima da comparada."),
        ("Retornos brutos",
         "Os cálculos não consideram impostos, taxas, custos, liquidez nem risco de crédito de produtos específicos."),
        ("Fontes",
         "CDI e IPCA: Banco Central do Brasil. S&P 500 e câmbio: Yahoo Finance (índice de preço, sem dividendos)."),
    ]
    c = L.c
    cw, ch = (RIGHT - LEFT - 24) / 2, 190
    for i, (titulo, texto) in enumerate(itens):
        x = LEFT + (i % 2) * (cw + 24)
        top = 228 + (i // 2) * (ch + 24)
        caixa(c, x, top, cw, ch, 10)
        c.setFillColor(colors.HexColor("#D8D2C6"))
        c.rect(x + 2, Y(top + 4), cw - 4, 4, fill=1, stroke=0)
        escrever(c, f"{i + 1:02d}", x + 28, top + 46, 16, "bold", RED)
        escrever(c, titulo, x + 28, top + 82, 24, "bold", INK)
        _paragrafo(c, texto, x + 28, top + 118, cw - 56, 17, MUTED)
    L.rodape("Material de apoio para conversa com o cliente.")


def _paragrafo(c, texto, x, top, largura_max, tamanho, cor, entrelinha=1.42):
    palavras = texto.split()
    linha = ""
    t = top
    for p in palavras:
        teste = (linha + " " + p).strip()
        if largura(teste, F["regular"], tamanho) > largura_max and linha:
            escrever(c, linha, x, t, tamanho, "regular", cor)
            t += tamanho * entrelinha
            linha = p
        else:
            linha = teste
    if linha:
        escrever(c, linha, x, t, tamanho, "regular", cor)


def render(c, d):
    c.setPageSize(PAGE)
    c.setTitle(d.get("documentTitle", "Radar de Retorno"))
    L = Lamina(c, d)
    inc = d.get("include") or {}
    anuais = inc.get("annual")
    for i in range(1, len(d["series"])):
        if anuais is None or d["series"][i]["code"] in anuais:
            lamina_anualizada(L, d, i)
    if inc.get("accum", True):
        lamina_acumulada(L, d)
    if d.get("calendar") and len(d["calendar"]["rows"]) >= 2:
        if inc.get("calendar", True):
            lamina_calendario_barras(L, d)
        if inc.get("calendarTable", True):
            lamina_calendario_tabela(L, d)
    if d.get("periodChart") and inc.get("period", True):
        lamina_periodo(L, d)
    if inc.get("assumptions", True):
        lamina_premissas(L, d)
