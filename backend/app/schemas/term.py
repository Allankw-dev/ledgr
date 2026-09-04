from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


class CreateTermRequest(BaseModel):
    name: str = Field(min_length=2)
    start_date: datetime
    end_date: datetime


class TermResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    school_id: str
    name: str
    start_date: datetime
    end_date: datetime
    is_active: bool


class CreateClassRequest(BaseModel):
    name: str = Field(min_length=1)


class ClassResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    school_id: str
    name: str
