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
    # NOTE: get_remote_address reads the socket peer, so behind a reverse proxy
    # every request looks like the proxy IP. In prod, terminate that upstream
    # (WAF/edge limiter) and/or configure trusted X-Forwarded-For handling.
    RATE_LIMIT_EMAIL_SEND: str = "5/hour"
    RATE_LIMIT_AUTH: str = "10/minute"
    RATE_LIMIT_TOKEN: str = "20/minute"

    # Database
    DATABASE_URL: str

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