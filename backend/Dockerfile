# Backend image for NC++ (FastAPI + uvicorn).
# Build context is the REPO ROOT so the `backend` package copies whole and its
# `from backend....` imports resolve (same reason alembic/env.py puts the repo
# root on sys.path):  docker build -f backend/Dockerfile -t ncplusplus-backend .

# ---- deps: install into a venv we can copy (keeps build tools out of runtime)
FROM python:3.11-slim AS deps
ENV PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY backend/requirements.lock.txt .
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip \
 && /opt/venv/bin/pip install -r requirements.lock.txt

# ---- runtime: slim image, non-root, migrate-then-serve
FROM python:3.11-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /app
COPY --from=deps /opt/venv /opt/venv
COPY backend ./backend
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
