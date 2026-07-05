"""Cross-cutting security regressions: secret leakage, CORS, auth gating, and
GET-can't-mutate."""

import pytest

from backend.tests.helpers import (
    auth_header,
    login,
    register,
    register_and_verify,
)

ALLOWED_ORIGIN = "http://localhost:5173"
DISALLOWED_ORIGIN = "http://evil.example"


def test_no_endpoint_echoes_refresh_token_in_body(client, sent_emails):
    user = register_and_verify(client, sent_emails)

    login_body = login(client).json()
    refresh_body = client.post("/auth/refresh").json()
    for body in (login_body, refresh_body):
        assert "refresh_token" not in body
        # ...nor under any other key.
        assert not any("refresh" in k for k in body)


def test_users_me_never_exposes_password_hash_or_internal_flags(client, sent_emails):
    user = register_and_verify(client, sent_emails)
    resp = client.get("/users/me", headers=auth_header(user["access_token"]))
    assert resp.status_code == 200, resp.text

    body = resp.json()
    # Exactly the UserPublic shape the frontend expects — nothing more.
    assert set(body.keys()) == {"id", "username", "email", "verified"}
    for leaky in ("hashed_password", "password", "is_active", "last_used"):
        assert leaky not in body


@pytest.mark.parametrize(
    "method,path,needs_body",
    [
        ("GET", "/users/me", False),
        ("GET", "/users/me/dashboard", False),
        ("PATCH", "/users/me/password", True),
        ("PATCH", "/users/me/email", True),
        ("DELETE", "/users/me", True),
        ("POST", "/auth/resend-verification", False),
    ],
)
def test_protected_routes_require_authentication(client, method, path, needs_body):
    body = {"current_password": "x", "new_password": "Password123", "new_email": "z@example.com"} if needs_body else None
    resp = client.request(method, path, json=body)
    assert resp.status_code == 401, f"{method} {path} -> {resp.status_code}"


def test_invalid_bearer_token_is_401(client):
    resp = client.get("/users/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert resp.status_code == 401


def test_unverified_user_blocked_from_verified_only_route(client, sent_emails):
    """require_verified_user gates the dashboard: authenticated-but-unverified
    is a 403 (authenticated, not permitted), not a 401."""
    register(client, email="alice@example.com")  # not verified
    resp = login(client, email="alice@example.com")
    token = resp.json()["access_token"]

    dash = client.get("/users/me/dashboard", headers=auth_header(token))
    assert dash.status_code == 403
    assert dash.json()["detail"] == "Email address not verified"


def test_state_mutating_token_endpoints_reject_get(client):
    """Scanner/prefetch safety: the single-use-token routes are POST-only, so a
    bare GET (email preview bot) can't consume a token or trigger a side effect."""
    for path in ("/auth/verify", "/auth/reset-password", "/auth/forgot-password"):
        assert client.get(path).status_code == 405


def test_cors_allows_configured_origin(client):
    resp = client.get("/health", headers={"Origin": ALLOWED_ORIGIN})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN
    assert resp.headers.get("access-control-allow-credentials") == "true"


def test_cors_rejects_disallowed_origin(client):
    """A disallowed origin must NOT be reflected back — otherwise a credentialed
    cross-origin read would be permitted."""
    resp = client.get("/health", headers={"Origin": DISALLOWED_ORIGIN})
    acao = resp.headers.get("access-control-allow-origin")
    assert acao != DISALLOWED_ORIGIN
    assert acao is None


def test_cors_preflight_disallowed_origin_not_approved(client):
    resp = client.options(
        "/auth/login",
        headers={
            "Origin": DISALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp.headers.get("access-control-allow-origin") != DISALLOWED_ORIGIN
