from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


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
