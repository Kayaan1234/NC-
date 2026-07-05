"""Shared fixtures for the auth/user test suite.

Design notes (why the setup looks the way it does):

* **In-memory SQLite, one fresh DB per test.** A StaticPool keeps a single
  shared connection alive so every session in a test sees the same in-memory
  schema, and the whole engine is torn down between tests — no state bleed.

* **`base_url="https://testserver"`.** The refresh-token cookie is minted with
  `Secure=True` (the prod default; it's not overridden in `.env`). httpx's
  cookie jar refuses to *send* a Secure cookie back over plain http, so an
  http:// TestClient would drop the cookie on every /auth/refresh and /logout
  and manufacture spurious 401s. Talking https to the ASGI app keeps the whole
  cookie round-trip realistic — and lets us assert the Secure flag for real.

* **Email is faked, not sent.** The raw verification/reset token only ever
  exists inside the email (the DB stores only its SHA-256). We monkeypatch the
  two senders where `verification.py` references them and capture the raw token,
  which is how the token-consuming tests get something to POST.

* **Rate limiting is disabled by default.** slowapi's limiter is process-global
  and keyed on client IP; under TestClient every request shares one IP, so the
  5/hour email limit would trip mid-suite and fail unrelated tests. It's turned
  off here and switched back on only in test_auth_rate_limit.py.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_db
from backend import models  # noqa: F401  (registers all tables on Base.metadata)
import backend.main as main_module
import backend.routers.auth as auth_module
from backend.core.limiter import limiter


@pytest.fixture()
def db_sessionmaker():
    """A fresh in-memory database + sessionmaker, isolated to one test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    try:
        yield TestingSession
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def db_session(db_sessionmaker):
    """A raw session for tests that need to seed or inspect the DB directly."""
    session = db_sessionmaker()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def sent_emails(monkeypatch):
    """Capture outbound emails instead of hitting Resend.

    Each entry is {"kind", "to_email", "token"}. Patched on
    `backend.core.verification`, which is the module that actually references
    the senders (it imports them by name), so the patch is seen by the code
    under test regardless of what `core.email` does.
    """
    captured: list[dict] = []

    def fake_verification(token: str, to_email: str) -> None:
        captured.append({"kind": "verify_email", "to_email": to_email, "token": token})

    def fake_reset(token: str, to_email: str) -> None:
        captured.append({"kind": "reset_password", "to_email": to_email, "token": token})

    def fake_account_exists(to_email: str) -> None:
        captured.append({"kind": "account_exists", "to_email": to_email, "token": None})

    def fake_email_changed(to_email: str, new_email: str) -> None:
        captured.append({
            "kind": "email_changed", "to_email": to_email, "token": None, "new_email": new_email,
        })

    import backend.core.verification as verification_module
    import backend.routers.users as users_module

    monkeypatch.setattr(verification_module, "send_verification_email", fake_verification)
    monkeypatch.setattr(verification_module, "send_password_reset_email", fake_reset)
    # These are called directly, imported into their respective routers.
    monkeypatch.setattr(auth_module, "send_account_exists_email", fake_account_exists)
    monkeypatch.setattr(users_module, "send_email_changed_notification", fake_email_changed)
    return captured


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Wipe the process-global limiter state and disable it for every test.

    Rate-limit behaviour is exercised explicitly in test_auth_rate_limit.py,
    which re-enables the limiter itself. Everywhere else it must be inert so the
    shared-IP TestClient doesn't accumulate hits across tests.
    """
    limiter.reset()
    limiter.enabled = False
    yield
    limiter.reset()
    # Suite default is disabled; test_auth_rate_limit.py opts back in per-test.
    limiter.enabled = False


@pytest.fixture()
def client_factory(db_sessionmaker, monkeypatch, sent_emails):
    """Factory for TestClients that all share the one per-test database.

    Returns a callable so a test can spin up two independent clients (separate
    cookie jars) to model two devices/sessions of the same or different users.
    """
    def _get_db_override():
        db = db_sessionmaker()
        try:
            yield db
        finally:
            db.close()

    main_module.app.dependency_overrides[get_db] = _get_db_override
    # forgot-password runs its DB work in a BackgroundTask via SessionLocal()
    # (not the request session), so point that at the test DB too.
    monkeypatch.setattr(auth_module, "SessionLocal", db_sessionmaker)

    created: list[TestClient] = []

    def _make(host: str | None = None) -> TestClient:
        # `host` sets scope["client"] so slowapi's get_remote_address sees a
        # distinct IP — used to prove rate-limit buckets aren't shared.
        kwargs = {"base_url": "https://testserver"}
        if host is not None:
            kwargs["client"] = (host, 50000)
        c = TestClient(main_module.app, **kwargs)
        created.append(c)
        return c

    try:
        yield _make
    finally:
        for c in created:
            c.close()
        main_module.app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def client(client_factory):
    """The default single TestClient (cookies persist across calls in a test)."""
    return client_factory()
