"""CLI entrypoint for the content seeder.

Run from the repo root with the project venv:

    ./venv/bin/python -m backend.seed

Populates the rungs/exercises tables from ``backend/seed/manifest.py``. Safe to
re-run: rows are upserted on their natural keys, so a second run updates content
in place rather than duplicating or erroring. Requires the same environment as
the app (``DATABASE_URL`` etc.) and an already-migrated schema
(``./venv/bin/alembic upgrade head``).
"""

from backend import models
from backend.database import SessionLocal
from backend.seed.seeder import seed


def main() -> None:
    db = SessionLocal()
    try:
        seed(db)
        db.commit()
        rungs = db.query(models.Rungs).count()
        exercises = db.query(models.Exercise).count()
        print(f"Seed complete: {rungs} rungs, {exercises} exercises.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
