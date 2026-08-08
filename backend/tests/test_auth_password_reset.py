"""Unauthenticated password reset: /auth/forgot-password,
/auth/reset-password/validate, /auth/reset-password.

Note the two-hop shape these tests have to work with. /auth/forgot-password does
no user lookup — it stages a FORGOT_PASSWORD_REQUEST row and returns. The
worker's drain resolves that to a user, applies the cooldown, mints the token and
enqueues the send. `request_password_reset` performs both hops; the token then
lives in `outbox.delivered_*`, not in the table, because a delivered row is
deleted.
"""

from datetime import datetime, timedelta, timezone

from backend import models
from backend.core.security import hash_token
from backend.models.EmailOutbox import EmailType
from backend.tests.helpers import (
    VALID_PASSWORD,
    login,
    register_and_verify,
    request_password_reset,
)

GENERIC_FORGOT_MSG = "If the email is registered, a password reset link has been sent"


def _naive_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def test_forgot_password_unknown_email_gives_generic_response_and_sends_nothing(client, outbox):
    resp = request_password_reset(client, outbox, email="ghost@example.com")
    assert resp.status_code == 200
    assert resp.json() == {"message": GENERIC_FORGOT_MSG}
    # The request row was still written and drained — identical work either way —
    # but resolving it found no user, so no reset link went out.
    assert outbox.delivered_of("password_reset") == []


def test_forgot_password_known_email_same_response_but_sends_link(client, outbox):
    register_and_verify(client, outbox, email="alice@example.com")

    resp = request_password_reset(client, outbox, email="alice@example.com")
    assert resp.status_code == 200
    assert resp.json() == {"message": GENERIC_FORGOT_MSG}
    # Same body as the unknown-email case, but a real reset token was emailed.
    assert outbox.delivered_token("password_reset")


def test_forgot_password_response_is_identical_for_known_and_unknown_emails(client, outbox):
    """The enumeration property stated as an equality, not a vibe: an attacker
    comparing the two responses byte for byte must learn nothing."""
    register_and_verify(client, outbox, email="alice@example.com")
    outbox.clear()  # drop the registration's verification email from the queue

    known = client.post("/auth/forgot-password", json={"email": "alice@example.com"})
    unknown = client.post("/auth/forgot-password", json={"email": "ghost@example.com"})

    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    # And the queue itself looks the same — one resolve row per call, with no
    # user lookup having happened yet on either.
    assert outbox.kinds() == [EmailType.FORGOT_PASSWORD_REQUEST.value] * 2


def test_reset_resend_cooldown_is_a_silent_no_op(client, outbox):
    """Account-tier throttle: two forgot-password calls in quick succession for
    the SAME real user send exactly ONE email. The 2nd is silently swallowed
    (per-user RESET_RESEND_COOLDOWN) — same generic 200, no second link, and no
    hint that the address exists. It returns rather than raising CooldownError
    precisely because a 429 here would confirm the address is registered."""
    register_and_verify(client, outbox, email="alice@example.com")

    first = client.post("/auth/forgot-password", json={"email": "alice@example.com"})
    second = client.post("/auth/forgot-password", json={"email": "alice@example.com"})
    outbox.drain()

    assert first.json() == second.json() == {"message": GENERIC_FORGOT_MSG}
    assert len(outbox.delivered_of("password_reset")) == 1, (
        "cooldown should have suppressed the 2nd reset email"
    )


def test_validate_reset_token_is_read_only(client, outbox):
    register_and_verify(client, outbox, email="alice@example.com")
    request_password_reset(client, outbox, email="alice@example.com")
    token = outbox.delivered_token("password_reset")

    # Validate twice — must NOT consume the single-use token.
    for _ in range(2):
        resp = client.post("/auth/reset-password/validate", json={"token": token})
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"message": "Reset link is valid"}

    # And the token is still usable to actually reset.
    used = client.post(
        "/auth/reset-password", json={"token": token, "new_password": "NewPass456"}
    )
    assert used.status_code == 200, used.text


def test_reset_token_is_single_use(client, outbox):
    register_and_verify(client, outbox, email="alice@example.com")
    request_password_reset(client, outbox, email="alice@example.com")
    token = outbox.delivered_token("password_reset")

    first = client.post(
        "/auth/reset-password", json={"token": token, "new_password": "NewPass456"}
    )
    assert first.status_code == 200, first.text

    second = client.post(
        "/auth/reset-password", json={"token": token, "new_password": "AnotherPass789"}
    )
    assert second.status_code == 400


def test_expired_reset_token_rejected(client, outbox, db_session):
    register_and_verify(client, outbox, email="alice@example.com")
    request_password_reset(client, outbox, email="alice@example.com")
    token = outbox.delivered_token("password_reset")

    db_session.execute(
        models.EmailToken.__table__.update()
        .where(models.EmailToken.token_hash == hash_token(token))
        .values(expires_at=_naive_utc() - timedelta(hours=1))
    )
    db_session.commit()

    resp = client.post(
        "/auth/reset-password", json={"token": token, "new_password": "NewPass456"}
    )
    assert resp.status_code == 400


def test_verification_token_cannot_be_used_on_reset_endpoint(client, outbox):
    """Purpose confusion: a VERIFY_EMAIL token must not reset a password, even
    though both are EmailToken rows with the same shape and lifetime."""
    from backend.tests.helpers import register

    assert register(client).status_code == 200
    verify_token = outbox.token(EmailType.VERIFY_EMAIL)

    resp = client.post(
        "/auth/reset-password", json={"token": verify_token, "new_password": "NewPass456"}
    )
    assert resp.status_code == 400


def test_garbage_reset_token_rejected(client):
    resp = client.post(
        "/auth/reset-password", json={"token": "garbage", "new_password": "NewPass456"}
    )
    assert resp.status_code == 400


def test_reset_weak_password_rejected(client, outbox):
    register_and_verify(client, outbox, email="alice@example.com")
    request_password_reset(client, outbox, email="alice@example.com")
    token = outbox.delivered_token("password_reset")

    resp = client.post(
        "/auth/reset-password", json={"token": token, "new_password": "weak"}
    )
    assert resp.status_code == 422  # StrongPassword policy enforced on reset too


def test_reset_changes_password_and_kills_all_sessions(client, outbox):
    """After reset: old password dead, new password works, and the session that
    existed before the reset (this client's refresh cookie) is revoked."""
    register_and_verify(client, outbox, email="alice@example.com")
    assert client.post("/auth/refresh").status_code == 200  # live session pre-reset

    request_password_reset(client, outbox, email="alice@example.com")
    token = outbox.delivered_token("password_reset")
    resp = client.post(
        "/auth/reset-password", json={"token": token, "new_password": "NewPass456"}
    )
    assert resp.status_code == 200, resp.text

    # Old session revoked (even though the reset was requested unauthenticated).
    assert client.post("/auth/refresh").status_code == 401

    # Old password no longer works; new one does.
    assert login(client, email="alice@example.com", password=VALID_PASSWORD).status_code == 400
    assert login(client, email="alice@example.com", password="NewPass456").status_code == 200


def test_reset_endpoints_are_post_only(client):
    assert client.get("/auth/forgot-password").status_code == 405
    assert client.get("/auth/reset-password").status_code == 405
    assert client.get("/auth/reset-password/validate").status_code == 405
