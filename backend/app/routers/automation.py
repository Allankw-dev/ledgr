from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_school_scope, require_roles
from app.core.rate_limit import limiter
from app.models.invoice import Invoice, InvoiceReminderLog
from app.models.school import School
from app.models.student import Student
from app.schemas.automation import (
    AutomationSettingsResponse,
    UpdateAutomationSettingsRequest,
    SweepResultResponse,
    ReminderLogEntry,
)
from app.services.overdue_automation_service import run_overdue_reminder_sweep

router = APIRouter(prefix="/api/automation", tags=["automation"], dependencies=[Depends(get_current_user)])


@router.get("/settings", response_model=AutomationSettingsResponse)
def get_automation_settings(
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    _user=Depends(require_roles("SCHOOL_ADMIN", "BURSAR")),
):
    school = db.get(School, school_id)
    if not school:
        raise HTTPException(404, "School not found")
    return AutomationSettingsResponse(enabled=school.auto_reminders_enabled)


@router.put("/settings", response_model=AutomationSettingsResponse)
def update_automation_settings(
    payload: UpdateAutomationSettingsRequest,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    _user=Depends(require_roles("SCHOOL_ADMIN")),  # opt-in to auto-messaging parents is an admin-level call, not a bursar one
):
    school = db.get(School, school_id)
    if not school:
        raise HTTPException(404, "School not found")
    school.auto_reminders_enabled = payload.enabled
    db.commit()
    return AutomationSettingsResponse(enabled=school.auto_reminders_enabled)


@router.post("/run-now", response_model=SweepResultResponse)
@limiter.limit("5/hour")
def run_now(
    request: Request,  # required by @limiter.limit — unused otherwise
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    _user=Depends(require_roles("SCHOOL_ADMIN", "BURSAR")),
):
    """Triggers a sweep immediately instead of waiting for the daily
    schedule — same escalation logic, same per-invoice tier cap, so running
    this twice in a row is safe: the second run finds nothing new to send."""
    result = run_overdue_reminder_sweep(db, school_id)
    return SweepResultResponse(
        invoices_checked=result.invoices_checked,
        reminders_sent=result.reminders_sent,
        errors=result.errors,
    )


@router.get("/history", response_model=list[ReminderLogEntry])
def get_reminder_history(
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    _user=Depends(require_roles("SCHOOL_ADMIN", "BURSAR")),
):
    rows = db.execute(
        select(InvoiceReminderLog, Student)
        .join(Invoice, InvoiceReminderLog.invoice_id == Invoice.id)
        .join(Student, Invoice.student_id == Student.id)
        .where(InvoiceReminderLog.school_id == school_id)
        .order_by(InvoiceReminderLog.sent_at.desc())
        .limit(20)
    ).all()

    return [ReminderLogEntry(student_name=student.full_name, tier=log.tier, sent_at=log.sent_at) for log, student in rows]
