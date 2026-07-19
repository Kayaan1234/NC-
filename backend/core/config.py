from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/


class Settings(BaseSettings):
    # Auth
    JWT_SECRET: str
    JWT_ALGORITHM: str
    TIMEOUT_MINUTES: int = 30
    REFRESH_TIMEOUT_DAYS: int = 7
    VERIFICATION_TTL_HOURS: int = 24
    RESET_TTL_HOURS: int = 1
    # Per-user throttle on (re)issuing verification emails. Keyed on user_id so
    # it survives email/password changes.
    VERIFICATION_RESEND_COOLDOWN_MINUTES: int = 10
    # Per-user throttle on (re)issuing password-reset emails. Unlike the
    # verification cooldown this trips as a *silent no-op* (the request has
    # already returned by the time it's checked), so it caps inbox flooding of a
    # registered address without leaking whether that address exists. Keyed on
    # user_id.
    RESET_RESEND_COOLDOWN_MINUTES: int = 10
    # Separate, stricter throttle on actually *changing* the email address.
    EMAIL_CHANGE_COOLDOWN_HOURS: int = 24

    # Refresh-token cookie. The refresh token is delivered ONLY as an httpOnly
    # cookie (never in a JSON body), so page JS can't read it and an XSS bug
    # can't exfiltrate it. Set/cleared through core/cookies.py so every call site
    # uses identical attributes (delete_cookie only clears when they match).
    #   - COOKIE_SECURE: cookie only sent over HTTPS. Keep True in prod. Modern
    #     browsers treat localhost/127.0.0.1 as secure contexts, so True also
    #     works over http in dev — don't weaken it for local testing.
    #   - COOKIE_SAMESITE: "strict" is correct whenever the SPA and API share a
    #     registrable domain (e.g. app.x.com + api.x.com — cross-origin but
    #     same-site; CORS handles the origin part). Only drop to "none" if the
    #     API lives on a *different* registrable domain than the SPA, and then
    #     you MUST add CSRF protection — SameSite no longer shields /auth/refresh
    #     and /auth/logout once the cookie rides cross-site requests.
    #   - COOKIE_DOMAIN: None => host-only cookie (most restrictive). Set an
    #     explicit parent domain only to deliberately share across subdomains.
    #   - Scoped to REFRESH_COOKIE_PATH (/auth) so only refresh + logout ever
    #     receive it, not the rest of the API.
    COOKIE_SECURE: bool = True
    COOKIE_SAMESITE: Literal["strict", "lax", "none"] = "strict"
    COOKIE_DOMAIN: str | None = None
    REFRESH_COOKIE_NAME: str = "refresh_token"
    REFRESH_COOKIE_PATH: str = "/auth"

    # slowapi IP-based rate limits (see core/limiter.py), tiered by sensitivity:
    #   _EMAIL_SEND: routes that fire an outbound email to a caller-influenced
    #                address (register, forgot-password, resend, email change).
    #                Primary defense against using us as a mail-spam relay.
    #   _AUTH:       credential submission (login) — bcrypt DoS + credential
    #                stuffing.
    #   _TOKEN:      token-bearing endpoints (verify, reset, validate).
    #   _TRAIN:      queueing a training job — each one spawns a real process,
    #                so this caps how much compute one IP can enqueue.
    # These key on the client IP (get_remote_address). That IP is only trustworthy
    # because the single-origin container derives it via nginx's realip module and
    # uvicorn trusts ONLY 127.0.0.1 (--forwarded-allow-ips=127.0.0.1) — the backend
    # has no public URL, so a caller can't reach uvicorn directly to forge XFF. See
    # docker/nginx.conf.template and DEPLOYMENT_AUDIT_DELTA.md D2.
    RATE_LIMIT_EMAIL_SEND: str = "5/hour"
    RATE_LIMIT_AUTH: str = "10/minute"
    RATE_LIMIT_TOKEN: str = "20/minute"
    RATE_LIMIT_TRAIN: str = "20/hour"
    #   _DEFAULT:    catch-all backstop applied to every route via
    #                SlowAPIMiddleware (see core/limiter.py), so an undecorated
    #                route (e.g. /refresh, /logout, a future endpoint) is never
    #                wide open. /health is exempted. Kept generous because it keys
    #                on client IP and users behind one corporate NAT share an IP.
    RATE_LIMIT_DEFAULT: str = "120/minute"
    # slowapi counter storage. Default in-memory is per-process, so with more than
    # one API instance every limit is effectively N× looser. Point this at Redis
    # (redis://host:6379) in prod so the counters are shared across instances. The
    # `limits` backend for a scheme is imported lazily, so memory:// needs no redis
    # package. See core/limiter.py.
    RATE_LIMIT_STORAGE_URI: str = "memory://"

    # Training jobs.
    # Jobs are executed by a separate worker process (`python -m backend.worker`),
    # never inside the API — App Runner throttles container CPU whenever no
    # request is in flight, so work started after a response returns would be
    # starved, and instance recycling would kill it regardless. Until that worker
    # has a home in prod, keep TRAINING_ENABLED=false there: POST would otherwise
    # queue jobs that nothing ever drains.
    TRAINING_ENABLED: bool = True
    JOB_POLL_INTERVAL_SECONDS: float = 1.0
    JOB_HEARTBEAT_SECONDS: int = 10
    # How long a RUNNING job may go without a heartbeat before the worker treats
    # it as abandoned and fails it, freeing that user's one active slot.
    #
    # INVARIANT: this is a multiple of JOB_HEARTBEAT_SECONDS, and must stay
    # comfortably above it so a slow tick can't kill a healthy job. It is
    # deliberately INDEPENDENT of how long a job runs — liveness is proven by the
    # heartbeat, not by elapsed time. A 20-minute job beating every 10s is
    # healthy; a 20-second job silent for 90s is dead. Do not tie this to
    # ModelSpec.timeout_seconds.
    JOB_HEARTBEAT_STALE_SECONDS: int = 90

    # Email outbox. Transactional emails are written to the email_outbox table in
    # the same transaction as the change that triggers them, and delivered by a
    # drain loop running on a thread inside the worker process (see
    # backend.services.email_drain). This is durable where a FastAPI
    # BackgroundTask is not: an App Runner instance recycled between response and
    # send would silently drop the email — most damagingly a signup verification.
    EMAIL_OUTBOX_POLL_SECONDS: float = 2.0
    # Give up after this many failed delivery attempts and mark the row `dead`.
    EMAIL_OUTBOX_MAX_ATTEMPTS: int = 6
    # Exponential backoff between attempts: min(BASE * 2**(attempts-1), CAP).
    EMAIL_OUTBOX_BACKOFF_BASE_SECONDS: int = 30
    EMAIL_OUTBOX_BACKOFF_CAP_SECONDS: int = 3600
    # A row left `sending` longer than this (its drainer died mid-delivery) is
    # swept back to `queued`. Must exceed a realistic Resend call + retry latency.
    EMAIL_OUTBOX_CLAIM_STALE_SECONDS: int = 300

    # Database
    DATABASE_URL: str
    # SQLAlchemy connection pool, per process. Applied only on Postgres (SQLite
    # uses its own pool class and rejects these). Sized so autoscaled API
    # instances plus the worker stay within the RDS max_connections budget:
    # each process holds up to DB_POOL_SIZE + DB_MAX_OVERFLOW connections.
    # DB_POOL_RECYCLE_SECONDS drops connections older than the window so RDS's
    # idle reaping / failovers don't leave stale ones checked into the pool.
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5
    DB_POOL_RECYCLE_SECONDS: int = 1800

    # Skip re-writing users.last_used on activity (login/refresh) if the stored
    # value is newer than this. Refresh fires ~every access-token TTL per active
    # user; without the throttle that's a users-row write per refresh. See
    # core/activity.touch_activity.
    ACTIVITY_WRITE_THROTTLE_MINUTES: int = 5

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # Email
    RESEND_API_KEY: str
    EMAIL_FROM: str = "noreply@ncplusplus.com"

    # Frontend
    FRONTEND_URL: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8")

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def split_cors_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @model_validator(mode="after")
    def _samesite_none_requires_secure(self) -> "Settings":
        # Browsers silently drop a `SameSite=None` cookie that isn't also
        # `Secure`, which would leave refresh totally broken with no error.
        if self.COOKIE_SAMESITE == "none" and not self.COOKIE_SECURE:
            raise ValueError(
                "COOKIE_SAMESITE='none' requires COOKIE_SECURE=True "
                "(browsers reject SameSite=None cookies without Secure)."
            )
        return self


settings = Settings()