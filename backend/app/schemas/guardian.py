from pydantic import BaseModel, Field


class LinkGuardianRequest(BaseModel):
    """
    Records a parent's details against a student. If an account with this
    phone number already exists (e.g. linking a second child to the same
    parent), that account is linked immediately. Otherwise no account is
    created here — the parent isn't given a password by the bursar;
    instead their name + phone are held as an invite so that when THEY
    sign up (choosing their own email and password) with this same phone
    and name, they're connected to this student automatically rather than
    waiting on approval.
    """
    full_name: str = Field(min_length=2)
    phone: str = Field(min_length=7, description="e.g. 0712 345 678 or +254712345678")
    relationship_type: str = Field(min_length=2, examples=["mother", "father", "guardian"])
    is_primary: bool = True


class GuardianResponse(BaseModel):
    id: str
    user_id: str | None = None
    full_name: str
    email: str | None  # only known once they've actually signed up
    phone: str
    relationship_type: str
    is_primary: bool
    status: str  # "linked" (has an account already) or "invited" (waiting for them to sign up)
