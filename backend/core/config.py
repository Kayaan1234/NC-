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
    # Finished (succeeded/failed) jobs older than this, measured from finished_at,
    # are deleted automatically by the worker loop (see worker.purge_finished_jobs).
    # Safe to delete outright: job result/stdout are plain DB columns (the
    # container filesystem is ephemeral), so no external artifact is orphaned.
    JOB_RETENTION_DAYS: int = 30
    # How often the worker loop checks whether it's time to run that purge.
    # Deliberately separate from JOB_RETENTION_DAYS: retention answers "how old",
    # this answers "how often to check" — reusing the 30-day value here would mean
    # the sweep might not run again for a month once it does.
    JOB_RETENTION_PURGE_INTERVAL_SECONDS: int = 3600

    # Bridge feasibility engine (bridge-plan-v3.md). Runs on the worker like
    # training; the API only inserts bridge_jobs rows. Off by default for the
    # same reason TRAINING_ENABLED is false in prod until the worker has a home —
    # and additionally because every live run spends real API dollars, so the
    # switch must be a conscious flip, never a default.
    BRIDGE_ENABLED: bool = False
    # Queueing a bridge run costs us money per request (LLM + embeddings), which
    # is a strictly stronger version of the argument that rate-limits /train.
    # Library lookups are free and stay under the generous default limit.
    RATE_LIMIT_BRIDGE: str = "3/hour"
    # Hard per-run spend ceiling, checked BEFORE each paid batch is dispatched —
    # not after — so a topic with an unexpectedly wide candidate pool aborts
    # mid-run instead of surfacing in a bill (bridge-plan-v3.md §14.8).
    BRIDGE_VERDICT_SPEND_CEILING_USD: float = 0.15
    # Global daily cap across ALL users and seed runs. POST /bridge/runs refuses
    # (429) once the day's summed job cost crosses this.
    BRIDGE_DAILY_SPEND_CAP_USD: float = 1.00
    # Overall wall-clock deadline for one live run, checked between pipeline
    # stages. Separate from the heartbeat (liveness) exactly as ModelSpec's
    # timeout is: a run can be alive and still be taking too long.
    BRIDGE_RUN_TIMEOUT_SECONDS: int = 420
    BRIDGE_JOB_POLL_INTERVAL_SECONDS: float = 2.0
    BRIDGE_JOB_HEARTBEAT_SECONDS: int = 10
    # Longer than the training stale window: pipeline stages block on outbound
    # HTTP calls (search, LLM), and a beat only lands between them.
    BRIDGE_JOB_HEARTBEAT_STALE_SECONDS: int = 180
    # How long the OLDEST queued job may sit unclaimed before the API reports the
    # queue as stalled. This is the other half of the liveness story: the stale
    # window above rescues a job that started and went silent, but a job nothing
    # ever claims has no heartbeat to go silent, so only its age tells us the
    # drain is gone. Generous compared with the 2s poll — this should only fire
    # when no worker is running at all.
    BRIDGE_JOB_QUEUE_STALE_SECONDS: int = 300
    # How many scout searches run concurrently during fan-out.
    BRIDGE_SCOUT_CONCURRENCY: int = 4
    # Ceiling on how many candidates get relevance-judged in one run. This is
    # the pipeline's dominant cost: judging is one paid call per candidate and
    # the candidate's card text is the bulk of the tokens, so it scales linearly
    # with pool size (two scouts on a popular topic return 60-70). Candidates
    # are sorted by downloads first, so the cap drops the long tail of obscure
    # repos rather than an arbitrary slice. Raising this raises cost per verdict
    # roughly proportionally.
    BRIDGE_MAX_JUDGED_CANDIDATES: int = 40

    # Bridge API keys. All optional so the WEB container boots without them
    # (they are worker concerns); check_bridge_registry refuses to boot with
    # BRIDGE_ENABLED=true if a required one is missing.
    ANTHROPIC_API_KEY: str | None = None
    # Voyage AI embeddings. Named VOYAGER_ (not the SDK's VOYAGE_) to match the
    # key already provisioned in backend/.env; the client is constructed with an
    # explicit api_key from here, so the SDK's own env lookup never runs.
    VOYAGER_API_KEY: str | None = None
    # Langfuse observability (cloud.langfuse.com). Optional on purpose: tracing
    # no-ops cleanly when unset, so a missing account never blocks a run.
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"
    # Kaggle dataset search requires an authenticated token; the Kaggle scout
    # activates only when both are set and skips gracefully otherwise.
    KAGGLE_USERNAME: str | None = None
    KAGGLE_KEY: str | None = None

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
    # Dead-lettered (retries exhausted) outbox rows older than this are deleted by
    # the email drain loop (see email_drain.purge_dead). Aged off created_at, not
    # a dedicated "went dead" timestamp — there isn't one, and dead-lettering only
    # happens after EMAIL_OUTBOX_MAX_ATTEMPTS exhausts its backoff, which is well
    # under an hour with the settings above, negligible against a 30-day window.
    EMAIL_OUTBOX_RETENTION_DAYS: int = 30
    EMAIL_OUTBOX_RETENTION_PURGE_INTERVAL_SECONDS: int = 3600

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

    # Interactive API docs (/scalar, /docs, /redoc, /openapi.json).
    #
    # Off by default, which is the opposite of FastAPI's default and deliberate:
    # forgetting to disable them in prod is the failure mode, not forgetting to
    # enable them in dev. Two reasons they must stay off on a public deployment:
    #   1. All three renderers load their JavaScript from a third-party CDN
    #      (scalar_fastapi defaults to cdn.jsdelivr.net). The privacy policy tells
    #      users there are no third-party scripts, and the nginx CSP allows only
    #      our own origin — so the page would be both a broken promise and a
    #      blocked request.
    #   2. It publishes the full API surface, including every auth and
    #      rate-limited endpoint, to anyone who guesses the path.
    # Turn it on locally with DOCS_ENABLED=true in backend/.env.
    DOCS_ENABLED: bool = False

    # extra="ignore": backend/.env may hold keys no Settings field declares yet
    # (e.g. a provider key stashed before its feature lands). The pydantic
    # default is to refuse to boot on them, which turns "added a key to .env"
    # into a crashed container — ignoring unknown entries is the right failure
    # mode for a human-edited file. The cost is that a typo'd setting name is
    # silently ignored rather than flagged.
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

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