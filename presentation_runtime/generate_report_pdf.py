import json
import math
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle


if len(sys.argv) != 3:
    raise SystemExit("Uso: python generate_report_pdf.py entrada.json saida.pdf")

input_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])
data = json.loads(input_path.read_text(encoding="utf-8"))

PAGE = landscape(A4)
W, H = PAGE
MARGIN = 34
NAVY = colors.HexColor("#08264C")
BLUE = colors.HexColor("#1756A9")
BRIGHT_BLUE = colors.HexColor("#3279DF")
CYAN = colors.HexColor("#19BBD3")
GOLD = colors.HexColor("#E9AE28")
GREEN = colors.HexColor("#228B66")
RED = colors.HexColor("#C84B4B")
PURPLE = colors.HexColor("#7656D6")
INK = colors.HexColor("#132238")
MUTED = colors.HexColor("#5E6C7B")
LIGHT = colors.HexColor("#F1F3F6")
LIGHT_BLUE = colors.HexColor("#EAF3FC")
GRID = colors.HexColor("#D7DEE7")
WHITE = colors.white
SERIES_COLORS = [BRIGHT_BLUE, CYAN, GOLD, PURPLE, GREEN, RED]

c = canvas.Canvas(str(output_path), pagesize=PAGE)
c.setTitle("Radar de Retorno")
c.setAuthor("Radar de Retorno")
page_number = 0


def text(value, x, y, size=9, bold=False, color=INK, right=False):
    c.setFillColor(color)
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    if right:
        c.drawRightString(x, y, str(value))
    else:
        c.drawString(x, y, str(value))


def wrapped(value, x, y, width, size=9, bold=False, color=INK, leading=None):
    style = ParagraphStyle(
        "wrapped",
        fontName="Helvetica-Bold" if bold else "Helvetica",
        fontSize=size,
        leading=leading or size * 1.2,
        textColor=color,
        alignment=TA_LEFT,
        splitLongWords=True,
    )
    paragraph = Paragraph(str(value), style)
    _, height = paragraph.wrap(width, H)
    paragraph.drawOn(c, x, y - height)
    return height


def footer():
    c.setStrokeColor(GRID)
    c.setLineWidth(0.6)
    c.line(MARGIN, 24, W - MARGIN, 24)
    text("Radar de Retorno | Material informativo", MARGIN, 10, 7.5, color=MUTED)
    text(f"Página {page_number}", W - MARGIN, 10, 7.5, color=MUTED, right=True)


def finish_page():
    footer()
    c.showPage()


def page_header(title_value, subtitle=""):
    global page_number
    page_number += 1
    text("RADAR DE RETORNO", MARGIN, H - 35, 10, True, NAVY)
    text(data.get("generatedAt", ""), W - MARGIN, H - 35, 8.5, color=MUTED, right=True)
    c.setStrokeColor(NAVY)
    c.setLineWidth(1.3)
    c.line(MARGIN, H - 47, W - MARGIN, H - 47)
    text(title_value, MARGIN, H - 72, 18, True, NAVY)
    if subtitle:
        text(subtitle, MARGIN, H - 88, 8.5, color=MUTED)


def cover(title_value, subtitle):
    global page_number
    page_number += 1
    c.setFillColor(WHITE)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    bands = [NAVY, colors.HexColor("#12498E"), BRIGHT_BLUE, colors.HexColor("#5FA0EE")]
    band_width = 36
    for index, color in enumerate(bands):
        c.setFillColor(color)
        c.rect(W - band_width * (4 - index), 0, band_width, H, fill=1, stroke=0)
    text("RADAR DE RETORNO", MARGIN + 48, H - 70, 12, True, NAVY)
    c.setStrokeColor(CYAN)
    c.setLineWidth(4)
    c.line(MARGIN + 48, H - 82, MARGIN + 160, H - 82)
    wrapped(title_value, MARGIN + 48, H - 155, W * 0.58, 34, True, NAVY, 38)
    wrapped(subtitle, MARGIN + 48, H - 255, W * 0.56, 14, False, MUTED, 18)
    text("Relatório de análise e performance", MARGIN + 48, 110, 11, True, NAVY)
    text(f"Gerado em {data.get('generatedAt', '')}", MARGIN + 48, 91, 9, color=MUTED)
    finish_page()


def pct(value, digits=2):
    if value is None:
        return "—"
    return f"{float(value) * 100:.{digits}f}%".replace(".", ",")


def number(value, digits=2):
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}".replace(".", ",")


def paragraph_cell(value, size=7.5, bold=False, color=INK):
    return Paragraph(
        str(value),
        ParagraphStyle(
            "cell",
            fontName="Helvetica-Bold" if bold else "Helvetica",
            fontSize=size,
            leading=size * 1.15,
            textColor=color,
            splitLongWords=True,
        ),
    )


def draw_table(rows, x, top, width, col_widths=None, font_size=7.5, header=True):
    if not rows:
        return top
    if col_widths is None:
        col_widths = [width / len(rows[0])] * len(rows[0])
    prepared = []
    for row_index, row in enumerate(rows):
        prepared.append(
            [
                paragraph_cell(value, font_size, bold=header and row_index == 0,
                               color=WHITE if header and row_index == 0 else INK)
                for value in row
            ]
        )
    table = Table(prepared, colWidths=col_widths, repeatRows=1 if header else 0)
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.35, GRID),
        ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [WHITE, LIGHT]),
    ]
    if header:
        commands.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ]
        )
    table.setStyle(TableStyle(commands))
    _, height = table.wrap(width, H)
    table.drawOn(c, x, top - height)
    return top - height


def draw_metric_cards(items, top, columns=4):
    gap = 10
    card_width = (W - 2 * MARGIN - gap * (columns - 1)) / columns
    card_height = 58
    for index, (label, value) in enumerate(items):
        row = index // columns
        column = index % columns
        x = MARGIN + column * (card_width + gap)
        y = top - row * (card_height + gap) - card_height
        c.setFillColor(LIGHT_BLUE if index % 2 == 0 else LIGHT)
        c.setStrokeColor(GRID)
        c.roundRect(x, y, card_width, card_height, 4, fill=1, stroke=1)
        wrapped(label, x + 9, y + card_height - 10, card_width - 18, 7.5, False, MUTED)
        wrapped(value, x + 9, y + 25, card_width - 18, 13, True, NAVY)
    rows = math.ceil(len(items) / columns)
    return top - rows * (card_height + gap)


def draw_line_chart(
    chart, x, y, width, height, percent_axis=False, percentage_points=False
):
    series_list = chart.get("series", [])
    if not series_list:
        return
    values = [float(value) for series in series_list for value in series.get("values", [])]
    if not values:
        return
    y_min, y_max = min(values), max(values)
    if percent_axis:
        y_min = min(0, y_min)
    padding = max(0.01 if percent_axis else 1.0, (y_max - y_min) * 0.12)
    y_min -= padding
    y_max += padding
    for tick in range(5):
        value = y_min + (y_max - y_min) * tick / 4
        py = y + height * tick / 4
        c.setStrokeColor(GRID)
        c.setLineWidth(0.5)
        c.line(x, py, x + width, py)
        if percent_axis:
            label = pct(value, 1)
        elif percentage_points:
            label = f"{value:.1f}%".replace(".", ",")
        else:
            label = f"{value:.0f}"
        text(label, x - 8, py - 3, 7, color=MUTED, right=True)
    for series_index, series in enumerate(series_list):
        values_series = [float(value) for value in series.get("values", [])]
        denominator = max(1, len(values_series) - 1)
        c.setStrokeColor(SERIES_COLORS[series_index % len(SERIES_COLORS)])
        c.setLineWidth(1.8)
        if series.get("dashed"):
            c.setDash(5, 3)
        else:
            c.setDash()
        points = []
        for index, value in enumerate(values_series):
            px = x + width * index / denominator
            py = y + height * (value - y_min) / max(1e-9, y_max - y_min)
            points.append((px, py))
        for first, second in zip(points, points[1:]):
            c.line(first[0], first[1], second[0], second[1])
    c.setDash()
    categories = chart.get("categories", [])
    if categories:
        positions = sorted(set([0, len(categories) // 2, len(categories) - 1]))
        for index in positions:
            px = x + width * index / max(1, len(categories) - 1)
            text(categories[index], px, y - 15, 7, color=MUTED, right=index == len(categories) - 1)
    legend_x = x
    legend_y = y - 34
    for index, series in enumerate(series_list):
        if legend_x + 155 > x + width:
            legend_x = x
            legend_y -= 14
        c.setFillColor(SERIES_COLORS[index % len(SERIES_COLORS)])
        c.circle(legend_x + 4, legend_y + 3, 3, fill=1, stroke=0)
        label = str(series.get("name", ""))
        if len(label) > 24:
            label = label[:23] + "…"
        text(label, legend_x + 11, legend_y, 7, color=INK)
        legend_x += 155


def methodology_page(source_text):
    page_header("Como interpretar este relatório")
    paragraphs = [
        "O relatório organiza as informações selecionadas no Radar de Retorno para facilitar a apresentação e a comparação.",
        "Rentabilidade passada não representa garantia de resultados futuros. Volatilidade, drawdown e cenários são medidas históricas ou simulações, não previsões.",
        "Os cálculos são brutos e podem não considerar impostos, taxas, custos, liquidez, risco de crédito ou condições específicas de cada produto.",
        source_text,
    ]
    y = H - 125
    for index, item in enumerate(paragraphs, start=1):
        text(f"{index:02d}", MARGIN, y, 14, True, BRIGHT_BLUE)
        height = wrapped(item, MARGIN + 38, y + 3, W - 2 * MARGIN - 38, 10, False, INK, 14)
        y -= max(52, height + 22)
    c.setFillColor(LIGHT_BLUE)
    c.roundRect(MARGIN, 62, W - 2 * MARGIN, 60, 4, fill=1, stroke=0)
    text("Uso recomendado", MARGIN + 14, 100, 9, True, NAVY)
    wrapped(
        "Utilize este material em conjunto com documentos oficiais, regulamentos e uma avaliação adequada ao perfil e aos objetivos do cliente.",
        MARGIN + 14,
        88,
        W - 2 * MARGIN - 28,
        8.5,
        False,
        MUTED,
    )
    finish_page()


def render_funds():
    cover(data.get("title", "Análise de fundos"), data.get("subtitle", ""))
    page_header("Visão geral dos fundos", data.get("subtitle", ""))
    funds = data.get("funds", [])
    columns = min(3, max(1, len(funds)))
    gap = 12
    card_width = (W - 2 * MARGIN - gap * (columns - 1)) / columns
    for index, fund in enumerate(funds):
        row = index // columns
        column = index % columns
        x = MARGIN + column * (card_width + gap)
        y = H - 122 - row * 150
        c.setFillColor(LIGHT)
        c.setStrokeColor(GRID)
        c.roundRect(x, y - 126, card_width, 126, 4, fill=1, stroke=1)
        c.setFillColor(NAVY)
        c.rect(x, y - 27, card_width, 27, fill=1, stroke=0)
        wrapped(fund.get("name", ""), x + 8, y - 7, card_width - 16, 7.5, True, WHITE, 8.5)
        details = [
            ("CNPJ", fund.get("cnpj", "—")),
            ("Gestão", fund.get("manager", "—")),
            ("Administrador", fund.get("administrator", "—")),
            ("Classificação", fund.get("classification", "—")),
        ]
        dy = y - 44
        for label, value in details:
            text(label, x + 8, dy, 6.8, color=MUTED)
            wrapped(value, x + 70, dy + 2, card_width - 78, 6.8, True, INK, 7.5)
            dy -= 20
    summary_rows = [["Fundo", "Retorno", "Volatilidade a.a.", "Sharpe", "Maior queda"]]
    for item in data.get("summary", []):
        summary_rows.append(
            [
                item.get("name", ""),
                pct(item.get("periodReturn")),
                pct(item.get("volatility")),
                number(item.get("sharpe")),
                pct(item.get("drawdown")),
            ]
        )
    table_top = 230 if len(funds) <= 3 else 90
    draw_table(summary_rows, MARGIN, table_top, W - 2 * MARGIN,
               [310, 105, 115, 90, 105], 7.2)
    finish_page()

    returns = data.get("returnsByPeriod", {})
    return_columns = returns.get("columns", [])
    return_rows = returns.get("rows", [])
    if return_columns:
        page_header("Rentabilidade por período", data.get("subtitle", ""))
        first_width = 205
        remaining = W - 2 * MARGIN - first_width
        other_width = remaining / max(1, len(return_columns) - 1)
        draw_table(
            [return_columns] + return_rows,
            MARGIN,
            H - 112,
            W - 2 * MARGIN,
            [first_width] + [other_width] * (len(return_columns) - 1),
            6.3,
        )
        if any("Desde o início" in str(column) for column in return_columns):
            text(
                "Desde o início usa o primeiro período comum disponível para os ativos selecionados.",
                MARGIN,
                55,
                7.5,
                color=MUTED,
            )
        finish_page()

    page_header("Evolução da rentabilidade", data.get("subtitle", ""))
    draw_line_chart(data.get("chart", {}), 72, 125, W - 115, H - 245, False)
    text("Índice base 100 no início do período selecionado.", MARGIN, 70, 8, color=MUTED)
    finish_page()

    risk = data.get("risk", {})
    rolling_return = risk.get("rollingReturn", {})
    rolling_volatility = risk.get("rollingVolatility", {})
    if rolling_return.get("series") or rolling_volatility.get("series"):
        page_header(
            "Análise de risco - janelas móveis",
            f"{risk.get('label', '')} | Janela: {risk.get('windowDays', 21)} dias úteis",
        )
        text("Retorno efetivo móvel", MARGIN, H - 116, 10, True, NAVY)
        draw_line_chart(rolling_return, 70, 330, W - 112, 115, True)
        text("Volatilidade móvel anualizada", MARGIN, 265, 10, True, NAVY)
        draw_line_chart(rolling_volatility, 70, 82, W - 112, 115, True)
        finish_page()

    drawdown_chart = risk.get("drawdown", {})
    moving_windows = data.get("movingWindows", {})
    moving_chart = moving_windows.get("chart", {})
    if drawdown_chart.get("series") or moving_chart.get("series"):
        page_header("Quedas e consistência histórica")
        current_y = H - 116
        if drawdown_chart.get("series"):
            text("Drawdown", MARGIN, current_y, 10, True, NAVY)
            draw_line_chart(drawdown_chart, 70, 315, W - 112, 120, True)
            current_y = 250
        if moving_chart.get("series"):
            text(
                f"Janelas móveis - {moving_windows.get('label', '')}",
                MARGIN,
                current_y,
                10,
                True,
                NAVY,
            )
            draw_line_chart(moving_chart, 70, 72, W - 112, 120, True)
        finish_page()

    monthly = data.get("monthly", {})
    columns_monthly = monthly.get("columns", [])
    rows_monthly = monthly.get("rows", [])
    comparison = bool(columns_monthly and columns_monthly[0] == "Fundo")
    if comparison:
        chunks = []
        for column_start in range(1, len(columns_monthly), 12):
            chunk_columns = [columns_monthly[0]] + columns_monthly[
                column_start:column_start + 12
            ]
            chunk_rows = [
                [row[0]] + row[column_start:column_start + 12]
                for row in rows_monthly
            ]
            chunks.append((chunk_columns, chunk_rows))
        if not chunks:
            chunks = [(columns_monthly, rows_monthly)]
    else:
        row_chunks = [
            rows_monthly[index:index + 12]
            for index in range(0, len(rows_monthly), 12)
        ] or [[]]
        chunks = [(columns_monthly, rows) for rows in row_chunks]
    for chunk_index, (chunk_columns, chunk_rows) in enumerate(chunks):
        page_header(
            "Rentabilidade mensal" + (f" - continuação {chunk_index + 1}" if chunk_index else ""),
            "Anos nas linhas para análise individual; fundos nas linhas para comparação.",
        )
        formatted = [chunk_columns]
        for row in chunk_rows:
            formatted_row = []
            for cell_index, value in enumerate(row):
                formatted_row.append(str(value) if cell_index == 0 else pct(value))
            formatted.append(formatted_row)
        first_width = 155 if comparison else 48
        remaining = W - 2 * MARGIN - first_width
        other_width = remaining / max(1, len(chunk_columns) - 1)
        draw_table(formatted, MARGIN, H - 115, W - 2 * MARGIN,
                   [first_width] + [other_width] * (len(chunk_columns) - 1), 6.2)
        finish_page()
    methodology_page("Fontes: Comissão de Valores Mobiliários (CVM) e benchmarks públicos selecionados.")


def render_indices():
    cover("Análise de índices", data.get("summarySubtitle", ""))
    page_header(data.get("summaryTitle", "Visão histórica"), data.get("summarySubtitle", ""))
    cards = [(item.get("label", ""), item.get("value", "")) for item in data.get("comparisons", [])]
    if cards:
        draw_metric_cards(cards, H - 120, min(3, len(cards)))
    stats = [["Referência", data.get("periodLabel", "Período"), "Equiv. anual", "Pior", "Mediana", "Melhor"]]
    for row in data.get("statistics", []):
        stats.append([
            row.get("name", ""), row.get("periodReturn", ""), row.get("periodAnnual", ""),
            row.get("worst", ""), row.get("median", ""), row.get("best", ""),
        ])
    draw_table(stats, MARGIN, 260, W - 2 * MARGIN, [260, 100, 95, 95, 95, 95], 7)
    finish_page()

    page_header(data.get("chartTitle", "Janelas móveis"))
    draw_line_chart(data.get("chart", {}), 72, 125, W - 115, H - 245, True)
    finish_page()

    page_header(f"Desempenho no período - {data.get('periodLabel', '')}")
    draw_line_chart(data.get("periodChart", {}), 72, 125, W - 115, H - 245, False)
    finish_page()

    methodology_page("Fontes: Banco Central do Brasil e Yahoo Finance (^GSPC e BRL=X).")


def render_fixed_income():
    cover(data.get("title", "Simulação de renda fixa"), data.get("subtitle", ""))
    page_header("Premissas e resultado", data.get("subtitle", ""))
    parameters = data.get("parameters", [])
    summary = data.get("summary", [])
    cards = [(label, value) for label, value in summary]
    bottom = draw_metric_cards(cards, H - 115, 4)
    text("Premissas da simulação", MARGIN, bottom - 8, 10, True, NAVY)
    param_rows = [["Parâmetro", "Valor"]] + parameters
    draw_table(param_rows, MARGIN, bottom - 20, W - 2 * MARGIN, [300, 465], 8)
    finish_page()

    page_header("Sensibilidade à taxa de mercado", "Variação estimada do preço por vencimento.")
    sensitivity = data.get("sensitivity", {})
    chart = {
        "categories": [],
        "series": [
            {"name": item.get("name", ""), "values": item.get("y", [])}
            for item in sensitivity.get("series", [])
        ],
    }
    first_series = sensitivity.get("series", [])[:1]
    if first_series:
        chart["categories"] = [f"{value:.1f}%" for value in first_series[0].get("x", [])]
    draw_line_chart(chart, 72, 125, W - 115, H - 245, percentage_points=True)
    finish_page()

    page_header("Cenários de taxa")
    scenarios = data.get("scenarios", {})
    scenario_rows = [scenarios.get("columns", [])] + scenarios.get("rows", [])
    draw_table(scenario_rows, MARGIN, H - 110, W - 2 * MARGIN, [120, 120, 140, 140, 245], 7.5)
    finish_page()

    cashflows = data.get("cashflows", {})
    cashflow_rows = cashflows.get("rows", [])
    chunks = [cashflow_rows[index:index + 18] for index in range(0, len(cashflow_rows), 18)] or [[]]
    for index, chunk in enumerate(chunks):
        page_header("Fluxo de pagamentos" + (f" - continuação {index + 1}" if index else ""))
        rows = [cashflows.get("columns", [])] + chunk
        draw_table(rows, MARGIN, H - 110, W - 2 * MARGIN, [220, 270, 275], 7.5)
        finish_page()
    methodology_page("A simulação usa as premissas informadas pelo usuário e não estima inadimplência, spread de crédito ou liquidez.")


report_type = data.get("reportType", "indices")
if report_type == "fundos":
    render_funds()
elif report_type == "renda_fixa":
    render_fixed_income()
else:
    render_indices()

c.save()
