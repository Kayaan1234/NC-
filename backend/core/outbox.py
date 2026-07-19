"""Enqueue a transactional email onto the durable outbox.

This is the single write-side entry point for every email the app sends. It only
STAGES the row (db.add) — it deliberately does not commit — so the caller can
persist the send in the same transaction as whatever triggered it (the
verification token, the email change, ...). If that transaction rolls back, no
email row exists either; if it commits, the intent to send is durable and the
worker's drain loop (backend.services.email_drain) picks it up.

The read/deliver side lives in email_drain.py; keeping enqueue here — depending
only on the model — means routers and core/verification can import it without
pulling in the drainer or the Resend client.
"""

from sqlalchemy.orm import Session

from backend.models.EmailOutbox import EmailOutbox, EmailOutboxStatus, EmailType


def enqueue_email(db: Session, email_type: EmailType, payload: dict) -> None:
    """Stage one outbox row. The caller owns the commit (see module docstring)."""
    db.add(
        EmailOutbox(
            email_type=email_type.value,
            status=EmailOutboxStatus.QUEUED.value,
            payload=payload,
        )
    )
