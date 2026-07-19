#!/bin/bash
# Entrypoint for the single-origin `web` container: migrate, then run uvicorn
# (localhost) and nginx (front) together as ONE App Runner service.
#
# If EITHER process exits, tear the other down and exit non-zero so the platform
# recycles the container — no "nginx up, API dead" zombie. SIGTERM is forwarded
# to both so uvicorn shuts down gracefully on a deploy/scale-in.
#
# NOTE (single-instance migration): `alembic upgrade head` here is fine for one
# instance. For multi-replica zero-downtime, run migrations as a one-off release
# step and drop this line — see DEPLOYMENT_AUDIT_DELTA.md D5.

alembic -c backend/alembic.ini upgrade head || exit 1

# Render the server block with the platform-provided PORT (App Runner injects
# it). Only $PORT is substituted; nginx's own $remote_addr/$host/... are left.
export PORT="${PORT:-8080}"
envsubst '$PORT' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf

# uvicorn bound to localhost ONLY: nginx is the sole front door, and uvicorn
# trusts X-Forwarded-For only from 127.0.0.1 (nginx), so no external caller can
# forge the client IP the rate limiter keys on.
uvicorn backend.main:app --host 127.0.0.1 --port 8000 \
    --proxy-headers --forwarded-allow-ips=127.0.0.1 &
UVICORN_PID=$!

nginx -g 'daemon off;' &
NGINX_PID=$!

# Forward termination to both children, then reap.
trap 'kill -TERM "$UVICORN_PID" "$NGINX_PID" 2>/dev/null' TERM INT

# Wake as soon as EITHER exits (crash or shutdown)...
wait -n "$UVICORN_PID" "$NGINX_PID"
EXIT=$?
# ...then stop the other and wait for it to finish before exiting.
kill -TERM "$UVICORN_PID" "$NGINX_PID" 2>/dev/null || true
wait
exit "$EXIT"
