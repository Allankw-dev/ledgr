from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WebAuthnRegisterOptionsResponse(BaseModel):
    options: dict[str, Any]
    challenge_id: str


class WebAuthnRegisterVerifyRequest(BaseModel):
    challenge_id: str = Field(max_length=64)
    credential: dict[str, Any]
    device_name: str | None = Field(default=None, max_length=150)


class WebAuthnLoginOptionsResponse(BaseModel):
    options: dict[str, Any]
    challenge_id: str


class WebAuthnLoginVerifyRequest(BaseModel):
    challenge_id: str = Field(max_length=64)
    credential: dict[str, Any]


class WebAuthnCredentialResponse(BaseModel):
    id: str
    device_name: str | None
    created_at: datetime
    last_used_at: datetime | None
