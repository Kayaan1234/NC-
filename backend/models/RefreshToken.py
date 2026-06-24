from datetime import datetime
from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from backend.database import Base
import uuid
from sqlalchemy.dialects.postgresql import UUID

import backend.models.user

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id : Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id : Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash : Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    created_at : Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at : Mapped[datetime] = mapped_column(DateTime)
    revoked : Mapped[bool] = mapped_column(Boolean, default=False)
    
    user : Mapped["backend.models.user.User"] = relationship("User", back_populates="refresh_tokens")