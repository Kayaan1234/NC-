from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import String, Integer, DateTime, JSON, Index, Uuid
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base
import uuid


def utcnow() -> datetime:
    """Naive UTC, matching how the rest of the app stores timestamps.

    Same reason as TrainingJob.utcnow: these rows are compared and subtracted
    against Python-side UTC datetimes (next_attempt_at, claimed_at cutoffs), so
    they must come from the same clock, never the DB server's local `func.now()`.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class EmailType(str, PyEnum):
    """What an outbox row represents.

    Most are *send* rows — the worker renders and delivers them via Resend. The
    one exception is FORGOT_PASSWORD_REQUEST, a *resolve* row: it carries only a
    raw email address (no user lookup happened on the request path, so timing
    can't reveal whether the address is registered), and the worker resolves it
    to a user, applies the reset cooldown, mints a token, and enqueues a
    PASSWORD_RESET send row. Keeping the lookup off the request path is what
    preserves email-enumeration resistance for /auth/forgot-password.
    """

    VERIFY_EMAIL = "verify_email"            # payload: {to_email, token}
    ACCOUNT_EXISTS = "account_exists"        # payload: {to_email}
    EMAIL_CHANGED = "email_changed"          # payload: {to_email, new_email}
    PASSWORD_RESET = "password_reset"        # payload: {to_email, token}
    FORGOT_PASSWORD_REQUEST = "forgot_password_request"  # payload: {email}


class EmailOutboxStatus(str, PyEnum):
    """Lifecycle of an outbox row.

    queued -> sending (claimed by a drainer) -> deleted on success. A send that
    keeps failing goes queued -> sending -> queued (backoff) until it exhausts
    its attempts, then `dead`. A drainer that dies mid-send leaves a row `sending`
    forever; a periodic reclaim sweeps stale `sending` rows back to `queued`
    (mirrors the training worker's heartbeat/reclaim).
    """

    QUEUED = "queued"
    SENDING = "sending"
    DEAD = "dead"


class EmailOutbox(Base):
    """Durable queue of emails to send. This table IS the outbox.

    Every transactional email is written here in the SAME transaction as the
    change that triggers it (the verification token, the email-change, ...), so
    the intent to send is atomic with the state change and survives an API
    instance being recycled — unlike a FastAPI BackgroundTask, which runs
    in-process after the response and is lost if the instance goes away. A drain
    loop in the worker process (see backend.services.email_drain) claims rows
    with SELECT ... FOR UPDATE SKIP LOCKED and delivers them with retry/backoff.

    Delivery is at-least-once: a crash after a successful Resend call but before
    the row is deleted results in the row being retried, i.e. a duplicate email.
    That is deliberately preferred over at-most-once (a dropped email), and a
    duplicate verification/notification email is benign.
    """

    __tablename__ = "email_outbox"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    # Stored as the enum VALUE (a plain string), not a SQLAlchemy Enum column, to
    # avoid minting another Postgres native ENUM type (which complicates
    # migrations/downgrade — see the emailtokenpurpose handling in the baseline).
    email_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=EmailOutboxStatus.QUEUED.value
    )
    # The raw token (for verify/reset) lives here until the row is delivered and
    # deleted — the same secret already rides in the email link. Rows are removed
    # on success and scrubbed of the token when they go `dead`, keeping the
    # at-rest window to the delivery attempt.
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, server_default=func.now()
    )
    # When this row becomes eligible to (re)send. Set to now on enqueue; pushed
    # into the future by exponential backoff after a failed attempt.
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    # Stamped when a drainer claims the row (status -> sending); used by the
    # stale-claim reclaim, and cleared whenever the row returns to queued.
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    __table_args__ = (
        # The claim query is: status='queued' AND next_attempt_at <= now, oldest
        # first. This index serves that hot path directly.
        Index("ix_email_outbox_claim", "status", "next_attempt_at"),
    )
