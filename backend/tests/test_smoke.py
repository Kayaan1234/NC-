"""Load-bearing infrastructure check: the cookie round-trip must work end to
end (register -> verify -> login -> refresh -> logout) or the whole priority-1
area (refresh/rotation/revocation) is testing an artifact, not the backend."""

from backend.tests.helpers import login, register, register_and_verify, verify_latest


def test_full_cookie_round_trip(client, sent_emails):
    reg = register(client)
    assert reg.status_code == 200, reg.text

    verify = verify_latest(client, sent_emails)
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
