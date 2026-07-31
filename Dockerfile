# ── Build stage ───────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.11-slim

LABEL maintainer="hpa-testing"
LABEL description="Flask load-testing app for Kubernetes HPA experiments"

# Non-root user for security
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY app/ ./app/
COPY run.py .

# SQLite DB directory (will be overridden by a volume in K8s if needed)
RUN mkdir -p /data && chown -R appuser:appgroup /app /data

USER appuser

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_URL=sqlite:////data/app.db \
    SECRET_KEY=change-me-in-production \
    PORT=5000

EXPOSE 5000

# Gunicorn: 4 sync workers + gevent for slow endpoints
# Workers = 2 × CPU + 1 → override via K8s env GUNICORN_WORKERS
CMD gunicorn \
    --bind 0.0.0.0:${PORT} \
    --workers ${GUNICORN_WORKERS:-4} \
    --worker-class sync \
    --timeout 30 \
    --keep-alive 5 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    "run:app"
