from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MpesaAccountUpdate(BaseModel):
    """What the platform operator enters for a school's own paybill.

    The three secrets are WRITE-ONLY: they are never returned by any endpoint. On a later edit leave them out (or
    blank) to keep what is saved, and send a value only to replace it."""

    environment: Literal["SANDBOX", "PRODUCTION"]
    shortcode: str = Field(min_length=3, max_length=12, pattern=r"^\d+$", description="The paybill number, digits only")
    consumer_key: str | None = Field(default=None, max_length=200)
    consumer_secret: str | None = Field(default=None, max_length=200)
    passkey: str | None = Field(default=None, max_length=500)


class MpesaModeUpdate(BaseModel):
    mode: Literal["OFF", "GLOBAL", "OWN"]


class MpesaAccountStatus(BaseModel):
    """Everything about a school's M-Pesa set-up EXCEPT its secrets."""

    school_id: str
    mode: Literal["OFF", "GLOBAL", "OWN"]
    has_account: bool
    environment: Literal["SANDBOX", "PRODUCTION"] | None = None
    shortcode: str | None = None
    tested_at: datetime | None = None
    c2b_registered_at: datetime | None = None
    last_error: str | None = None
    global_configured: bool  # are the server-wide MPESA_* settings complete (what GLOBAL mode uses)?
    addresses_ready: bool  # does the server know its own public address (needed to register with Safaricom)?
    other_schools_on_global: int  # how many OTHER schools also use the server-wide paybill


class MpesaActionResult(BaseModel):
    ok: bool
    message: str
    status: MpesaAccountStatus
