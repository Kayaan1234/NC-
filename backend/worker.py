"""The training worker: claims queued jobs and runs them.

Run it as its own process, alongside the API:

    python -m backend.worker

It is deliberately NOT part of the API process. AWS App Runner throttles
container CPU whenever no request is actively being served, so work started after
a response returns is starved; instance recycling would kill a long job anyway.
Training therefore cannot run in a BackgroundTask or an API thread, and until the
worker has a home in production, TRAINING_ENABLED stays false there (the API
would otherwise queue jobs nothing ever drains).

The queue is just the training_jobs table. Claiming uses SELECT ... FOR UPDATE
SKIP LOCKED, so running several workers is safe: each claims a different row
rather than blocking on the same one. Concurrency today is one job at a time,
strictly FIFO.
"""

import logging
import signal
import sys
import time
from datetime import timedelta
from types import FrameType

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.database import SessionLocal
from backend.models.TrainingJob import JobStatus, TrainingJob, utcnow as _utcnow
from backend.services.registry import get_model
from backend.services.runner import run_training

logger = logging.getLogger("backend.worker")

# Set by the signal handler; the loop checks it at each safe point rather than
# tearing down mid-write.
_shutdown = False


def reclaim_stale(db: Session) -> int:
    """Fail jobs whose worker died, freeing their user's active slot.

    A killed worker leaves a job RUNNING forever. Because the partial unique index
    counts running as active, that user could never queue anything again — one
    crash would lock them out permanently.

    Liveness is the heartbeat, NOT elapsed time. That distinction is the whole
    point: a job legitimately training for 20 minutes and a job whose worker died
    10 seconds in look identical if you only measure duration. A stale heartbeat
    is unambiguous.
    """
    cutoff = _utcnow() - timedelta(seconds=settings.JOB_HEARTBEAT_STALE_SECONDS)
    result = db.execute(
        update(TrainingJob)
        .where(
            TrainingJob.status == JobStatus.RUNNING.value,
            # A job claimed but never beaten yet is protected by started_at; the
            # claim stamps heartbeat_at, so NULL here means an older row.
            TrainingJob.heartbeat_at.is_not(None),
            TrainingJob.heartbeat_at < cutoff,
        )
        .values(
            status=JobStatus.FAILED.value,
            error="Training was interrupted (the worker stopped responding).",
            finished_at=_utcnow(),
        )
    )
    db.commit()
    if result.rowcount:
        logger.warning("reclaimed %d stale job(s)", result.rowcount)
    return result.rowcount


def claim_one(db: Session) -> TrainingJob | None:
    """Atomically take the oldest queued job, or return None if there's none.

    SKIP LOCKED means a second worker steps over a row this one has locked
    instead of blocking behind it, so workers never collide and never serialise.
    Postgres-only — SQLite ignores it — which is fine: the worker only ever runs
    against the real database.
    """
    job = db.execute(
        select(TrainingJob)
        .where(TrainingJob.status == JobStatus.QUEUED.value)
        .order_by(TrainingJob.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    ).scalars().first()

    if job is None:
        return None

    now = _utcnow()
    job.status = JobStatus.RUNNING.value
    job.started_at = now
    job.heartbeat_at = now      # claim counts as the first beat
    db.commit()                 # releases the row lock
    return job


def execute(db: Session, job: TrainingJob) -> bool:
    """Run one claimed job and record the outcome. True if it reached a terminal
    state; False if it was aborted for shutdown and needs requeueing.

    Every failure must land in the job row. An exception escaping to the loop
    would leave the job RUNNING and hold the user's only slot until the stale
    reclaim catches it — correct eventually, but a bad experience for something
    we can record now.
    """
    def beat() -> None:
        job.heartbeat_at = _utcnow()
        db.commit()

    try:
        spec = get_model(job.model_id)
        if spec is None:
            # The model was removed from the registry after the job was queued.
            raise ValueError(f"Unknown model: {job.model_id}")

        outcome = run_training(
            spec, job.params, on_heartbeat=beat, should_abort=lambda: _shutdown
        )
        if outcome.aborted:
            return False

        job.stdout = outcome.stdout
        job.result = outcome.result
        job.exit_code = outcome.exit_code
        job.error = outcome.error
        job.status = JobStatus.SUCCEEDED.value if outcome.ok else JobStatus.FAILED.value
    except Exception as exc:                     # noqa: BLE001 - see docstring
        logger.exception("job %s crashed", job.id)
        job.status = JobStatus.FAILED.value
        job.error = f"Training failed unexpectedly: {exc}"

    job.finished_at = _utcnow()
    db.commit()
    logger.info("job %s -> %s", job.id, job.status)
    return True


def release(db: Session, job: TrainingJob) -> None:
    """Put an in-flight job back on the queue on graceful shutdown.

    Requeued rather than failed: the work never started failing, the worker just
    went away, and the user shouldn't be charged a failed run for our deploy.
    """
    job.status = JobStatus.QUEUED.value
    job.started_at = None
    job.heartbeat_at = None
    db.commit()
    logger.info("requeued in-flight job %s on shutdown", job.id)


def _handle_signal(signum: int, _frame: FrameType | None) -> None:
    global _shutdown
    _shutdown = True
    logger.info("signal %s received; finishing up", signum)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    logger.info("worker started (poll=%ss, heartbeat=%ss, stale=%ss)",
                settings.JOB_POLL_INTERVAL_SECONDS,
                settings.JOB_HEARTBEAT_SECONDS,
                settings.JOB_HEARTBEAT_STALE_SECONDS)

    # One long-lived session: this is a single-threaded loop, and it owns its own
    # connection rather than borrowing a request-scoped one (there is no request).
    #
    # TODO(prod worker): this session lives for the life of the process, and the
    # loop below reuses it after a rollback. That's fine locally, but if the
    # connection genuinely drops, the rollback can itself raise and the loop will
    # spin on a dead session — pool_pre_ping validates a connection at checkout,
    # not one a session is already holding. A long-lived deployed worker wants a
    # fresh session per iteration, or reconnect-on-error.
    db = SessionLocal()
    current: TrainingJob | None = None
    try:
        while not _shutdown:
            try:
                reclaim_stale(db)
                current = claim_one(db)
                if current is None:
                    time.sleep(settings.JOB_POLL_INTERVAL_SECONDS)
                    continue
                logger.info("claimed job %s (%s)", current.id, current.model_id)
                if execute(db, current):
                    current = None      # terminal; nothing to release
            except Exception:                    # noqa: BLE001
                # A database blip must not kill the worker; log, back off, retry.
                logger.exception("worker loop error; backing off")
                db.rollback()
                current = None
                time.sleep(max(1.0, settings.JOB_POLL_INTERVAL_SECONDS))

        if current is not None:
            release(db, current)
    finally:
        db.close()
        logger.info("worker stopped")


if __name__ == "__main__":
    sys.exit(main())
