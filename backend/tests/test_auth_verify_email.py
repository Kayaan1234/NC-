"""POST /auth/verify — single-use email verification token semantics."""

from datetime import datetime, timedelta, timezone

from backend import models
from backend.core.security import hash_token
from backend.tests.helpers import latest_token, register


def _naive_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def test_valid_token_verifies_account_once(client, sent_emails, db_session):
    register(client, email="alice@example.com")
    token = latest_token(sent_emails, kind="verify_email")

    resp = client.post("/auth/verify", json={"token": token})
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"message": "Email verified"}

    user = db_session.execute(
        models.User.__table__.select().where(models.User.email == "alice@example.com")
    ).first()
    assert user.verified is True


def test_reusing_consumed_token_fails(client, sent_emails):
    register(client, email="alice@example.com")
    token = latest_token(sent_emails, kind="verify_email")

    first = client.post("/auth/verify", json={"token": token})
    assert first.status_code == 200, first.text

    second = client.post("/auth/verify", json={"token": token})
    assert second.status_code == 400
    assert "invalid or expired" in second.json()["detail"].lower()


def test_expired_token_fails(client, sent_emails, db_session):
    register(client, email="alice@example.com")
    token = latest_token(sent_emails, kind="verify_email")

    # Push the token's expiry into the past (no wall-clock time travel needed).
    row = db_session.execute(
        models.EmailToken.__table__.select().where(
            models.EmailToken.token_hash == hash_token(token)
        )
    ).first()
    db_session.execute(
        models.EmailToken.__table__.update()
        .where(models.EmailToken.id == row.id)
        .values(expires_at=_naive_utc() - timedelta(hours=1))
    )
    db_session.commit()

    resp = client.post("/auth/verify", json={"token": token})
    assert resp.status_code == 400


def test_garbage_token_fails_safely(client):
    resp = client.post("/auth/verify", json={"token": "not-a-real-token"})
    assert resp.status_code == 400  # not a 500
    assert "invalid or expired" in resp.json()["detail"].lower()


def test_reset_token_cannot_be_used_on_verify_endpoint(client, sent_emails, db_session):
    """A RESET_PASSWORD token must not satisfy /auth/verify (purpose mismatch)."""
    register(client, email="alice@example.com")

    # Forge a live reset-purpose token directly in the DB for this user.
    user = db_session.execute(
        models.User.__table__.select().where(models.User.email == "alice@example.com")
    ).first()
    raw = "reset-purpose-raw-token"
    db_session.add(
        models.EmailToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            purpose=models.EmailTokenPurpose.RESET_PASSWORD,
            expires_at=_naive_utc() + timedelta(hours=1),
        )
    )
    db_session.commit()

    resp = client.post("/auth/verify", json={"token": raw})
    assert resp.status_code == 400


def test_verify_is_post_only(client):
    """GET must not consume the single-use token (scanner/prefetch safety)."""
    resp = client.get("/auth/verify")
    assert resp.status_code == 405
