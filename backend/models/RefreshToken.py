from datetime import datetime
from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, Uuid
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from backend.database import Base
import uuid

import backend.models.user

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    # Dialect-agnostic UUID: native uuid on Postgres, CHAR(32) on SQLite.
    id : Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    user_id : Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash : Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    created_at : Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at : Mapped[datetime] = mapped_column(DateTime)
    revoked : Mapped[bool] = mapped_column(Boolean, default=False)
    
    user : Mapped["backend.models.user.User"] = relationship("User", back_populates="refresh_tokens")