"""Shared fixtures for the whole suite.

Design notes (why the setup looks the way it does):

* **One engine, and it is the app's own.** The repo-root `conftest.py` sets
  `DATABASE_URL` before anything under `backend/` is imported, so
  `backend.database.engine` / `SessionLocal` *are* the test engine. There is
  deliberately **no** `dependency_overrides[get_db]` and no second engine: both
  `backend/worker.py` and `backend/services/email_drain.py` call `SessionLocal()`
  directly, so a fixture-owned engine would leave those tests reading a different
  database than the one the fixtures seeded — invisible rows and assertion
  failures that look like logic bugs. `_guard_test_database` proves the redirect
  took before any test runs.

* **Real Postgres, schema from Alembic.** SQLite would make several tests
  silently vacuous: `with_for_update()` (refresh rotation) and
  `FOR UPDATE SKIP LOCKED` (worker + outbox claim) are no-ops there, and
  `ondelete="CASCADE"` needs a per-connection PRAGMA. Running the migrations
  rather than `create_all` also means the migrations themselves get exercised on
  every suite run.

* **TRUNCATE between tests, not a wrapping transaction.** The code under test
  commits constantly (`core/verification.py`, both routers), which fights the
  rollback-a-nested-SAVEPOINT pattern. Truncate is boring and correct here.

* **`base_url="https://testserver"`.** The refresh cookie is minted with
  `Secure=True` (the prod default). httpx's cookie jar refuses to *send* a Secure
  cookie back over plain http, so an http:// client would drop it on every
  /auth/refresh and /logout and manufacture spurious 401s. Talking https to the
  ASGI app keeps the cookie round-trip realistic — and lets us assert the Secure
  flag for real.

* **Email is asserted on, not mocked.** Every send now goes through
  `core/outbox.enqueue_email`, which only stages an `email_outbox` row; delivery
  happens later in the worker. So the request path makes no network calls at all
  and needs no patching — the `outbox` fixture just reads the table. Patching is
  confined to `outbox.drain()`, which stubs the four senders to exercise the
  drain logic without Resend.

* **Rate limiting is disabled by default.** slowapi's limiter is process-global
  and keyed on client IP; under TestClient every request shares one IP, so the
  5/hour email limit would trip mid-suite and fail unrelated tests. It is turned
  off here and switched back on only in test_auth_rate_limit.py.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.engine import make_url

from backend import models  # noqa: F401  registers every table on Base.metadata
from backend.database import Base, SessionLocal, engine
from backend.core.limiter import limiter
from backend.models.EmailOutbox import EmailOutbox, EmailType

REPO_ROOT = Path(__file__).resolve().parents[2]
UNIT_DIR = Path(__file__).resolve().parent / "unit"


def _needs_database(request: pytest.FixtureRequest) -> bool:
    """False for the unit tier, which must run with no database at all.

    A subdirectory conftest cannot switch off a parent's autouse fixture, and
    pytest 8 removed `pytest_plugins` from non-root conftests — so the tier is
    decided by location. Anything under backend/tests/unit/ is by definition
    I/O-free; `pytest backend/tests/unit` then needs no Postgres running, which
    is what keeps that tier usable as a fast inner loop.
    """
    return UNIT_DIR not in Path(str(request.node.path)).parents


# --------------------------------------------------------------------------- #
# Database lifecycle
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="session")
def _guard_test_database():
    """Fail the whole run if the app didn't actually pick up the test database.

    The root conftest sets DATABASE_URL before the first backend import; this
    proves the engine was actually built from it. Without the check, a change to
    config.py's import order would silently point the suite at the *dev*
    database and `_clean_tables` would truncate it.

    Compared against os.environ rather than by importing the root conftest:
    both files are named `conftest`, so `import conftest` resolves to whichever
    landed in sys.modules first — which is this one.
    """
    # Compared as parsed URL objects, not strings: render_as_string()
    # percent-encodes reserved characters in the password, so a byte comparison
    # against the raw env var spuriously fails on e.g. a '!' in the password.
    expected = make_url(os.environ["DATABASE_URL"])
    assert engine.url == expected, (
        f"backend.database.engine is bound to {engine.url!r}, not to DATABASE_URL. "
        "The root conftest.py must run before any backend import."
    )
    # Belt and braces: the root conftest already refuses a non-_test name, but
    # this is the last line of defence before TRUNCATE runs.
    assert (engine.url.database or "").endswith("_test"), (
        f"refusing to run against database {engine.url.database!r}"
    )
    yield


@pytest.fixture(scope="session")
def _migrate(_guard_test_database):
    """Build the schema once per run, from the migrations.

    Dropped first so a database left at an older revision by a previous run
    can't wedge `upgrade head`. `alembic/env.py` reads the URL from
    `settings.DATABASE_URL`, so it follows the same redirect everything else does
    and needs no `-x` override.
    """
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    Base.metadata.drop_all(bind=engine)

    cfg = Config(str(REPO_ROOT / "backend" / "alembic.ini"))
    command.upgrade(cfg, "head")
    yield


# Truncating every table is one statement, so it is cheap enough to do per test
# and buys total isolation. alembic_version is not in Base.metadata, so building
# the list from the metadata is what keeps the schema version intact.
_TRUNCATE = text(
    "TRUNCATE TABLE {} RESTART IDENTITY CASCADE".format(
        ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    )
)


@pytest.fixture(autouse=True)
def _clean_tables(request):
    """Empty every table before each test. No test may depend on another's rows.

    `_migrate` is pulled in lazily rather than declared as a parameter so that a
    unit test never touches the database — not even to migrate it. That is what
    lets `pytest backend/tests/unit` run with Postgres stopped.
    """
    if not _needs_database(request):
        yield
        return

    request.getfixturevalue("_migrate")
    with engine.begin() as conn:
        conn.execute(_TRUNCATE)
    yield


@pytest.fixture()
def db_session():
    """A session for tests that seed or inspect the database directly."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# --------------------------------------------------------------------------- #
# Rate limiter
# --------------------------------------------------------------------------- #

@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Wipe the process-global limiter state and disable it for every test.

    Rate-limit behaviour is exercised explicitly in test_auth_rate_limit.py,
    which re-enables the limiter itself. Everywhere else it must be inert so the
    shared-IP TestClient doesn't accumulate hits across tests — note that
    RATE_LIMIT_DEFAULT ("120/minute") is applied to *every* route by
    SlowAPIMiddleware, so without this a long run starts 429ing partway through
    and it reads as an auth bug.
    """
    limiter.reset()
    limiter.enabled = False
    yield
    limiter.reset()
    # Suite default is disabled; test_auth_rate_limit.py opts back in per-test.
    limiter.enabled = False


# --------------------------------------------------------------------------- #
# Email outbox
# --------------------------------------------------------------------------- #

class Outbox:
    """Reads (and optionally drains) the `email_outbox` table.

    This is the seam that replaced monkeypatching the senders. Every email the
    app "sends" is a row here, staged in the same transaction as the change that
    triggered it — so assertions are just queries, and the request path never
    touches the network.

    The raw verification/reset token exists *only* in the payload (the
    email_tokens table stores nothing but its SHA-256), which is how the
    token-consuming tests get something to POST.
    """

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._monkeypatch = monkeypatch
        self.delivered: list[dict] = []

    def rows(self, email_type: EmailType | str | None = None) -> list[dict]:
        """Every queued row, oldest first, as plain dicts."""
        wanted = getattr(email_type, "value", email_type)
        with SessionLocal() as db:
            stmt = select(EmailOutbox).order_by(EmailOutbox.created_at, EmailOutbox.id)
            if wanted is not None:
                stmt = stmt.where(EmailOutbox.email_type == wanted)
            return [
                {
                    "kind": row.email_type,
                    "status": row.status,
                    "attempts": row.attempts,
                    "payload": dict(row.payload or {}),
                    "to_email": (row.payload or {}).get("to_email"),
                    "token": (row.payload or {}).get("token"),
                }
                for row in db.execute(stmt).scalars().all()
            ]

    def kinds(self) -> list[str]:
        return [row["kind"] for row in self.rows()]

    def clear(self) -> None:
        """Forget everything sent so far.

        Used to draw a line under setup (registering a user always emits a
        verification email) so an assertion can talk about what the *action under
        test* sent, without counting around the noise.
        """
        with SessionLocal() as db:
            db.query(EmailOutbox).delete()
            db.commit()
        self.delivered.clear()

    def latest(self, email_type: EmailType | str | None = None) -> dict:
        rows = self.rows(email_type)
        assert rows, f"no outbox row of type {email_type!r}; queue holds {self.kinds()}"
        return rows[-1]

    def token(self, email_type: EmailType | str) -> str:
        """The raw token from the most recent row of a type."""
        token = self.latest(email_type)["token"]
        assert token, f"outbox row of type {email_type!r} carries no token"
        return token

    def drain(self, max_rows: int = 20) -> list[dict]:
        """Run the worker's drain loop over the queue with the senders stubbed.

        Needed wherever delivery — not just intent — is what's under test. The
        clearest case is /auth/forgot-password: it enqueues only a
        FORGOT_PASSWORD_REQUEST row (no user lookup happens on the request path,
        which is what keeps the endpoint enumeration-resistant), and the drain is
        what resolves that into a PASSWORD_RESET row carrying a real token.

        Patch targets differ and both are load-bearing: `_handle` calls the four
        senders through email_drain's OWN module namespace, so they patch there;
        `_resolve_forgot_password` imports `issue_password_reset` inside the
        function body, so that one is left alone and runs for real.
        """
        from backend.services import email_drain

        def _record(kind: str, **fields):
            self.delivered.append({"kind": kind, **fields})

        self._monkeypatch.setattr(
            email_drain, "send_verification_email",
            lambda token, to_email: _record("verify_email", to_email=to_email, token=token),
        )
        self._monkeypatch.setattr(
            email_drain, "send_password_reset_email",
            lambda token, to_email: _record("password_reset", to_email=to_email, token=token),
        )
        self._monkeypatch.setattr(
            email_drain, "send_account_exists_email",
            lambda to_email: _record("account_exists", to_email=to_email, token=None),
        )
        self._monkeypatch.setattr(
            email_drain, "send_email_changed_notification",
            lambda to_email, new_email: _record(
                "email_changed", to_email=to_email, token=None, new_email=new_email
            ),
        )

        with SessionLocal() as db:
            for _ in range(max_rows):
                if not email_drain.drain_one(db):
                    break
            else:
                raise AssertionError(
                    f"outbox still had work after {max_rows} drains — probable loop"
                )
        return self.delivered

    def delivered_of(self, kind: str) -> list[dict]:
        """Emails actually handed to a sender by `drain()`, oldest first.

        Distinct from `rows()`, and the distinction matters: a successfully sent
        row is DELETED from the table, so after a drain the queue is empty and
        only this list still holds the evidence.
        """
        return [item for item in self.delivered if item["kind"] == kind]

    def delivered_token(self, kind: str) -> str:
        items = self.delivered_of(kind)
        assert items, (
            f"no {kind!r} email was delivered; "
            f"delivered={[i['kind'] for i in self.delivered]}, queue={self.kinds()}"
        )
        token = items[-1]["token"]
        assert token, f"delivered {kind!r} email carries no token"
        return token


@pytest.fixture()
def outbox(monkeypatch: pytest.MonkeyPatch) -> Outbox:
    return Outbox(monkeypatch)


# --------------------------------------------------------------------------- #
# HTTP clients
# --------------------------------------------------------------------------- #

@pytest.fixture()
def client_factory():
    """Factory for TestClients that all share the one test database.

    A callable rather than a fixture so a test can spin up two independent
    clients (separate cookie jars) to model two devices, or two users.

    `host` sets scope["client"] so slowapi's `get_remote_address` sees a distinct
    IP — that is how the rate-limit tests prove buckets aren't shared. It matters
    because the limits themselves are frozen at import time: the decorator
    argument `@limiter.limit(settings.RATE_LIMIT_AUTH)` is evaluated when
    routers/auth.py is imported, so monkeypatching `settings` later does nothing
    and the only way to test a limit is to actually trip it.
    """
    import backend.main as main_module

    created: list[TestClient] = []

    def _make(host: str | None = None) -> TestClient:
        kwargs: dict = {"base_url": "https://testserver"}
        if host is not None:
            kwargs["client"] = (host, 50000)
        made = TestClient(main_module.app, **kwargs)
        created.append(made)
        return made

    try:
        yield _make
    finally:
        for made in created:
            made.close()


@pytest.fixture()
def client(client_factory) -> TestClient:
    """The default single TestClient (cookies persist across calls in a test)."""
    return client_factory()
