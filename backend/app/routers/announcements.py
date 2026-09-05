from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user, get_school_scope, require_roles
from app.core.rate_limit import limiter
from app.models.school import School
from app.schemas.announcement import SendAnnouncementRequest, SendAnnouncementResponse
from app.services.announcement_service import send_bulk_announcement
from app.services.audit_service import log_audit

router = APIRouter(prefix="/api/announcements", tags=["announcements"], dependencies=[Depends(get_current_user)])


@router.post("/send", response_model=SendAnnouncementResponse)
@limiter.limit("5/hour")
def send_announcement(
    request: Request,  # required by @limiter.limit — unused otherwise
    payload: SendAnnouncementRequest,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles("SCHOOL_ADMIN", "BURSAR")),
):
    """A broadcast to every guardian in scope, not a targeted fee reminder —
    rate-limited tightly (5/hour) since a mistake here reaches every parent
    in the school at once instead of one at a time."""
    school = db.get(School, school_id)
    if not school:
        raise HTTPException(404, "School not found")

    result = send_bulk_announcement(
        db,
        school_id=school_id,
        school_name=school.name,
        subject=payload.subject,
        message=payload.message,
        class_id=payload.class_id,
    )

    log_audit(
        db,
        school_id=school_id,
        action="SEND_ANNOUNCEMENT",
        entity_type="announcement",
        entity_id=payload.class_id or "school-wide",
        user_id=user.user_id,
        metadata={
            "subject": payload.subject,
            "recipient_count": result.recipient_count,
            "emails_sent": result.emails_sent,
            "sms_sent": result.sms_sent,
        },
    )
    db.commit()

    return SendAnnouncementResponse(
        recipient_count=result.recipient_count,
        emails_sent=result.emails_sent,
        sms_sent=result.sms_sent,
        errors=result.errors,
    )
