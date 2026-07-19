"""Delivers the durable email outbox — the read/send side of core/outbox.py.

Runs as a loop on a dedicated thread inside the worker process (see
backend.worker). Claims queued rows with SELECT ... FOR UPDATE SKIP LOCKED,
delivers them via Resend with exponential backoff, and deletes each on success.
A row that keeps failing is retried until it exhausts EMAIL_OUTBOX_MAX_ATTEMPTS,
then marked `dead`. A drainer that dies mid-delivery leaves a row `sending`; a
periodic reclaim sweeps stale `sending` rows back to `queued`.

Why a thread in the worker and not the API: the same reason training runs in the
worker — App Runner throttles CPU and recycles instances outside request
handling, so a send started after the response is unreliable. The worker is
always-on, and this thread is independent of the training claim loop so a long
training run never delays a verification email.

Delivery is at-least-once: a crash after Resend accepts the message but before
the row is deleted re-sends on reclaim. A duplicate email is the acceptable cost
of never dropping one.
"""

import logging
import time
from datetime import timedelta
from typing import Any, Callable

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.email import (
    send_account_exists_email,
    send_email_changed_notification,
    send_password_reset_email,
    send_verification_email,
)
from backend.database import SessionLocal
from backend.models.EmailOutbox import EmailOutbox, EmailOutboxStatus, EmailType, utcnow
from backend.models.user import User

logger = logging.getLogger("backend.email_drain")


def _backoff_seconds(attempts: int) -> int:
    """Exponential backoff, capped. attempts is >= 1 (bumped at claim), so the
    first retry waits BASE, the next 2*BASE, then 4*BASE, ... up to CAP."""
    base = settings.EMAIL_OUTBOX_BACKOFF_BASE_SECONDS
    return min(settings.EMAIL_OUTBOX_BACKOFF_CAP_SECONDS, base * (2 ** (attempts - 1)))


def _resolve_forgot_password(db: Session, email: str) -> None:
    """Handler for a FORGOT_PASSWORD_REQUEST row: look the address up and, if it
    is a real user (and not within the reset cooldown), stage a PASSWORD_RESET
    send row via issue_password_reset. Unknown address -> nothing. Stages only;
    the caller commits it together with deleting the resolve row.

    issue_password_reset is imported lazily: verification imports core/outbox,
    and importing it at module scope here would form an avoidable import cycle.
    """
    from backend.core.verification import issue_password_reset

    user = db.execute(select(User).where(User.email == email)).scalars().first()
    if user is not None:
        issue_password_reset(user, db)


def _handle(db: Session, email_type: str, payload: dict[str, Any]) -> None:
    """Do the work for one row. Send rows call Resend (which raises on failure);
    the resolve row stages DB changes. Raises on any failure so the caller
    schedules a retry. Only the resolve branch touches `db`."""
    if email_type == EmailType.VERIFY_EMAIL.value:
        send_verification_email(token=payload["token"], to_email=payload["to_email"])
    elif email_type == EmailType.PASSWORD_RESET.value:
        send_password_reset_email(token=payload["token"], to_email=payload["to_email"])
    elif email_type == EmailType.ACCOUNT_EXISTS.value:
        send_account_exists_email(to_email=payload["to_email"])
    elif email_type == EmailType.EMAIL_CHANGED.value:
        send_email_changed_notification(
            to_email=payload["to_email"], new_email=payload["new_email"]
        )
    elif email_type == EmailType.FORGOT_PASSWORD_REQUEST.value:
        _resolve_forgot_password(db, payload["email"])
    else:
        raise ValueError(f"unknown email_type: {email_type!r}")


def _claim(db: Session) -> tuple[Any, str, dict[str, Any]] | None:
    """Atomically take the oldest *due* queued row. Marks it `sending`, bumps
    attempts, stamps claimed_at, then commits (releasing the row lock).

    Returns the row's (id, email_type, payload) as detached primitives, captured
    before the commit expires them — so delivery of a send row holds no open
    transaction during the outbound Resend call.
    """
    now = utcnow()
    row = db.execute(
        select(EmailOutbox)
        .where(
            EmailOutbox.status == EmailOutboxStatus.QUEUED.value,
            EmailOutbox.next_attempt_at <= now,
        )
        .order_by(EmailOutbox.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    ).scalars().first()
    if row is None:
        return None

    row.status = EmailOutboxStatus.SENDING.value
    row.attempts += 1
    row.claimed_at = now
    claimed = (row.id, row.email_type, dict(row.payload))
    db.commit()
    return claimed


def _fail(db: Session, row_id: Any, exc: Exception) -> None:
    """Record a failed attempt: back off and requeue, or mark `dead` once
    attempts are exhausted (scrubbing any token from the dead row's payload)."""
    row = db.get(EmailOutbox, row_id)
    if row is None:
        return
    row.error = str(exc)[:2000]
    row.claimed_at = None
    if row.attempts >= settings.EMAIL_OUTBOX_MAX_ATTEMPTS:
        row.status = EmailOutboxStatus.DEAD.value
        row.payload = {k: v for k, v in row.payload.items() if k != "token"}
        logger.error(
            "email %s (%s) dead after %d attempts: %s",
            row_id, row.email_type, row.attempts, exc,
        )
    else:
        row.status = EmailOutboxStatus.QUEUED.value
        row.next_attempt_at = utcnow() + timedelta(seconds=_backoff_seconds(row.attempts))
        logger.warning(
            "email %s (%s) attempt %d failed, retrying: %s",
            row_id, row.email_type, row.attempts, exc,
        )
    db.commit()


def drain_one(db: Session) -> bool:
    """Claim and deliver at most one row. True if a row was processed (so the
    caller polls again immediately), False if the queue was empty."""
    claimed = _claim(db)
    if claimed is None:
        return False
    row_id, email_type, payload = claimed

    try:
        _handle(db, email_type, payload)
    except Exception as exc:  # noqa: BLE001 — any failure must requeue, never crash the thread
        db.rollback()  # undo a resolve row's partially-staged token/send row
        _fail(db, row_id, exc)
        return True

    # Success: for a resolve row this commits the staged token + PASSWORD_RESET
    # row together with removing this row (atomic); for a send row it just removes
    # the delivered row.
    row = db.get(EmailOutbox, row_id)
    if row is not None:
        db.delete(row)
    db.commit()
    return True


def reclaim_stale(db: Session) -> int:
    """Requeue rows stuck `sending` past the cutoff (their drainer died mid-send).
    Idempotent; safe to run from several drainers."""
    cutoff = utcnow() - timedelta(seconds=settings.EMAIL_OUTBOX_CLAIM_STALE_SECONDS)
    result = db.execute(
        update(EmailOutbox)
        .where(
            EmailOutbox.status == EmailOutboxStatus.SENDING.value,
            EmailOutbox.claimed_at.is_not(None),
            EmailOutbox.claimed_at < cutoff,
        )
        .values(status=EmailOutboxStatus.QUEUED.value, claimed_at=None)
    )
    db.commit()
    if result.rowcount:
        logger.warning("reclaimed %d stale email row(s)", result.rowcount)
    return result.rowcount


def run(should_stop: Callable[[], bool]) -> None:
    """The drain loop. Owns its own session (a thread must not share the training
    loop's), exits when should_stop() is true, and never propagates an exception —
    a DB blip logs, backs off, and retries, so the thread outlives transient
    faults for the whole life of the worker."""
    logger.info("email drain started (poll=%ss)", settings.EMAIL_OUTBOX_POLL_SECONDS)
    db = SessionLocal()
    last_reclaim = 0.0
    try:
        while not should_stop():
            try:
                mono = time.monotonic()
                if mono - last_reclaim >= settings.EMAIL_OUTBOX_CLAIM_STALE_SECONDS:
                    reclaim_stale(db)
                    last_reclaim = mono
                if not drain_one(db):
                    time.sleep(settings.EMAIL_OUTBOX_POLL_SECONDS)
            except Exception:  # noqa: BLE001
                logger.exception("email drain loop error; backing off")
                db.rollback()
                time.sleep(max(1.0, settings.EMAIL_OUTBOX_POLL_SECONDS))
    finally:
        db.close()
        logger.info("email drain stopped")
