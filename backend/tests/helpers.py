"""Small, explicit helpers shared across the test files.

Kept as plain functions (not fixtures) so each test reads as a linear script:
register -> grab the token from the outbox -> verify -> login.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from backend.models.EmailOutbox import EmailType

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


def verify_latest(client: TestClient, outbox):
    """Consume the most recent verification token sitting in the outbox."""
    return client.post("/auth/verify", json={"token": outbox.token(EmailType.VERIFY_EMAIL)})


def login(client: TestClient, *, email: str = "alice@example.com", password: str = VALID_PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


def register_and_verify(
    client: TestClient,
    outbox,
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
    verified = verify_latest(client, outbox)
    assert verified.status_code == 200, verified.text
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


def request_password_reset(client: TestClient, outbox, *, email: str):
    """POST /auth/forgot-password and run the outbox through to delivery.

    Getting a reset link takes two hops, by design. The endpoint stages only a
    FORGOT_PASSWORD_REQUEST row carrying the raw address — it does no user lookup
    at all, so response timing can't reveal whether the address is registered.
    The drain is what resolves that row to a user, applies the per-user reset
    cooldown, mints the token and enqueues the actual send. Tests that want the
    token therefore have to drain; tests that want to prove the *endpoint* leaks
    nothing should not.

    Returns the endpoint's response. Read the token from
    `outbox.delivered_token("password_reset")`.
    """
    response = client.post("/auth/forgot-password", json={"email": email})
    outbox.drain()
    return response


def auth_header(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


def set_cookie_header(response) -> str:
    """The raw Set-Cookie header string(s), joined — for asserting cookie flags
    (HttpOnly/SameSite aren't exposed via the httpx cookie jar)."""
    return " || ".join(response.headers.get_list("set-cookie"))
