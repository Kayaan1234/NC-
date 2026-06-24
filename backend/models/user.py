from datetime import datetime
from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from backend.database import Base

class User(Base):
    __tablename__ = "users"

    id : Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username : Mapped[str] = mapped_column(String, unique=True, index=True)
    email : Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password : Mapped[str] = mapped_column(String)
    is_active : Mapped[bool] = mapped_column(Boolean, default=True)
    created_at : Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    