"""Rate limiting (slowapi). This is the ONE module that turns the limiter back
on; the autouse fixture in conftest disables it everywhere else.

Asserts the slowapi 429 contract: `detail` + `retry_after` in the body and a
numerically-consistent `Retry-After` header (see
main.py::rate_limit_exceeded_handler). The per-user cooldowns now raise
CooldownError and share this exact shape (pinned in
test_auth_resend_verification.py and test_users_email.py)."""

import pytest

from backend.core.config import settings
from backend.core.limiter import limiter
from backend.tests.helpers import VALID_PASSWORD, register


@pytest.fixture(autouse=True)
def _enable_limiter():
    """Re-enable + wipe the limiter for each test in this module only."""
    limiter.reset()
    limiter.enabled = True
    yield
    limiter.reset()
    limiter.enabled = False


def _limit_count(limit_str: str) -> int:
    # e.g. "10/minute" -> 10
    return int(limit_str.split("/")[0])


def test_login_trips_after_limit_with_custom_429_body(client):
    allowed = _limit_count(settings.RATE_LIMIT_AUTH)

    for _ in range(allowed):
        r = client.post("/auth/login", json={"email": "x@example.com", "password": VALID_PASSWORD})
        assert r.status_code == 400  # unknown user, but counts against the limit

    tripped = client.post("/auth/login", json={"email": "x@example.com", "password": VALID_PASSWORD})
    assert tripped.status_code == 429

    body = tripped.json()
    assert body["detail"] == "Too many requests. Please wait and try again."
    # The SPA reads retry_after from the body AND Retry-After from the header;
    # both must be present and agree.
    assert "retry_after" in body
    assert tripped.headers.get("Retry-After") == str(body["retry_after"])
    assert body["retry_after"] >= 0


def test_email_send_limit_trips_on_register(client):
    allowed = _limit_count(settings.RATE_LIMIT_EMAIL_SEND)

    for i in range(allowed):
        r = register(client, username=f"user{i}", email=f"user{i}@example.com")
        assert r.status_code == 200, r.text

    tripped = register(client, username="user_over", email="over@example.com")
    assert tripped.status_code == 429
    assert tripped.json()["detail"] == "Too many requests. Please wait and try again."


def test_limit_resets_when_window_clears(client):
    allowed = _limit_count(settings.RATE_LIMIT_AUTH)
    for _ in range(allowed + 1):
        client.post("/auth/login", json={"email": "x@example.com", "password": VALID_PASSWORD})

    assert client.post(
        "/auth/login", json={"email": "x@example.com", "password": VALID_PASSWORD}
    ).status_code == 429

    # Simulate the window elapsing (reset the fixed-window counters).
    limiter.reset()

    assert client.post(
        "/auth/login", json={"email": "x@example.com", "password": VALID_PASSWORD}
    ).status_code == 400


def test_different_ips_do_not_share_a_bucket(client_factory):
    allowed = _limit_count(settings.RATE_LIMIT_AUTH)

    ip_a = client_factory(host="10.0.0.1")
    ip_b = client_factory(host="10.0.0.2")

    # Exhaust IP A's bucket.
    for _ in range(allowed + 1):
        ip_a.post("/auth/login", json={"email": "x@example.com", "password": VALID_PASSWORD})
    assert ip_a.post(
        "/auth/login", json={"email": "x@example.com", "password": VALID_PASSWORD}
    ).status_code == 429

    # IP B is unaffected — separate bucket.
    assert ip_b.post(
        "/auth/login", json={"email": "x@example.com", "password": VALID_PASSWORD}
    ).status_code == 400
