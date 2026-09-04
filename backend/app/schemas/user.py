from pydantic import BaseModel, Field, ConfigDict


class UpdateMyProfileRequest(BaseModel):
    # Both optional — a user can update just their phone without resending
    # their name, etc. At least one field should be provided in practice,
    # but we don't hard-require it since a no-op PATCH is harmless.
    phone: str | None = Field(default=None, description="e.g. +254712345678")
    full_name: str | None = Field(default=None, min_length=2)


class MyProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    phone: str | None
    role: str
