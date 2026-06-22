from pydantic import BaseModel, EmailStr, field_validator, model_validator, Field
import re

class LoginRequest(BaseModel):
    email : EmailStr
    password : str
    model_config = {"str_strip_whitespace" : True}

class RegisterRequest(BaseModel):
    username: str = Field(min_length=3)
    email : EmailStr
    password : str = Field(min_length=8)
    confirm_password : str

    model_config = {"str_strip_whitespace": True}

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("Username may only contain letters, numbers, and underscores")
        return v
    
    @field_validator("password")
    @classmethod
    def password_strong(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
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
    user_id : int

class UserPublic(BaseModel):
   
    id: int
    username: str
    email: EmailStr