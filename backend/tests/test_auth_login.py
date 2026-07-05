"""POST /auth/login — credential check, cookie flags, generic failures, and the
constant-time (no email-enumeration) property.

Rather than the flaky wall-clock timing assertion the plan sketches, we test the
*mechanism* that makes the two failure paths indistinguishable: identical
status+body, and bcrypt actually running against the dummy hash when the email
is unknown."""

import backend.routers.auth as auth_module
from backend.tests.helpers import (
    VALID_PASSWORD,
    login,
    register,
    set_cookie_header,
)


def _register_alice(client):
    resp = register(client, username="alice", email="alice@example.com")
    assert resp.status_code == 200, resp.text


def test_login_success_body_shape_has_no_refresh_token(client, sent_emails):
    _register_alice(client)
    resp = login(client)
    assert resp.status_code == 200, resp.text

    body = resp.json()
    # Matches frontend TokenResponse: access_token, user_id, verified — and the
    # refresh token must NEVER appear in the body (httpOnly-cookie only).
    assert set(body.keys()) == {"access_token", "user_id", "verified"}
    assert "refresh_token" not in body
    assert body["access_token"]


def test_login_sets_refresh_cookie_with_correct_flags(client, sent_emails):
    _register_alice(client)
    resp = login(client)

    raw = set_cookie_header(resp)
    assert "refresh_token=" in raw
    assert "HttpOnly" in raw
    assert "Secure" in raw
    assert "samesite=strict" in raw.lower()
    assert "Path=/auth" in raw


def test_wrong_password_generic_400(client, sent_emails):
    _register_alice(client)
    resp = login(client, email="alice@example.com", password="WrongPass123")
    assert resp.status_code == 400
    assert resp.json() == {"detail": "Invalid email or password"}


def test_nonexistent_email_matches_wrong_password_exactly(client, sent_emails):
    """No enumeration: unknown-email and wrong-password are byte-identical."""
    _register_alice(client)

    wrong_pw = login(client, email="alice@example.com", password="WrongPass123")
    unknown = login(client, email="ghost@example.com", password=VALID_PASSWORD)

    assert wrong_pw.status_code == unknown.status_code == 400
    assert wrong_pw.json() == unknown.json() == {"detail": "Invalid email or password"}
    # Neither failure sets a refresh cookie.
    assert "set-cookie" not in {k.lower() for k in unknown.headers}


def test_unknown_email_still_runs_bcrypt_against_dummy_hash(client, monkeypatch):
    """The timing-oracle defence: even with no user row, login must run bcrypt
    (against _DUMMY_PASSWORD_HASH) so the unknown-email path costs the same as a
    wrong-password path."""
    calls: list[bytes] = []
    real_checkpw = auth_module.bcrypt.checkpw

    def spy(password: bytes, hashed: bytes) -> bool:
        calls.append(hashed)
        return real_checkpw(password, hashed)

    monkeypatch.setattr(auth_module.bcrypt, "checkpw", spy)

    resp = login(client, email="ghost@example.com", password=VALID_PASSWORD)
    assert resp.status_code == 400
    assert calls, "bcrypt.checkpw was skipped for an unknown email — timing oracle!"
    assert calls[0] == auth_module._DUMMY_PASSWORD_HASH


def test_login_is_post_only(client):
    resp = client.get("/auth/login")
    assert resp.status_code == 405
