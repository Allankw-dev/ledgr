"""
Fee statement generation — a full financial record for a student across
one or more terms: every invoice raised and every payment received,
running balance, in the order a parent or bursar would want to review
them. Deliberately separate from receipt_service.py: a receipt documents
ONE payment; a statement documents the whole account.
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
CLAY_700 = colors.HexColor("#8A3B2B")

METHOD_LABELS = {
    "MPESA": "M-Pesa",
    "BANK_TRANSFER": "Bank Transfer",
    "CASH": "Cash",
    "CARD": "Card",
    "CHEQUE": "Cheque",
    "OTHER": "Other",
}

INVOICE_STATUS_LABELS = {
    "PAID": "Paid",
    "PARTIALLY_PAID": "Partially paid",
    "ISSUED": "Issued",
    "OVERDUE": "Overdue",
    "DRAFT": "Draft",
    "CANCELLED": "Cancelled",
}


def generate_fee_statement_pdf(
    school_name: str,
    student_name: str,
    admission_number: str,
    class_name: str | None,
    currency: str,
    period_label: str,  # e.g. "Term 2 2026" or "All terms"
    invoices: list[dict],  # [{term_name, due_date, total_amount, amount_paid, status}]
    payments: list[dict],  # [{paid_at, amount, method, reference_code}]
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("StmtTitle", parent=styles["Title"], textColor=INK_900, fontSize=18, spaceAfter=2)
    subtitle_style = ParagraphStyle("StmtSubtitle", parent=styles["Normal"], textColor=INK_600, fontSize=10)
    section_style = ParagraphStyle(
        "Section", parent=styles["Heading2"], textColor=INK_900, fontSize=12, spaceBefore=8, spaceAfter=4
    )
    label_style = ParagraphStyle("Label", parent=styles["Normal"], textColor=INK_600, fontSize=9)
    footer_style = ParagraphStyle("Footer", parent=styles["Normal"], textColor=INK_600, fontSize=8, alignment=TA_CENTER)
    right_style = ParagraphStyle("Right", parent=styles["Normal"], fontSize=9, alignment=TA_RIGHT)

    def fmt_money(amt: Decimal) -> str:
        return f"{currency} {amt:,.2f}"

    def fmt_date(dt: datetime | None) -> str:
        return dt.strftime("%d %b %Y") if dt else "—"

    total_billed = sum((inv["total_amount"] for inv in invoices), Decimal("0"))
    total_paid = sum((inv["amount_paid"] for inv in invoices), Decimal("0"))
    total_outstanding = total_billed - total_paid

    story = []

    story.append(Paragraph(school_name, title_style))
    story.append(Paragraph(f"Fee Statement — {period_label}", subtitle_style))
    story.append(Spacer(1, 3 * mm))
    student_line = f"{student_name} ({admission_number})"
    if class_name:
        student_line += f" · {class_name}"
    story.append(Paragraph(student_line, subtitle_style))
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width="100%", thickness=1, color=INK_200))
    story.append(Spacer(1, 6 * mm))

    # Summary strip
    summary_data = [
        ["Total billed", "Total paid", "Balance outstanding"],
        [fmt_money(total_billed), fmt_money(total_paid), fmt_money(total_outstanding)],
    ]
    summary_table = Table(summary_data, colWidths=[56.6 * mm] * 3)
    summary_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("TEXTCOLOR", (0, 0), (-1, 0), INK_600),
                ("FONTSIZE", (0, 1), (-1, 1), 14),
                ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, 1), (1, 1), INK_900),
                ("TEXTCOLOR", (2, 1), (2, 1), CLAY_700 if total_outstanding > 0 else EMERALD_700),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
                ("TOPPADDING", (0, 1), (-1, 1), 2),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, INK_200),
                ("BOX", (0, 0), (-1, -1), 0.5, INK_200),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 8 * mm))

    # Invoices section
    story.append(Paragraph("Invoices", section_style))
    if invoices:
        rows = [["Term", "Due date", "Billed", "Paid", "Balance", "Status"]]
        for inv in invoices:
            balance = inv["total_amount"] - inv["amount_paid"]
            rows.append(
                [
                    inv["term_name"],
                    fmt_date(inv["due_date"]),
                    fmt_money(inv["total_amount"]),
                    fmt_money(inv["amount_paid"]),
                    fmt_money(balance),
                    INVOICE_STATUS_LABELS.get(inv["status"], inv["status"].replace("_", " ").title()),
                ]
            )
        inv_table = Table(rows, colWidths=[32 * mm, 26 * mm, 28 * mm, 28 * mm, 28 * mm, 28 * mm])
        inv_table.setStyle(
            TableStyle(
                [
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("TEXTCOLOR", (0, 0), (-1, 0), INK_600),
                    ("TEXTCOLOR", (0, 1), (-1, -1), INK_900),
                    ("ALIGN", (2, 0), (4, -1), "RIGHT"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.4, INK_200),
                ]
            )
        )
        story.append(inv_table)
    else:
        story.append(Paragraph("No invoices in this period.", label_style))

    story.append(Spacer(1, 8 * mm))

    # Payment history section
    story.append(Paragraph("Payment History", section_style))
    if payments:
        rows = [["Date", "Method", "Reference", "Amount"]]
        for p in sorted(payments, key=lambda x: x["paid_at"] or datetime.min.replace(tzinfo=timezone.utc)):
            rows.append(
                [
                    fmt_date(p["paid_at"]),
                    METHOD_LABELS.get(p["method"].upper(), p["method"].replace("_", " ").title()),
                    p.get("reference_code") or "—",
                    fmt_money(p["amount"]),
                ]
            )
        pay_table = Table(rows, colWidths=[30 * mm, 35 * mm, 55 * mm, 50 * mm])
        pay_table.setStyle(
            TableStyle(
                [
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("TEXTCOLOR", (0, 0), (-1, 0), INK_600),
                    ("TEXTCOLOR", (0, 1), (-1, -1), INK_900),
                    ("ALIGN", (3, 0), (3, -1), "RIGHT"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.4, INK_200),
                ]
            )
        )
        story.append(pay_table)
    else:
        story.append(Paragraph("No payments recorded in this period.", label_style))

    story.append(Spacer(1, 10 * mm))
    story.append(HRFlowable(width="100%", thickness=1, color=INK_200))
    story.append(Spacer(1, 4 * mm))
    story.append(
        Paragraph(
            f"Generated by Ledgr on {datetime.now(timezone.utc).strftime('%d %B %Y')}. "
            "This statement reflects the fee account as recorded at the time of generation.",
            footer_style,
        )
    )

    doc.build(story)
    return buffer.getvalue()
