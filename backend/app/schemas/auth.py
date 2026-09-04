from pydantic import BaseModel, EmailStr, Field


class RegisterSchoolRequest(BaseModel):
    school_name: str = Field(min_length=2)
    country: str = Field(min_length=2, max_length=2)  # ISO country code
    currency: str = Field(min_length=3, max_length=3)  # ISO 4217
    admin_email: EmailStr
    admin_password: str = Field(min_length=8)
    admin_full_name: str = Field(min_length=2)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    token: str
    user: dict
    school: dict | None = None


class TwoFactorRequiredResponse(BaseModel):
    requires_2fa: bool = True
    challenge_token: str


class TwoFactorSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class TwoFactorEnableRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class TwoFactorDisableRequest(BaseModel):
    password: str


class TwoFactorVerifyLoginRequest(BaseModel):
    challenge_token: str
    code: str = Field(min_length=6, max_length=6)
