"""worker.py — claim/lease, the stale reclaim, and outcome recording.

`worker.main()` is deliberately not exercised: it installs real signal handlers
and loops unbounded. Every decision it makes lives in the four functions below,
which are called directly.

`worker._shutdown` is a module-level global mutated by the signal handler. Any
test that sets it MUST restore it, or it poisons every later test in the run —
the `_restore_shutdown_flag` fixture does that unconditionally.
"""

from datetime import timedelta

import pytest
from sqlalchemy import select

from backend import worker
from backend.core.config import settings
from backend.models.TrainingJob import JobStatus, TrainingJob
from backend.models.user import User
from backend.services.runner import RunOutcome
from backend.tests.helpers import register_and_verify


@pytest.fixture(autouse=True)
def _restore_shutdown_flag():
    """Shared mutable state, contained. Without this a single test that trips the
    shutdown flag would abort every subsequent job in the run."""
    original = worker._shutdown
    yield
    worker._shutdown = original


@pytest.fixture()
def user_id(client, outbox, db_session):
    register_and_verify(client, outbox)
    return db_session.execute(select(User.id)).scalar_one()


def _job(db, user_id, *, status=JobStatus.QUEUED.value, **overrides) -> TrainingJob:
    job = TrainingJob(
        user_id=user_id,
        model_id="step0",
        params={"dataset": "tiny", "lr": 0.5, "epochs": 10, "seed": 42},
        status=status,
        **overrides,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


# --------------------------------------------------------------------------- #
# claim_one
# --------------------------------------------------------------------------- #

def test_claiming_an_empty_queue_returns_none(db_session):
    assert worker.claim_one(db_session) is None


def test_claiming_marks_the_job_running_and_stamps_both_timestamps(db_session, user_id):
    _job(db_session, user_id)

    claimed = worker.claim_one(db_session)

    assert claimed is not None
    assert claimed.status == JobStatus.RUNNING.value
    assert claimed.started_at is not None
    # The claim counts as the first beat — otherwise the reclaim sweep would see
    # a running job with no heartbeat and never be able to free it.
    assert claimed.heartbeat_at is not None


def test_a_running_job_is_not_claimed_twice(db_session, user_id):
    _job(db_session, user_id)
    assert worker.claim_one(db_session) is not None
    assert worker.claim_one(db_session) is None


def test_jobs_are_claimed_oldest_first(db_session, user_id, client, outbox, client_factory):
    """FIFO, so a user who queued first is served first."""
    bob_client = client_factory()
    register_and_verify(bob_client, outbox, username="bob", email="bob@example.com")
    bob_id = db_session.execute(
        select(User.id).where(User.email == "bob@example.com")
    ).scalar_one()

    first = _job(db_session, user_id)
    second = _job(db_session, bob_id)
    # created_at is stamped Python-side, so nudge the second one to be sure.
    second.created_at = first.created_at + timedelta(seconds=5)
    db_session.commit()

    assert worker.claim_one(db_session).id == first.id


# --------------------------------------------------------------------------- #
# execute
# --------------------------------------------------------------------------- #

def test_a_successful_run_is_recorded_in_full(db_session, user_id, monkeypatch):
    job = _job(db_session, user_id, status=JobStatus.RUNNING.value)
    monkeypatch.setattr(
        worker, "run_training",
        lambda *a, **k: RunOutcome(
            stdout="epoch 1\nRESULT {}", exit_code=0, result={"final_loss": 0.1}, error=None
        ),
    )

    assert worker.execute(db_session, job) is True

    db_session.refresh(job)
    assert job.status == JobStatus.SUCCEEDED.value
    assert job.result == {"final_loss": 0.1}
    assert job.exit_code == 0
    assert job.error is None
    assert job.finished_at is not None
    assert "epoch 1" in job.stdout


def test_a_failed_run_is_recorded_with_its_error(db_session, user_id, monkeypatch):
    job = _job(db_session, user_id, status=JobStatus.RUNNING.value)
    monkeypatch.setattr(
        worker, "run_training",
        lambda *a, **k: RunOutcome(
            stdout="boom", exit_code=3, result=None, error="Training exited with code 3."
        ),
    )

    assert worker.execute(db_session, job) is True

    db_session.refresh(job)
    assert job.status == JobStatus.FAILED.value
    assert job.error == "Training exited with code 3."
    assert job.finished_at is not None


def test_an_aborted_run_is_left_alone_for_requeueing(db_session, user_id, monkeypatch):
    job = _job(db_session, user_id, status=JobStatus.RUNNING.value)
    monkeypatch.setattr(
        worker, "run_training",
        lambda *a, **k: RunOutcome(
            stdout="", exit_code=None, result=None, error=None, aborted=True
        ),
    )

    assert worker.execute(db_session, job) is False

    db_session.refresh(job)
    assert job.status == JobStatus.RUNNING.value  # not failed
    assert job.finished_at is None


def test_an_unexpected_exception_fails_the_job_rather_than_escaping(db_session, user_id, monkeypatch):
    """An exception reaching the loop would leave the job RUNNING and hold the
    user's only slot until the stale reclaim caught it — correct eventually, but
    a bad experience for something recordable now."""
    def explode(*a, **k):
        raise RuntimeError("something unexpected")

    job = _job(db_session, user_id, status=JobStatus.RUNNING.value)
    monkeypatch.setattr(worker, "run_training", explode)

    assert worker.execute(db_session, job) is True

    db_session.refresh(job)
    assert job.status == JobStatus.FAILED.value
    assert "Training failed unexpectedly" in job.error
    assert "something unexpected" in job.error


def test_a_job_whose_model_left_the_registry_fails_cleanly(db_session, user_id):
    job = _job(db_session, user_id, status=JobStatus.RUNNING.value)
    job.model_id = "a-model-that-was-removed"
    db_session.commit()

    assert worker.execute(db_session, job) is True

    db_session.refresh(job)
    assert job.status == JobStatus.FAILED.value
    assert "Unknown model" in job.error


def test_the_heartbeat_callback_persists_a_new_timestamp(db_session, user_id, monkeypatch):
    job = _job(db_session, user_id, status=JobStatus.RUNNING.value)
    original = job.heartbeat_at

    def beat_then_finish(spec, params, on_heartbeat=None, should_abort=None):
        on_heartbeat()
        return RunOutcome(stdout="", exit_code=0, result={}, error=None)

    monkeypatch.setattr(worker, "run_training", beat_then_finish)
    worker.execute(db_session, job)

    db_session.refresh(job)
    assert job.heartbeat_at != original


def test_execute_reports_shutdown_through_should_abort(db_session, user_id, monkeypatch):
    """The abort predicate the worker passes down is the shutdown flag itself."""
    seen = {}

    def capture(spec, params, on_heartbeat=None, should_abort=None):
        seen["aborting"] = should_abort()
        return RunOutcome(stdout="", exit_code=0, result={}, error=None)

    monkeypatch.setattr(worker, "run_training", capture)

    worker._shutdown = True
    worker.execute(db_session, _job(db_session, user_id, status=JobStatus.RUNNING.value))

    assert seen["aborting"] is True


# --------------------------------------------------------------------------- #
# reclaim_stale — liveness is the heartbeat, not elapsed time
# --------------------------------------------------------------------------- #

def test_a_job_with_a_stale_heartbeat_is_failed_and_frees_the_slot(db_session, user_id):
    """A killed worker leaves a job RUNNING forever. Because the partial unique
    index counts running as active, that user could otherwise never queue
    anything again — one crash would lock them out permanently."""
    stale = worker._utcnow() - timedelta(seconds=settings.JOB_HEARTBEAT_STALE_SECONDS + 60)
    job = _job(db_session, user_id, status=JobStatus.RUNNING.value, heartbeat_at=stale)

    assert worker.reclaim_stale(db_session) == 1

    db_session.refresh(job)
    assert job.status == JobStatus.FAILED.value
    assert "worker stopped responding" in job.error
    assert job.finished_at is not None


def test_a_long_running_job_with_a_fresh_heartbeat_is_left_alone(db_session, user_id):
    """The whole point of using the heartbeat rather than duration: a job
    legitimately training for 20 minutes and one whose worker died 10 seconds in
    look identical if you only measure elapsed time."""
    old_start = worker._utcnow() - timedelta(hours=2)
    job = _job(
        db_session, user_id,
        status=JobStatus.RUNNING.value,
        started_at=old_start,
        heartbeat_at=worker._utcnow(),
    )

    assert worker.reclaim_stale(db_session) == 0

    db_session.refresh(job)
    assert job.status == JobStatus.RUNNING.value


def test_a_queued_job_is_never_reclaimed_however_old(db_session, user_id):
    ancient = worker._utcnow() - timedelta(days=7)
    job = _job(db_session, user_id, heartbeat_at=ancient)

    assert worker.reclaim_stale(db_session) == 0

    db_session.refresh(job)
    assert job.status == JobStatus.QUEUED.value


def test_a_running_job_with_no_heartbeat_at_all_is_never_reclaimed(db_session, user_id):
    """CURRENT BEHAVIOUR and a real gap: the sweep requires heartbeat_at IS NOT
    NULL, so a legacy row predating the claim-stamps-a-beat change stays RUNNING
    forever and permanently holds that user's slot. Pinned so the day someone
    drops the NULL guard, this test is the one that tells them why it was there.
    """
    job = _job(db_session, user_id, status=JobStatus.RUNNING.value, heartbeat_at=None)

    assert worker.reclaim_stale(db_session) == 0

    db_session.refresh(job)
    assert job.status == JobStatus.RUNNING.value


def test_reclaiming_a_stale_job_lets_its_user_queue_again(client, outbox, db_session):
    """The user-visible consequence of the reclaim, end to end."""
    from backend.tests.helpers import auth_header

    account = register_and_verify(client, outbox)
    uid = db_session.execute(select(User.id)).scalar_one()
    stale = worker._utcnow() - timedelta(seconds=settings.JOB_HEARTBEAT_STALE_SECONDS + 60)
    _job(db_session, uid, status=JobStatus.RUNNING.value, heartbeat_at=stale)

    headers = auth_header(account["access_token"])
    assert client.post("/train/step0/run", json={}, headers=headers).status_code == 409

    worker.reclaim_stale(db_session)

    assert client.post("/train/step0/run", json={}, headers=headers).status_code == 202


# --------------------------------------------------------------------------- #
# purge_finished_jobs — age is the only axis here; a finished job has no
# liveness left to reclaim, only an age to age out
# --------------------------------------------------------------------------- #

def test_a_finished_job_older_than_retention_is_purged(db_session, user_id):
    old = worker._utcnow() - timedelta(days=settings.JOB_RETENTION_DAYS + 1)
    job = _job(db_session, user_id, status=JobStatus.SUCCEEDED.value, finished_at=old)

    assert worker.purge_finished_jobs(db_session) == 1

    remaining = db_session.execute(
        select(TrainingJob).where(TrainingJob.id == job.id)
    ).scalar_one_or_none()
    assert remaining is None


@pytest.mark.parametrize("status", [JobStatus.SUCCEEDED.value, JobStatus.FAILED.value])
def test_a_finished_job_within_retention_is_kept(db_session, user_id, status):
    recent = worker._utcnow() - timedelta(days=1)
    job = _job(db_session, user_id, status=status, finished_at=recent)

    assert worker.purge_finished_jobs(db_session) == 0

    db_session.refresh(job)
    assert job.status == status


@pytest.mark.parametrize("status", [JobStatus.QUEUED.value, JobStatus.RUNNING.value])
def test_a_queued_or_running_job_is_never_purged_however_old(db_session, user_id, status):
    """CURRENT BEHAVIOUR should never change: only succeeded/failed jobs are in
    scope, however old finished_at is contrived to be — a queued/running job in
    the real world never has one set at all."""
    ancient = worker._utcnow() - timedelta(days=365)
    job = _job(db_session, user_id, status=status, finished_at=ancient)

    assert worker.purge_finished_jobs(db_session) == 0

    db_session.refresh(job)
    assert job.status == status


def test_purge_is_global_not_scoped_to_one_user(client_factory, outbox, db_session, user_id):
    """Deliberately different from routers.train.clear_finished_jobs, which is
    scoped to the caller's own rows: this purge is a background sweep with no
    caller, so it must clear every eligible row regardless of owner."""
    other = register_and_verify(client_factory(), outbox, username="bob", email="bob@example.com")
    other_uid = db_session.execute(select(User.id).where(User.email == other["email"])).scalar_one()

    old = worker._utcnow() - timedelta(days=settings.JOB_RETENTION_DAYS + 1)
    _job(db_session, user_id, status=JobStatus.SUCCEEDED.value, finished_at=old)
    _job(db_session, other_uid, status=JobStatus.FAILED.value, finished_at=old)

    assert worker.purge_finished_jobs(db_session) == 2


# --------------------------------------------------------------------------- #
# release
# --------------------------------------------------------------------------- #

def test_releasing_requeues_an_in_flight_job_and_clears_its_stamps(db_session, user_id):
    """Requeued rather than failed: the work never started failing, the worker
    just went away, and the user shouldn't be charged a failed run for a deploy."""
    job = _job(
        db_session, user_id,
        status=JobStatus.RUNNING.value,
        started_at=worker._utcnow(),
        heartbeat_at=worker._utcnow(),
    )

    worker.release(db_session, job)

    db_session.refresh(job)
    assert job.status == JobStatus.QUEUED.value
    assert job.started_at is None
    assert job.heartbeat_at is None


def test_a_released_job_is_claimable_again(db_session, user_id):
    job = _job(db_session, user_id, status=JobStatus.RUNNING.value)
    worker.release(db_session, job)
    assert worker.claim_one(db_session) is not None
