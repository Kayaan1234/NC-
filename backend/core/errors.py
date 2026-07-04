"""One consistent 429 contract across every throttle in the API.

The SPA (see frontend/src/api/client.ts::parseRetryAfter) reads a cooldown two
ways: a `retry_after` field in the JSON body (always readable) and a
`Retry-After` header (only exposed cross-origin via CORS). slowapi's IP limiter
already emits both (see main.py::rate_limit_exceeded_handler). The per-user
cooldowns (verification resend, email change) used to raise a bare
HTTPException, which produced `{detail}` with NO body `retry_after` — a second,
inconsistent shape. Routing those through CooldownError makes every 429 body
identical: `{detail, retry_after}` plus the `Retry-After` header.
"""

from fastapi import Request
from fastapi.responses import JSONResponse


class CooldownError(Exception):
    """A per-user cooldown rejection, rendered as a 429 whose body matches the
    slowapi limiter's shape. Raise this instead of HTTPException(429) so the
    frontend sees one 429 contract regardless of which throttle fired."""

    def __init__(self, detail: str, retry_after: int) -> None:
        self.detail = detail
        # Clamp to >= 0: a countdown must never be negative even if the window
        # math rounds oddly.
        self.retry_after = max(0, int(retry_after))
        super().__init__(detail)


def cooldown_exception_handler(request: Request, exc: CooldownError) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": exc.detail, "retry_after": exc.retry_after},
        headers={"Retry-After": str(exc.retry_after)},
    )
