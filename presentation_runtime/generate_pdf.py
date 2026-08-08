import json
import math
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.pdfgen import canvas


if len(sys.argv) != 3:
    raise SystemExit("Uso: python generate_pdf.py entrada.json saida.pdf")

input_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])
data = json.loads(input_path.read_text(encoding="utf-8"))

PAGE = landscape((7.5 * inch, 13.333 * inch))
W, H = PAGE
MARGIN = 38
BLUE = colors.HexColor("#174A7E")
GREEN = colors.HexColor("#1B7F5A")
RED = colors.HexColor("#C43D3D")
PURPLE = colors.HexColor("#7A4EAB")
ORANGE = colors.HexColor("#D47A22")
DARK_GRAY = colors.HexColor("#555555")
LIGHT_GRAY = colors.HexColor("#F2F2F2")
GRID = colors.HexColor("#DEDEDE")
SERIES_COLORS = [BLUE, GREEN, RED, PURPLE, ORANGE, DARK_GRAY]

c = canvas.Canvas(str(output_path), pagesize=PAGE)
c.setTitle("Radar de Retorno")
c.setAuthor("Radar de Retorno")


def draw_text(text, x, y, size, bold=False, color=colors.black):
    c.setFillColor(color)
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    c.drawString(x, y, str(text))


def draw_wrapped(text, x, y, width, height, size=16, bold=False, color=colors.black):
    style = ParagraphStyle(
        "body",
        fontName="Helvetica-Bold" if bold else "Helvetica",
        fontSize=size,
        leading=size * 1.22,
        textColor=color,
        alignment=TA_LEFT,
        splitLongWords=False,
    )
    paragraph = Paragraph(str(text), style)
    paragraph.wrapOn(c, width, height)
    paragraph.drawOn(c, x, y - paragraph.height)


def footer(page_number):
    c.setStrokeColor(colors.HexColor("#E5E5E5"))
    c.line(MARGIN, 27, W - MARGIN, 27)
    draw_text(str(page_number), W - MARGIN - 8, 11, 9, color=DARK_GRAY)


def new_page(page_number=None):
    if page_number is not None:
        footer(page_number)
    c.showPage()


# 1 - Capa
draw_text("RADAR DE RETORNO", MARGIN, H - 58, 23, bold=True)
c.setFont("Helvetica", 17)
c.setFillColor(DARK_GRAY)
c.drawRightString(W - MARGIN, H - 58, data["generatedAt"])
draw_wrapped("Janelas móveis<br/>de retorno", MARGIN, 205, W * 0.72, 210, 55, True)
new_page()


# 2 - Frequência histórica
draw_wrapped(data["summaryTitle"], MARGIN, H - 32, W - 2 * MARGIN, 55, 28, True)
draw_wrapped(data["summarySubtitle"], MARGIN, H - 86, W - 2 * MARGIN, 45, 15, False, colors.HexColor("#333333"))
callouts = data["comparisons"][:3]
count = max(1, len(callouts))
gap = 24
card_width = (W - 2 * MARGIN - gap * (count - 1)) / count
for index, item in enumerate(callouts):
    x = MARGIN + index * (card_width + gap)
    c.setFillColor(LIGHT_GRAY)
    c.setStrokeColor(colors.HexColor("#DDDDDD"))
    c.roundRect(x, 88, card_width, 260, 8, fill=1, stroke=1)
    draw_text(item["value"], x + 28, 240, 36, True, SERIES_COLORS[index])
    draw_wrapped(item["label"], x + 28, 200, card_width - 56, 80, 16, True)
footer(2)
new_page()


# 3 - Gráfico
draw_wrapped(data["chartTitle"], MARGIN, H - 32, W - 2 * MARGIN, 55, 28, True)
plot_x, plot_y = 78, 94
plot_w, plot_h = W - 122, H - 190
all_values = [value for series in data["chart"]["series"] for value in series["values"]]
y_min = min(0, min(all_values))
y_max = max(all_values)
padding = max(0.01, (y_max - y_min) * 0.12)
y_max += padding
y_min -= padding if y_min < 0 else 0

for tick in range(6):
    value = y_min + (y_max - y_min) * tick / 5
    py = plot_y + plot_h * tick / 5
    c.setStrokeColor(GRID)
    c.line(plot_x, py, plot_x + plot_w, py)
    c.setFillColor(DARK_GRAY)
    c.setFont("Helvetica", 9)
    c.drawRightString(plot_x - 10, py - 3, f"{value:.0%}")

categories = data["chart"]["categories"]
denominator = max(1, len(categories) - 1)
for series_index, series in enumerate(data["chart"]["series"]):
    c.setStrokeColor(SERIES_COLORS[series_index % len(SERIES_COLORS)])
    c.setLineWidth(2.2)
    if series.get("dashed"):
        c.setDash(6, 4)
    else:
        c.setDash()
    points = []
    for index, value in enumerate(series["values"]):
        px = plot_x + plot_w * index / denominator
        py = plot_y + plot_h * (value - y_min) / (y_max - y_min)
        points.append((px, py))
    for first, second in zip(points, points[1:]):
        c.line(first[0], first[1], second[0], second[1])
c.setDash()

label_positions = sorted(set([0, len(categories) // 4, len(categories) // 2, 3 * len(categories) // 4, len(categories) - 1]))
for index in label_positions:
    px = plot_x + plot_w * index / denominator
    c.setFont("Helvetica", 9)
    c.setFillColor(DARK_GRAY)
    c.drawCentredString(px, plot_y - 20, categories[index])

legend_y = 56
legend_width = (W - 2 * MARGIN) / max(1, len(data["chart"]["series"]))
for index, series in enumerate(data["chart"]["series"]):
    x = MARGIN + index * legend_width
    c.setStrokeColor(SERIES_COLORS[index % len(SERIES_COLORS)])
    c.setLineWidth(2.4)
    c.line(x, legend_y, x + 18, legend_y)
    draw_text(series["name"], x + 24, legend_y - 4, 9)
footer(3)
new_page()


# 4 - Desempenho no período selecionado
draw_wrapped(
    f"Desempenho no período - {data['periodLabel']}",
    MARGIN,
    H - 32,
    W - 2 * MARGIN,
    55,
    27,
    True,
)
plot_x, plot_y = 78, 94
plot_w, plot_h = W - 122, H - 190
period_values = [
    value for series in data["periodChart"]["series"] for value in series["values"]
]
y_min = min(period_values)
y_max = max(period_values)
padding = max(2, (y_max - y_min) * 0.12)
y_min -= padding
y_max += padding

for tick in range(6):
    value = y_min + (y_max - y_min) * tick / 5
    py = plot_y + plot_h * tick / 5
    c.setStrokeColor(GRID)
    c.line(plot_x, py, plot_x + plot_w, py)
    c.setFillColor(DARK_GRAY)
    c.setFont("Helvetica", 9)
    c.drawRightString(plot_x - 10, py - 3, f"{value:.0f}")

period_categories = data["periodChart"]["categories"]
period_denominator = max(1, len(period_categories) - 1)
for series_index, series in enumerate(data["periodChart"]["series"]):
    c.setStrokeColor(SERIES_COLORS[series_index % len(SERIES_COLORS)])
    c.setLineWidth(2.2)
    c.setDash(6, 4) if series.get("dashed") else c.setDash()
    points = []
    for index, value in enumerate(series["values"]):
        px = plot_x + plot_w * index / period_denominator
        py = plot_y + plot_h * (value - y_min) / (y_max - y_min)
        points.append((px, py))
    for first, second in zip(points, points[1:]):
        c.line(first[0], first[1], second[0], second[1])
c.setDash()

period_label_positions = sorted(set([
    0,
    len(period_categories) // 4,
    len(period_categories) // 2,
    3 * len(period_categories) // 4,
    len(period_categories) - 1,
]))
for index in period_label_positions:
    px = plot_x + plot_w * index / period_denominator
    c.setFont("Helvetica", 9)
    c.setFillColor(DARK_GRAY)
    c.drawCentredString(px, plot_y - 20, period_categories[index])

legend_y = 56
legend_width = (W - 2 * MARGIN) / max(1, len(data["periodChart"]["series"]))
for index, series in enumerate(data["periodChart"]["series"]):
    x = MARGIN + index * legend_width
    c.setStrokeColor(SERIES_COLORS[index % len(SERIES_COLORS)])
    c.setLineWidth(2.4)
    c.line(x, legend_y, x + 18, legend_y)
    draw_text(series["name"], x + 24, legend_y - 4, 9)
footer(4)
new_page()


# 5 - Tabela
draw_wrapped("O histórico mostra amplitude e recorrência", MARGIN, H - 32, W - 2 * MARGIN, 55, 27, True)
draw_wrapped(
    f"Retornos anualizados nas janelas selecionadas e desempenho acumulado em {data['periodLabel'].lower()}.",
    MARGIN,
    H - 88,
    W - 2 * MARGIN,
    45,
    14,
    False,
    colors.HexColor("#333333"),
)
table_data = [["Referência", data["periodLabel"], "Equiv. anual", "Pior janela", "Mediana", "Melhor janela"]]
for row in data["statistics"]:
    table_data.append([row["name"], row["periodReturn"], row["periodAnnual"], row["worst"], row["median"], row["best"]])
tbl = Table(table_data, colWidths=[220, 132, 122, 122, 122, 122], rowHeights=42)
tbl.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), BLUE),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
    ("FONTNAME", (1, 1), (-1, -1), "Helvetica"),
    ("FONTSIZE", (0, 0), (-1, -1), 10),
    ("ALIGN", (1, 0), (-1, -1), "CENTER"),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#C8C8C8")),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F7F7")]),
    ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
]))
tbl.wrapOn(c, W - 2 * MARGIN, H)
tbl.drawOn(c, MARGIN, H - 175 - 42 * len(table_data))
footer(5)
new_page()


# 6 - Metodologia
draw_wrapped("Como interpretar esta análise", MARGIN, H - 32, W - 2 * MARGIN, 55, 28, True)
draw_wrapped(
    "Uma análise entre apenas duas datas é uma fotografia. As janelas móveis "
    "repetem o mesmo prazo em diferentes meses de entrada e saída, mostrando "
    "se o resultado foi consistente ou se dependeu de uma data específica.",
    58,
    H - 85,
    W - 116,
    70,
    14,
    False,
    colors.HexColor("#333333"),
)
bullets = [
    f"Cada ponto usa uma janela de {data['parameters']['windowYears']} anos encerrada no mês indicado.",
    f"O histórico exibido cobre {data['parameters']['historyYears']} anos e contém janelas mensais sobrepostas.",
    "Retornos são brutos e não consideram impostos, taxas, custos ou condições específicas de produtos.",
    "Resultados históricos não representam garantia de rentabilidade futura.",
    "No S&P 500, a participação multiplica ganhos e perdas mensais; na combinação com IPCA, a inflação permanece integral.",
]
for index, bullet in enumerate(bullets):
    draw_wrapped(
        f"{index + 1:02d}  {bullet}",
        58,
        H - 165 - index * 58,
        W - 116,
        48,
        15,
        index == 3,
    )
draw_text(
    "Criado por Lucas Mesquita | Economista e assessor de investimentos | Aprovado no CFA Level II",
    58,
    60,
    10,
    bold=True,
    color=DARK_GRAY,
)
draw_text("Fontes: Banco Central do Brasil e Yahoo Finance (^GSPC).", 58, 42, 9, color=DARK_GRAY)
footer(6)
c.save()
