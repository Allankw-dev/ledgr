from pydantic import BaseModel, EmailStr, Field


class LinkGuardianRequest(BaseModel):
    """
    Links a parent account to a student. If a user with this email already
    exists (e.g. linking a second child to the same parent), we reuse that
    account and ignore the password field — we never silently overwrite an
    existing password.
    """
    email: EmailStr
    full_name: str = Field(min_length=2)
    phone: str | None = Field(default=None, description="e.g. +254712345678")
    password: str = Field(min_length=8, description="Only used if this email doesn't have an account yet")
    relationship_type: str = Field(min_length=2, examples=["mother", "father", "guardian"])
    is_primary: bool = True


class GuardianResponse(BaseModel):
    id: str
    user_id: str
    full_name: str
    email: str
    phone: str | None
    relationship_type: str
    is_primary: bool
