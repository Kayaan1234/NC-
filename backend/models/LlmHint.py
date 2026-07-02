from datetime import datetime
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, Uuid, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from backend.database import Base
import uuid

from enum import Enum as PyEnum

import backend.models.user


class HintSessionStatus(str, PyEnum):
    ACTIVE = "active"
    CLOSED = "closed"


class HintMessageRole(str, PyEnum):
    USER = "user"
    ASSISTANT = "assistant"


class LlmHintSession(Base):
    """A Socratic-tutor chat scoped to a single submission.

    Hints are gated behind a submission: a session is born from one
    `UserSolutions` row and replays *that* code (not prior attempts) into the
    LLM. The user gets a fixed budget of questions (enforced in the app as a
    cap on `role="user"` messages); once spent, `status` flips to CLOSED and a
    new (differing) submission is required to open the next session.

    The system prompt (exercise + model solution + static hint ladder) is
    rebuilt each turn, so only the user/assistant turns are persisted as
    `messages`. `exercise_id` is kept denormalised (derivable via the solution)
    to save a join when listing a user's sessions for an exercise.
    """
    __tablename__ = "llm_hint_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # One session per submission (unique), so this both anchors the replayed
    # code and stops a second live chat spawning off the same attempt.
    solution_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("user_solutions.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True
    )
    status: Mapped[HintSessionStatus] = mapped_column(
        String(20), nullable=False, default=HintSessionStatus.ACTIVE.value
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["backend.models.user.User"] = relationship(
        "User", back_populates="hint_sessions"
    )
    solution: Mapped["backend.models.UserProgress.UserSolutions"] = relationship(
        "UserSolutions", back_populates="hint_session"
    )
    messages: Mapped[list["LlmHintMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="LlmHintMessage.seq",
    )


class LlmHintMessage(Base):
    """One turn in a hint session. `seq` gives a stable in-session ordering
    (created_at alone can tie on same-instant inserts)."""
    __tablename__ = "llm_hint_messages"
    __table_args__ = (
        UniqueConstraint("session_id", "seq", name="uq_hint_message_session_seq"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("llm_hint_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[HintMessageRole] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    session: Mapped["LlmHintSession"] = relationship(back_populates="messages")
