from datetime import datetime
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
