"""core/config.py — the settings validators, and one documented trap.

`settings = Settings()` runs at import, so a validation failure here is not a
bad request, it is a process that will not boot. Both validators are pure and
directly constructible.
"""

import pytest
from pydantic import ValidationError

from backend.core.config import Settings, settings

# Every required field, so a Settings(...) built here doesn't depend on whatever
# happens to be in the developer's backend/.env.
REQUIRED = {
    "JWT_SECRET": "unit-test-secret",
    "JWT_ALGORITHM": "HS256",
    "DATABASE_URL": "postgresql+psycopg://u:p@localhost/x_test",
    "RESEND_API_KEY": "unit-test-key",
}


def _settings(**overrides) -> Settings:
    return Settings(**{**REQUIRED, **overrides})


# --------------------------------------------------------------------------- #
# The SameSite=None cross-field rule
# --------------------------------------------------------------------------- #

def test_samesite_none_without_secure_refuses_to_build():
    """SameSite=None is meaningless — and rejected by browsers — without Secure.
    Failing at construction means the process dies on boot rather than minting
    cookies no browser will store."""
    with pytest.raises(ValidationError):
        _settings(COOKIE_SAMESITE="none", COOKIE_SECURE=False)


def test_samesite_none_with_secure_is_allowed():
    built = _settings(COOKIE_SAMESITE="none", COOKIE_SECURE=True)
    assert built.COOKIE_SAMESITE == "none"


@pytest.mark.parametrize("samesite", ["strict", "lax"])
def test_the_other_samesite_values_do_not_require_secure(samesite):
    """Local http development needs Secure off, and strict/lax work fine there."""
    assert _settings(COOKIE_SAMESITE=samesite, COOKIE_SECURE=False).COOKIE_SAMESITE == samesite


# --------------------------------------------------------------------------- #
# CORS_ORIGINS — and the trap
# --------------------------------------------------------------------------- #

def test_a_comma_separated_string_is_split_when_passed_as_an_argument():
    built = _settings(CORS_ORIGINS="http://a.example, http://b.example")
    assert built.CORS_ORIGINS == ["http://a.example", "http://b.example"]


def test_a_list_is_taken_as_is():
    origins = ["http://a.example"]
    assert _settings(CORS_ORIGINS=origins).CORS_ORIGINS == origins


def test_the_comma_splitting_validator_is_unreachable_from_an_environment_variable(monkeypatch):
    """THE TRAP, pinned deliberately.

    pydantic-settings JSON-decodes complex (list-typed) fields in
    EnvSettingsSource *before* field validators run. So the comma-splitting
    validator above only ever fires for init-kwargs — from the environment, a
    bare `CORS_ORIGINS=http://a.example` raises at import and the process never
    starts. Deployments must supply a JSON array.

    If a future pydantic-settings makes the bare string work, this test fails,
    and that is the signal to simplify the deployment docs.
    """
    monkeypatch.setenv("CORS_ORIGINS", "http://a.example, http://b.example")
    with pytest.raises(Exception):
        Settings(**REQUIRED)

    monkeypatch.setenv("CORS_ORIGINS", '["http://a.example", "http://b.example"]')
    assert Settings(**REQUIRED).CORS_ORIGINS == ["http://a.example", "http://b.example"]


# --------------------------------------------------------------------------- #
# Defaults that other tests and prod behaviour depend on
# --------------------------------------------------------------------------- #

def test_docs_are_off_by_default():
    """/docs, /redoc, /openapi.json and /scalar all load a CDN-hosted renderer or
    expose the schema, which the privacy policy rules out. Opt-in only."""
    assert _settings().DOCS_ENABLED is False


def test_cookies_are_secure_and_strict_by_default():
    built = _settings()
    assert built.COOKIE_SECURE is True
    assert built.COOKIE_SAMESITE == "strict"
    assert built.REFRESH_COOKIE_PATH == "/auth"


@pytest.mark.parametrize("field", sorted(REQUIRED))
def test_every_required_field_really_is_required(field, monkeypatch):
    """No silent default may creep in: a missing JWT_SECRET must stop the
    process, not fall back to something guessable.

    Both other sources have to be shut off to see this: `_env_file=None` blocks
    backend/.env, and the env var itself is unset because the root conftest puts
    all four into os.environ for the rest of the suite.
    """
    monkeypatch.delenv(field, raising=False)
    incomplete = {k: v for k, v in REQUIRED.items() if k != field}
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **incomplete)


def test_the_live_settings_object_points_at_the_test_database():
    """A cheap tripwire: if this ever names the dev database, the whole suite is
    running against the wrong Postgres."""
    assert settings.DATABASE_URL.rsplit("/", 1)[-1].endswith("_test")
