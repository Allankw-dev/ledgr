from pydantic import BaseModel, EmailStr, Field


class LinkGuardianRequest(BaseModel):
    """
    Records a parent's details against a student. If a user with this phone
    number (or email, if given) already exists — e.g. linking a second child
    to the same parent — that account is linked immediately. Otherwise no
    account is created here — the parent isn't given a password by the
    bursar; instead their details are held as an invite so that when THEY
    sign up (choosing their own password) with this same phone number or
    email, they're connected to this student automatically rather than
    waiting on approval.
    """
    phone: str = Field(min_length=7, description="e.g. +254712345678")
    email: EmailStr | None = None
    full_name: str = Field(min_length=2)
    relationship_type: str = Field(min_length=2, examples=["mother", "father", "guardian"])
    is_primary: bool = True


class GuardianResponse(BaseModel):
    id: str
    user_id: str | None = None
    full_name: str
    phone: str | None
    email: str | None
    relationship_type: str
    is_primary: bool
    status: str  # "linked" (has an account already) or "invited" (waiting for them to sign up)
