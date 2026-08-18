"""POST /auth/refresh — rotation, revocation-on-use, expiry, and the
server-side hash storage invariant."""

from datetime import datetime, timedelta, timezone

from backend import models
from backend.core.security import hash_token
from backend.tests.helpers import login, register_and_verify, set_cookie_header


def _naive_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def test_valid_refresh_issues_new_access_token(client, outbox):
    register_and_verify(client, outbox)
    resp = client.post("/auth/refresh")
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert set(body.keys()) == {"access_token", "user_id", "verified"}
    assert "refresh_token" not in body
    assert body["access_token"]


def test_refresh_rotates_and_old_cookie_is_revoked(client, outbox, db_session):
    register_and_verify(client, outbox)

    # Capture the raw refresh token currently in the jar (set at login).
    old_raw = client.cookies["refresh_token"]

    first = client.post("/auth/refresh")
    assert first.status_code == 200
    new_raw = client.cookies["refresh_token"]
    assert new_raw != old_raw, "refresh token was not rotated"

    # Server-side: the presented (old) token is now revoked.
    old_row = db_session.execute(
        models.RefreshToken.__table__.select().where(
            models.RefreshToken.token_hash == hash_token(old_raw)
        )
    ).first()
    assert old_row.revoked is True

    # Replaying the OLD token directly (bypassing the browser jar) must fail.
    client.cookies.set("refresh_token", old_raw)
    replay = client.post("/auth/refresh")
    assert replay.status_code == 401


def test_missing_cookie_returns_401_not_500(client):
    resp = client.post("/auth/refresh")
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid or expired refresh token"}


def test_expired_refresh_token_returns_401(client, outbox, db_session):
    register_and_verify(client, outbox)
    raw = client.cookies["refresh_token"]

    db_session.execute(
        models.RefreshToken.__table__.update()
        .where(models.RefreshToken.token_hash == hash_token(raw))
        .values(expires_at=_naive_utc() - timedelta(days=1))
    )
    db_session.commit()

    resp = client.post("/auth/refresh")
    assert resp.status_code == 401


def test_stored_hash_matches_issued_token_and_raw_is_never_stored(client, outbox, db_session):
    """Spot-check the hashing invariant directly: the DB holds SHA-256(raw),
    never the raw token itself."""
    register_and_verify(client, outbox)
    raw = client.cookies["refresh_token"]

    rows = db_session.execute(models.RefreshToken.__table__.select()).fetchall()
    hashes = {r.token_hash for r in rows}
    assert hash_token(raw) in hashes
    assert raw not in hashes  # raw token is not persisted anywhere


def test_refresh_is_post_only(client):
    resp = client.get("/auth/refresh")
    assert resp.status_code == 405
