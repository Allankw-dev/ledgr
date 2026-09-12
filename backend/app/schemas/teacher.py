from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, ConfigDict


class CreateTeacherRequest(BaseModel):
    full_name: str = Field(min_length=2)
    email: EmailStr
    class_ids: list[str] = Field(default_factory=list, description="Grades this teacher is assigned to")


class UpdateTeacherClassesRequest(BaseModel):
    class_ids: list[str]


class TeacherResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    full_name: str
    email: str
    is_active: bool
    created_at: datetime
    class_ids: list[str] = []
    class_names: list[str] = []
