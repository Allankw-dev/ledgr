"""Statement PDF reversal labelling — no database needed."""

from datetime import datetime, timezone
from decimal import Decimal

from app.services.statement_service import _reference_label, generate_fee_statement_pdf

D = Decimal


def test_reference_labels():
    assert _reference_label({"reference_code": "RCP1"}) == "RCP1"
    assert _reference_label({"reference_code": None}) == "—"
    assert _reference_label({"reference_code": "RCP1", "was_reversed": True}) == "RCP1 (reversed)"
    assert _reference_label({"reference_code": None, "was_reversed": True}) == "(reversed)"
    assert _reference_label({"reference_code": None, "is_reversal": True}) == "Reversal"


def test_statement_pdf_renders_with_a_reversed_payment():
    now = datetime.now(timezone.utc)
    pdf = generate_fee_statement_pdf(
        school_name="Test Academy", student_name="Kid One", admission_number="1001", class_name="Grade 4",
        currency="KES", period_label="All terms",
        invoices=[{"term_name": "Term 1", "due_date": now, "total_amount": D("10000"), "amount_paid": D("0"), "status": "Issued"}],
        payments=[
            {"paid_at": now, "amount": D("5000"), "method": "MPESA", "reference_code": "RCP1", "was_reversed": True},
            {"paid_at": now, "amount": D("-5000"), "method": "MPESA", "reference_code": None, "is_reversal": True},
        ],
    )
    assert pdf.startswith(b"%PDF")
