from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from backend import models
from backend.core.deps import require_verified_user
from backend.database import get_db
from backend.schemas.auth import (
    ExerciseListItem,
    ExerciseProgressStatus,
    UserRungProgressResponse,
)

router = APIRouter(prefix="/rungs", tags=["Rungs"])


@router.get("/{rung_number}/exercises", response_model=UserRungProgressResponse)
def get_rung_exercises(
    rung_number: int,
    user: Annotated[models.User, Depends(require_verified_user)],
    db: Annotated[Session, Depends(get_db)],
) -> UserRungProgressResponse:
    """The exercises of one rung with this user's progress, plus a resume pointer.

    Rungs are addressed by their public `number` (0-9, the same value the dashboard
    and the SPA's /rung/:number route use) — not their UUID id. A rung with no
    authored exercises returns an empty list (200), which is distinct from an
    unknown rung (404).
    """
    rung = db.execute(
        select(models.Rungs.id).where(models.Rungs.number == rung_number)
    ).scalar_one_or_none()
    if rung is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rung not found")

    # One LEFT JOIN pulls every exercise with this user's progress row (or NULL) in
    # a single ordered query — no N+1 across exercises.
    rows = db.execute(
        select(models.Exercise, models.UserExerciseProgress.status)
        .outerjoin(
            models.UserExerciseProgress,
            and_(
                models.UserExerciseProgress.exercise_id == models.Exercise.id,
                models.UserExerciseProgress.user_id == user.id,
            ),
        )
        .where(models.Exercise.rung_id == rung)
        .order_by(models.Exercise.order_index)
    ).all()

    exercises: list[ExerciseListItem] = []
    next_incomplete_slug: str | None = None
    for exercise, progress_status in rows:
        item_status = (
            ExerciseProgressStatus.NOT_STARTED
            if progress_status is None
            else ExerciseProgressStatus(progress_status)
        )
        exercises.append(
            ExerciseListItem(
                id=exercise.id,
                slug=exercise.slug,
                title=exercise.title,
                order_index=exercise.order_index,
                status=item_status,
                read_only=exercise.read_only,
            )
        )
        # Resume point: the first exercise (in order) the user hasn't finished.
        if next_incomplete_slug is None and item_status != ExerciseProgressStatus.COMPLETED:
            next_incomplete_slug = exercise.slug

    return UserRungProgressResponse(exercises=exercises, next_incomplete_slug=next_incomplete_slug)
