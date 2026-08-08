"""core/cookies.py — the refresh cookie's attributes.

The load-bearing property is symmetry. `Response.delete_cookie()` only actually
clears a cookie when its path/domain/samesite/secure match how `set_cookie()`
wrote it. If they drift, logout looks like it works — 204, no error anywhere —
and the browser silently keeps the cookie. Nothing else in the suite would catch
that, so the diff test below is the whole point of this file.
"""

from http.cookies import SimpleCookie

import pytest
from fastapi import Response

from backend.core import cookies
from backend.core.config import settings
from backend.core.cookies import clear_refresh_cookie, set_refresh_cookie

RAW_TOKEN = "a-raw-refresh-token-value"


def _attributes(response: Response) -> dict[str, str]:
    """Parse the Set-Cookie header into a normalised attribute dict.

    Needed because httpx's cookie jar drops HttpOnly and SameSite entirely — the
    flags only exist in the raw header.
    """
    header = response.headers["set-cookie"]
    jar = SimpleCookie()
    jar.load(header)
    morsel = jar[settings.REFRESH_COOKIE_NAME]
    attrs = {key: value for key, value in morsel.items() if value != ""}
    # `secure`/`httponly` are valueless flags; SimpleCookie renders them as True.
    attrs["httponly"] = bool(morsel["httponly"])
    attrs["secure"] = bool(morsel["secure"])
    return attrs


def _set() -> Response:
    response = Response()
    set_refresh_cookie(response, RAW_TOKEN)
    return response


def _clear() -> Response:
    response = Response()
    clear_refresh_cookie(response)
    return response


# --------------------------------------------------------------------------- #
# The symmetry check — the reason this module exists
# --------------------------------------------------------------------------- #

SCOPING_ATTRIBUTES = ("path", "domain", "samesite", "secure", "httponly")


@pytest.mark.parametrize("attribute", SCOPING_ATTRIBUTES)
def test_set_and_clear_agree_on_every_scoping_attribute(attribute):
    """If these ever diverge, logout stops clearing the cookie in a real browser
    while every server-side assertion still passes."""
    written = _attributes(_set())
    cleared = _attributes(_clear())
    assert written.get(attribute) == cleared.get(attribute), (
        f"set_refresh_cookie and clear_refresh_cookie disagree on {attribute!r}; "
        "delete_cookie will silently no-op in a browser"
    )


# --------------------------------------------------------------------------- #
# The individual flags
# --------------------------------------------------------------------------- #

def test_the_cookie_carries_the_raw_token_as_its_value():
    jar = SimpleCookie()
    jar.load(_set().headers["set-cookie"])
    assert jar[settings.REFRESH_COOKIE_NAME].value == RAW_TOKEN


def test_the_cookie_is_httponly_so_script_cannot_read_it():
    assert _attributes(_set())["httponly"] is True


def test_the_cookie_is_secure_by_default():
    assert _attributes(_set())["secure"] is True


def test_the_cookie_is_samesite_strict_by_default():
    assert _attributes(_set())["samesite"].lower() == "strict"


def test_the_cookie_is_scoped_to_the_auth_path_only():
    """Path=/auth means the cookie is not sent to /users or /train — the refresh
    token is only ever presented to the endpoints that rotate it."""
    assert _attributes(_set())["path"] == settings.REFRESH_COOKIE_PATH == "/auth"


def test_the_cookie_max_age_matches_the_configured_refresh_lifetime():
    expected = settings.REFRESH_TIMEOUT_DAYS * 24 * 60 * 60
    assert int(_attributes(_set())["max-age"]) == expected


def test_clearing_the_cookie_expires_it_immediately():
    cleared = _attributes(_clear())
    # delete_cookie sets an empty value plus a past/zero expiry.
    assert cleared.get("max-age") in (None, "0") or "expires" in cleared


def test_the_flags_follow_configuration_rather_than_being_hardcoded(monkeypatch):
    """Proves the settings are read at call time, which is what lets a
    localhost-over-http deployment turn Secure off without a code change."""
    monkeypatch.setattr(cookies.settings, "COOKIE_SECURE", False)
    monkeypatch.setattr(cookies.settings, "COOKIE_SAMESITE", "lax")

    attrs = _attributes(_set())
    assert attrs["secure"] is False
    assert attrs["samesite"].lower() == "lax"
