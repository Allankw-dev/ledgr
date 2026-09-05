from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_school_scope, require_roles
from app.models.invoice import Invoice
from app.models.student import Student, SchoolClass, Term
from app.models.school import School
from app.models.enums import InvoiceStatus
from app.schemas.analytics import DashboardAnalyticsResponse, TermCollectionPoint, TopRiskInvoice
from app.services.export_service import BursarReportRow, generate_bursar_report_csv, generate_bursar_report_xlsx
from app.services.risk_scoring import compute_risk_score

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
    risk_scoring service) — this just aggregates it for the dashboard."""
    if not school_id:
        raise HTTPException(400, "SUPER_ADMIN must act within a specific school for analytics")

    # --- Headline stats (previously computed by fetching every invoice and
    # student to the frontend and summing there — same numbers, now a few
    # cheap SQL aggregates instead of transferring and summing full tables) ---
    totals_row = db.execute(
        select(
            func.coalesce(func.sum(Invoice.amount_paid), 0),
            func.coalesce(func.sum(Invoice.total_amount - Invoice.amount_paid), 0),
            func.count().filter(Invoice.status == InvoiceStatus.OVERDUE),
        ).where(Invoice.school_id == school_id)
    ).one()
    total_collected, total_outstanding, overdue_count = totals_row

    active_student_count = db.execute(
        select(func.count()).select_from(Student).where(Student.school_id == school_id, Student.is_active == True)  # noqa: E712
    ).scalar_one()

    # --- Collection by term ---
    term_rows = db.execute(
        select(
            Term.id,
            Term.name,
            func.coalesce(func.sum(Invoice.total_amount), 0),
            func.coalesce(func.sum(Invoice.amount_paid), 0),
        )
        .outerjoin(Invoice, Invoice.term_id == Term.id)
        .where(Term.school_id == school_id)
        .group_by(Term.id, Term.name, Term.start_date)
        .order_by(Term.start_date)
    ).all()

    collection_by_term = [
        TermCollectionPoint(term_id=tid, term_name=name, total_billed=billed, total_paid=paid)
        for tid, name, billed, paid in term_rows
    ]

    # --- Top-risk unpaid invoices ---
    # Risk scoring does real per-invoice computation (queries the student's
    # payment history), so we bound it to a candidate pool rather than
    # scoring every unpaid invoice in the school — most-overdue-first is a
    # cheap pre-filter that reliably contains the truly high-risk ones.
    candidates = db.execute(
        select(Invoice, Student, SchoolClass)
        .join(Student, Invoice.student_id == Student.id)
        .outerjoin(SchoolClass, Student.class_id == SchoolClass.id)
        .where(
            Invoice.school_id == school_id,
            Invoice.status.notin_([InvoiceStatus.PAID, InvoiceStatus.CANCELLED]),
            Invoice.total_amount > Invoice.amount_paid,
        )
        .order_by(Invoice.due_date)
        .limit(30)
    ).all()

    scored = []
    for invoice, student, school_class in candidates:
        assessment = compute_risk_score(db, student.id, invoice.id)
        scored.append(
            TopRiskInvoice(
                invoice_id=invoice.id,
                student_id=student.id,
                student_name=student.full_name,
                class_name=school_class.name if school_class else "—",
                balance=invoice.total_amount - invoice.amount_paid,
                risk_score=assessment.score,
                risk_level=assessment.level,
            )
        )
    top_risk = sorted(scored, key=lambda r: r.risk_score, reverse=True)[:5]

    return DashboardAnalyticsResponse(
        total_collected=total_collected,
        total_outstanding=total_outstanding,
        overdue_count=overdue_count,
        active_student_count=active_student_count,
        collection_by_term=collection_by_term,
        top_risk=top_risk,
    )
