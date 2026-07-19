"""Helpers for keeping the User activity fields (`is_active`, `last_used`)
accurate across the auth/user endpoints.

Semantics:
  - `is_active` = the user currently has at least one *valid* refresh token
    (not revoked, not expired) — i.e. a live session.
  - `last_used` = last-activity heartbeat, bumped on login and token refresh.

These feed a future cleanup job that deletes unverified users inactive for 30
days. That job must rely on `last_used` / the refresh_tokens table (source of
truth), NOT on the stored `is_active` flag: tokens expire silently with no code
running, so `is_active` can drift stale between endpoint updates.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from backend import models
from backend.core.config import settings


def utcnow() -> datetime:
    """Naive UTC, matching the DateTime columns (`last_used`, `expires_at`)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def has_active_refresh_token(db: Session, user_id: uuid.UUID) -> bool:
    """True if the user has any non-revoked, unexpired refresh token."""
    stmt = select(
        exists().where(
            models.RefreshToken.user_id == user_id,
            models.RefreshToken.revoked.is_(False),
            models.RefreshToken.expires_at > utcnow(),
        )
    )
    return bool(db.scalar(stmt))


def touch_activity(user: models.User) -> None:
    """Record a live-session activity heartbeat (login / refresh).

    Stages the change on `user`; the caller commits. To avoid a users-row write
    on every refresh (which fires ~every access-token TTL per active user), skip
    the update when it wouldn't change anything: the user is already active and
    last_used was written within ACTIVITY_WRITE_THROTTLE_MINUTES. Login still
    records activity because last_used is None/stale then, and is_active is only
    ever set True here (cleared elsewhere on logout/revoke), so an already-active
    refreshing user needs no rewrite.
    """
    now = utcnow()
    if (
        user.is_active
        and user.last_used is not None
        and now - user.last_used < timedelta(minutes=settings.ACTIVITY_WRITE_THROTTLE_MINUTES)
    ):
        return
    user.last_used = now
    user.is_active = True
