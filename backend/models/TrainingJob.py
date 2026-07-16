from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, ForeignKey, Uuid, Text, JSON, Index, text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from backend.database import Base
import uuid
from enum import Enum as PyEnum

import backend.models.user


def utcnow() -> datetime:
    """Naive UTC, matching how the rest of the app stores timestamps.

    Every timestamp on a job MUST come from this one clock. They get compared to
    each other (did it start before it finished?) and subtracted (how long did it
    take?), so a second source would have to agree exactly — and one doesn't:
    `func.now()` returns the *database server's* local time, and this deployment's
    Postgres runs in Europe/London. Stamping created_at server-side and the rest
    here put them an hour apart under BST, making a job look like it started
    before it was created. Worse, the gap is zero in winter, so the bug would
    disappear and come back with the clocks.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class JobStatus(str, PyEnum):
    """Lifecycle of a training job.

    queued/running are the *active* states — exactly one per user at a time (see
    the partial unique index below). succeeded/failed are terminal, and fall out
    of that index, which is what frees the user's next slot.
    """

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class TrainingJob(Base):
    """One requested training run. This table IS the queue.

    The API only ever inserts rows here; a separate worker process claims them
    with SELECT ... FOR UPDATE SKIP LOCKED. Postgres is a perfectly good queue at
    this scale, and it means a job survives an API restart — nothing is held in
    process memory.
    """

    __tablename__ = "training_jobs"

    # Dialect-agnostic UUID: native uuid on Postgres, CHAR(32) on SQLite.
    id : Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    user_id : Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # Key into backend.services.registry.MODELS — not a path, never joined onto one.
    model_id : Mapped[str] = mapped_column(String(50), nullable=False)
    # The validated TrainRequest as submitted. Stored verbatim so a finished
    # report is self-describing even after the model's defaults or bounds change.
    params : Mapped[dict] = mapped_column(JSON, nullable=False)

    # Stored as a plain string holding the enum's VALUE, deliberately not
    # Enum(JobStatus). SQLAlchemy's Enum type persists the member NAME ("QUEUED"),
    # which would silently break the partial index below: its predicate matches
    # lowercase values, so it would cover zero rows, no IntegrityError would ever
    # fire, and the one-job-per-user rule would be unenforced while appearing to
    # work. JobStatus subclasses str, so `job.status == JobStatus.QUEUED` still
    # compares correctly and assignment stores the value.
    status : Mapped[str] = mapped_column(String(20), nullable=False, default=JobStatus.QUEUED.value, index=True)

    # default (Python-side, UTC) wins on every ORM insert and is what keeps this
    # column comparable with the four below. server_default stays only as a
    # backstop for a row inserted outside the ORM — see utcnow() for why the two
    # sources disagree.
    created_at : Mapped[datetime] = mapped_column(DateTime, default=utcnow, server_default=func.now())
    started_at : Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at : Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Stamped by the worker while the subprocess runs. Liveness is proven by this,
    # not by elapsed time: a long job that keeps beating is healthy, and a silent
    # one is abandoned. See worker.reclaim_stale.
    heartbeat_at : Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # The downloadable report: exactly what the driver printed (epochs, loss,
    # accuracy). Lives in the DB because the container filesystem is ephemeral.
    stdout : Mapped[str | None] = mapped_column(Text, nullable=True)
    # The parsed RESULT line from the run.
    result : Mapped[dict | None] = mapped_column(JSON, nullable=True)
    exit_code : Mapped[int | None] = mapped_column(Integer, nullable=True)
    error : Mapped[str | None] = mapped_column(Text, nullable=True)

    user : Mapped["backend.models.user.User"] = relationship("User", back_populates="training_jobs")

    __table_args__ = (
        # One active job per user, enforced by the DATABASE. A check-then-insert
        # in the router would race: two concurrent POSTs both read "no active job"
        # and both insert. The predicate lists the active states only, so a job
        # reaching a terminal state drops out of the index and frees the slot with
        # no extra bookkeeping.
        Index(
            "uq_training_jobs_active_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status IN ('queued','running')"),
            sqlite_where=text("status IN ('queued','running')"),
        ),
    )
