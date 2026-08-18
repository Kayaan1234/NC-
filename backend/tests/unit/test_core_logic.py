"""Pure logic from core/errors.py, core/activity.py, core/deps.py and
services/email_drain.py's backoff — the bits that decide behaviour without
touching a database.

`touch_activity` and `require_verified_user` are covered here rather than in the
integration tier because both operate on a plain User object: no session, no
commit, nothing to set up.
"""

from datetime import timedelta

import pytest
from fastapi import HTTPException

from backend.core import activity
from backend.core.activity import touch_activity, utcnow
from backend.core.deps import require_verified_user
from backend.core.errors import CooldownError, cooldown_exception_handler
from backend.models.user import User
from backend.services import email_drain
from backend.services.email_drain import _backoff_seconds


def _user(*, verified=True, is_active=False, last_used=None) -> User:
    """A detached User — never added to a session, so nothing here can persist."""
    return User(
        username="alice",
        email="alice@example.com",
        hashed_password="not-a-real-hash",
        verified=verified,
        is_active=is_active,
        last_used=last_used,
    )


# --------------------------------------------------------------------------- #
# CooldownError — the unified 429 contract
# --------------------------------------------------------------------------- #

def test_cooldown_retry_after_is_clamped_to_zero_rather_than_going_negative():
    """A countdown must never be negative even if the window math rounds oddly."""
    assert CooldownError("wait", -5).retry_after == 0


def test_cooldown_retry_after_truncates_rather_than_rounding_up():
    """int() truncates, so a 1.9s wait is reported as 1. Pinned because a client
    that trusts it and retries at t=1 gets one more 429 — deliberate, but worth
    being explicit about."""
    assert CooldownError("wait", 1.9).retry_after == 1


def test_cooldown_keeps_a_whole_second_value_intact():
    assert CooldownError("wait", 600).retry_after == 600


def test_the_cooldown_handler_emits_the_same_shape_as_the_rate_limiter():
    """Both throttles must render identically: {detail, retry_after} in the body
    plus a Retry-After header, so the SPA has one 429 contract to read."""
    response = cooldown_exception_handler(None, CooldownError("Slow down", 42))

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "42"
    assert b'"retry_after":42' in response.body
    assert b'"detail":"Slow down"' in response.body


# --------------------------------------------------------------------------- #
# require_verified_user
# --------------------------------------------------------------------------- #

def test_a_verified_user_passes_straight_through():
    user = _user(verified=True)
    assert require_verified_user(user) is user


def test_an_unverified_user_gets_403_not_401():
    """403, not 401: the caller IS authenticated, just not permitted yet.
    Returning 401 would make the SPA try to refresh and then log them out."""
    with pytest.raises(HTTPException) as exc:
        require_verified_user(_user(verified=False))

    assert exc.value.status_code == 403
    assert exc.value.detail == "Email address not verified"


# --------------------------------------------------------------------------- #
# touch_activity — the write throttle
# --------------------------------------------------------------------------- #

def test_a_first_login_records_activity():
    user = _user(is_active=False, last_used=None)
    touch_activity(user)
    assert user.is_active is True
    assert user.last_used is not None


def test_an_inactive_user_is_reactivated_even_if_last_used_is_recent():
    """is_active is cleared on logout/revoke, so a fresh login must set it back
    regardless of how recently last_used was written."""
    user = _user(is_active=False, last_used=utcnow())
    touch_activity(user)
    assert user.is_active is True


def test_an_active_user_inside_the_throttle_window_is_not_rewritten(monkeypatch):
    """The whole point: /auth/refresh fires roughly every access-token TTL per
    active user, and each one would otherwise be a users-row write."""
    monkeypatch.setattr(activity.settings, "ACTIVITY_WRITE_THROTTLE_MINUTES", 5)
    stamp = utcnow() - timedelta(minutes=1)
    user = _user(is_active=True, last_used=stamp)

    touch_activity(user)

    assert user.last_used == stamp, "should have been a no-op inside the window"


def test_an_active_user_past_the_throttle_window_is_rewritten(monkeypatch):
    monkeypatch.setattr(activity.settings, "ACTIVITY_WRITE_THROTTLE_MINUTES", 5)
    stale = utcnow() - timedelta(minutes=30)
    user = _user(is_active=True, last_used=stale)

    touch_activity(user)

    assert user.last_used > stale


def test_a_user_with_no_last_used_is_always_written(monkeypatch):
    """Guards the None branch — `now - None` would raise if the check were
    reordered."""
    monkeypatch.setattr(activity.settings, "ACTIVITY_WRITE_THROTTLE_MINUTES", 5)
    user = _user(is_active=True, last_used=None)
    touch_activity(user)
    assert user.last_used is not None


def test_utcnow_is_naive_so_it_can_be_compared_against_the_columns():
    """Every DateTime column in this app stores naive UTC. A tz-aware value
    compared against one raises TypeError, so this is load-bearing."""
    assert utcnow().tzinfo is None


# --------------------------------------------------------------------------- #
# Email outbox backoff
# --------------------------------------------------------------------------- #

def test_backoff_doubles_from_the_base_on_each_attempt(monkeypatch):
    monkeypatch.setattr(email_drain.settings, "EMAIL_OUTBOX_BACKOFF_BASE_SECONDS", 30)
    monkeypatch.setattr(email_drain.settings, "EMAIL_OUTBOX_BACKOFF_CAP_SECONDS", 3600)

    assert [_backoff_seconds(n) for n in range(1, 8)] == [30, 60, 120, 240, 480, 960, 1920]


def test_backoff_stops_at_the_cap_rather_than_growing_without_bound(monkeypatch):
    monkeypatch.setattr(email_drain.settings, "EMAIL_OUTBOX_BACKOFF_BASE_SECONDS", 30)
    monkeypatch.setattr(email_drain.settings, "EMAIL_OUTBOX_BACKOFF_CAP_SECONDS", 3600)

    assert _backoff_seconds(8) == 3600
    assert _backoff_seconds(50) == 3600  # no overflow, no absurd wait


def test_backoff_is_monotonic_over_the_full_attempt_range(monkeypatch):
    monkeypatch.setattr(email_drain.settings, "EMAIL_OUTBOX_BACKOFF_BASE_SECONDS", 30)
    monkeypatch.setattr(email_drain.settings, "EMAIL_OUTBOX_BACKOFF_CAP_SECONDS", 3600)

    waits = [_backoff_seconds(n) for n in range(1, 20)]
    assert waits == sorted(waits)
