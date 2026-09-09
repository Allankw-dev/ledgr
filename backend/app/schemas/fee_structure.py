from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict

from app.models.enums import FeeCategory


class CreateFeeStructureRequest(BaseModel):
    term_id: str
    class_id: str | None = None  # null = applies to every class
    category: FeeCategory
    name: str = Field(min_length=2)
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
    class_id: str | None = None
    category: FeeCategory | None = None
    name: str | None = Field(default=None, min_length=2)
    amount: Decimal | None = Field(default=None, gt=0)
    is_mandatory: bool | None = None
