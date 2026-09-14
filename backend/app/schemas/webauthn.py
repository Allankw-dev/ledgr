from datetime import datetime
from typing import Any

from pydantic import BaseModel


class WebAuthnRegisterOptionsResponse(BaseModel):
    options: dict[str, Any]
    challenge_id: str


class WebAuthnRegisterVerifyRequest(BaseModel):
    challenge_id: str
    credential: dict[str, Any]
    device_name: str | None = None


class WebAuthnLoginOptionsResponse(BaseModel):
    options: dict[str, Any]
    challenge_id: str


class WebAuthnLoginVerifyRequest(BaseModel):
    challenge_id: str
    credential: dict[str, Any]


class WebAuthnCredentialResponse(BaseModel):
    id: str
    device_name: str | None
    created_at: datetime
    last_used_at: datetime | None
