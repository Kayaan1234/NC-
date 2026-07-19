from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend import models
from backend.core.config import settings
from backend.core.errors import CooldownError
from backend.core.outbox import enqueue_email
from backend.core.security import generate_verification_token
from backend.models.EmailOutbox import EmailType


def issue_email_verification(
    user: models.User,
    db: Session,
    *,
    enforce_cooldown: bool = True,
) -> None:
    """Mint a fresh verification link for `user` and enqueue the email.

    Lives in core/ (not a router) because both the auth and users routers need
    it — keeping it here stops users.py from having to import from auth.py.

    - When enforce_cooldown is set (resend path), the 10-min per-user throttle
      applies, keyed on user_id (email/password can change) so it can't be used
      to spam an inbox. Callers already governed by a stricter limit — e.g. the
      once-per-day email change — pass enforce_cooldown=False so a legitimate
      change always gets its verification email.
    - Any still-live verification tokens are invalidated first, so only the
      newest link works (limits the blast radius of a leaked older link).
    - The email is written to the outbox, not sent here; that row and the token
      commit together in the single db.commit() below, so the send is durable and
      atomic with the token. Callers can stage other changes (e.g. an email
      update) beforehand and let this persist them all in one transaction.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    if enforce_cooldown:
        last_token = db.execute(
            select(models.EmailToken)
            .where(
                models.EmailToken.user_id == user.id,
                models.EmailToken.purpose == models.EmailTokenPurpose.VERIFY_EMAIL,
            )
            .order_by(models.EmailToken.created_at.desc())
        ).scalars().first()

        cooldown = timedelta(minutes=settings.VERIFICATION_RESEND_COOLDOWN_MINUTES)
        if last_token is not None and last_token.created_at is not None:
            elapsed = now - last_token.created_at
            if elapsed < cooldown:
                retry_after = int((cooldown - elapsed).total_seconds())
                raise CooldownError(
                    "A verification email was sent recently. Please wait before requesting another.",
                    retry_after,
                )

    db.execute(
        update(models.EmailToken)
        .where(
            models.EmailToken.user_id == user.id,
            models.EmailToken.purpose == models.EmailTokenPurpose.VERIFY_EMAIL,
            models.EmailToken.used_at.is_(None),
        )
        .values(used_at=now)
    )

    raw_token, token_hash = generate_verification_token()
    db.add(models.EmailToken(
        user_id=user.id,
        token_hash=token_hash,
        purpose=models.EmailTokenPurpose.VERIFY_EMAIL,
        expires_at=now + timedelta(hours=settings.VERIFICATION_TTL_HOURS),
    ))
    enqueue_email(db, EmailType.VERIFY_EMAIL, {"to_email": user.email, "token": raw_token})
    db.commit()


def issue_password_reset(
    user: models.User,
    db: Session,
) -> None:
    """Mint a fresh password-reset link for `user` and enqueue the email.

    Called only by the outbox drainer while resolving a FORGOT_PASSWORD_REQUEST
    row (see backend.services.email_drain), never on the request path. It STAGES
    the token and the PASSWORD_RESET outbox row but does NOT commit: the drainer
    commits them together with deleting the resolve row, so the whole resolve step
    is atomic and idempotent on retry.

    Any still-live reset tokens are invalidated first, so only the newest link
    works (limits the blast radius of a leaked older link).

    A per-user resend cooldown caps how often a *registered* address can be
    emailed, so an attacker rotating source IPs still can't flood one victim's
    inbox. Two properties:
      - it's checked *before* the invalidation UPDATE below, so a throttled
        request doesn't burn the still-valid token it's declining to replace;
      - it returns silently (no raise) — enumeration resistance means the caller
        must never learn whether the address was registered or throttled. On a
        drainer retry this same check sees the just-minted token and short-circuits,
        so a transient failure can't mint a second token.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    last_token = db.execute(
        select(models.EmailToken)
        .where(
            models.EmailToken.user_id == user.id,
            models.EmailToken.purpose == models.EmailTokenPurpose.RESET_PASSWORD,
        )
        .order_by(models.EmailToken.created_at.desc())
    ).scalars().first()

    cooldown = timedelta(minutes=settings.RESET_RESEND_COOLDOWN_MINUTES)
    if (
        last_token is not None
        and last_token.created_at is not None
        and now - last_token.created_at < cooldown
    ):
        return

    db.execute(
        update(models.EmailToken)
        .where(
            models.EmailToken.user_id == user.id,
            models.EmailToken.purpose == models.EmailTokenPurpose.RESET_PASSWORD,
            models.EmailToken.used_at.is_(None),
        )
        .values(used_at=now)
    )

    raw_token, token_hash = generate_verification_token()
    db.add(models.EmailToken(
        user_id=user.id,
        token_hash=token_hash,
        purpose=models.EmailTokenPurpose.RESET_PASSWORD,
        expires_at=now + timedelta(hours=settings.RESET_TTL_HOURS),
    ))
    enqueue_email(db, EmailType.PASSWORD_RESET, {"to_email": user.email, "token": raw_token})
    # No commit: the drainer commits this together with deleting the resolve row.