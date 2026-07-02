from datetime import datetime
import uuid

from sqlalchemy import Integer, String, Text, ForeignKey, Uuid, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from backend.database import Base


class Rungs(Base):
    __tablename__ = "rungs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    number: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    exercises: Mapped[list["Exercise"]] = relationship(
        back_populates="rung", cascade="all, delete-orphan", order_by="Exercise.order_index"
    )


class Exercise(Base):
    __tablename__ = "exercises"
    __table_args__ = (
        UniqueConstraint("rung_id", "order_index", name="uq_exercise_rung_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    rung_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("rungs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    starter_code: Mapped[str] = mapped_column(Text, nullable=False)
    model_solution: Mapped[str] = mapped_column(Text, nullable=False)

    rung: Mapped["Rungs"] = relationship(back_populates="exercises")
    hints: Mapped[list["Hint"]] = relationship(
        back_populates="exercise", cascade="all, delete-orphan", order_by="Hint.order_index"
    )


class Hint(Base):
    __tablename__ = "hints"
    __table_args__ = (
        UniqueConstraint("exercise_id", "order_index", name="uq_hint_exercise_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    exercise_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    exercise: Mapped["Exercise"] = relationship(back_populates="hints")