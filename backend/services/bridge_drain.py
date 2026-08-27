"""Drains the bridge_jobs queue — the worker-side twin of routers/bridge.py.

Runs as a loop on its own thread inside the worker process, beside the email
drain: a feasibility run takes 1-4 minutes and must not block training claims
or verification emails (and vice versa). Claims with SELECT ... FOR UPDATE
SKIP LOCKED, heartbeats through the run (ProgressLog beats on every event),
and reclaims stale RUNNING jobs by heartbeat — never by elapsed time.

Same-worker contention is a decided trade (bridge-plan-v3.md §11): probes are
capped small, training runs in a subprocess (no GIL contention), and a second
Fargate task would cost real money for a personal project. If probe latency
ever hurts real training runs, the decision to revisit is recorded in
BRIDGE_SERVICES.md.
"""

import logging
import time
from datetime import timedelta
from typing import Callable

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.database import SessionLocal, close_quietly, reset_session
from backend.models.Bridge import BridgeJob, BridgeJobStatus
from backend.models.TrainingJob import utcnow
from backend.services.bridge.pipeline import run_bridge_job

logger = logging.getLogger("backend.bridge_drain")


def reclaim_stale(db: Session) -> int:
    """Fail RUNNING jobs whose heartbeat went silent, freeing the user's active
    slot. The window is longer than training's: pipeline stages block on
    outbound HTTP and only beat between stages."""
    cutoff = utcnow() - timedelta(seconds=settings.BRIDGE_JOB_HEARTBEAT_STALE_SECONDS)
    result = db.execute(
        update(BridgeJob)
        .where(
            BridgeJob.status == BridgeJobStatus.RUNNING.value,
            BridgeJob.heartbeat_at.is_not(None),
            BridgeJob.heartbeat_at < cutoff,
        )
        .values(
            status=BridgeJobStatus.FAILED.value,
            error="The feasibility run was interrupted (the worker stopped responding).",
            finished_at=utcnow(),
        )
    )
    db.commit()
    if result.rowcount:
        logger.warning("reclaimed %d stale bridge job(s)", result.rowcount)
    return result.rowcount


def claim_one(db: Session) -> BridgeJob | None:
    job = db.execute(
        select(BridgeJob)
        .where(BridgeJob.status == BridgeJobStatus.QUEUED.value)
        .order_by(BridgeJob.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    ).scalars().first()
    if job is None:
        return None
    now = utcnow()
    job.status = BridgeJobStatus.RUNNING.value
    job.started_at = now
    job.heartbeat_at = now      # the claim is the first beat
    db.commit()                 # releases the row lock
    return job


def run(should_stop: Callable[[], bool]) -> None:
    """The drain loop. Owns its own session (a thread must not share another
    loop's); on error the session is REPLACED, never rolled back — rollback on
    a dropped connection raises inside the handler and kills the thread
    (database.reset_session exists for exactly this)."""
    logger.info("bridge drain started (poll=%ss)", settings.BRIDGE_JOB_POLL_INTERVAL_SECONDS)
    db = SessionLocal()
    last_reclaim = 0.0
    try:
        while not should_stop():
            try:
                if not settings.BRIDGE_ENABLED:
                    # The API 503s POSTs while disabled, so the queue is never
                    # fed; idle rather than exiting so a config flip mid-life
                    # doesn't need a restart to notice.
                    time.sleep(settings.BRIDGE_JOB_POLL_INTERVAL_SECONDS)
                    continue

                mono = time.monotonic()
                if mono - last_reclaim >= settings.BRIDGE_JOB_HEARTBEAT_STALE_SECONDS:
                    reclaim_stale(db)
                    last_reclaim = mono

                job = claim_one(db)
                if job is None:
                    time.sleep(settings.BRIDGE_JOB_POLL_INTERVAL_SECONDS)
                    continue
                logger.info("claimed bridge job %s (%s / %s)",
                            job.id, job.topic_slug, job.model_id)
                run_bridge_job(db, job)
            except Exception:  # noqa: BLE001
                logger.exception("bridge drain loop error; backing off")
                db = reset_session(db)
                # An in-flight job stays RUNNING and the stale-heartbeat
                # reclaim frees it — same recovery story as the training loop.
                time.sleep(max(1.0, settings.BRIDGE_JOB_POLL_INTERVAL_SECONDS))
    finally:
        close_quietly(db)
        logger.info("bridge drain stopped")
