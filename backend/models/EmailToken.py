from datetime import datetime
from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, Uuid, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from backend.database import Base
import uuid
from enum import Enum as PyEnum


import backend.models.user

class EmailTokenPurpose(str, PyEnum):
    VERIFY_EMAIL = "verify_email"
    RESET_PASSWORD = "reset_password"

class EmailToken(Base):
    __tablename__ = "email_tokens"

    # Dialect-agnostic UUID: native uuid on Postgres, CHAR(32) on SQLite.
    id : Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    user_id : Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash : Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    created_at : Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at : Mapped[datetime] = mapped_column(DateTime)
    used_at : Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    purpose : Mapped[EmailTokenPurpose] = mapped_column(Enum(EmailTokenPurpose), nullable=False)
    user : Mapped["backend.models.user.User"] = relationship("User", back_populates="email_tokens")