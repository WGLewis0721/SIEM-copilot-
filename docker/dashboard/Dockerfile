# =============================================================================
# CNAP AI SIEM Copilot — Dashboard Dockerfile
# Lightweight Flask report viewer
# =============================================================================

FROM python:3.11-slim

LABEL org.opencontainers.image.title="CNAP AI SIEM Copilot — Dashboard"
LABEL org.opencontainers.image.description="Read-only security report viewer"

ARG APP_USER=appuser
ARG APP_UID=1000

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid "$APP_UID" "$APP_USER" \
    && useradd --uid "$APP_UID" --gid "$APP_USER" --shell /bin/bash --create-home "$APP_USER"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY templates/ templates/

RUN mkdir -p /app/data/outputs \
    && chown -R "$APP_USER:$APP_USER" /app

USER $APP_USER

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -sf http://localhost:5000/health || exit 1

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "30", "app:app"]
