"""
Invoice PDF generation — an itemized bill for one invoice: what's charged,
what's been paid against it, and the remaining balance. Deliberately
narrower than statement_service.py (which covers a student's whole
account) and receipt_service.py (which documents one payment already
received) — this is the "here's what you're being billed for" document,
matching the itemized breakdown a parent already sees expanded in the
Invoices page.
"""

import io
from datetime import datetime, timezone
from decimal import Decimal

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_RIGHT, TA_CENTER

INK_900 = colors.HexColor("#16213D")
INK_600 = colors.HexColor("#3D5280")
INK_200 = colors.HexColor("#E4E2DA")
EMERALD_700 = colors.HexColor("#16543C")
CLAY_700 = colors.HexColor("#8A3626")

INVOICE_STATUS_LABELS = {
    "PAID": "Paid",
    "PARTIALLY_PAID": "Partially paid",
    "ISSUED": "Issued",
    "OVERDUE": "Overdue",
    "DRAFT": "Draft",
    "CANCELLED": "Cancelled",
}


def generate_invoice_pdf(
    invoice_number: str,
    school_name: str,
    student_name: str,
    admission_number: str,
    class_name: str | None,
    term_name: str,
    currency: str,
    due_date: datetime,
    status: str,
    total_amount: Decimal,
    amount_paid: Decimal,
    items: list[dict],  # [{name, category, amount}]
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=22 * mm,
        bottomMargin=22 * mm,
        leftMargin=22 * mm,
        rightMargin=22 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("InvTitle", parent=styles["Title"], textColor=INK_900, fontSize=19, spaceAfter=2)
    subtitle_style = ParagraphStyle("InvSubtitle", parent=styles["Normal"], textColor=INK_600, fontSize=10)
    label_style = ParagraphStyle("Label", parent=styles["Normal"], textColor=INK_600, fontSize=9)
    balance_style = ParagraphStyle(
        "Balance", parent=styles["Normal"],
        textColor=CLAY_700 if (total_amount - amount_paid) > 0 else EMERALD_700,
        fontSize=22, alignment=TA_CENTER, spaceBefore=4, spaceAfter=4,
    )
    footer_style = ParagraphStyle("Footer", parent=styles["Normal"], textColor=INK_600, fontSize=8, alignment=TA_CENTER)

    def fmt_money(amt: Decimal) -> str:
        return f"{currency} {amt:,.2f}"

    balance = total_amount - amount_paid
    story = []

    story.append(Paragraph(school_name, title_style))
    story.append(Paragraph(f"Invoice — {term_name}", subtitle_style))
    story.append(Spacer(1, 3 * mm))
    student_line = f"{student_name} ({admission_number})"
    if class_name:
        student_line += f" · {class_name}"
    story.append(Paragraph(student_line, subtitle_style))
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width="100%", thickness=1, color=INK_200))
    story.append(Spacer(1, 6 * mm))

    details = [
        ["Invoice No.", invoice_number],
        ["Due date", due_date.strftime("%d %B %Y")],
        ["Status", INVOICE_STATUS_LABELS.get(status, status.replace("_", " ").title())],
    ]
    detail_table = Table(details, colWidths=[45 * mm, 105 * mm])
    detail_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TEXTCOLOR", (0, 0), (0, -1), INK_600),
                ("TEXTCOLOR", (1, 0), (1, -1), INK_900),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(detail_table)
    story.append(Spacer(1, 8 * mm))

    story.append(Paragraph("Itemized charges", ParagraphStyle("Section", parent=styles["Heading2"], textColor=INK_900, fontSize=12)))
    story.append(Spacer(1, 2 * mm))
    if items:
        rows = [["Item", "Category", "Amount"]]
        for item in items:
            rows.append([item["name"], item["category"].replace("_", " ").title(), fmt_money(item["amount"])])
        rows.append(["", "Total", fmt_money(total_amount)])
        item_table = Table(rows, colWidths=[75 * mm, 55 * mm, 45 * mm])
        item_table.setStyle(
            TableStyle(
                [
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("TEXTCOLOR", (0, 0), (-1, 0), INK_600),
                    ("TEXTCOLOR", (0, 1), (-1, -2), INK_900),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                    ("TEXTCOLOR", (0, -1), (-1, -1), INK_900),
                    ("ALIGN", (2, 0), (2, -1), "RIGHT"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("LINEBELOW", (0, 0), (-1, -2), 0.4, INK_200),
                    ("LINEABOVE", (0, -1), (-1, -1), 0.8, INK_900),
                ]
            )
        )
        story.append(item_table)
    else:
        story.append(Paragraph("No itemized breakdown available for this invoice.", label_style))

    story.append(Spacer(1, 10 * mm))
    story.append(HRFlowable(width="100%", thickness=1, color=INK_200))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Balance due" if balance > 0 else "Paid in full", label_style))
    story.append(Paragraph(fmt_money(balance if balance > 0 else total_amount), balance_style))
    if amount_paid > 0 and balance > 0:
        story.append(Paragraph(f"{fmt_money(amount_paid)} already paid toward this invoice", label_style))

    story.append(Spacer(1, 10 * mm))
    story.append(HRFlowable(width="100%", thickness=1, color=INK_200))
    story.append(Spacer(1, 4 * mm))
    story.append(
        Paragraph(
            f"Generated by Ledgr on {datetime.now(timezone.utc).strftime('%d %B %Y')}. "
            "This invoice reflects charges billed to the student's fee account.",
            footer_style,
        )
    )

    doc.build(story)
    return buffer.getvalue()
