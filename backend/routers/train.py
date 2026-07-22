from fastapi import APIRouter, HTTPException, Depends, Request, Response
from sqlalchemy.exc import IntegrityError
from backend.database import get_db
from backend import models
from backend.schemas.train import *
from sqlalchemy.orm import Session
from typing import Annotated, Any
from fastapi import status
from sqlalchemy import delete, func, select

from uuid import UUID

from backend.core.deps import require_verified_user
from backend.core.config import settings
from backend.core.limiter import limiter
from backend.models.TrainingJob import JobStatus, TrainingJob
from backend.services.params import ParamError, effective_max, validate
from backend.services.registry import MODELS, ModelSpec, get_model

router = APIRouter(
    prefix="/train",
    tags=["Train"]
)

# Every route here requires a *verified* user, not merely an authenticated one:
# each job spawns a real process, so an unverified address must not be able to
# burn compute.

ACTIVE_STATUSES = (JobStatus.QUEUED.value, JobStatus.RUNNING.value) 


def _spec_response(spec: ModelSpec) -> ModelSpecResponse:
    """Project a ModelSpec onto the wire.

    Everything here is copied from the descriptors — nothing is hardcoded per
    model. The one thing deliberately withheld is each parameter's `flag`: the
    client never builds a command line, and the argv is assembled server-side
    from the same specs (services/runner.build_argv).
    """
    return ModelSpecResponse(
        model_id=spec.model_id,
        name=spec.name,
        description=spec.description,
        params=[
            ParamSpecResponse(
                name=p.name,
                kind=p.kind,
                label=p.label,
                default=p.default,
                choices=list(p.choices),
                minimum=p.minimum,
                # The bound the form shows is the one the server will actually
                # apply, which may be tighter than the spec's own if a HARD_LIMIT
                # caps it.
                maximum=effective_max(p),
                max_items=p.max_items,
                item_min=p.item_min,
                item_max=p.item_max,
                help=p.help,
            )
            for p in spec.params
        ],
        result_fields=[
            ResultFieldResponse(key=r.key, label=r.label, format=r.format)
            for r in spec.result_fields
        ],
        dataset_defaults=spec.dataset_defaults,
    )


def _queue_position(db: Session, job: TrainingJob) -> int | None:
    """How many queued jobs are ahead of this one; 0 means next. None if not queued."""
    if job.status != JobStatus.QUEUED.value:
        return None
    return db.execute(
        select(func.count())
        .select_from(TrainingJob)
        .where(
            TrainingJob.status == JobStatus.QUEUED.value,
            TrainingJob.created_at < job.created_at,
        )
    ).scalar_one()


def _job_response(db: Session, job: TrainingJob) -> JobStatusResponse:
    return JobStatusResponse(
        id=job.id,
        model_id=job.model_id,
        params=job.params,
        status=job.status,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        result=job.result,
        error=job.error,
        queue_position=_queue_position(db, job),
        report_available=job.status not in ACTIVE_STATUSES,
    )


def _get_owned_job(job_id: UUID, current_user: models.User, db: Session) -> TrainingJob:
    """Fetch a job the caller owns, or 404.

    404 rather than 403 for someone else's job: a 403 would confirm the id exists,
    letting a caller enumerate job ids. From outside, another user's job and a
    non-existent one are indistinguishable — which is the point.
    """
    job = db.execute(
        select(TrainingJob).where(
            TrainingJob.id == job_id,
            TrainingJob.user_id == current_user.id,
        )
    ).scalars().first()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.get("/models", response_model=list[ModelSpecResponse])
def list_models(
    current_user: Annotated[models.User, Depends(require_verified_user)],
):
    """The trainable models and the bounds their parameter forms should honour.

    Served from the same registry the router validates against, so the UI cannot
    offer a parameter the server would reject.
    """
    return [_spec_response(spec) for spec in MODELS.values()]


@router.post("/{model_id}/run", response_model=JobCreatedResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit(settings.RATE_LIMIT_TRAIN)
def run_model(
    request: Request,
    model_id: str,
    body: dict[str, Any],
    current_user: Annotated[models.User, Depends(require_verified_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Queue a training job. 202: accepted, not finished.

    This handler does NOT run anything — it only inserts a row. The separate
    worker process (`python -m backend.worker`) claims it. That split is not
    stylistic: App Runner throttles CPU once a response is sent, so work started
    here would be starved, and a long run would be killed by instance recycling.
    """
    if not settings.TRAINING_ENABLED:
        # No worker is draining the queue in this environment, so accepting the
        # job would leave it queued forever. Say so instead of lying with a 202.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Training is currently unavailable.",
        )

    spec = get_model(model_id)
    if spec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown model")

    # All parameter validation — types, per-model bounds, and the absolute
    # cross-model ceiling — happens in one call against this model's descriptors.
    # There is no request schema to keep in step: see services/params.py.
    try:
        params = validate(spec, body)
    except ParamError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    job = TrainingJob(
        user_id=current_user.id,
        model_id=spec.model_id,
        params=params,
        status=JobStatus.QUEUED.value,
    )
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        # The partial unique index on (user_id) WHERE status IN ('queued','running')
        # fired: this user already has an active job. Enforced by the database
        # rather than a prior SELECT, because two concurrent POSTs would both pass
        # a check-then-insert.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a training job queued or running. Wait for it to finish.",
        )

    db.refresh(job)
    return JobCreatedResponse(id=job.id, status=job.status, created_at=job.created_at)


@router.get("/jobs", response_model=list[JobStatusResponse])
def list_jobs(
    current_user: Annotated[models.User, Depends(require_verified_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """The caller's jobs, newest first."""
    jobs = db.execute(
        select(TrainingJob)
        .where(TrainingJob.user_id == current_user.id)
        .order_by(TrainingJob.created_at.desc())
    ).scalars().all()
    return [_job_response(db, job) for job in jobs]


@router.delete("/jobs", response_model=ClearedJobsResponse)
def clear_finished_jobs(
    current_user: Annotated[models.User, Depends(require_verified_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Delete the caller's terminal jobs (succeeded/failed) to declutter history.

    Deliberately only touches terminal jobs: a `queued`/`running` job is still the
    user's single active slot, and deleting it would free that slot mid-run and
    orphan the worker's subprocess (it would finish, then write to a row that no
    longer exists). The status filter is part of the WHERE, so this stays a single
    atomic DELETE and is safe against a worker concurrently finishing a job — the
    worst case is a just-finished job surviving one extra click.
    """
    result = db.execute(
        delete(TrainingJob).where(
            TrainingJob.user_id == current_user.id,
            TrainingJob.status.in_(
                [JobStatus.SUCCEEDED.value, JobStatus.FAILED.value]
            ),
        )
    )
    db.commit()
    return ClearedJobsResponse(deleted=result.rowcount)


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job(
    job_id: UUID,
    current_user: Annotated[models.User, Depends(require_verified_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Poll one job. Includes queue_position while it's still waiting."""
    return _job_response(db, _get_owned_job(job_id, current_user, db))


@router.get("/jobs/{job_id}/report", response_class=Response)
def download_report(
    job_id: UUID,
    current_user: Annotated[models.User, Depends(require_verified_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Download the run's report: exactly what the driver printed.

    A failed job is terminal and so downloadable — it serves whatever output was
    captured with the error appended, which is more use than an empty file when
    you're trying to work out what went wrong.
    """
    job = _get_owned_job(job_id, current_user, db)

    if job.status in ACTIVE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This job hasn't finished yet.",
        )

    body = job.stdout or ""
    if job.error:
        if body and not body.endswith("\n"):
            body += "\n"
        body += f"\n=== job failed ===\n{job.error}\n"

    filename = f"training-{job.model_id}-{str(job.id)[:8]}.txt"
    return Response(
        content=body,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
