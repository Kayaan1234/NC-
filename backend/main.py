import time

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from scalar_fastapi import get_scalar_api_reference
from backend.routers.auth import router as auth_router
from backend.routers.users import router as user_router
from backend.routers.train import router as train_router


from backend.core.config import settings

from backend.core.limiter import limiter
from backend.core.errors import CooldownError, cooldown_exception_handler
from slowapi.errors import RateLimitExceeded


def _retry_after_seconds(request: Request) -> int | None:
    """Seconds until the tripped limit's window resets, or None if unknown.

    slowapi stashes the limit that fired on request.state.view_rate_limit as
    (RateLimitItem, [keys]); its window stats give the reset epoch, and we
    subtract now. Mirrors slowapi's own header math (reset_in = 1 + reset_ts)."""
    view_limit = getattr(request.state, "view_rate_limit", None)
    if not view_limit:
        return None
    item, keys = view_limit
    reset_ts, _remaining = limiter.limiter.get_window_stats(item, *keys)
    return max(0, int(reset_ts - time.time()) + 1)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """429 handler for slowapi. Puts the message under `detail` (what the SPA's
    ApiError reads, unlike slowapi's default `error` key) and attaches an
    integer-seconds `Retry-After` header — mirrored into the body as
    `retry_after` so the SPA can drive an exact cooldown countdown even if the
    header gets stripped somewhere in transit."""
    retry_after = _retry_after_seconds(request)
    body: dict[str, object] = {"detail": "Too many requests. Please wait and try again."}
    headers: dict[str, str] = {}
    if retry_after is not None:
        body["retry_after"] = retry_after
        headers["Retry-After"] = str(retry_after)
    return JSONResponse(status_code=429, content=body, headers=headers)


app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
# Per-user cooldowns share the slowapi 429 body shape via this handler.
app.add_exception_handler(CooldownError, cooldown_exception_handler)
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(train_router)



app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Retry-After isn't a CORS-safelisted response header, so the browser hides
    # it from JS unless we opt it in here — the SPA needs it to time the 429
    # cooldown countdown.
    expose_headers=["Retry-After"],)


@app.get("/health", tags=["Health"])
def health():
    """Liveness probe for load balancers / orchestrators."""
    return {"status": "ok"}


@app.get("/scalar")
def get_scalar_docs():
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title = "Scalar API",
    )

    