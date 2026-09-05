from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_school_scope, require_roles
from app.models.invoice import Invoice
from app.models.student import Student, SchoolClass, Term
from app.models.school import School
from app.services.export_service import BursarReportRow, generate_bursar_report_csv, generate_bursar_report_xlsx

router = APIRouter(prefix="/api/reports", tags=["reports"], dependencies=[Depends(get_current_user)])


@router.get("/bursar-export")
def export_bursar_report(
    term_id: str,
    format: Literal["xlsx", "csv"] = "xlsx",
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    _user=Depends(require_roles("SCHOOL_ADMIN", "BURSAR", "SUPER_ADMIN")),
):
    """Per-student billed/paid/balance ledger for a term, as a downloadable
    file. Excel version has live SUM formulas; CSV has plain totals since
    CSV has no formula support."""
    term = db.get(Term, term_id)
    if not term or (school_id and term.school_id != school_id):
        raise HTTPException(404, "Term not found")

    school = db.get(School, term.school_id)
    if not school:
        raise HTTPException(404, "School not found")

    results = db.execute(
        select(Invoice, Student, SchoolClass)
        .join(Student, Invoice.student_id == Student.id)
        .outerjoin(SchoolClass, Student.class_id == SchoolClass.id)
        .where(Invoice.school_id == term.school_id, Invoice.term_id == term_id)
        .order_by(SchoolClass.name, Student.full_name)
    ).all()

    rows = [
        BursarReportRow(
            admission_number=student.admission_number,
            full_name=student.full_name,
            class_name=school_class.name if school_class else "—",
            total_amount=invoice.total_amount,
            amount_paid=invoice.amount_paid,
            status=invoice.status.value,
        )
        for invoice, student, school_class in results
    ]

    if format == "csv":
        content = generate_bursar_report_csv(school.name, term.name, school.currency, rows)
        media_type = "text/csv"
        ext = "csv"
    else:
        content = generate_bursar_report_xlsx(school.name, term.name, school.currency, rows)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ext = "xlsx"

    filename = f"bursar-report-{term.name.replace(' ', '-')}.{ext}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
