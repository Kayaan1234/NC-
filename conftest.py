"""Repo-root conftest. Its ONLY job is to point the app at a test database
*before* anything under `backend/` is imported.

Why this file has to exist at all
---------------------------------
`backend/core/config.py` does two things that together make a bare `pytest`
dangerous:

    BASE_DIR = Path(__file__).resolve().parent.parent      # -> backend/
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env")
    settings = Settings()                                  # at IMPORT time

The env_file path is absolute, so it resolves to the developer's real
`backend/.env` no matter where pytest runs from, and the singleton is built the
moment `backend.core.config` is imported. `backend.database` then builds its
engine from `settings.DATABASE_URL` at import time too.

So without this file, `pytest` boots against the **development Postgres**.
`app.dependency_overrides[get_db]` would not save you: `backend/worker.py` and
`backend/services/email_drain.py` call `SessionLocal()` directly, and those
tests would happily truncate the dev database.

Environment variables win over the `.env` file in pydantic-settings, so setting
them here — at conftest import, which pytest performs before collecting any test
module — is what redirects the whole app. Nothing in this file may import
`backend`; the guard fixture in `backend/tests/conftest.py` verifies afterwards
that the redirect actually took.
"""

import os
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine import make_url

REPO_ROOT = Path(__file__).resolve().parent


def _test_database_url() -> str:
    """The URL every test runs against.

    `TEST_DATABASE_URL` wins if set (that's what CI uses). Otherwise we reuse the
    developer's own credentials from `backend/.env` and swap only the database
    name, so nobody has to keep a second password in a second place.

    The swap is deliberately done on the raw string rather than via
    `make_url(...).set(database=...).render_as_string()`. Rendering percent-
    encodes reserved characters in the password, and alembic's
    `config.set_main_option` (backend/alembic/env.py:33) feeds the URL through
    configparser's BasicInterpolation, which then dies with
    "invalid interpolation syntax" on the resulting '%'. Passing the original
    bytes through untouched sidesteps that entirely.
    """
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit

    dev_url = dotenv_values(REPO_ROOT / "backend" / ".env").get("DATABASE_URL")
    if not dev_url:
        raise RuntimeError(
            "No TEST_DATABASE_URL set and no DATABASE_URL in backend/.env, so the "
            "test database cannot be located. Set TEST_DATABASE_URL, e.g.\n"
            "  export TEST_DATABASE_URL="
            "'postgresql+psycopg://ncplusplus_user:PASSWORD@localhost/ncplusplus_test'"
        )

    base, question, query = dev_url.partition("?")
    prefix, slash, name = base.rpartition("/")
    if not slash or not name:
        raise RuntimeError(f"Could not find a database name in DATABASE_URL: {base!r}")
    # ncplusplus_dev -> ncplusplus_test, anything_else -> anything_else_test
    swapped = name[: -len("_dev")] + "_test" if name.endswith("_dev") else f"{name}_test"
    return f"{prefix}/{swapped}{question}{query}"


def _assert_is_a_test_database(url_string: str) -> None:
    """Refuse to run against anything not obviously disposable.

    The suite TRUNCATEs every table between tests. If the URL is ever wrong, the
    damage is silent and total, so the check is a hard failure rather than a
    warning — and it lives here, before the first import, rather than in a
    fixture that a `-p no:cacheprovider`-style mistake could skip.
    """
    name = make_url(url_string).database or ""
    if not name.endswith("_test"):
        raise RuntimeError(
            f"Refusing to run the test suite against database {name!r}: the name "
            "must end in '_test'. This suite truncates every table between tests."
        )


_TEST_DATABASE_URL = _test_database_url()
_assert_is_a_test_database(_TEST_DATABASE_URL)

# Exported so backend/tests/conftest.py can assert the engine actually picked
# this up, rather than trusting that it did.
TEST_DATABASE_URL = _TEST_DATABASE_URL

os.environ.update(
    {
        "DATABASE_URL": TEST_DATABASE_URL,
        # 32+ bytes: pyjwt warns below that, and a warning-free baseline means a
        # future warning is signal.
        "JWT_SECRET": "test-secret-not-used-anywhere-real-0123456789",
        "JWT_ALGORITHM": "HS256",
        # config.py requires this even though nothing on the request path calls
        # Resend — only the worker's drain loop does, and tests stub it.
        "RESEND_API_KEY": "test-resend-key-unused",
        # Cookies stay Secure (the prod default) because the tests assert the
        # real flags; TestClient talks https to compensate. See tests/conftest.py.
        "COOKIE_SECURE": "true",
        "COOKIE_SAMESITE": "strict",
        # Keep /docs, /redoc, /openapi.json and /scalar unregistered, matching
        # prod, so a test can assert they 404.
        "DOCS_ENABLED": "false",
        # MUST be a JSON array. pydantic-settings JSON-decodes list-typed fields
        # before field validators run, so a bare "http://x" raises SettingsError
        # at import and the whole suite fails to collect. The comma-splitting
        # validator in config.py only ever fires for init-kwargs, never env.
        "CORS_ORIGINS": '["http://localhost:5173"]',
        "FRONTEND_URL": "http://localhost:5173",
        "TRAINING_ENABLED": "true",
        # In-process counter storage; the autouse fixture resets it per test.
        "RATE_LIMIT_STORAGE_URI": "memory://",
    }
)
