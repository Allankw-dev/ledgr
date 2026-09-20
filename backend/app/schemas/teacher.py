from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, ConfigDict, model_validator

from app.core.phone import normalize_phone


class CreateTeacherRequest(BaseModel):
    full_name: str = Field(min_length=2)
    # A teacher needs at least ONE way to sign in and receive their invite:
    # an email address, a phone number, or both.
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    class_ids: list[str] = Field(default_factory=list, description="Grades this teacher is assigned to")

    @model_validator(mode="after")
    def _need_email_or_phone(self):
        if not self.email and not (self.phone and self.phone.strip()):
            raise ValueError("Enter an email address or a phone number for the teacher")
        if self.phone and self.phone.strip() and normalize_phone(self.phone) is None:
            raise ValueError("That phone number doesn't look valid")
        return self


class UpdateTeacherClassesRequest(BaseModel):
    class_ids: list[str]


class TeacherResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    full_name: str
    email: str | None = None  # None for teachers who signed up with a phone number only
    phone: str | None = None
    is_active: bool
    created_at: datetime
    class_ids: list[str] = []
    class_names: list[str] = []
    # Filled in by create/resend: which channels the set-password link went out on.
    invite_channels: list[str] = []
