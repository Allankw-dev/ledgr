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


class GoogleAuthRequest(BaseModel):
    credential: str  # the ID token JWT string Google's Sign In button returns


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


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


class ForgotPasswordResponse(BaseModel):
    # Deliberately generic — never reveals whether the email is registered,
    # so this endpoint can't be used to check who has an account.
    message: str = "If an account exists for that email, a reset link has been sent."
