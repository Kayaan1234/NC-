from datetime import datetime, timedelta, timezone

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend import models
from backend.core.config import settings
from backend.core.email import send_verification_email
from backend.core.security import generate_verification_token


def issue_email_verification(
    user: models.User,
    db: Session,
    background_tasks: BackgroundTasks,
    *,
    enforce_cooldown: bool = True,
) -> None:
    """Mint and email a fresh verification link for `user`.

    Lives in core/ (not a router) because both the auth and users routers need
    it — keeping it here stops users.py from having to import from auth.py.

    - When enforce_cooldown is set (resend path), the 10-min per-user throttle
      applies, keyed on user_id (email/password can change) so it can't be used
      to spam an inbox. Callers already governed by a stricter limit — e.g. the
      once-per-day email change — pass enforce_cooldown=False so a legitimate
      change always gets its verification email.
    - Any still-live verification tokens are invalidated first, so only the
      newest link works (limits the blast radius of a leaked older link).
    - Commits the surrounding transaction, so callers can stage other changes
      (e.g. an email update) and let this persist them atomically.
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
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="A verification email was sent recently. Please wait before requesting another.",
                    headers={"Retry-After": str(retry_after)},
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
    db.commit()

    background_tasks.add_task(
        send_verification_email,
        to_email=user.email,
        token=raw_token,
    )
