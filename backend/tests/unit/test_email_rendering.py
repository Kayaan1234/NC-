"""core/email.py — the link each email actually contains.

These senders run only in the worker's drain loop, so nothing else in the suite
exercises them. The part worth covering is the URL: every one of these emails is
useless if its link points at the wrong page, and that has happened before.

`resend.Emails.send` is stubbed. Failures inside these functions are meant to
PROPAGATE — the drainer catches them and schedules a retry — so the propagation
is asserted rather than smoothed over.
"""

import pytest
import resend

from backend.core import email as email_module
from backend.core.config import settings
from backend.core.email import (
    send_account_exists_email,
    send_email_changed_notification,
    send_password_reset_email,
    send_verification_email,
)

TOKEN = "a-raw-single-use-token"


@pytest.fixture()
def sent(monkeypatch):
    """Capture the params handed to Resend instead of making a network call."""
    captured: list[dict] = []
    monkeypatch.setattr(resend.Emails, "send", lambda params: captured.append(params))
    return captured


def test_the_verification_link_points_at_the_spas_verify_page(sent):
    send_verification_email(token=TOKEN, to_email="alice@example.com")

    html = sent[0]["html"]
    assert f"{settings.FRONTEND_URL}/verify-email?token={TOKEN}" in html


def test_the_reset_link_points_at_the_spas_reset_page_not_the_verify_page(sent):
    """The regression guard for a real past bug: reusing the verification sender
    here produced a link that POSTs to /auth/verify, which rejects any token whose
    purpose isn't VERIFY_EMAIL — so the reset link could never be consumed and the
    only symptom was users saying the link "didn't work"."""
    send_password_reset_email(token=TOKEN, to_email="alice@example.com")

    html = sent[0]["html"]
    assert f"{settings.FRONTEND_URL}/password-reset?token={TOKEN}" in html
    assert "/verify-email" not in html


def test_the_two_token_links_are_never_the_same_url(sent):
    send_verification_email(token=TOKEN, to_email="alice@example.com")
    send_password_reset_email(token=TOKEN, to_email="alice@example.com")

    assert sent[0]["html"] != sent[1]["html"]
    assert sent[0]["subject"] != sent[1]["subject"]


@pytest.mark.parametrize(
    "call",
    [
        lambda: send_verification_email(token=TOKEN, to_email="alice@example.com"),
        lambda: send_password_reset_email(token=TOKEN, to_email="alice@example.com"),
        lambda: send_account_exists_email(to_email="alice@example.com"),
        lambda: send_email_changed_notification(
            to_email="old@example.com", new_email="new@example.com"
        ),
    ],
    ids=["verify", "reset", "account_exists", "email_changed"],
)
def test_every_email_is_addressed_from_the_configured_sender(sent, call):
    call()
    params = sent[0]
    assert params["from"] == settings.EMAIL_FROM
    assert params["to"] == ["alice@example.com"] or params["to"] == ["old@example.com"]
    assert params["subject"]
    assert params["html"]


def test_the_account_exists_email_carries_no_token(sent):
    """It goes to an address that tried to register again, so it must not hand
    the sender anything that could act on the existing account."""
    send_account_exists_email(to_email="alice@example.com")

    html = sent[0]["html"]
    assert "token=" not in html
    assert f"{settings.FRONTEND_URL}/login" in html
    assert f"{settings.FRONTEND_URL}/forgot-password" in html


def test_the_email_changed_notice_goes_to_the_old_address_and_names_the_new_one(sent):
    """Sessions deliberately survive an email change, so this notice is the real
    protection against an unauthorised one — it has to reach the address that is
    losing the account."""
    send_email_changed_notification(to_email="old@example.com", new_email="new@example.com")

    params = sent[0]
    assert params["to"] == ["old@example.com"]
    assert "new@example.com" in params["html"]


def test_a_resend_failure_propagates_so_the_drainer_can_retry(monkeypatch):
    """Swallowing here would turn a transient Resend outage into a silently
    dropped email — the exact durability hole the outbox exists to close."""
    def boom(params):
        raise RuntimeError("resend is down")

    monkeypatch.setattr(resend.Emails, "send", boom)

    with pytest.raises(RuntimeError, match="resend is down"):
        send_verification_email(token=TOKEN, to_email="alice@example.com")


def test_the_api_key_is_taken_from_settings_at_call_time(sent, monkeypatch):
    monkeypatch.setattr(email_module.settings, "RESEND_API_KEY", "key-set-at-call-time")

    send_account_exists_email(to_email="alice@example.com")

    assert resend.api_key == "key-set-at-call-time"
