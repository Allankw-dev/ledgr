from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class SubscriptionResponse(BaseModel):
    """What a school's own staff see."""

    status: Literal["TRIAL", "ACTIVE", "GRACE", "EXPIRED", "SUSPENDED"]
    read_only: bool
    days_left: int | None
    ends_at: datetime | None
    plan: str
    learner_count: int
    learner_limit: int | None
    over_limit: bool


class PlatformSchool(BaseModel):
    """One row of the operator's list of schools."""

    id: str
    name: str
    contact_email: str
    created_at: datetime
    plan: str
    subscription_status: Literal["TRIAL", "ACTIVE", "SUSPENDED"]
    status: Literal["TRIAL", "ACTIVE", "GRACE", "EXPIRED", "SUSPENDED"]
    read_only: bool
    days_left: int | None
    trial_ends_at: datetime | None
    paid_until: datetime | None
    learner_count: int
    learner_limit: int | None
    last_payment_on: datetime | None = None  # the school's most recent (non-voided) payment to the operator


class SubscriptionUpdate(BaseModel):
    """Everything is optional; send only what should change. `learner_limit: null` removes the limit."""

    status: Literal["TRIAL", "ACTIVE", "SUSPENDED"] | None = None
    plan: str | None = Field(default=None, min_length=1, max_length=40)
    paid_until: datetime | None = None
    trial_ends_at: datetime | None = None
    learner_limit: int | None = Field(default=None, ge=1)
    extend_months: int | None = Field(default=None, ge=1, le=36)
    trial_days: int | None = Field(default=None, ge=1, le=120)


class CreateSchoolRequest(BaseModel):
    """The platform operator onboarding a new school. The school's first admin gets an emailed link to set
    their own password, so the operator never sees or chooses it."""

    school_name: str = Field(min_length=2, max_length=120)
    country: str = Field(default="KE", min_length=2, max_length=2)  # ISO country code
    currency: str = Field(default="KES", min_length=3, max_length=3)  # ISO 4217
    admin_full_name: str = Field(min_length=2, max_length=120)
    admin_email: EmailStr
    plan: str | None = Field(default=None, min_length=1, max_length=40)
    learner_limit: int | None = Field(default=None, ge=1)
    trial_days: int | None = Field(default=None, ge=1, le=120)


class CreateSchoolResponse(PlatformSchool):
    """The new school's row, plus whether the admin's set-password email actually went out."""

    invite_sent: bool


# ---- what schools pay the operator -----------------------------------------------------------------

PaymentMethodName = Literal["MPESA", "BANK_TRANSFER", "CASH", "CHEQUE", "OTHER"]


class SubscriptionPaymentCreate(BaseModel):
    """Booking a payment a school made for using Ledgr. `months` also extends the paid-until date in the same step
    (0 books the money without touching the date, e.g. a deposit)."""

    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    method: PaymentMethodName
    reference: str | None = Field(default=None, max_length=60)
    paid_on: datetime | None = None  # defaults to now
    months: int = Field(default=0, ge=0, le=36)
    note: str | None = Field(default=None, max_length=300)


class SubscriptionPaymentVoid(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


class SubscriptionPaymentOut(BaseModel):
    id: str
    school_id: str
    amount: Decimal
    currency: str
    method: PaymentMethodName
    reference: str | None
    paid_on: datetime
    months_added: int
    note: str | None
    created_at: datetime | None
    voided_at: datetime | None
    void_reason: str | None


class SubscriptionPaymentList(BaseModel):
    payments: list[SubscriptionPaymentOut]
    total_paid: Decimal  # sum of the non-voided rows
    currency: str


# ---- payments health (one row per school) -----------------------------------------------------------


class SchoolPaymentsHealth(BaseModel):
    """How one school's online payments are doing. Counts only, never a name, phone number or amount per person."""

    school_id: str
    school_name: str
    currency: str
    subscription_status: Literal["TRIAL", "ACTIVE", "GRACE", "EXPIRED", "SUSPENDED"]
    read_only: bool
    mpesa_mode: Literal["OFF", "GLOBAL", "OWN"]
    environment: str | None
    shortcode: str | None
    tested_at: datetime | None
    c2b_registered_at: datetime | None
    last_error: str | None
    confirmed_30d_count: int
    confirmed_30d_amount: Decimal
    last_confirmed_at: datetime | None
    stuck_pending: int  # M-Pesa prompts sent more than 15 minutes ago that never got an answer
    failed_7d: int
    mismatches: int  # waiting for a bursar: Safaricom reported a different amount
    unallocated: int  # money received that no invoice has claimed yet
    unmatched_c2b: int  # direct paybill payments no student could be found for
    shared_paybill: bool
    severity: Literal["ok", "info", "warn", "bad"]
    attention: list[str]
