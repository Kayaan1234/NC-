#!/bin/sh
# Run pending DB migrations, then start the app (whatever the CMD is).
#
# NOTE (single-instance only): running migrations from the serving entrypoint is
# fine for one container. For multi-replica / zero-downtime, run migrations as a
# dedicated one-off release step BEFORE shifting traffic and drop this line — see
# docs/deployment.md §3.2 / §6.4.
set -e

# DATABASE_URL comes from the environment (compose env_file / cloud env vars),
# read by backend.core.config.settings; env.py puts the repo root on sys.path.
alembic -c backend/alembic.ini upgrade head

exec "$@"
