"""Unit-tier guarantees.

The tier's whole claim is "no I/O". `backend/tests/conftest.py` already keeps the
database fixtures away from anything under this directory; this file enforces the
other half — no network.

It matters most for test_email_rendering.py, which calls the real `resend`
library with `resend.Emails.send` stubbed. A future test that forgot the stub
would otherwise reach out to Resend's API for real, and the only symptom would be
a slow test (or, in CI, a flaky one).
"""

import socket

import pytest


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Turn any attempt to open a socket into a loud failure."""
    def blocked(*args, **kwargs):
        raise RuntimeError(
            "A unit test tried to open a network connection. Unit tests must do no "
            "I/O — stub the client, or move the test to the integration tier."
        )

    monkeypatch.setattr(socket, "socket", blocked)
    # urllib/requests reach for these directly, so blocking socket.socket alone
    # would leave a way through.
    monkeypatch.setattr(socket, "create_connection", blocked)
