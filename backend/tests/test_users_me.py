"""GET /users/me — the response shape the SPA consumes (UserPublic).

This file used to also cover GET /users/me/dashboard and the rung lock/unlock
logic. That route, the DashboardOut schema, and the Rungs/Exercises models were
all removed when exercise content moved into the SPA bundle, so those tests were
dropped rather than restored — they had no code left to exercise.
"""

from uuid import UUID

from backend.tests.helpers import auth_header, register_and_verify


def test_users_me_returns_userpublic_shape(client, outbox):
    user = register_and_verify(client, outbox, username="alice", email="alice@example.com")
    resp = client.get("/users/me", headers=auth_header(user["access_token"]))
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert set(body.keys()) == {"id", "username", "email", "verified"}
    assert body["username"] == "alice"
    assert body["email"] == "alice@example.com"
    assert body["verified"] is True
    UUID(body["id"])


def test_users_me_never_leaks_the_password_hash(client, outbox):
    """UserPublic is an allowlist, not an exclusion list — but assert the
    consequence directly, since a future field added to the model would
    otherwise only be caught by the key-set check above."""
    user = register_and_verify(client, outbox)
    body = client.get("/users/me", headers=auth_header(user["access_token"])).json()

    serialised = str(body).lower()
    assert "hashed_password" not in serialised
    assert "$2b$" not in serialised  # a bcrypt hash's prefix
    assert "is_active" not in body
    assert "last_used" not in body
