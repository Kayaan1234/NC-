from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr, model_validator, Field
import re

from uuid import UUID

from enum import Enum as PyEnum


def _password_strength(v: str) -> str:
    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[0-9]", v):
        raise ValueError("Password must contain at least one digit")
    return v


# 8–30 chars, ≥1 uppercase, ≥1 digit. Shared so the reset-password path enforces
# exactly the same policy as registration instead of accepting any string.
StrongPassword = Annotated[str, Field(min_length=8, max_length=30), AfterValidator(_password_strength)]


class LoginRequest(BaseModel):
    email : EmailStr
    password : str
    model_config = {"str_strip_whitespace" : True}

class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, pattern = r"^[a-zA-Z0-9_]+$")
    email : EmailStr
    password : StrongPassword
    confirm_password : str

    model_config = {"str_strip_whitespace": True}

    @model_validator(mode="after")
    def passwords_match(self) -> "RegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self
    
class RegisterResponse(BaseModel):
    # Message-only ON PURPOSE: the response must be byte-identical whether the
    # email was free (account created) or already taken (nothing created). A
    # user_id/verified field would leak that difference and re-open email
    # enumeration. The SPA ignores the body anyway — it auto-logs-in afterward.
    message: str

class UserPublic(BaseModel):

    id: UUID
    username: str
    email: EmailStr
    verified : bool = Field(default=False)

    model_config={"from_attributes": True}

class TokenPayload(BaseModel):
    sub: UUID
    exp: int
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshRequest(BaseModel):
    refresh_token : str

class ResendVerificationResponse(BaseModel):
    message: str

class VerifyEmailRequest(BaseModel):
    token: str

class UpdateEmailRequest(BaseModel):
    new_email: EmailStr
    current_password: str

class DeleteAccountRequest(BaseModel):
    current_password: str

    model_config = {"str_strip_whitespace": True}

class ResetPasswordRequest(BaseModel):
    current_password: str
    new_password: StrongPassword

    model_config = {"str_strip_whitespace": True}

class ResetPasswordResponse(BaseModel):
    message: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ForgotPasswordToken(BaseModel):
    token: str
    new_password: StrongPassword

class ValidateResetTokenRequest(BaseModel):
    token: str

class RungStatus(str, PyEnum):
    LOCKED = "locked"
    UNLOCKED = "unlocked"
    COMPLETED = "completed"


class RungProgressOut(BaseModel):
    id: UUID
    number: int
    slug: str
    title: str
    status: RungStatus
    exercises_completed: int
    exercises_total: int

    model_config = {"from_attributes": True}

class DashboardOut(BaseModel):
    rungs: list[RungProgressOut]
    current_rung_number: int | None = None