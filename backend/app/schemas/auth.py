from pydantic import BaseModel, EmailStr, Field

from app.schemas.passwords import NewPassword


class RegisterSchoolRequest(BaseModel):
    school_name: str = Field(min_length=2, max_length=150)
    country: str = Field(min_length=2, max_length=2)  # ISO country code
    currency: str = Field(min_length=3, max_length=3)  # ISO 4217
    admin_email: EmailStr
    admin_password: NewPassword
    admin_full_name: str = Field(min_length=2, max_length=150)


class LoginRequest(BaseModel):
    # An email address, or (for teachers) a phone number. Field name kept as
    # `email` so existing clients keep working.
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)


class GoogleAuthRequest(BaseModel):
    credential: str = Field(max_length=4000)  # the ID token JWT string Google's Sign In button returns


class TokenResponse(BaseModel):
    token: str
    refresh_token: str | None = None
    user: dict
    school: dict | None = None


class TwoFactorRequiredResponse(BaseModel):
    requires_2fa: bool = True
    challenge_token: str


class TwoFactorSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class TwoFactorEnableRequest(BaseModel):
    code: str = Field(min_length=6, max_length=8)  # up to 8 so "123 456" pastes; spaces are stripped server-side


class TwoFactorDisableRequest(BaseModel):
    password: str = Field(min_length=1, max_length=200)


class TwoFactorVerifyLoginRequest(BaseModel):
    challenge_token: str = Field(max_length=2000)
    code: str = Field(min_length=6, max_length=8)  # up to 8 so "123 456" pastes; spaces are stripped server-side


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)  # email, or a teacher's phone number


class ResetPasswordRequest(BaseModel):
    token: str = Field(max_length=2000)
    new_password: NewPassword


class ForgotPasswordResponse(BaseModel):
    # Deliberately generic — never reveals whether the email is registered,
    # so this endpoint can't be used to check who has an account.
    message: str = "If an account exists for that email, a reset link has been sent."


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=200)


class EmailChangeRequest(BaseModel):
    new_email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class EmailChangeConfirmRequest(BaseModel):
    token: str = Field(max_length=2000)
