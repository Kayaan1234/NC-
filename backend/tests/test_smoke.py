"""Load-bearing infrastructure check: the cookie round-trip must work end to
end (register -> verify -> login -> refresh -> logout) or the whole priority-1
area (refresh/rotation/revocation) is testing an artifact, not the backend."""

from backend.models.EmailOutbox import EmailType
from backend.tests.helpers import login, register, verify_latest


def test_full_cookie_round_trip(client, outbox):
    reg = register(client)
    assert reg.status_code == 200, reg.text

    verify = verify_latest(client, outbox)
    assert verify.status_code == 200, verify.text

    resp = login(client)
    assert resp.status_code == 200, resp.text
    assert "refresh_token" in client.cookies  # cookie landed in the jar

    # The Secure cookie must actually be sent back over https://testserver.
    refreshed = client.post("/auth/refresh")
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["access_token"]

    logout = client.post("/auth/logout")
    assert logout.status_code == 204, logout.text


def test_registration_stages_exactly_one_verification_email(client, outbox):
    """The harness's email seam: registering enqueues one outbox row carrying the
    raw token, and makes no network call at all."""
    assert register(client).status_code == 200

    rows = outbox.rows()
    assert [row["kind"] for row in rows] == [EmailType.VERIFY_EMAIL.value]
    assert rows[0]["status"] == "queued"
    assert rows[0]["to_email"] == "alice@example.com"
    assert rows[0]["token"]


def test_tables_are_empty_at_the_start_of_every_test(db_session):
    """Guards the TRUNCATE fixture. If this ever fails, tests have started
    leaking state into each other and results downstream are untrustworthy."""
    from sqlalchemy import func, select

    from backend import models

    for model in (models.User, models.RefreshToken, models.EmailToken):
        count = db_session.execute(select(func.count()).select_from(model)).scalar_one()
        assert count == 0, f"{model.__name__} was not empty at test start"
