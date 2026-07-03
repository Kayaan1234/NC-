"""Single source of truth for the refresh-token cookie.

login() and refresh() both mint a refresh token and hand it to the client as an
httpOnly cookie; logout() clears it. Routing every set/clear through these two
helpers keeps the cookie's attributes identical across all three call sites,
which is load-bearing: Response.delete_cookie() only actually clears a cookie
when its path/domain/samesite/secure match how set_cookie() wrote it. If those
drift, logout looks like it works but silently leaves the cookie in place.
"""

from fastapi import Response

from backend.core.config import settings


def set_refresh_cookie(response: Response, raw_token: str) -> None:
    """Attach the refresh token as an httpOnly cookie (see module docstring)."""
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=raw_token,
        max_age=settings.REFRESH_TIMEOUT_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        path=settings.REFRESH_COOKIE_PATH,
    )


def clear_refresh_cookie(response: Response) -> None:
    """Expire the refresh cookie. Attributes mirror set_refresh_cookie() so the
    browser actually drops it (see module docstring)."""
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN,
        path=settings.REFRESH_COOKIE_PATH,
    )
