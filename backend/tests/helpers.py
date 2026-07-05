"""Small, explicit helpers shared across the auth test files.

Kept as plain functions (not fixtures) so each test reads as a linear script:
register -> grab token from the fake inbox -> verify -> login.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

# A password that satisfies the StrongPassword policy (8-30 chars, >=1 upper,
# >=1 digit). Reused so tests don't each reinvent a valid password.
VALID_PASSWORD = "Password123"


def register(
    client: TestClient,
    *,
    username: str = "alice",
    email: str = "alice@example.com",
    password: str = VALID_PASSWORD,
    confirm_password: str | None = None,
):
    return client.post(
        "/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
            "confirm_password": password if confirm_password is None else confirm_password,
        },
    )


def latest_token(sent_emails: list[dict], *, kind: str | None = None) -> str:
    """Return the raw token from the most recent captured email (optionally of a
    given kind: 'verify_email' or 'reset_password')."""
    items = [e for e in sent_emails if kind is None or e["kind"] == kind]
    assert items, f"no captured email of kind={kind!r}"
    return items[-1]["token"]


def verify_latest(client: TestClient, sent_emails: list[dict]):
    token = latest_token(sent_emails, kind="verify_email")
    return client.post("/auth/verify", json={"token": token})


def login(client: TestClient, *, email: str = "alice@example.com", password: str = VALID_PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


def register_and_verify(
    client: TestClient,
    sent_emails: list[dict],
    *,
    username: str = "alice",
    email: str = "alice@example.com",
    password: str = VALID_PASSWORD,
) -> dict[str, Any]:
    """Register a user, consume the verification email, and log them in.

    Returns {"email", "password", "username", "user_id", "access_token"} with a
    live refresh cookie already sitting in `client`'s jar.
    """
    reg = register(client, username=username, email=email, password=password)
    assert reg.status_code == 200, reg.text
    verify_latest(client, sent_emails)
    resp = login(client, email=email, password=password)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return {
        "email": email,
        "password": password,
        "username": username,
        "user_id": body["user_id"],
        "access_token": body["access_token"],
    }


def auth_header(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def set_cookie_header(response) -> str:
    """The raw Set-Cookie header string(s), joined — for asserting cookie flags
    (HttpOnly/SameSite aren't exposed via the httpx cookie jar)."""
    return " || ".join(response.headers.get_list("set-cookie"))
