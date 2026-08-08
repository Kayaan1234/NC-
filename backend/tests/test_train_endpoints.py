"""routers/train.py — ownership boundaries, rejection ordering, and the
one-active-job-per-user rule.

The ownership tests are the important ones here: a job row is the only thing in
this app that is per-user *and* addressable by an opaque id a caller can guess
at, so "user A cannot see user B's job" is the boundary worth pinning.
"""

import pytest
from sqlalchemy import select, text

from backend.core.config import settings
from backend.models.TrainingJob import JobStatus, TrainingJob
from backend.routers.train import ACTIVE_STATUSES
from backend.services.params import effective_max
from backend.services.registry import MODELS
from backend.tests.helpers import auth_header, register_and_verify

MODEL = "step0"


@pytest.fixture()
def alice(client, outbox):
    return register_and_verify(client, outbox, username="alice", email="alice@example.com")


@pytest.fixture()
def bob(client_factory, outbox):
    """A second user with their own client, i.e. their own cookie jar."""
    bob_client = client_factory()
    account = register_and_verify(
        bob_client, outbox, username="bob", email="bob@example.com"
    )
    account["client"] = bob_client
    return account


def _queue(client, account, model=MODEL, **params):
    return client.post(
        f"/train/{model}/run", json=params, headers=auth_header(account["access_token"])
    )


# --------------------------------------------------------------------------- #
# GET /train/models
# --------------------------------------------------------------------------- #

def test_listing_models_returns_every_registry_entry(client, alice):
    resp = client.get("/train/models", headers=auth_header(alice["access_token"]))
    assert resp.status_code == 200, resp.text
    assert {m["model_id"] for m in resp.json()} == set(MODELS)


def test_the_advertised_maximum_is_the_one_the_server_will_actually_enforce(client, alice):
    """If the form offered a spec's own looser maximum, a user could pick a value
    the server then rejects on submit. The wire value is effective_max()."""
    body = client.get("/train/models", headers=auth_header(alice["access_token"])).json()
    by_id = {m["model_id"]: m for m in body}

    for spec in MODELS.values():
        wire = {p["name"]: p for p in by_id[spec.model_id]["params"]}
        for param in spec.params:
            assert wire[param.name]["maximum"] == effective_max(param)


def test_the_command_line_flag_is_never_sent_to_the_client(client, alice):
    """The client never builds an argv — that happens server-side from the same
    specs — so the flag is deliberately withheld."""
    body = client.get("/train/models", headers=auth_header(alice["access_token"])).json()
    for model in body:
        for param in model["params"]:
            assert "flag" not in param


# --------------------------------------------------------------------------- #
# POST /train/{model_id}/run — rejection ordering
# --------------------------------------------------------------------------- #

def test_queueing_a_job_returns_202_with_a_queued_row(client, alice):
    resp = _queue(client, alice)
    assert resp.status_code == 202, resp.text

    body = resp.json()
    assert body["status"] == JobStatus.QUEUED.value
    assert body["id"] and body["created_at"]


def test_an_unknown_model_is_404(client, alice):
    assert _queue(client, alice, model="not-a-model").status_code == 404


@pytest.mark.parametrize(
    "attempt",
    ["..%2F..%2Fetc%2Fpasswd", "..", "%2e%2e", "step0%00", "../../../../etc/passwd"],
)
def test_a_model_id_that_looks_like_a_path_is_just_a_miss(client, alice, attempt):
    """model_id is only ever a dict key and is never joined onto a filesystem
    path, so traversal attempts are indistinguishable from typos.

    Note a dot-segment that the *client* resolves before sending (e.g.
    "step0/../step1") never reaches the server as such — that is URL
    normalisation, not a server-side decision, so it isn't tested here.
    """
    assert _queue(client, alice, model=attempt).status_code in (404, 405)


def test_an_out_of_range_parameter_is_422_with_a_plain_string_detail(client, alice):
    """Not FastAPI's own 422 shape. `detail` is a sentence raised by hand in the
    handler, not a list of {loc, msg} — a client reading detail[0]["msg"] would
    raise TypeError."""
    resp = _queue(client, alice, epochs=99_999)
    assert resp.status_code == 422
    assert isinstance(resp.json()["detail"], str)
    assert "at most" in resp.json()["detail"]


def test_an_unknown_parameter_is_rejected_rather_than_ignored(client, alice):
    resp = _queue(client, alice, not_a_param=1)
    assert resp.status_code == 422
    assert "Unknown parameter" in resp.json()["detail"]


def test_a_body_that_is_not_an_object_is_rejected_by_fastapi_first(client, alice):
    resp = client.post(
        f"/train/{MODEL}/run", json=[1, 2, 3], headers=auth_header(alice["access_token"])
    )
    assert resp.status_code == 422


def test_training_disabled_shadows_every_later_check(client, alice, monkeypatch):
    """Ordering is observable: with training off, even an unknown model gets 503
    rather than 404, because the switch is checked first. Accepting the job would
    mean queueing something no worker will ever drain."""
    monkeypatch.setattr(settings, "TRAINING_ENABLED", False)

    assert _queue(client, alice).status_code == 503
    assert _queue(client, alice, model="not-a-model").status_code == 503


# --------------------------------------------------------------------------- #
# The one-active-job-per-user rule
# --------------------------------------------------------------------------- #

def test_a_second_active_job_for_the_same_user_is_409(client, alice):
    """Enforced by a partial unique index, not a prior SELECT — two concurrent
    POSTs would both pass a check-then-insert."""
    assert _queue(client, alice).status_code == 202
    second = _queue(client, alice)
    assert second.status_code == 409
    assert "already have a training job" in second.json()["detail"]


def test_the_slot_frees_up_once_the_job_reaches_a_terminal_state(client, alice, db_session):
    assert _queue(client, alice).status_code == 202

    db_session.execute(
        TrainingJob.__table__.update().values(status=JobStatus.SUCCEEDED.value)
    )
    db_session.commit()

    assert _queue(client, alice).status_code == 202


def test_two_different_users_each_get_their_own_active_slot(client, alice, bob):
    assert _queue(client, alice).status_code == 202
    assert _queue(bob["client"], bob).status_code == 202


def test_the_status_column_stores_the_lowercase_value_not_the_enum_name(db_session, client, alice):
    """The regression guard for the whole one-active-job rule.

    `status` is String(20) holding the enum's VALUE, deliberately not
    Enum(JobStatus) — SQLAlchemy's Enum persists the member NAME ('QUEUED'),
    which would silently stop the partial index matching. No IntegrityError would
    ever fire, and the rule would be unenforced while appearing to work.
    """
    assert _queue(client, alice).status_code == 202

    raw = db_session.execute(text("SELECT status FROM training_jobs")).scalar_one()
    assert raw == "queued"
    assert raw == JobStatus.QUEUED.value


def test_the_active_statuses_constant_matches_the_index_predicate():
    """Three files have to agree: the JobStatus values, ACTIVE_STATUSES here, and
    the index's WHERE clause in the model."""
    assert set(ACTIVE_STATUSES) == {JobStatus.QUEUED.value, JobStatus.RUNNING.value}

    index = next(
        ix for ix in TrainingJob.__table__.indexes
        if ix.name == "uq_training_jobs_active_per_user"
    )
    predicate = str(index.dialect_options["postgresql"]["where"])
    for value in ACTIVE_STATUSES:
        assert f"'{value}'" in predicate


# --------------------------------------------------------------------------- #
# Ownership — the boundary that matters
# --------------------------------------------------------------------------- #

def test_a_user_cannot_read_another_users_job_and_gets_404_not_403(client, alice, bob):
    """404 on purpose: a 403 would confirm the id exists, letting a caller
    enumerate job ids."""
    job_id = _queue(bob["client"], bob).json()["id"]

    resp = client.get(f"/train/jobs/{job_id}", headers=auth_header(alice["access_token"]))
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Job not found"


def test_another_users_job_is_indistinguishable_from_one_that_does_not_exist(client, alice, bob):
    real = _queue(bob["client"], bob).json()["id"]
    fake = "00000000-0000-4000-8000-000000000000"

    headers = auth_header(alice["access_token"])
    theirs = client.get(f"/train/jobs/{real}", headers=headers)
    nothing = client.get(f"/train/jobs/{fake}", headers=headers)

    assert (theirs.status_code, theirs.json()) == (nothing.status_code, nothing.json())


def test_a_user_cannot_download_another_users_report(client, alice, bob, db_session):
    job_id = _queue(bob["client"], bob).json()["id"]
    db_session.execute(
        TrainingJob.__table__.update().values(status=JobStatus.SUCCEEDED.value, stdout="secret")
    )
    db_session.commit()

    resp = client.get(f"/train/jobs/{job_id}/report", headers=auth_header(alice["access_token"]))
    assert resp.status_code == 404
    assert b"secret" not in resp.content


def test_listing_jobs_returns_only_the_callers_own(client, alice, bob):
    _queue(client, alice)
    _queue(bob["client"], bob)

    mine = client.get("/train/jobs", headers=auth_header(alice["access_token"])).json()
    assert len(mine) == 1
    assert mine[0]["model_id"] == MODEL


def test_clearing_finished_jobs_leaves_other_users_rows_alone(client, alice, bob, db_session):
    _queue(client, alice)
    _queue(bob["client"], bob)
    db_session.execute(
        TrainingJob.__table__.update().values(status=JobStatus.SUCCEEDED.value)
    )
    db_session.commit()

    cleared = client.delete("/train/jobs", headers=auth_header(alice["access_token"]))
    assert cleared.status_code == 200
    assert cleared.json()["deleted"] == 1

    remaining = db_session.execute(select(TrainingJob)).scalars().all()
    assert len(remaining) == 1
    assert str(remaining[0].user_id) == bob["user_id"]


def test_clearing_never_deletes_an_active_job(client, alice):
    """A queued/running job is the user's active slot; deleting it would free the
    slot mid-run and orphan the worker's subprocess."""
    _queue(client, alice)

    cleared = client.delete("/train/jobs", headers=auth_header(alice["access_token"]))
    assert cleared.json()["deleted"] == 0
    assert len(client.get("/train/jobs", headers=auth_header(alice["access_token"])).json()) == 1


# --------------------------------------------------------------------------- #
# Job status projection and the report
# --------------------------------------------------------------------------- #

def test_a_queued_job_reports_its_queue_position_and_no_report(client, alice):
    job_id = _queue(client, alice).json()["id"]

    body = client.get(f"/train/jobs/{job_id}", headers=auth_header(alice["access_token"])).json()
    assert body["queue_position"] == 0  # nothing ahead of it
    assert body["report_available"] is False


def test_downloading_the_report_of_an_unfinished_job_is_409(client, alice):
    job_id = _queue(client, alice).json()["id"]

    resp = client.get(f"/train/jobs/{job_id}/report", headers=auth_header(alice["access_token"]))
    assert resp.status_code == 409


def test_a_finished_report_is_served_as_a_named_text_attachment(client, alice, db_session):
    job_id = _queue(client, alice).json()["id"]
    db_session.execute(
        TrainingJob.__table__.update().values(
            status=JobStatus.SUCCEEDED.value, stdout="epoch 1 loss 0.5\nRESULT {}\n"
        )
    )
    db_session.commit()

    resp = client.get(f"/train/jobs/{job_id}/report", headers=auth_header(alice["access_token"]))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert f'filename="training-{MODEL}-{job_id[:8]}.txt"' in resp.headers["content-disposition"]
    assert "RESULT {}" in resp.text


def test_a_failed_job_still_serves_a_report_with_the_error_appended(client, alice, db_session):
    """More use than an empty file when you're trying to work out what broke."""
    job_id = _queue(client, alice).json()["id"]
    db_session.execute(
        TrainingJob.__table__.update().values(
            status=JobStatus.FAILED.value, stdout="partial output", error="it exploded"
        )
    )
    db_session.commit()

    resp = client.get(f"/train/jobs/{job_id}/report", headers=auth_header(alice["access_token"]))
    assert resp.status_code == 200
    assert "partial output" in resp.text
    assert "=== job failed ===" in resp.text
    assert "it exploded" in resp.text
