"""The bridge API: the library (free lookups) and the live path (queued runs).

Same conventions as routers/train.py, with one stronger argument behind each:
every live run spends real API dollars, so require_verified_user, a dedicated
RATE_LIMIT_BRIDGE tier, the one-active-job partial unique index, AND a global
daily spend cap all guard POST /bridge/runs. Library reads are cheap SELECTs
and stay under the catch-all limit.
"""

from datetime import datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend import models
from backend.core.config import settings
from backend.core.deps import require_verified_user
from backend.core.limiter import limiter
from backend.database import get_db
from backend.models.Bridge import (
    BridgeJob,
    BridgeJobSource,
    BridgeJobStatus,
    BridgeRecentSearch,
    BridgeVerdict,
    BridgeVerdictStatus,
)
from backend.models.TrainingJob import utcnow
from backend.schemas.bridge import (
    BridgeJobResponse,
    BridgeLibraryEntry,
    BridgeRecentEntry,
    BridgeRecentLookup,
    BridgeRunAccepted,
    BridgeRunRequest,
    BridgeSpecResponse,
    BridgeVerdictResponse,
)
from backend.services.bridge import plain
from backend.services.bridge.recents import record_search
from backend.services.bridge.registry import BRIDGE_SPECS, get_spec
from backend.services.bridge.slug import slugify_topic
from backend.services.registry import MODELS

router = APIRouter(prefix="/bridge", tags=["Bridge"])

ACTIVE_STATUSES = (BridgeJobStatus.QUEUED.value, BridgeJobStatus.RUNNING.value)


def _queue_head(db: Session) -> datetime | None:
    """When the oldest still-queued job was created, or None if nothing waits.

    This is the drain's pulse as seen from the web tier, and it is deliberately
    ONE query per request rather than one per job: list_runs renders in a loop.
    """
    return db.execute(
        select(func.min(BridgeJob.created_at)).where(
            BridgeJob.status == BridgeJobStatus.QUEUED.value
        )
    ).scalar_one_or_none()


def _is_stalled(job: BridgeJob, head: datetime | None) -> bool:
    """Whether this queued job is waiting on a queue that isn't moving.

    Judged on the HEAD of the queue, never on the job's own age or its position.
    A job sitting second in line is stalled just as surely as the one in front of
    it, and its own age says nothing while a live drain is working through a real
    backlog. The head is the signal that separates those two cases: a running
    drain keeps advancing it, a dead one lets it rot.

    The web tier cannot do better than this without a worker heartbeat of its
    own, which is deliberately not built (see BRIDGE_SERVICES.md).
    """
    if job.status != BridgeJobStatus.QUEUED.value or head is None:
        return False
    return head < utcnow() - timedelta(seconds=settings.BRIDGE_JOB_QUEUE_STALE_SECONDS)


def _job_response(db: Session, job: BridgeJob, head: datetime | None) -> BridgeJobResponse:
    verdict_ready = job.status == BridgeJobStatus.SUCCEEDED.value
    return BridgeJobResponse(
        id=job.id,
        topic_input=job.topic_input,
        topic_slug=job.topic_slug,
        model_id=job.model_id,
        status=job.status,
        stage=job.stage,
        progress=job.progress,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error=job.error,
        queue_position=_queue_position(db, job),
        verdict_ready=verdict_ready,
        stalled=_is_stalled(job, head),
    )


def _queue_position(db: Session, job: BridgeJob) -> int | None:
    if job.status != BridgeJobStatus.QUEUED.value:
        return None
    return db.execute(
        select(func.count())
        .select_from(BridgeJob)
        .where(
            BridgeJob.status == BridgeJobStatus.QUEUED.value,
            BridgeJob.created_at < job.created_at,
        )
    ).scalar_one()


def _daily_spend(db: Session) -> float:
    """Today's LIVE bridge spend across all users, the global cap's denominator.
    UTC midnight boundary, matching the app's clock.

    Seed runs are excluded deliberately. Seeding is curation done from the CLI
    with its own `--max-spend`, and a seeding session costs multiples of the
    daily cap by design; counting it here would lock every learner out of the
    feature for the rest of the day as a side effect of stocking the library.
    """
    midnight = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    total = db.execute(
        select(func.coalesce(func.sum(BridgeJob.cost_usd), 0)).where(
            BridgeJob.created_at >= midnight,
            BridgeJob.source == BridgeJobSource.LIVE.value,
        )
    ).scalar_one()
    return float(total)


@router.get("/specs", response_model=list[BridgeSpecResponse])
def list_specs(
    current_user: Annotated[models.User, Depends(require_verified_user)],
):
    """The full ten-step ladder, availability derived from the model registry.
    Steps that can't train yet still answer feasibility questions — that's the
    point of BRIDGE_SPECS being a superset of MODELS."""
    return [
        BridgeSpecResponse(
            model_id=spec.model_id,
            ordinal=spec.ordinal,
            display_name=spec.display_name,
            capability=spec.capability,
            modality=spec.modality.value,
            data_requirement=spec.data_requirement.value,
            has_probe=spec.probe is not None,
            available=spec.model_id in MODELS,
        )
        for spec in sorted(BRIDGE_SPECS.values(), key=lambda s: s.ordinal)
    ]


def _library_entry(row: BridgeVerdict) -> BridgeLibraryEntry:
    dataset = (row.verdict or {}).get("dataset") or {}
    scale = dataset.get("scale") or {}
    return BridgeLibraryEntry(
        topic_slug=row.topic_slug,
        topic_display=plain.topic_title(row.topic_display),
        model_id=row.model_id,
        verdict_value=row.verdict.get("verdict", ""),
        summary=row.verdict.get("summary", ""),
        dataset_title=dataset.get("title"),
        rows=scale.get("num_rows"),
        published=row.status == BridgeVerdictStatus.PUBLISHED.value,
    )


@router.get("/library", response_model=list[BridgeLibraryEntry])
def browse_library(
    current_user: Annotated[models.User, Depends(require_verified_user)],
    db: Annotated[Session, Depends(get_db)],
    model_id: str | None = None,
):
    """The published library: reviewed verdicts only, the handful featured on a
    step's dataset page. Filtered by step when `model_id` is given."""
    query = select(BridgeVerdict).where(
        BridgeVerdict.status == BridgeVerdictStatus.PUBLISHED.value
    )
    if model_id is not None:
        query = query.where(BridgeVerdict.model_id == model_id)
    rows = db.execute(
        query.order_by(BridgeVerdict.topic_slug, BridgeVerdict.model_id)
    ).scalars().all()
    return [_library_entry(row) for row in rows]


@router.get("/topics", response_model=list[BridgeLibraryEntry])
def list_checked_topics(
    current_user: Annotated[models.User, Depends(require_verified_user)],
    db: Annotated[Session, Depends(get_db)],
    model_id: str | None = None,
):
    """Every topic already checked for a step, published or not.

    This is the cache made visible: a topic in here has been through the whole
    pipeline once, so pulling it up is a lookup rather than a paid agent run.
    The list is small and static enough to filter in the browser as the student
    types, which beats a request per keystroke.
    """
    query = select(BridgeVerdict)
    if model_id is not None:
        query = query.where(BridgeVerdict.model_id == model_id)
    rows = db.execute(query.order_by(BridgeVerdict.topic_display)).scalars().all()
    return [_library_entry(row) for row in rows]


@router.get("/recent", response_model=list[BridgeRecentEntry])
def list_recent_searches(
    current_user: Annotated[models.User, Depends(require_verified_user)],
    db: Annotated[Session, Depends(get_db)],
    model_id: str | None = None,
):
    """The topics this student looked up for this step, newest first.

    The shelf below it is curated and global; this is the half of the page that
    is theirs. It exists because a live run's verdict is stored DRAFT and the
    shelf lists PUBLISHED only, so a student's own result can never appear there
    without a curator promoting it.

    INNER JOIN, so a remembered row whose verdict has gone simply stops
    rendering. The alternative — a card that 404s when clicked — is worse than
    forgetting the search.
    """
    query = (
        select(BridgeRecentSearch, BridgeVerdict)
        .join(
            BridgeVerdict,
            (BridgeVerdict.topic_slug == BridgeRecentSearch.topic_slug)
            & (BridgeVerdict.model_id == BridgeRecentSearch.model_id),
        )
        .where(BridgeRecentSearch.user_id == current_user.id)
    )
    if model_id is not None:
        query = query.where(BridgeRecentSearch.model_id == model_id)
    rows = db.execute(
        query.order_by(BridgeRecentSearch.searched_at.desc(), BridgeRecentSearch.id.desc())
    ).all()
    return [
        BridgeRecentEntry(
            **_library_entry(verdict).model_dump(),
            searched_at=recent.searched_at,
        )
        for recent, verdict in rows
    ]


@router.post("/recent", response_model=BridgeRecentLookup)
def record_recent_search(
    body: BridgeRunRequest,
    current_user: Annotated[models.User, Depends(require_verified_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Look a topic up on the shelf and, on a hit, remember that they did.

    This is the free half of searching, deliberately split off from POST /runs.
    RATE_LIMIT_BRIDGE is 3/hour and its decorator sits *outside* that handler, so
    it counts a request before the handler can discover the answer was already
    cached and cost nothing. That made the fourth lookup in an hour a 429 even
    when all four were free — which is precisely the "search a fourth topic and
    watch the oldest drop off" flow the finder is built around. The hourly limit
    belongs on the endpoint that spends money; this one stays under the catch-all.

    Slugifying here rather than in the browser is the same cost-control argument
    as everywhere else: the slug IS the cache key, so a client-side copy drifting
    from `slugify_topic` would quietly buy two verdicts for one topic.
    """
    spec = get_spec(body.model_id)
    if spec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown step")

    topic_slug = slugify_topic(body.topic)
    if not topic_slug:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="That topic doesn't contain any usable words.",
        )

    existing = db.execute(
        select(BridgeVerdict).where(
            BridgeVerdict.topic_slug == topic_slug,
            BridgeVerdict.model_id == spec.model_id,
        )
    ).scalars().first()
    if existing is None:
        # Nothing to open, so nothing to remember. Recording here would put a
        # dead card on the page and evict a real result to make room for it.
        return BridgeRecentLookup(topic_slug=topic_slug, exists=False)

    record_search(db, user_id=current_user.id, model_id=spec.model_id, topic_slug=topic_slug)
    return BridgeRecentLookup(topic_slug=topic_slug, exists=True)


@router.get("/verdicts/{topic_slug}/{model_id}", response_model=BridgeVerdictResponse)
def get_verdict(
    topic_slug: str,
    model_id: str,
    current_user: Annotated[models.User, Depends(require_verified_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """One stored verdict artefact. Drafts are served too — the artefact is the
    same data either way; `published` gates only the library LISTING."""
    row = db.execute(
        select(BridgeVerdict).where(
            BridgeVerdict.topic_slug == topic_slug,
            BridgeVerdict.model_id == model_id,
        )
    ).scalars().first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No verdict for that topic and step")
    spec = get_spec(row.model_id)
    artefact = row.verdict or {}
    dataset = artefact.get("dataset") or {}
    return BridgeVerdictResponse(
        topic_slug=row.topic_slug,
        model_id=row.model_id,
        topic_display=plain.topic_title(row.topic_display),
        status=row.status,
        verdict=artefact,
        last_verified=row.last_verified,
        plain_fit=plain.fit_line(artefact, spec),
        plain_license=plain.license_line(dataset.get("license")),
        plain_difficulty=plain.difficulty_line(artefact.get("difficulty")),
        plain_done=plain.done_line(artefact, spec),
        step_name=spec.display_name if spec else row.model_id,
    )


@router.post("/runs", response_model=BridgeRunAccepted, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit(settings.RATE_LIMIT_BRIDGE)
def start_run(
    request: Request,
    body: BridgeRunRequest,
    current_user: Annotated[models.User, Depends(require_verified_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Queue a feasibility run — or short-circuit to a stored verdict for free.

    The handler runs nothing (the worker's bridge drain claims the row); it
    only decides whether a run is allowed to spend money right now.
    """
    spec = get_spec(body.model_id)
    if spec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown step")

    topic_slug = slugify_topic(body.topic)
    if not topic_slug:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="That topic doesn't contain any usable words.",
        )

    # Library / cache hit: same slug + step = same verdict, zero cost (§14.6).
    existing = db.execute(
        select(BridgeVerdict).where(
            BridgeVerdict.topic_slug == topic_slug,
            BridgeVerdict.model_id == body.model_id,
        )
    ).scalars().first()
    if existing is not None:
        # Reachable when a verdict landed between the finder's POST /bridge/recent
        # and this call — someone else's run finishing, or a second tab. The
        # common path never gets here, but when it does the search is just as real
        # and belongs in their list. record_search commits; this branch is
        # otherwise a bare return that writes nothing.
        record_search(
            db, user_id=current_user.id, model_id=body.model_id, topic_slug=topic_slug
        )
        return BridgeRunAccepted(library_hit=True, topic_slug=topic_slug, model_id=body.model_id)

    if not settings.BRIDGE_ENABLED:
        # No drain is running in this environment; accepting would queue a job
        # nothing ever claims. Same honesty rule as TRAINING_ENABLED.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Feasibility runs are currently unavailable.",
        )

    if _daily_spend(db) >= settings.BRIDGE_DAILY_SPEND_CAP_USD:
        # The global cap. 429 (not 503): the resource exists, the budget is
        # spent; tomorrow it resets.
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Today's feasibility-run budget is used up. Try again tomorrow, or browse the library.",
        )

    job = BridgeJob(
        user_id=current_user.id,
        topic_input=body.topic.strip(),
        topic_slug=topic_slug,
        model_id=spec.model_id,
        source=BridgeJobSource.LIVE.value,
        status=BridgeJobStatus.QUEUED.value,
    )
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        # uq_bridge_jobs_active_per_user fired — DB-enforced, race-proof.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a feasibility run in progress. Wait for it to finish.",
        )
    db.refresh(job)
    return BridgeRunAccepted(
        library_hit=False,
        topic_slug=topic_slug,
        model_id=spec.model_id,
        job=_job_response(db, job, _queue_head(db)),
    )


@router.get("/runs", response_model=list[BridgeJobResponse])
def list_runs(
    current_user: Annotated[models.User, Depends(require_verified_user)],
    db: Annotated[Session, Depends(get_db)],
):
    jobs = db.execute(
        select(BridgeJob)
        .where(BridgeJob.user_id == current_user.id)
        .order_by(BridgeJob.created_at.desc())
    ).scalars().all()
    head = _queue_head(db)
    return [_job_response(db, job, head) for job in jobs]


@router.get("/runs/{run_id}", response_model=BridgeJobResponse)
def get_run(
    run_id: UUID,
    current_user: Annotated[models.User, Depends(require_verified_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Poll one run; carries the progress narrative. 404 (not 403) for someone
    else's run — same enumeration defence as /train."""
    job = db.execute(
        select(BridgeJob).where(
            BridgeJob.id == run_id,
            BridgeJob.user_id == current_user.id,
        )
    ).scalars().first()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return _job_response(db, job, _queue_head(db))


@router.delete("/runs/{run_id}", response_model=BridgeJobResponse)
def cancel_run(
    run_id: UUID,
    current_user: Annotated[models.User, Depends(require_verified_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Give up on a run that hasn't started, freeing the caller's active slot.

    QUEUED only, and that restriction is the whole safety argument. It is the
    mirror image of the reasoning in train.py's clear_finished_jobs: there, an
    active job must be left alone because a worker is mid-flight on it; here, a
    queued job is by definition one no worker has touched, so releasing it
    orphans nothing. A RUNNING job is refused for exactly train.py's reason.

    One atomic conditional UPDATE, not read-then-write: the drain can claim this
    row between the student's click and this statement, and the WHERE clause is
    what makes that race a clean 409 instead of a job cancelled out from under a
    worker that is already spending money on it.
    """
    result = db.execute(
        update(BridgeJob)
        .where(
            BridgeJob.id == run_id,
            BridgeJob.user_id == current_user.id,
            BridgeJob.status == BridgeJobStatus.QUEUED.value,
        )
        .values(
            status=BridgeJobStatus.CANCELLED.value,
            finished_at=utcnow(),
        )
    )
    db.commit()

    job = db.execute(
        select(BridgeJob).where(
            BridgeJob.id == run_id,
            BridgeJob.user_id == current_user.id,
        )
    ).scalars().first()
    if job is None:
        # Never distinguish "no such run" from "someone else's run" — same
        # enumeration defence as get_run.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That search has already started, so it can't be called off now.",
        )
    return _job_response(db, job, _queue_head(db))
