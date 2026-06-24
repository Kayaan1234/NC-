from datetime import datetime
from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from backend.database import Base
import uuid
from sqlalchemy.dialects.postgresql import UUID

import backend.models.RefreshToken

class User(Base):
    __tablename__ = "users"

    id : Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    username : Mapped[str] = mapped_column(String(100), unique=True, index=True)
    email : Mapped[str] = mapped_column(String(100), unique=True, index=True)
    hashed_password : Mapped[str] = mapped_column(String(200), nullable=False)
    is_active : Mapped[bool] = mapped_column(Boolean, default=True)
    created_at : Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    verified : Mapped[bool] = mapped_column(Boolean, default=False)

    refresh_tokens : Mapped[list["backend.models.RefreshToken.RefreshToken"]] = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    
