from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict

from app.models.enums import FeeCategory


class CreateFeeStructureRequest(BaseModel):
    term_id: str = Field(max_length=64)
    class_id: str | None = Field(default=None, max_length=64)  # null = applies to every class
    category: FeeCategory
    name: str = Field(min_length=2, max_length=150)
    amount: Decimal = Field(gt=0)
    is_mandatory: bool = True


class FeeStructureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    term_id: str
    class_id: str | None
    category: FeeCategory
    name: str
    amount: Decimal
    is_mandatory: bool


class UpdateFeeStructureRequest(BaseModel):
    class_id: str | None = Field(default=None, max_length=64)
    category: FeeCategory | None = None
    name: str | None = Field(default=None, min_length=2, max_length=150)
    amount: Decimal | None = Field(default=None, gt=0)
    is_mandatory: bool | None = None
