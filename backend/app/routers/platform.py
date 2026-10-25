"""The platform operator's view across every school. SUPER_ADMIN only.

These endpoints deliberately use the system (table-owner) session: a platform operator has no school of their
own, and row-level security is set up per school, so a normal session would see nothing. That is only safe
because every route here is locked to SUPER_ADMIN and none of them returns anything but subscription facts.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_system_db
from app.core.deps import CurrentUser, require_roles
from app.models.school import School
from app.models.student import Student
from app.schemas.subscription import PlatformSchool, SubscriptionUpdate
from app.services.subscription_service import _UNSET, apply_update, compute_state

router = APIRouter(prefix="/api/platform", tags=["platform"])


def _row(school: School, learners: int) -> PlatformSchool:
    state = compute_state(school.subscription_status, school.trial_ends_at, school.paid_until)
    return PlatformSchool(
        id=school.id,
        name=school.name,
        contact_email=school.contact_email,
        created_at=school.created_at,
        plan=school.plan,
        subscription_status=school.subscription_status,  # type: ignore[arg-type]
        status=state.status,  # type: ignore[arg-type]
        read_only=state.read_only,
        days_left=state.days_left,
        trial_ends_at=school.trial_ends_at,
        paid_until=school.paid_until,
        learner_count=learners,
        learner_limit=school.learner_limit,
    )


@router.get("/schools", response_model=list[PlatformSchool])
def list_schools(db: Session = Depends(get_system_db), _user: CurrentUser = Depends(require_roles("SUPER_ADMIN"))):
    counts = dict(
        db.execute(select(Student.school_id, func.count()).where(Student.is_active.is_(True)).group_by(Student.school_id)).all()
    )
    schools = db.execute(select(School).order_by(School.created_at.asc())).scalars().all()
    return [_row(s, counts.get(s.id, 0)) for s in schools]


@router.patch("/schools/{school_id}/subscription", response_model=PlatformSchool)
def update_subscription(
    school_id: str,
    data: SubscriptionUpdate,
    db: Session = Depends(get_system_db),
    user: CurrentUser = Depends(require_roles("SUPER_ADMIN")),
):
    school = db.get(School, school_id)
    if not school:
        raise HTTPException(404, "School not found")

    sent = data.model_fields_set  # tells "not sent" apart from an explicit null (which clears a date or the limit)
    apply_update(
        db,
        school,
        operator_id=user.user_id,
        status=data.status,
        plan=data.plan,
        paid_until=data.paid_until if "paid_until" in sent else _UNSET,
        trial_ends_at=data.trial_ends_at if "trial_ends_at" in sent else _UNSET,
        learner_limit=data.learner_limit if "learner_limit" in sent else _UNSET,
        extend_months=data.extend_months,
        trial_days=data.trial_days,
    )
    count = db.scalar(select(func.count()).select_from(Student).where(Student.school_id == school.id, Student.is_active.is_(True))) or 0
    return _row(school, count)
