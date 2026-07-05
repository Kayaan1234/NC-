"""PATCH /users/me/email — update flow, validation branches, and the
once-per-day change cooldown (an account-tier throttle with its own 429 shape).

The successful path is covered in test_auth_revocation.py
(test_email_change_does_not_revoke_sessions, which also flags that it does NOT
revoke sessions). Here we pin the rejection branches."""

from backend.tests.helpers import (
    VALID_PASSWORD,
    auth_header,
    register_and_verify,
)


def test_successful_change_notifies_the_old_address(client, sent_emails):
    """The old email is warned so an unauthorised change is recoverable (we keep
    sessions alive by design, so this notice is the real protection)."""
    alice = register_and_verify(client, sent_emails, email="old@example.com")
    sent_emails.clear()

    resp = client.patch(
        "/users/me/email",
        json={"new_email": "new@example.com", "current_password": VALID_PASSWORD},
        headers=auth_header(alice["access_token"]),
    )
    assert resp.status_code == 200, resp.text

    changed = [e for e in sent_emails if e["kind"] == "email_changed"]
    assert len(changed) == 1
    # Notice goes to the PREVIOUS address and names the new one.
    assert changed[0]["to_email"] == "old@example.com"
    assert changed[0]["new_email"] == "new@example.com"

    # And the new address still gets its verification email (verified=False).
    assert any(e["kind"] == "verify_email" and e["to_email"] == "new@example.com" for e in sent_emails)


def test_failed_change_does_not_notify(client, sent_emails):
    """A rejected change (wrong password) must not fire the notification."""
    alice = register_and_verify(client, sent_emails, email="old@example.com")
    sent_emails.clear()

    resp = client.patch(
        "/users/me/email",
        json={"new_email": "new@example.com", "current_password": "WrongPass123"},
        headers=auth_header(alice["access_token"]),
    )
    assert resp.status_code == 400
    assert [e for e in sent_emails if e["kind"] == "email_changed"] == []


def test_change_to_existing_email_rejected(client, client_factory, sent_emails):
    """CURRENT BEHAVIOUR — same enumeration surface flagged for /auth/register:
    changing to an address already in use returns a distinguishing 400 'Email
    already in use', confirming to an authenticated caller that the address is
    taken."""
    alice = register_and_verify(client, sent_emails, username="alice", email="alice@example.com")
    bob_client = client_factory()
    register_and_verify(bob_client, sent_emails, username="bob", email="bob@example.com")

    resp = client.patch(
        "/users/me/email",
        json={"new_email": "bob@example.com", "current_password": VALID_PASSWORD},
        headers=auth_header(alice["access_token"]),
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Email already in use"


def test_change_to_same_email_rejected(client, sent_emails):
    alice = register_and_verify(client, sent_emails, email="alice@example.com")
    resp = client.patch(
        "/users/me/email",
        json={"new_email": "alice@example.com", "current_password": VALID_PASSWORD},
        headers=auth_header(alice["access_token"]),
    )
    assert resp.status_code == 400
    assert "different" in resp.json()["detail"].lower()


def test_change_with_wrong_password_rejected(client, sent_emails):
    alice = register_and_verify(client, sent_emails, email="alice@example.com")
    resp = client.patch(
        "/users/me/email",
        json={"new_email": "alice.new@example.com", "current_password": "WrongPass123"},
        headers=auth_header(alice["access_token"]),
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Incorrect password"


def test_second_change_within_cooldown_returns_unified_429(client, sent_emails):
    """The once-per-day cooldown raises CooldownError, so its 429 matches the
    slowapi limiter's shape: detail + body `retry_after` + a matching
    Retry-After header (one consistent contract across all throttles)."""
    alice = register_and_verify(client, sent_emails, email="alice@example.com")

    first = client.patch(
        "/users/me/email",
        json={"new_email": "alice.new@example.com", "current_password": VALID_PASSWORD},
        headers=auth_header(alice["access_token"]),
    )
    assert first.status_code == 200, first.text

    second = client.patch(
        "/users/me/email",
        json={"new_email": "alice.newer@example.com", "current_password": VALID_PASSWORD},
        headers=auth_header(alice["access_token"]),
    )
    assert second.status_code == 429
    body = second.json()
    assert "retry_after" in body
    assert body["retry_after"] >= 0
    assert second.headers.get("Retry-After") == str(body["retry_after"])
    assert "once per day" in body["detail"].lower()
