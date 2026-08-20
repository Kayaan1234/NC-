# Single-origin image for NC++. ONE Dockerfile, TWO targets from shared stages:
#   --target web    -> App Runner: nginx (front) + uvicorn (127.0.0.1) + the SPA
#                      in ONE container, so the backend has no public URL and the
#                      client IP the rate limiter keys on cannot be forged.
#   --target worker -> Fargate: python + the training binaries only; runs the
#                      claim loop (training jobs + the email-outbox drain thread).
#                      Needs >= 1GB RAM — a Step1 MNIST run peaks near 500MB.
# Build context is the REPO ROOT (needs backend/ AND frontend/ AND docker/):
#   docker build --target web    -t ncplusplus-web .
#   docker build --target worker -t ncplusplus-worker .

# ---- build the SPA bundle. VITE_API_URL is baked in HERE, at BUILD time.
FROM node:22-alpine AS build
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
# "" => the SPA calls /auth, /users, ... on its OWN origin (same-origin nginx).
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# ---- python deps into a copyable venv (keeps build tools out of runtime)
FROM python:3.11-slim AS deps-base
ENV PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY backend/requirements.lock.txt .
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip \
 && /opt/venv/bin/pip install -r requirements.lock.txt

# ---- worker-only extras (bridge feasibility engine): numpy/scikit-learn/
# anthropic/voyageai/langfuse/huggingface_hub/kagglehub. A SEPARATE venv, not
# layered onto deps-base's, so `web` never inherits this weight. See
# bridge-plan-v3.md §11: "adding scikit-learn bloats the web image too."
FROM python:3.11-slim AS deps-worker
ENV PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY backend/requirements-worker.lock.txt .
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip \
 && /opt/venv/bin/pip install -r requirements-worker.lock.txt

# ---- compile the training binaries FOR LINUX (the worker shells out to them).
# gcc:13 is bookworm-based, matching python:3.11-slim; -static-libstdc++/-libgcc
# drop the C++ runtime deps so they run on the slim image. Mirrors each Makefile.
# One stage per rung's compile, one line each — see ADDING_A_MODEL.md.
FROM gcc:13-bookworm AS ccbuild
WORKDIR /build
COPY backend/services/Step0/ ./Step0/
RUN cd Step0 && g++ -std=c++17 -O2 -Wall -Wextra -static-libstdc++ -static-libgcc -o nn main.cpp
# Sources only: Step1 ships 53MB of MNIST idx files, and there is no reason to
# drag them through the compiler stage (the runtime gets them from `COPY backend`).
COPY backend/services/Step1/*.cpp backend/services/Step1/*.hpp ./Step1/
RUN cd Step1 && g++ -std=c++17 -O2 -Wall -Wextra -static-libstdc++ -static-libgcc -o nn main.cpp

# ---- common runtime base: backend package + Linux training binaries, non-root.
# Deliberately does NOT copy a venv — `web` and `worker` each pull their own
# (deps-base vs deps-worker) below, so the split actually lands in the image.
FROM python:3.11-slim AS runtime-base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /app
# Carries Step1's MNIST idx files (~53MB) as well as the Python package. The
# `web` target doesn't need them but inherits this layer; accepted over splitting
# the copy, since only the worker image is on a hot deploy path.
COPY backend ./backend
# Drop the freshly compiled Linux binaries in over the source tree (the committed
# macOS ones are kept out of the build context by .dockerignore).
COPY --from=ccbuild /build/Step0/nn ./backend/services/Step0/nn
COPY --from=ccbuild /build/Step1/nn ./backend/services/Step1/nn
RUN adduser --disabled-password --gecos "" appuser && chown -R appuser /app

# ---- worker: the claim loop (Fargate). No nginx, no SPA — stays lean.
FROM runtime-base AS worker
COPY --from=deps-worker /opt/venv /opt/venv
USER appuser
# The `web` container runs migrations; the worker just drains (compose/prod order
# the worker to start after the web service is healthy).
CMD ["python", "-m", "backend.worker"]

# ---- web: nginx (front) + uvicorn (localhost) + SPA (App Runner entry point)
FROM runtime-base AS web
COPY --from=deps-base /opt/venv /opt/venv
# nginx + envsubst (gettext-base for rendering the server block's $PORT).
USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends nginx gettext-base \
 && rm -rf /var/lib/apt/lists/*
COPY --from=build /app/dist /usr/share/nginx/html
COPY docker/nginx.conf /etc/nginx/nginx.conf
COPY docker/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY docker/web-entrypoint.sh /web-entrypoint.sh
# Make every path the non-root user writes (rendered conf, nginx pid/temp are in
# /tmp already; log/lib dirs, static root, conf.d) owned by appuser.
RUN chmod +x /web-entrypoint.sh \
 && mkdir -p /etc/nginx/conf.d \
 && chown -R appuser /usr/share/nginx/html /etc/nginx/conf.d /var/log/nginx /var/lib/nginx
USER appuser
# App Runner injects PORT; nginx listens on it, uvicorn stays on 127.0.0.1:8000.
ENV PORT=8080
EXPOSE 8080
ENTRYPOINT ["/web-entrypoint.sh"]
