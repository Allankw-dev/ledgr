from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, ConfigDict, model_validator


class CreateStudentRequest(BaseModel):
    class_id: str | None = None
    admission_number: str = Field(min_length=1)
    full_name: str = Field(min_length=2)
    date_of_birth: datetime | None = None

    # Optional AS A GROUP — fill these in alongside the student so their
    # parent is connected automatically the moment they sign up, instead of
    # needing a separate "Link parent" step later. No password is collected
    # here: the parent sets their own when they self-register. But if any
    # guardian field is given at all, guardian_full_name + guardian_phone
    # become required together: phone is what a returning parent's signup
    # gets matched against (see _link_or_invite_guardian), so a name with no
    # phone can't be matched to anyone later. Email stays optional.
    guardian_full_name: str | None = Field(default=None, min_length=2)
    guardian_phone: str | None = Field(default=None, description="e.g. +254712345678")
    guardian_email: EmailStr | None = None
    guardian_relationship_type: str | None = Field(default=None, examples=["mother", "father", "guardian"])

    @model_validator(mode="after")
    def _guardian_group_requires_phone(self) -> "CreateStudentRequest":
        wants_guardian = self.guardian_full_name or self.guardian_phone or self.guardian_email
        if wants_guardian:
            if not self.guardian_full_name or len(self.guardian_full_name.strip()) < 2:
                raise ValueError("Enter the parent's full name")
            if not self.guardian_phone:
                raise ValueError("Enter the parent's phone number")
        return self


class UpdateStudentClassRequest(BaseModel):
    class_id: str | None = None  # None clears the assignment (unassigned/no grade)


class UpdateStudentRequest(BaseModel):
    """Covers the 'typo at enrollment' case — misspelled name, wrong
    admission number keyed in, wrong DOB. Deliberately separate from
    UpdateStudentClassRequest so a routine grade promotion and a details
    correction stay two distinct, independently-auditable actions."""

    admission_number: str | None = Field(default=None, min_length=1)
    full_name: str | None = Field(default=None, min_length=2)
    date_of_birth: datetime | None = None


class StudentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    school_id: str
    class_id: str | None
    admission_number: str
    full_name: str
    is_active: bool
    created_at: datetime
