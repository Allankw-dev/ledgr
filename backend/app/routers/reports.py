from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_school_scope, require_roles
from app.models.invoice import Invoice
from app.models.student import Student, SchoolClass, Term
from app.models.school import School
from app.schemas.analytics import DashboardAnalyticsResponse, TermCollectionPoint, TopRiskInvoice
from app.services.export_service import BursarReportRow, generate_bursar_report_csv, generate_bursar_report_xlsx
from app.services.analytics_service import get_summary_stats, get_collection_by_term, get_top_risk_invoices

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


@router.get("/analytics", response_model=DashboardAnalyticsResponse)
def dashboard_analytics(
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    _user=Depends(require_roles("SCHOOL_ADMIN", "BURSAR", "SUPER_ADMIN")),
):
    """Two things a bursar checks daily: collection trend across terms, and
    which unpaid invoices are most likely to go bad. Both are derived from
    data that's already tracked elsewhere (invoices + the existing
    risk_scoring service) — this just aggregates it for the dashboard.

    The actual queries live in analytics_service so the AI assistant's
    tools can reuse the exact same numbers instead of recomputing them."""
    if not school_id:
        raise HTTPException(400, "SUPER_ADMIN must act within a specific school for analytics")

    stats = get_summary_stats(db, school_id)

    collection_by_term = [
        TermCollectionPoint(term_id=t.term_id, term_name=t.term_name, total_billed=t.total_billed, total_paid=t.total_paid)
        for t in get_collection_by_term(db, school_id)
    ]

    top_risk = [
        TopRiskInvoice(
            invoice_id=r.invoice_id,
            student_id=r.student_id,
            student_name=r.student_name,
            class_name=r.class_name,
            balance=r.balance,
            risk_score=r.risk_score,
            risk_level=r.risk_level,
        )
        for r in get_top_risk_invoices(db, school_id, limit=5)
    ]

    return DashboardAnalyticsResponse(
        total_collected=stats.total_collected,
        total_outstanding=stats.total_outstanding,
        overdue_count=stats.overdue_count,
        active_student_count=stats.active_student_count,
        collection_by_term=collection_by_term,
        top_risk=top_risk,
    )
