"""POST /auth/logout — cookie clearing and server-side token invalidation."""

from backend import models
from backend.core.security import hash_token
from backend.tests.helpers import register_and_verify, set_cookie_header


def test_logout_clears_cookie(client, sent_emails):
    register_and_verify(client, sent_emails)

    resp = client.post("/auth/logout")
    assert resp.status_code == 204

    raw = set_cookie_header(resp).lower()
    assert "refresh_token=" in raw
    # An expiry in the past / Max-Age=0 is how the browser is told to drop it.
    assert "max-age=0" in raw or "expires=" in raw


def test_logout_invalidates_server_side_token(client, sent_emails, db_session):
    register_and_verify(client, sent_emails)
    raw = client.cookies["refresh_token"]

    assert client.post("/auth/logout").status_code == 204

    # Server-side record is revoked...
    row = db_session.execute(
        models.RefreshToken.__table__.select().where(
            models.RefreshToken.token_hash == hash_token(raw)
        )
    ).first()
    assert row.revoked is True

    # ...so replaying the raw token directly (bypassing the cleared browser
    # cookie) still fails.
    client.cookies.set("refresh_token", raw)
    replay = client.post("/auth/refresh")
    assert replay.status_code == 401


def test_logout_is_idempotent_without_cookie(client):
    # No session at all — still a clean 204, never a 500.
    resp = client.post("/auth/logout")
    assert resp.status_code == 204


def test_logout_with_unknown_token_still_204(client):
    client.cookies.set("refresh_token", "never-issued")
    resp = client.post("/auth/logout")
    assert resp.status_code == 204
