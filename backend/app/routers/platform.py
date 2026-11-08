"""The platform operator's view across every school. SUPER_ADMIN only.

These endpoints deliberately use the system (table-owner) session: a platform operator has no school of their
own, and row-level security is set up per school, so a normal session would see nothing. That is only safe
because every route here is locked to a SUPER_ADMIN with two-factor on and none of them returns anything but subscription facts. (The M-Pesa
set-up routes live in routers/platform_mpesa.py. They hold secrets, so they never return them.)
"""

import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.database import get_system_db
from app.core.deps import CurrentUser, require_operator
from app.core.emails import email_equals, normalize_email
from app.core.security import create_password_reset_token, hash_password
from app.models.enums import UserRole
from app.models.school import School, User
from app.models.student import Student
from app.models.subscription_payment import SubscriptionPayment
from app.schemas.subscription import (
    CreateSchoolRequest,
    CreateSchoolResponse,
    PlatformSchool,
    SchoolPaymentsHealth,
    SubscriptionPaymentCreate,
    SubscriptionPaymentList,
    SubscriptionPaymentOut,
    SubscriptionPaymentVoid,
    SubscriptionUpdate,
)
from app.services.audit_service import log_audit
from app.services.notification_service import NotificationConfigError, send_email
from app.services.payments_health import build_payments_health
from app.services.platform_billing import (
    AlreadyVoided,
    DuplicateReference,
    last_payment_by_school,
    list_subscription_payments,
    record_subscription_payment,
    void_subscription_payment,
)
from app.services.subscription_service import _UNSET, apply_update, compute_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/platform", tags=["platform"])


def _row(school: School, learners: int, last_payment_on=None) -> PlatformSchool:
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
        last_payment_on=last_payment_on,
    )


@router.get("/schools", response_model=list[PlatformSchool])
def list_schools(db: Session = Depends(get_system_db), _user: CurrentUser = Depends(require_operator)):
    counts = dict(
        db.execute(select(Student.school_id, func.count()).where(Student.is_active.is_(True)).group_by(Student.school_id)).all()
    )
    schools = db.execute(select(School).order_by(School.created_at.asc())).scalars().all()
    last_paid = last_payment_by_school(db)
    return [_row(s, counts.get(s.id, 0), last_paid.get(s.id)) for s in schools]


@router.patch("/schools/{school_id}/subscription", response_model=PlatformSchool)
@limiter.limit("60/minute")
def update_subscription(
    request: Request,
    school_id: str,
    data: SubscriptionUpdate,
    db: Session = Depends(get_system_db),
    user: CurrentUser = Depends(require_operator),
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
    return _row(school, count, last_payment_by_school(db).get(school.id))


@router.get("/payments-health", response_model=list[SchoolPaymentsHealth])
def payments_health(db: Session = Depends(get_system_db), _user: CurrentUser = Depends(require_operator)):
    """How every school's online payments are doing, worst first. Counts only."""
    return build_payments_health(db)


def _payment_out(row: SubscriptionPayment) -> SubscriptionPaymentOut:
    return SubscriptionPaymentOut(
        id=row.id,
        school_id=row.school_id,
        amount=row.amount,
        currency=row.currency,
        method=row.method,  # type: ignore[arg-type]
        reference=row.reference,
        paid_on=row.paid_on,
        months_added=row.months_added,
        note=row.note,
        created_at=row.created_at,
        voided_at=row.voided_at,
        void_reason=row.void_reason,
    )


@router.get("/schools/{school_id}/subscription-payments", response_model=SubscriptionPaymentList)
def get_subscription_payments(
    school_id: str, db: Session = Depends(get_system_db), _user: CurrentUser = Depends(require_operator)
):
    school = db.get(School, school_id)
    if not school:
        raise HTTPException(404, "School not found")
    rows, total = list_subscription_payments(db, school_id)
    return SubscriptionPaymentList(payments=[_payment_out(r) for r in rows], total_paid=total, currency=school.currency)


@router.post("/schools/{school_id}/subscription-payments", response_model=SubscriptionPaymentOut, status_code=201)
@limiter.limit("60/minute")
def add_subscription_payment(
    request: Request,
    school_id: str,
    data: SubscriptionPaymentCreate,
    db: Session = Depends(get_system_db),
    user: CurrentUser = Depends(require_operator),
):
    """Books what a school paid for using Ledgr and, if `months` is set, extends its paid-until date in the same step."""
    school = db.get(School, school_id)
    if not school:
        raise HTTPException(404, "School not found")
    if data.method in ("MPESA", "BANK_TRANSFER") and not (data.reference or "").strip():
        raise HTTPException(422, "Enter the M-Pesa code or bank reference so this payment can be traced.")
    try:
        row = record_subscription_payment(
            db,
            school,
            operator_id=user.user_id,
            amount=data.amount,
            method=data.method,
            reference=data.reference,
            paid_on=data.paid_on,
            months=data.months,
            note=data.note,
        )
    except DuplicateReference:
        raise HTTPException(409, "That reference is already booked for this school.")
    return _payment_out(row)


@router.post("/subscription-payments/{payment_id}/void", response_model=SubscriptionPaymentOut)
@limiter.limit("30/minute")
def void_payment(
    request: Request,
    payment_id: str,
    data: SubscriptionPaymentVoid,
    db: Session = Depends(get_system_db),
    user: CurrentUser = Depends(require_operator),
):
    """Marks a booked payment as entered by mistake. It stays in the book (struck through). It does NOT move the
    school's paid-until date back: change that deliberately if it should change."""
    row = db.get(SubscriptionPayment, payment_id)
    if not row:
        raise HTTPException(404, "Payment not found")
    try:
        row = void_subscription_payment(db, row, operator_id=user.user_id, reason=data.reason)
    except AlreadyVoided:
        raise HTTPException(409, "That payment is already voided.")
    return _payment_out(row)


def _send_admin_invite(admin: User, school: School) -> bool:
    """Emails the new school's admin a link to set their own password. The link goes only to them, never
    back to the operator. If the email can't go out the school still exists, and the admin can use
    "Forgot password" with the same address."""
    token = create_password_reset_token(admin.id, admin.password_hash)
    link = f"{settings.frontend_url}/reset-password?token={token}"
    try:
        send_email(
            admin.email,
            "Your school is set up on Ledgr",
            f"Hi {admin.full_name},\n\n"
            f"{school.name} has been set up on Ledgr and you are its administrator. Set your password to get "
            f"started (this link expires in 30 minutes):\n\n{link}\n\n"
            "If the link has expired, open the Ledgr sign-in page and choose \"Forgot password\" with this "
            "email address.",
        )
        return True
    except NotificationConfigError:
        logger.warning("School admin invite not sent: email isn't configured")
    except Exception:  # noqa: BLE001 — a mail outage must not undo creating the school
        logger.warning("School admin invite email failed", exc_info=True)
    return False


@router.post("/schools", response_model=CreateSchoolResponse, status_code=201)
@limiter.limit("20/minute")
def create_school(
    request: Request,
    data: CreateSchoolRequest,
    db: Session = Depends(get_system_db),
    user: CurrentUser = Depends(require_operator),
):
    """Onboards a new school and its first SCHOOL_ADMIN. This is the only way to add a school after the
    first one (the public register-school endpoint refuses once any school exists). The admin is created
    with an unusable random password and told by email to set their own."""
    admin_email = normalize_email(data.admin_email)
    if db.execute(select(User.id).where(email_equals(User.email, admin_email))).first():
        raise HTTPException(409, "An account with that email already exists")

    school = School(
        name=data.school_name.strip(),
        country=data.country.upper(),
        currency=data.currency.upper(),
        contact_email=admin_email,
    )
    if data.plan:
        school.plan = data.plan
    if data.learner_limit is not None:
        school.learner_limit = data.learner_limit
    db.add(school)
    db.flush()

    admin = User(
        school_id=school.id,
        email=admin_email,
        password_hash=hash_password(secrets.token_urlsafe(32)),
        role=UserRole.SCHOOL_ADMIN,
        full_name=data.admin_full_name.strip(),
    )
    db.add(admin)
    log_audit(
        db,
        school_id=school.id,
        action="SCHOOL_CREATED",
        entity_type="School",
        entity_id=school.id,
        user_id=user.user_id,
        metadata={"admin_email": admin_email, "plan": school.plan, "learner_limit": school.learner_limit},
    )
    try:
        db.commit()
    except IntegrityError:  # someone took the email between the check above and now
        db.rollback()
        raise HTTPException(409, "An account with that email already exists")
    db.refresh(school)
    db.refresh(admin)

    if data.trial_days is not None:
        apply_update(db, school, operator_id=user.user_id, trial_days=data.trial_days)

    invite_sent = _send_admin_invite(admin, school)
    row = _row(school, 0)
    return CreateSchoolResponse(**row.model_dump(), invite_sent=invite_sent)
