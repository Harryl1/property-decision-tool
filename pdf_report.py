import os
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    Image,
    KeepTogether
)

# ==========================================
# Brand configuration
# ==========================================

BRAND = {
    "name": "equiome",
    "primary": colors.HexColor("#12344D"),      # deep slate/navy
    "accent": colors.HexColor("#2A7F9E"),       # muted blue-teal
    "text": colors.HexColor("#243342"),
    "subtext": colors.HexColor("#5B6573"),
    "border": colors.HexColor("#D7DEE7"),
    "card_bg": colors.HexColor("#F5F7FA"),
    "highlight_bg": colors.HexColor("#EAF4F8"),
    "white": colors.white,
}


# ==========================================
# Helpers
# ==========================================

def safe_text(value, fallback="—"):
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback

def format_currency(value, prefix="£", decimals=0):
    try:
        if value is None:
            return f"{prefix}0"
        return f"{prefix}{float(value):,.{decimals}f}"
    except Exception:
        return f"{prefix}0"

def format_currency_range(low, high, prefix="£", decimals=0):
    return f"{format_currency(low, prefix, decimals)} – {format_currency(high, prefix, decimals)}"

def ensure_parent_dir(filepath):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

def build_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="ReportTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        textColor=BRAND["primary"],
        spaceAfter=4,
    ))

    styles.add(ParagraphStyle(
        name="ReportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=BRAND["subtext"],
        spaceAfter=8,
    ))

    styles.add(ParagraphStyle(
        name="SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=14,
        textColor=BRAND["primary"],
        spaceAfter=8,
        spaceBefore=4,
    ))

    styles.add(ParagraphStyle(
        name="Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=BRAND["text"],
        spaceAfter=6,
    ))

    styles.add(ParagraphStyle(
        name="Small",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=BRAND["subtext"],
    ))

    styles.add(ParagraphStyle(
        name="Label",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=10,
        textColor=BRAND["subtext"],
    ))

    styles.add(ParagraphStyle(
        name="MetricLabel",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=10,
        textColor=BRAND["subtext"],
        spaceAfter=4,
    ))

    styles.add(ParagraphStyle(
        name="MetricValue",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=18,
        textColor=BRAND["primary"],
    ))

    styles.add(ParagraphStyle(
        name="MetricValueHighlight",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=20,
        textColor=BRAND["accent"],
    ))

    styles.add(ParagraphStyle(
        name="SummaryKicker",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=BRAND["accent"],
        spaceAfter=6,
    ))

    styles.add(ParagraphStyle(
        name="SummaryHeadline",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=BRAND["primary"],
        spaceAfter=6,
    ))

    styles.add(ParagraphStyle(
        name="SummaryBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=BRAND["text"],
    ))

    styles.add(ParagraphStyle(
        name="Footer",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=BRAND["subtext"],
        alignment=TA_RIGHT,
    ))

    return styles


# ==========================================
# Page chrome
# ==========================================

def draw_page_chrome(canvas, doc):
    canvas.saveState()

    page_width, page_height = A4

    # Thin top accent line
    canvas.setStrokeColor(BRAND["accent"])
    canvas.setLineWidth(2)
    canvas.line(doc.leftMargin, page_height - 12 * mm, page_width - doc.rightMargin, page_height - 12 * mm)

    # Footer line
    canvas.setStrokeColor(BRAND["border"])
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, 14 * mm, page_width - doc.rightMargin, 14 * mm)

    # Footer text
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(BRAND["subtext"])
    canvas.drawString(doc.leftMargin, 9 * mm, f"{BRAND['name']} property report")
    canvas.drawRightString(page_width - doc.rightMargin, 9 * mm, f"Page {canvas.getPageNumber()}")

    canvas.restoreState()


# ==========================================
# Building blocks
# ==========================================

def metric_card(label, value, styles, width, highlight=False):
    bg = BRAND["highlight_bg"] if highlight else BRAND["card_bg"]
    value_style = styles["MetricValueHighlight"] if highlight else styles["MetricValue"]

    t = Table(
        [[
            Paragraph(label, styles["MetricLabel"]),
        ], [
            Paragraph(value, value_style),
        ]],
        colWidths=[width]
    )

    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("BOX", (0, 0), (-1, -1), 0.8, BRAND["border"]),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t

def summary_box(report_data, styles, content_width):
    headline = f"Estimated maximum budget: {format_currency(report_data.get('max_budget'))}"

    body_text = (
        f"Based on your current position, your estimated available equity is "
        f"<b>{format_currency(report_data.get('net_proceeds'))}</b> and your indicative "
        f"borrowing power is <b>{format_currency(report_data.get('borrowing_power'))}</b>."
    )

    table = Table(
        [[Paragraph("AT A GLANCE", styles["SummaryKicker"])],
         [Paragraph(headline, styles["SummaryHeadline"])],
         [Paragraph(body_text, styles["SummaryBody"])]],
        colWidths=[content_width]
    )

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND["highlight_bg"]),
        ("BOX", (0, 0), (-1, -1), 0.8, BRAND["border"]),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))
    return table

def detail_row(label, value, styles, total_width):
    label_width = 58 * mm
    value_width = total_width - label_width

    t = Table(
        [[
            Paragraph(f"<b>{label}</b>", styles["Body"]),
            Paragraph(safe_text(value), styles["Body"])
        ]],
        colWidths=[label_width, value_width]
    )

    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t

def boxed_section(title, body_flowables, styles, content_width):
    inner = [[Paragraph(title, styles["SectionHeading"])]]
    for item in body_flowables:
        inner.append([item])

    t = Table(inner, colWidths=[content_width])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND["card_bg"]),
        ("BOX", (0, 0), (-1, -1), 0.8, BRAND["border"]),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t


# ==========================================
# Main report function
# ==========================================

def generate_pdf_report(report_data, filepath, logo_path=None):
    """
    report_data expected keys:
    {
        "name": "Jane Smith",
        "email": "jane@example.com",
        "valuation_low": 425000,
        "valuation_high": 450000,
        "moving_costs": 12000,
        "net_proceeds": 433000,
        "borrowing_power": 280000,
        "max_budget": 713000,
        "recommendation": "Based on your estimated equity and borrowing position...",
        "selected_services": ["Local agent valuation", "Mortgage advice", "Conveyancing quote"]  # optional
    }
    """

    ensure_parent_dir(filepath)

    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = build_styles()
    story = []

    content_width = A4[0] - doc.leftMargin - doc.rightMargin

    # ------------------------------------------
    # Header / branding
    # ------------------------------------------
    header_left = []
    if logo_path and os.path.exists(logo_path):
        try:
            print("Trying to load logo from:", logo_path)
            img = Image(logo_path, width=36 * mm, height=12 * mm)
            img.hAlign = "LEFT"
            header_left.append(img)
            header_left.append(Spacer(1, 4))
            print("Logo loaded successfully")
        except Exception as e:
            print("Logo failed to load:", str(e))
    else:
        print("Logo path missing or file does not exist:", logo_path)

    header_left.append(Paragraph("Your Property Report", styles["ReportTitle"]))
    header_left.append(Paragraph(
        "A personalised view of your equity and next-property budget.",
        styles["ReportSubtitle"]
    ))

    prepared_for = (
        f"<b>Prepared for:</b> {safe_text(report_data.get('name'))}<br/>"
        f"<b>Email:</b> {safe_text(report_data.get('email'))}<br/>"
        f"<b>Date:</b> {datetime.now().strftime('%d %B %Y')}"
    )

    header_table = Table(
        [[
            header_left,
            Paragraph(prepared_for, styles["Body"])
        ]],
        colWidths=[content_width * 0.62, content_width * 0.38]
    )
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))

    story.append(header_table)
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=0.6, color=BRAND["border"]))
    story.append(Spacer(1, 14))

    # ------------------------------------------
    # Summary panel
    # ------------------------------------------
    story.append(summary_box(report_data, styles, content_width))
    story.append(Spacer(1, 16))

    # ------------------------------------------
    # Financial breakdown heading
    # ------------------------------------------
    story.append(Paragraph("Estimated financial position", styles["SectionHeading"]))

    card_gap = 8
    col_width = (content_width - card_gap) / 2

    row_1 = Table([[
        metric_card(
            "Estimated property value",
            format_currency_range(
                report_data.get("valuation_low"),
                report_data.get("valuation_high")
            ),
            styles,
            col_width
        ),
        metric_card(
            "Estimated sale and moving costs",
            format_currency(report_data.get("moving_costs")),
            styles,
            col_width
        )
    ]], colWidths=[col_width, col_width])

    row_1.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    row_2 = Table([[
        metric_card(
            "Estimated available equity",
            format_currency(report_data.get("net_proceeds")),
            styles,
            col_width
        ),
        metric_card(
            "Estimated borrowing power",
            format_currency(report_data.get("borrowing_power")),
            styles,
            col_width
        )
    ]], colWidths=[col_width, col_width])

    row_2.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    row_3 = Table([[
        metric_card(
            "Estimated maximum purchase budget",
            format_currency(report_data.get("max_budget")),
            styles,
            content_width,
            highlight=True
        )
    ]], colWidths=[content_width])

    row_3.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    story.append(row_1)
    story.append(Spacer(1, 8))
    story.append(row_2)
    story.append(Spacer(1, 8))
    story.append(row_3)
    story.append(Spacer(1, 16))

    # ------------------------------------------
    # Recommendation section
    # ------------------------------------------
    recommendation_text = safe_text(
        report_data.get("recommendation"),
        "We recommend reviewing your figures with a local expert before making any property decisions."
    )

    recommendation_items = [
        Paragraph(
            recommendation_text,
            styles["Body"]
        )
    ]

    recommendation_box = boxed_section(
        "Recommended next step",
        recommendation_items,
        styles,
        content_width
    )
    story.append(recommendation_box)
    story.append(Spacer(1, 16))

    # ------------------------------------------
    # Optional client details / assumptions
    # ------------------------------------------
    assumptions_items = [
        detail_row("Client name", safe_text(report_data.get("name")), styles, content_width),
        detail_row("Email", safe_text(report_data.get("email")), styles, content_width),
        detail_row("Address", safe_text(report_data.get("address")), styles, content_width),
        detail_row(
            "Valuation range",
            format_currency_range(report_data.get("valuation_low"), report_data.get("valuation_high")),
            styles,
            content_width
        ),
        detail_row(
            "Available equity",
            format_currency(report_data.get("net_proceeds")),
            styles,
            content_width
        ),
        detail_row(
            "Maximum budget",
            format_currency(report_data.get("max_budget")),
            styles,
            content_width
        ),
    ]

    assumptions_box = boxed_section(
        "Report summary",
        assumptions_items,
        styles,
        content_width
    )
    story.append(assumptions_box)

    # ------------------------------------------
    # Optional services requested
    # ------------------------------------------
    selected_services = report_data.get("selected_services") or []
    if selected_services:
        story.append(Spacer(1, 16))
        service_lines = [Paragraph("You asked to hear about:", styles["Body"])]
        for service in selected_services:
            service_lines.append(Paragraph(f"• {safe_text(service)}", styles["Body"]))

        services_box = boxed_section(
            "Next-step services",
            service_lines,
            styles,
            content_width
        )
        story.append(services_box)

    # ------------------------------------------
    # Disclaimer
    # ------------------------------------------
    story.append(Spacer(1, 18))
    story.append(HRFlowable(width="100%", thickness=0.6, color=BRAND["border"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "This report is an indicative estimate only and should not be treated as financial, mortgage, "
        "or legal advice. Final figures may vary depending on lender criteria, local market conditions, "
        "sale price achieved, and transaction costs.",
        styles["Small"]
    ))

    doc.build(
        story,
        onFirstPage=draw_page_chrome,
        onLaterPages=draw_page_chrome
    )

    return filepath