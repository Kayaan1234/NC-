from datetime import datetime
from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from backend.database import Base
import uuid


import backend.models.user

from enum import Enum as PyEnum

class ProgressStatus(str, PyEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class UserExerciseProgress(Base):
    __tablename__ = "user_exercise_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "exercise_id", name="uq_user_exercise"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[ProgressStatus] = mapped_column(String(20), nullable=False, default=ProgressStatus.NOT_STARTED.value)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["backend.models.user.User"] = relationship("User", back_populates="exercise_progress")

class UserSolutions(Base):
    __tablename__ = "user_solutions"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    solution_code: Mapped[str] = mapped_column(String, nullable=False, maxlength=1000)

    user: Mapped["backend.models.user.User"] = relationship("User", back_populates="user_solutions")
    # A submission may spawn one hint session (gated behind this submission).
    hint_session: Mapped["backend.models.LlmHint.LlmHintSession | None"] = relationship(
        "LlmHintSession", back_populates="solution", cascade="all, delete-orphan", uselist=False
    )


class UserHintViews(Base):
    __tablename__ = "user_hint_views"
    __table_args__ = (
        UniqueConstraint("user_id", "hint_id", "viewed_at", name="uq_user_hint"),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hint_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("hints.id", ondelete="CASCADE"), nullable=False, index=True
    )
    viewed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    user: Mapped["backend.models.user.User"] = relationship("User", back_populates="user_hint_views")