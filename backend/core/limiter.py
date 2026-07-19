from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.core.config import settings

# key_func = client IP (request.client.host). That host is the REAL client only
# because the single-origin container hands uvicorn a trustworthy X-Forwarded-For:
# nginx's realip module resolves the true client and uvicorn trusts only
# 127.0.0.1, and the backend has no public URL to reach directly. See config.py's
# RATE_LIMIT_* note and docker/nginx.conf.template.
#
# storage_uri: the counter backend. memory:// is per-process (fine for one
# instance / local); prod sets redis:// so limits hold across API instances.
#
# headers_enabled is left off on purpose: turning it on makes slowapi try to
# attach X-RateLimit-* headers to *every* response via a wrapper that requires
# each route to declare a `response: Response` param, which we don't want to
# thread through every endpoint. Instead the 429 handler in main.py computes the
# `Retry-After` seconds itself from the tripped limit's window (see
# rate_limit_exceeded_handler) — that's all the SPA countdown needs.
#
# default_limits: a catch-all applied to EVERY route (once SlowAPIMiddleware is
# added in main.py) so a route that forgets an explicit @limiter.limit still has
# a backstop instead of being wide open. @limiter.limit sets override_defaults,
# so decorated routes keep their own (stricter) tier and this does NOT stack on
# them; /health is exempted in main.py (App Runner's probes would otherwise all
# key on one ingress IP and 429 the health check). Keep it generous: it keys on
# client IP, and users behind one corporate NAT share an IP.
#
# in_memory_fallback_enabled: fail-mode when storage_uri points at Redis and
# ElastiCache blips. Without it, a storage error propagates → HTTP 500 on every
# limited route (a cache blip becomes an auth outage). With it, slowapi marks the
# store dead, transparently falls back to a per-process in-memory counter, and
# auto-probes to flip back when Redis recovers — the site stays UP and limits
# stay enforced (per-instance, so looser across instances, but present).
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.RATE_LIMIT_STORAGE_URI,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    in_memory_fallback_enabled=True,
)
