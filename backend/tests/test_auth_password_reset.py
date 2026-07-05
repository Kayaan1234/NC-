"""Unauthenticated password reset: /auth/forgot-password,
/auth/reset-password/validate, /auth/reset-password."""

from datetime import datetime, timedelta, timezone

from backend import models
from backend.core.security import hash_token
from backend.tests.helpers import (
    VALID_PASSWORD,
    latest_token,
    login,
    register_and_verify,
)

GENERIC_FORGOT_MSG = "If the email is registered, a password reset link has been sent"


def _naive_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def test_forgot_password_unknown_email_gives_generic_response_and_sends_nothing(client, sent_emails):
    resp = client.post("/auth/forgot-password", json={"email": "ghost@example.com"})
    assert resp.status_code == 200
    assert resp.json() == {"message": GENERIC_FORGOT_MSG}
    # No user => no reset email queued.
    assert [e for e in sent_emails if e["kind"] == "reset_password"] == []


def test_forgot_password_known_email_same_response_but_sends_link(client, sent_emails):
    register_and_verify(client, sent_emails, email="alice@example.com")

    resp = client.post("/auth/forgot-password", json={"email": "alice@example.com"})
    assert resp.status_code == 200
    assert resp.json() == {"message": GENERIC_FORGOT_MSG}
    # Same body as the unknown-email case, but a real reset token was emailed.
    assert latest_token(sent_emails, kind="reset_password")


def test_reset_resend_cooldown_is_a_silent_no_op(client, sent_emails):
    """Account-tier throttle: two forgot-password calls in quick succession for
    the SAME real user send exactly ONE email. The 2nd is silently swallowed
    (per-user RESET_RESEND_COOLDOWN) — same generic 200, no second link, and no
    hint that the address exists."""
    register_and_verify(client, sent_emails, email="alice@example.com")

    first = client.post("/auth/forgot-password", json={"email": "alice@example.com"})
    second = client.post("/auth/forgot-password", json={"email": "alice@example.com"})

    assert first.json() == second.json() == {"message": GENERIC_FORGOT_MSG}
    resets = [e for e in sent_emails if e["kind"] == "reset_password"]
    assert len(resets) == 1, "cooldown should have suppressed the 2nd reset email"


def test_validate_reset_token_is_read_only(client, sent_emails):
    register_and_verify(client, sent_emails, email="alice@example.com")
    client.post("/auth/forgot-password", json={"email": "alice@example.com"})
    token = latest_token(sent_emails, kind="reset_password")

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


def test_reset_token_is_single_use(client, sent_emails):
    register_and_verify(client, sent_emails, email="alice@example.com")
    client.post("/auth/forgot-password", json={"email": "alice@example.com"})
    token = latest_token(sent_emails, kind="reset_password")

    first = client.post(
        "/auth/reset-password", json={"token": token, "new_password": "NewPass456"}
    )
    assert first.status_code == 200, first.text

    second = client.post(
        "/auth/reset-password", json={"token": token, "new_password": "AnotherPass789"}
    )
    assert second.status_code == 400


def test_expired_reset_token_rejected(client, sent_emails, db_session):
    register_and_verify(client, sent_emails, email="alice@example.com")
    client.post("/auth/forgot-password", json={"email": "alice@example.com"})
    token = latest_token(sent_emails, kind="reset_password")

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


def test_garbage_reset_token_rejected(client):
    resp = client.post(
        "/auth/reset-password", json={"token": "garbage", "new_password": "NewPass456"}
    )
    assert resp.status_code == 400


def test_reset_weak_password_rejected(client, sent_emails):
    register_and_verify(client, sent_emails, email="alice@example.com")
    client.post("/auth/forgot-password", json={"email": "alice@example.com"})
    token = latest_token(sent_emails, kind="reset_password")

    resp = client.post(
        "/auth/reset-password", json={"token": token, "new_password": "weak"}
    )
    assert resp.status_code == 422  # StrongPassword policy enforced on reset too


def test_reset_changes_password_and_kills_all_sessions(client, sent_emails):
    """After reset: old password dead, new password works, and the session that
    existed before the reset (this client's refresh cookie) is revoked."""
    register_and_verify(client, sent_emails, email="alice@example.com")
    assert client.post("/auth/refresh").status_code == 200  # live session pre-reset

    client.post("/auth/forgot-password", json={"email": "alice@example.com"})
    token = latest_token(sent_emails, kind="reset_password")
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
