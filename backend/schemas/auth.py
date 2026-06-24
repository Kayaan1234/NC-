from pydantic import BaseModel, EmailStr, field_validator, model_validator, Field
import re

from uuid import UUID

class LoginRequest(BaseModel):
    email : EmailStr
    password : str
    model_config = {"str_strip_whitespace" : True}

class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, pattern = r"^[a-zA-Z0-9_]+$")
    email : EmailStr
    password : str = Field(min_length=8)
    confirm_password : str

    model_config = {"str_strip_whitespace": True}

   
    
    @field_validator("password")
    @classmethod
    def password_strong(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit")
        return v
    @model_validator(mode="after")
    def passwords_match(self) -> "RegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self
    
class AuthResponse(BaseModel):
    message : str
    user_id : UUID
    verified : bool = Field(default=False)

class UserPublic(BaseModel):

    id: UUID
    username: str
    email: EmailStr
    verified : bool = Field(default=False)

class TokenPayload(BaseModel):
    sub: UUID
    exp: int
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"