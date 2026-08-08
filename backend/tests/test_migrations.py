"""The migrations and the ORM models must not drift apart.

`Base.metadata.create_all` is not called anywhere any more — the schema comes
solely from `backend/alembic/versions/`. That makes a model change committed
without a matching migration invisible in development (the dev database already
has the column) and a 500 in production. This test closes that gap: the suite's
schema is built by running the migrations, so comparing it back against the
models catches the omission on the next test run.

Verified empty against the current tree, including the dialect-specific partial
index on training_jobs and the `server_default=func.now()` columns — both of
which can otherwise produce phantom diffs.
"""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from backend import models  # noqa: F401  registers every table on Base.metadata
from backend.database import Base, engine


def test_models_match_migrations_with_no_pending_diff():
    with engine.connect() as connection:
        diffs = compare_metadata(MigrationContext.configure(connection), Base.metadata)

    assert diffs == [], (
        "The ORM models and the Alembic migrations have diverged. Generate a "
        "migration with:\n"
        "    .venv/bin/alembic -c backend/alembic.ini revision --autogenerate -m '<what changed>'\n"
        f"Pending changes: {diffs}"
    )
