"""POST /auth/resend-verification — the already-verified guard, the per-user
resend cooldown (an account-tier throttle), and its 429 contract.

The cooldown raises CooldownError, so its 429 body matches the slowapi limiter's
shape exactly: {detail, retry_after} plus a consistent Retry-After header."""

from datetime import datetime, timedelta, timezone

from backend import models
from backend.models.EmailOutbox import EmailType
from backend.tests.helpers import (
    auth_header,
    login,
    register,
    verify_latest,
)


def _naive_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _age_verify_tokens(db_session, minutes: int) -> None:
    """Backdate the user's verify tokens so the resend cooldown has elapsed."""
    db_session.execute(
        models.EmailToken.__table__.update()
        .where(models.EmailToken.purpose == models.EmailTokenPurpose.VERIFY_EMAIL)
        .values(created_at=_naive_utc() - timedelta(minutes=minutes))
    )
    db_session.commit()


def test_resend_requires_authentication(client):
    assert client.post("/auth/resend-verification").status_code == 401


def test_resend_for_already_verified_user_is_400(client, outbox):
    register(client, email="alice@example.com")
    verify_latest(client, outbox)
    token = login(client, email="alice@example.com").json()["access_token"]

    resp = client.post("/auth/resend-verification", headers=auth_header(token))
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Email is already verified"


def test_immediate_resend_after_register_hits_cooldown_429(client, outbox):
    """Register already minted a verify token, so an immediate resend trips the
    per-user cooldown. The 429 uses the unified shape: detail + body
    `retry_after` + a matching Retry-After header."""
    register(client, email="alice@example.com")  # unverified
    token = login(client, email="alice@example.com").json()["access_token"]

    resp = client.post("/auth/resend-verification", headers=auth_header(token))
    assert resp.status_code == 429
    body = resp.json()
    assert "retry_after" in body
    assert body["retry_after"] >= 0
    assert resp.headers.get("Retry-After") == str(body["retry_after"])
    assert "wait" in body["detail"].lower()


def test_resend_succeeds_once_cooldown_elapsed(client, outbox, db_session):
    register(client, email="alice@example.com")  # 1st verify email
    token = login(client, email="alice@example.com").json()["access_token"]

    _age_verify_tokens(db_session, minutes=30)  # cooldown window has passed

    resp = client.post("/auth/resend-verification", headers=auth_header(token))
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"message": "Verification email sent"}

    verify_emails = outbox.rows(EmailType.VERIFY_EMAIL)
    assert len(verify_emails) == 2  # a fresh link went out

    # The newly-issued token verifies the account (old one was invalidated).
    fresh = outbox.token(EmailType.VERIFY_EMAIL)
    assert client.post("/auth/verify", json={"token": fresh}).status_code == 200
