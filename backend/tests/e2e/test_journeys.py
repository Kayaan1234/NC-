"""End-to-end journeys, driven in-process against the real test database.

Deliberately small. Each test below crosses every layer the app has — HTTP
handler, service, outbox, worker, subprocess, database — so a break anywhere in
the chain fails here even when every unit test still passes. Anything that can
be pinned at a lower layer belongs at that layer instead.

"In-process" means the worker's sub-functions (`claim_one`, `execute`) are called
directly rather than running `worker.main()`, which installs real signal handlers
and loops forever. The C++ binary is a stub script, so no `g++` and no MNIST.
"""

import stat

import pytest
from sqlalchemy import select

from backend import worker
from backend.core.config import settings
from backend.models.EmailOutbox import EmailType
from backend.models.RefreshToken import RefreshToken
from backend.models.TrainingJob import JobStatus, TrainingJob
from backend.services import registry
from backend.services.registry import MODELS
from backend.tests.helpers import (
    VALID_PASSWORD,
    auth_header,
    login,
    register,
    request_password_reset,
)

pytestmark = pytest.mark.e2e


@pytest.fixture()
def stubbed_step0(tmp_path, monkeypatch):
    """Point the step0 model at a stub binary for the duration of one test.

    MODELS holds frozen dataclasses shared process-wide, so the entry is replaced
    via monkeypatch.setitem (restored automatically) rather than mutated.
    """
    script = tmp_path / "nn"
    script.write_text(
        '#!/bin/sh\n'
        'echo "argv: $@"\n'
        'echo "epoch    0 loss 0.6931 acc 50.0000%"\n'
        'echo "epoch  499 loss 0.0121 acc 100.0000%"\n'
        'echo \'RESULT {"final_accuracy": 1.0, "final_loss": 0.0121}\'\n'
        'exit 0\n'
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    original = MODELS["step0"]
    monkeypatch.setitem(MODELS, "step0", registry.ModelSpec(
        model_id=original.model_id,
        name=original.name,
        description=original.description,
        binary=script,
        params=original.params,
        result_fields=original.result_fields,
        timeout_seconds=10,
        dataset_defaults=original.dataset_defaults,
    ))
    monkeypatch.setattr(settings, "JOB_POLL_INTERVAL_SECONDS", 0.01)
    return script


def _drain_outbox(outbox):
    """Deliver everything queued, exercising the real drain loop."""
    return outbox.drain()


def test_a_new_user_can_sign_up_verify_log_in_and_train_to_a_downloadable_report(
    client, outbox, db_session, stubbed_step0
):
    """The primary journey. If this breaks, the product does not work.

    signup -> outbox -> verification email -> verify -> login -> queue a job ->
    worker claims it -> subprocess runs -> report downloads.
    """
    # 1. Sign up. Nothing is sent inline; an outbox row is staged.
    assert register(client, username="alice", email="alice@example.com").status_code == 200
    assert outbox.kinds() == [EmailType.VERIFY_EMAIL.value]

    # 2. The worker delivers it, and the raw token exists only in that email.
    delivered = _drain_outbox(outbox)
    assert [item["kind"] for item in delivered] == ["verify_email"]
    token = outbox.delivered_token("verify_email")

    # 3. Before verifying, training is barred — an unverified address must not
    #    be able to burn compute.
    unverified_login = login(client, email="alice@example.com")
    assert unverified_login.status_code == 200
    unverified_token = unverified_login.json()["access_token"]
    assert client.get("/train/models", headers=auth_header(unverified_token)).status_code == 403

    # 4. Verify, then log in properly.
    assert client.post("/auth/verify", json={"token": token}).status_code == 200
    session = login(client, email="alice@example.com")
    assert session.status_code == 200
    headers = auth_header(session.json()["access_token"])

    # 5. The refresh cookie round-trips over https.
    assert client.post("/auth/refresh").status_code == 200

    # 6. Queue a job. 202 — accepted, not finished.
    queued = client.post("/train/step0/run", json={"epochs": 500}, headers=headers)
    assert queued.status_code == 202, queued.text
    job_id = queued.json()["id"]

    polled = client.get(f"/train/jobs/{job_id}", headers=headers).json()
    assert polled["status"] == JobStatus.QUEUED.value
    assert polled["report_available"] is False

    # 7. The worker claims and runs it — the split the API relies on.
    claimed = worker.claim_one(db_session)
    assert claimed is not None and str(claimed.id) == job_id
    assert worker.execute(db_session, claimed) is True

    # 8. The finished job is visible over HTTP with its parsed result.
    finished = client.get(f"/train/jobs/{job_id}", headers=headers).json()
    assert finished["status"] == JobStatus.SUCCEEDED.value
    assert finished["result"] == {"final_accuracy": 1.0, "final_loss": 0.0121}
    assert finished["error"] is None
    assert finished["report_available"] is True

    # 9. And the report downloads as the driver's own output.
    report = client.get(f"/train/jobs/{job_id}/report", headers=headers)
    assert report.status_code == 200
    assert "epoch  499 loss 0.0121" in report.text
    assert "--epochs 500" in report.text  # the parameters really reached the process

    # 10. The slot is free again now the job is terminal.
    assert client.post("/train/step0/run", json={}, headers=headers).status_code == 202


def test_a_forgotten_password_can_be_reset_and_every_existing_session_dies(
    client, client_factory, outbox, db_session
):
    """The recovery journey, including the security property that makes it safe:
    a reset must kill sessions the attacker may already hold."""
    # A verified user, signed in on two devices.
    assert register(client, username="alice", email="alice@example.com").status_code == 200
    _drain_outbox(outbox)
    assert client.post(
        "/auth/verify", json={"token": outbox.delivered_token("verify_email")}
    ).status_code == 200

    phone = client_factory()
    assert login(client, email="alice@example.com").status_code == 200
    assert login(phone, email="alice@example.com").status_code == 200
    assert db_session.execute(
        select(RefreshToken).where(RefreshToken.revoked.is_(False))
    ).scalars().all()

    # Forgot password. The endpoint itself performs no user lookup.
    outbox.clear()
    response = request_password_reset(client, outbox, email="alice@example.com")
    assert response.status_code == 200
    reset_token = outbox.delivered_token("password_reset")

    # The link validates without being consumed, then resets.
    assert client.post(
        "/auth/reset-password/validate", json={"token": reset_token}
    ).status_code == 200
    assert client.post(
        "/auth/reset-password", json={"token": reset_token, "new_password": "BrandNew456"}
    ).status_code == 200

    # BOTH sessions are dead, not just the one that did the reset.
    assert client.post("/auth/refresh").status_code == 401
    assert phone.post("/auth/refresh").status_code == 401

    # Old password is gone; the new one works; the token is single-use.
    assert login(client, email="alice@example.com", password=VALID_PASSWORD).status_code == 400
    assert login(client, email="alice@example.com", password="BrandNew456").status_code == 200
    assert client.post(
        "/auth/reset-password", json={"token": reset_token, "new_password": "Another789"}
    ).status_code == 400


def test_a_job_whose_worker_dies_is_reclaimed_so_the_user_is_not_locked_out(
    client, outbox, db_session, stubbed_step0
):
    """The failure journey. A crashed worker leaves a job RUNNING forever, and
    because the partial unique index counts running as active, that user could
    never queue anything again — one crash would lock them out permanently."""
    from datetime import timedelta

    assert register(client, username="alice", email="alice@example.com").status_code == 200
    _drain_outbox(outbox)
    client.post("/auth/verify", json={"token": outbox.delivered_token("verify_email")})
    headers = auth_header(login(client, email="alice@example.com").json()["access_token"])

    job_id = client.post("/train/step0/run", json={}, headers=headers).json()["id"]

    # The worker claims it, then "dies" without ever finishing.
    claimed = worker.claim_one(db_session)
    assert claimed.status == JobStatus.RUNNING.value

    # The user is now blocked, correctly — they have an active job.
    assert client.post("/train/step0/run", json={}, headers=headers).status_code == 409

    # Time passes with no heartbeat, and the sweep frees them.
    db_session.execute(
        TrainingJob.__table__.update().values(
            heartbeat_at=worker._utcnow()
            - timedelta(seconds=settings.JOB_HEARTBEAT_STALE_SECONDS + 60)
        )
    )
    db_session.commit()

    assert worker.reclaim_stale(db_session) == 1

    failed = client.get(f"/train/jobs/{job_id}", headers=headers).json()
    assert failed["status"] == JobStatus.FAILED.value
    assert "worker stopped responding" in failed["error"]

    # And the user can train again.
    assert client.post("/train/step0/run", json={}, headers=headers).status_code == 202


def test_deleting_an_account_removes_every_trace_of_it(
    client, outbox, db_session, stubbed_step0
):
    """The exit journey — data-integrity class. Jobs and refresh tokens must go
    with the user, via the FK cascade rather than application code."""
    from backend.models.user import User

    assert register(client, username="alice", email="alice@example.com").status_code == 200
    _drain_outbox(outbox)
    client.post("/auth/verify", json={"token": outbox.delivered_token("verify_email")})
    headers = auth_header(login(client, email="alice@example.com").json()["access_token"])

    client.post("/train/step0/run", json={}, headers=headers)
    assert db_session.execute(select(TrainingJob)).scalars().all()
    assert db_session.execute(select(RefreshToken)).scalars().all()

    deleted = client.request(
        "DELETE", "/users/me",
        json={"current_password": VALID_PASSWORD},
        headers=headers,
    )
    assert deleted.status_code == 204, deleted.text

    db_session.expire_all()
    assert db_session.execute(select(User)).scalars().all() == []
    assert db_session.execute(select(TrainingJob)).scalars().all() == []
    assert db_session.execute(select(RefreshToken)).scalars().all() == []

    # The old access token is cryptographically valid but names a user who is
    # gone, so it must not authenticate.
    assert client.get("/users/me", headers=headers).status_code == 401
