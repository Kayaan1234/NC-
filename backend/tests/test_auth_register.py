"""POST /auth/register — registration, validation, and the enumeration-resistant
response contract (a message-only body, identical for free vs. taken emails)."""

import pytest

from backend.routers.auth import GENERIC_REGISTER_MESSAGE
from backend.tests.helpers import VALID_PASSWORD, login, register


def test_valid_registration_returns_message_only_shape(client, sent_emails):
    resp = register(client, username="alice", email="alice@example.com")
    assert resp.status_code == 200, resp.text

    body = resp.json()
    # Message-only: no user_id/verified that could differ between free/taken.
    assert set(body.keys()) == {"message"}
    assert body["message"] == GENERIC_REGISTER_MESSAGE


def test_registration_triggers_verification_email_with_usable_token(client, sent_emails):
    register(client, email="alice@example.com")

    assert len(sent_emails) == 1
    email = sent_emails[0]
    assert email["kind"] == "verify_email"
    assert email["to_email"] == "alice@example.com"

    # The emailed token actually verifies the account (single-use path proven in
    # test_auth_verify_email.py).
    verify = client.post("/auth/verify", json={"token": email["token"]})
    assert verify.status_code == 200, verify.text


@pytest.mark.parametrize(
    "field,value",
    [
        ("email", "not-an-email"),
        ("password", "short1A"),          # < 8 chars
        ("password", "alllowercase1"),    # no uppercase
        ("password", "NoDigitsHere"),     # no digit
        ("username", "ab"),               # < 3 chars
        ("username", "has spaces"),       # pattern violation
        ("username", "bad!char"),         # pattern violation
    ],
)
def test_invalid_fields_rejected_with_422(client, field, value):
    payload = {
        "username": "alice",
        "email": "alice@example.com",
        "password": VALID_PASSWORD,
        "confirm_password": VALID_PASSWORD,
    }
    payload[field] = value
    if field == "password":
        payload["confirm_password"] = value

    resp = register(
        client,
        username=payload["username"],
        email=payload["email"],
        password=payload["password"],
    )
    assert resp.status_code == 422, resp.text
    # 422 detail is the {loc,msg}[] array the SPA's extractDetail flattens.
    assert isinstance(resp.json()["detail"], list)


def test_password_mismatch_rejected(client):
    resp = client.post(
        "/auth/register",
        json={
            "username": "alice",
            "email": "alice@example.com",
            "password": VALID_PASSWORD,
            "confirm_password": "Different123",
        },
    )
    assert resp.status_code == 422, resp.text


def test_new_user_is_unverified_but_can_still_log_in(client, sent_emails):
    """DESIGN NOTE (confirm the intended rule): login does NOT gate on `verified`.
    A freshly-registered, still-unverified account logs in successfully and gets
    tokens; verification is only enforced on verified-gated routes such as
    /users/me/dashboard (see test_users_me.py). If unverified users should be
    blocked from logging in entirely, that rule is currently missing in
    routers/auth.py::login."""
    register(client, email="alice@example.com")
    resp = login(client, email="alice@example.com")
    assert resp.status_code == 200, resp.text
    assert resp.json()["verified"] is False


def test_duplicate_email_does_not_disclose_and_notifies_owner(client, sent_emails):
    """Enumeration-resistant: a second registration with an existing email
    returns the SAME generic 200 body as a fresh signup (no 'already registered'
    tell), and the real owner is nudged via an out-of-band account-exists email.
    """
    first = register(client, username="alice", email="dupe@example.com")
    assert first.status_code == 200
    assert first.json()["message"] == GENERIC_REGISTER_MESSAGE
    sent_emails.clear()

    # Different username (so we don't trip the username-taken path), same email.
    second = register(client, username="bob", email="dupe@example.com")
    assert second.status_code == 200
    # Byte-identical response to a fresh registration.
    assert second.json() == first.json()

    # No new account was created — no verification email — but the owner is told.
    kinds = [e["kind"] for e in sent_emails]
    assert kinds == ["account_exists"]
    assert sent_emails[0]["to_email"] == "dupe@example.com"


def test_duplicate_email_response_matches_fresh_email_response(client, sent_emails):
    """The whole point: free-email and taken-email responses are indistinguishable."""
    register(client, username="alice", email="taken@example.com")

    taken = register(client, username="bob", email="taken@example.com")
    fresh = register(client, username="carol", email="free@example.com")
    assert taken.status_code == fresh.status_code == 200
    assert taken.json() == fresh.json()


def test_duplicate_username_still_rejected_with_400(client, sent_emails):
    """Usernames are public identifiers — a clash IS surfaced so signup can
    prompt for another. (Only email existence is hidden.)"""
    register(client, username="alice", email="a@example.com")
    resp = register(client, username="alice", email="b@example.com")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Username already taken"
