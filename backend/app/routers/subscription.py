from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user, get_school_scope, require_roles
from app.models.school import School
from app.schemas.subscription import SubscriptionResponse
from app.services.subscription_service import compute_state, learner_count

router = APIRouter(prefix="/api/subscription", tags=["subscription"])


@router.get("", response_model=SubscriptionResponse)
def my_subscription(
    db: Session = Depends(get_db),
    school_id: str = Depends(get_school_scope),
    _user: CurrentUser = Depends(require_roles("SCHOOL_ADMIN", "BURSAR", "TEACHER")),
):
    """The school's own standing, for the banner staff see. Parents never need this and never see it."""
    school = db.get(School, school_id)
    if not school:
        raise HTTPException(404, "School not found")
    state = compute_state(school.subscription_status, school.trial_ends_at, school.paid_until)
    count = learner_count(db, school_id)
    return SubscriptionResponse(
        status=state.status,  # type: ignore[arg-type]
        read_only=state.read_only,
        days_left=state.days_left,
        ends_at=state.ends_at,
        plan=school.plan,
        learner_count=count,
        learner_limit=school.learner_limit,
        over_limit=school.learner_limit is not None and count > school.learner_limit,
    )
