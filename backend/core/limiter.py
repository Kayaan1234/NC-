from slowapi import Limiter
from slowapi.util import get_remote_address

# key_func = client IP. headers_enabled is left off on purpose: turning it on
# makes slowapi try to attach X-RateLimit-* headers to *every* response via a
# wrapper that requires each route to declare a `response: Response` param, which
# we don't want to thread through every endpoint. Instead the 429 handler in
# main.py computes the `Retry-After` seconds itself from the tripped limit's
# window (see rate_limit_exceeded_handler) — that's all the SPA countdown needs.
limiter = Limiter(key_func=get_remote_address)
