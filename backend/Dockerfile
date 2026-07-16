# Backend image for NC++ (FastAPI + uvicorn).
# Build context is the REPO ROOT so the `backend` package copies whole and its
# `from backend....` imports resolve (same reason alembic/env.py puts the repo
# root on sys.path):  docker build -f backend/Dockerfile -t ncplusplus-backend .

# ---- deps: install into a venv we can copy (keeps build tools out of runtime)

# this installs a slim Python 3.11 image, creates a virtual environment, and installs the dependencies from requirements.lock.txt into that venv. The venv is then copied into the runtime image, which is also based on python:3.11-slim, but without the build tools and cache.

FROM python:3.11-slim AS deps
# create a virtual environment and install dependencies
ENV PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY backend/requirements.lock.txt .
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip \
 && /opt/venv/bin/pip install -r requirements.lock.txt

# ---- ccbuild: compile the Step0 training binary FOR LINUX.
# The worker (`python -m backend.worker`) shells out to this binary via
# services/runner.py. The committed `nn` is a macOS build that can't run in the
# container (and .dockerignore keeps it out of the context), so the image builds
# its own. gcc:13 is bookworm-based, matching the python:3.11-slim runtime, and
# -static-libstdc++/-static-libgcc drop the C++ runtime deps so the binary runs
# on the slim image whether or not libstdc++6 happens to be installed there.
# Flags otherwise mirror services/Step0/Makefile (C++17 is required).
FROM gcc:13-bookworm AS ccbuild
WORKDIR /build
COPY backend/services/Step0/ ./Step0/
RUN cd Step0 && g++ -std=c++17 -O2 -Wall -Wextra -static-libstdc++ -static-libgcc -o nn main.cpp

# ---- runtime: slim image, non-root, migrate-then-serve
FROM python:3.11-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /app
COPY --from=deps /opt/venv /opt/venv
COPY backend ./backend
# Drop the freshly compiled Linux training binary in over the source tree (the
# macOS one was excluded from the context). Same image serves the API and the
# worker; only the worker runs it, but it lives in the one shared image.
COPY --from=ccbuild /build/Step0/nn ./backend/services/Step0/nn
# Alembic migrations are run in the entrypoint, so copy the migration scripts too, entry point needs them to run migrations before starting the server.
COPY docker/backend-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh \
 && adduser --disabled-password --gecos "" appuser \
 && chown -R appuser /app
USER appuser
EXPOSE 8000
# Entrypoint runs Alembic migrations, then hands off to the CMD (uvicorn).
ENTRYPOINT ["/entrypoint.sh"]
# --proxy-headers + --forwarded-allow-ips: behind nginx/an LB, trust
# X-Forwarded-Proto so the Secure cookie is set and the real client scheme/IP
# are seen. On Cloud Run, pass `--port 8000` to the deploy (it routes to PORT).
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
