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


def test_no_endpoint_echoes_refresh_token_in_body(client, outbox):
    user = register_and_verify(client, outbox)

    login_body = login(client).json()
    refresh_body = client.post("/auth/refresh").json()
    for body in (login_body, refresh_body):
        assert "refresh_token" not in body
        # ...nor under any other key.
        assert not any("refresh" in k for k in body)


def test_users_me_never_exposes_password_hash_or_internal_flags(client, outbox):
    user = register_and_verify(client, outbox)
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
        # /users/me/dashboard used to sit here; the route is gone. /train/* is
        # the current authenticated surface, so it takes the slot.
        ("GET", "/train/models", False),
        ("GET", "/train/jobs", False),
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


def test_a_token_whose_subject_is_not_a_uuid_is_401_not_500(client):
    """get_current_user parses `sub` with UUID(), which raises ValueError on
    anything else. Without the try/except that would be a 500 — and a 500 tells
    an attacker their input reached further into the system than a 401 does."""
    from backend.core.security import create_access_token

    resp = client.get(
        "/users/me", headers=auth_header(create_access_token("not-a-uuid"))
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Could not validate credentials"


def test_a_token_for_a_deleted_user_is_401(client, outbox, db_session):
    """A JWT is stateless, so it stays cryptographically valid for its full TTL
    after the row it names is gone. The user lookup is what closes that window."""
    from backend import models

    account = register_and_verify(client, outbox)
    headers = auth_header(account["access_token"])
    assert client.get("/users/me", headers=headers).status_code == 200

    db_session.execute(models.User.__table__.delete())
    db_session.commit()

    assert client.get("/users/me", headers=headers).status_code == 401


def test_all_three_rejection_paths_are_indistinguishable_from_outside(client):
    """Garbage token, valid-but-non-UUID subject, and unknown user must produce
    the same response — otherwise the differences map out which stage rejected
    the caller."""
    from backend.core.security import create_access_token

    responses = [
        client.get("/users/me", headers={"Authorization": "Bearer not.a.jwt"}),
        client.get("/users/me", headers=auth_header(create_access_token("not-a-uuid"))),
        client.get(
            "/users/me",
            headers=auth_header(create_access_token("00000000-0000-4000-8000-000000000000")),
        ),
    ]

    shapes = {(r.status_code, r.json()["detail"], r.headers.get("www-authenticate")) for r in responses}
    assert len(shapes) == 1, f"rejection paths are distinguishable: {shapes}"


def test_unverified_user_blocked_from_verified_only_route(client, outbox):
    """require_verified_user gates /train: authenticated-but-unverified is a 403
    (authenticated, not permitted), not a 401.

    Originally written against /users/me/dashboard, which no longer exists;
    /train/models is the verified-only route today. The distinction under test is
    the dependency, not the specific path.
    """
    register(client, email="alice@example.com")  # not verified
    resp = login(client, email="alice@example.com")
    token = resp.json()["access_token"]

    gated = client.get("/train/models", headers=auth_header(token))
    assert gated.status_code == 403
    assert gated.json()["detail"] == "Email address not verified"


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
