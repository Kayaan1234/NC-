"""Idempotent upsert of the manifest content into the database.

Keyed on natural keys — ``Rungs.number`` and ``Exercise.(rung_id, order_index)``
— so re-running updates rows in place instead of raising on the unique
constraints. This is what makes the seed *repeatable*: run it as many times as
you like, edit the manifest, run it again, and the tables converge on the
manifest without duplicates.

The caller owns the transaction (this function only flushes); the CLI entrypoint
in ``__main__`` commits, and tests can drive :func:`seed` against their own
session and assert before committing.

Note: this is upsert-only. Rows removed from the manifest are left in place;
pruning stale content is deliberately out of scope for now.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend import models
from backend.seed.manifest import RUNGS, ExerciseSeed, RungSeed


def _upsert_rung(db: Session, rung: RungSeed) -> models.Rungs:
    row = db.execute(
        select(models.Rungs).where(models.Rungs.number == rung.number)
    ).scalar_one_or_none()
    if row is None:
        row = models.Rungs(number=rung.number)
        db.add(row)
    row.slug = rung.slug
    row.title = rung.title
    row.description = rung.description
    db.flush()  # populate row.id so exercises can reference it
    return row


def _upsert_exercise(db: Session, rung_id: UUID, ex: ExerciseSeed) -> models.Exercise:
    row = db.execute(
        select(models.Exercise).where(
            models.Exercise.rung_id == rung_id,
            models.Exercise.order_index == ex.order_index,
        )
    ).scalar_one_or_none()
    if row is None:
        row = models.Exercise(rung_id=rung_id, order_index=ex.order_index)
        db.add(row)
    row.slug = ex.slug
    row.title = ex.title
    row.prompt = ex.prompt
    row.starter_code = ex.starter_code()  # None for read-only / no-scaffold exercises
    row.model_solution = ex.model_solution()
    row.read_only = ex.read_only
    db.flush()
    return row


def seed(db: Session) -> None:
    """Upsert every rung/exercise in the manifest. Does not commit."""
    for rung in RUNGS:
        row = _upsert_rung(db, rung)
        for ex in rung.exercises:
            _upsert_exercise(db, row.id, ex)
