"""Session revocation across the authenticated user routes.

Two independent TestClients (separate cookie jars) model two devices holding
live sessions for the same account."""

from uuid import UUID

from sqlalchemy import select

from backend import models
from backend.tests.helpers import (
    VALID_PASSWORD,
    auth_header,
    login,
    register_and_verify,
)


def _second_device(client_factory, email, password=VALID_PASSWORD):
    """Log the same user in on a fresh client and return (client, access_token)."""
    dev = client_factory()
    resp = login(dev, email=email, password=password)
    assert resp.status_code == 200, resp.text
    return dev, resp.json()["access_token"]


def test_password_change_revokes_all_sessions(client, client_factory, outbox, db_session):
    user = register_and_verify(client, outbox, email="alice@example.com")
    device_b, _ = _second_device(client_factory, "alice@example.com")

    # Device A changes the password.
    resp = client.patch(
        "/users/me/password",
        json={"current_password": VALID_PASSWORD, "new_password": "NewPass456"},
        headers=auth_header(user["access_token"]),
    )
    assert resp.status_code == 200, resp.text

    # Device B's refresh token is dead.
    assert device_b.post("/auth/refresh").status_code == 401
    # Device A's own session was revoked too.
    assert client.post("/auth/refresh").status_code == 401

    # DB: no live (non-revoked) refresh tokens remain for this user.
    rows = db_session.execute(
        select(models.RefreshToken).where(
            models.RefreshToken.user_id == UUID(user["user_id"])
        )
    ).scalars().all()
    assert rows and all(r.revoked for r in rows)


def test_account_deletion_revokes_and_cascades_at_db_level(client, client_factory, outbox, db_session):
    user = register_and_verify(client, outbox, email="alice@example.com")
    device_b, _ = _second_device(client_factory, "alice@example.com")

    resp = client.request(
        "DELETE",
        "/users/me",
        json={"current_password": VALID_PASSWORD},
        headers=auth_header(user["access_token"]),
    )
    assert resp.status_code == 204, resp.text

    # Device B can no longer refresh (token row was deleted by cascade).
    assert device_b.post("/auth/refresh").status_code == 401

    # DB: user row and its child rows are actually gone, not orphaned.
    remaining_user = db_session.execute(
        models.User.__table__.select().where(models.User.email == "alice@example.com")
    ).first()
    assert remaining_user is None

    remaining_tokens = db_session.execute(
        models.RefreshToken.__table__.select()
    ).fetchall()
    assert remaining_tokens == []
    remaining_email_tokens = db_session.execute(
        models.EmailToken.__table__.select()
    ).fetchall()
    assert remaining_email_tokens == []


def test_delete_account_wrong_password_rejected(client, outbox):
    user = register_and_verify(client, outbox, email="alice@example.com")
    resp = client.request(
        "DELETE",
        "/users/me",
        json={"current_password": "WrongPass123"},
        headers=auth_header(user["access_token"]),
    )
    assert resp.status_code == 400
    # Session must survive a failed deletion.
    assert client.post("/auth/refresh").status_code == 200


def test_password_change_wrong_current_password_rejected(client, outbox):
    user = register_and_verify(client, outbox, email="alice@example.com")
    resp = client.patch(
        "/users/me/password",
        json={"current_password": "WrongPass123", "new_password": "NewPass456"},
        headers=auth_header(user["access_token"]),
    )
    assert resp.status_code == 400
    assert client.post("/auth/refresh").status_code == 200


def test_email_change_does_not_revoke_sessions(client, client_factory, outbox, db_session):
    """CURRENT BEHAVIOUR — FLAGGED, not an endorsement.

    auth_test_suite.md (line 66) expects 'Changing email revokes sessions', but
    routers/users.py::update_email does NOT touch refresh tokens — it only flips
    verified=False and re-sends verification. This test pins the current
    behaviour so the gap is visible; decide whether email change should join
    password-change/delete in the revoke-all set.
    """
    user = register_and_verify(client, outbox, email="alice@example.com")
    device_b, _ = _second_device(client_factory, "alice@example.com")

    resp = client.patch(
        "/users/me/email",
        json={"new_email": "alice.new@example.com", "current_password": VALID_PASSWORD},
        headers=auth_header(user["access_token"]),
    )
    assert resp.status_code == 200, resp.text

    # Sessions still work — the point being flagged.
    assert device_b.post("/auth/refresh").status_code == 200
    assert client.post("/auth/refresh").status_code == 200
