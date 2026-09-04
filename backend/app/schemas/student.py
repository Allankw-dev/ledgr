from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


class CreateStudentRequest(BaseModel):
    class_id: str | None = None
    admission_number: str = Field(min_length=1)
    full_name: str = Field(min_length=2)
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
