from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_school_scope, require_roles
from app.models.payment import AuditLog
from app.models.school import User
from app.schemas.audit_log import AuditLogEntry
from app.schemas.pagination import Page, PageMeta

router = APIRouter(prefix="/api/audit-logs", tags=["audit-logs"], dependencies=[Depends(get_current_user)])

MAX_PAGE_SIZE = 100


@router.get("", response_model=Page[AuditLogEntry])
def list_audit_logs(
    page: int = 1,
    page_size: int = 25,
    action: str | None = None,
    entity_type: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    _user=Depends(require_roles("SCHOOL_ADMIN", "BURSAR")),
):
    """A financial system's audit trail needs to be readable, not just
    written — this is what makes 'who reversed that payment, and when'
    an answerable question instead of a database query someone has to run
    by hand."""
    page = max(page, 1)
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)

    filters = [AuditLog.school_id == school_id]
    if action:
        filters.append(AuditLog.action == action)
    if entity_type:
        filters.append(AuditLog.entity_type == entity_type)
    if start_date:
        filters.append(AuditLog.created_at >= start_date)
    if end_date:
        filters.append(AuditLog.created_at <= end_date)

    total = db.execute(select(func.count()).select_from(AuditLog).where(*filters)).scalar_one()

    rows = db.execute(
        select(AuditLog, User)
        .outerjoin(User, AuditLog.user_id == User.id)
        .where(*filters)
        .order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [
        AuditLogEntry(
            id=log.id,
            actor_name=user.full_name if user else "System",
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            metadata=log.log_metadata,
            created_at=log.created_at,
        )
        for log, user in rows
    ]

    return Page(
        items=items,
        meta=PageMeta(page=page, page_size=page_size, total=total, has_more=(page * page_size) < total),
    )


@router.get("/actions", response_model=list[str])
def list_distinct_actions(
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    _user=Depends(require_roles("SCHOOL_ADMIN", "BURSAR")),
):
    """Powers the filter dropdown — only shows actions that actually exist
    for this school, instead of a hardcoded list that drifts out of sync
    with whatever the codebase currently logs."""
    rows = db.execute(
        select(AuditLog.action).where(AuditLog.school_id == school_id).distinct().order_by(AuditLog.action)
    ).scalars().all()
    return rows
