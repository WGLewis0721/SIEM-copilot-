# =============================================================================
# CNAP AI SIEM Copilot — RAG Agent Dockerfile
# Python 3.11-slim, minimal footprint, non-root user
# =============================================================================

FROM python:3.11-slim

# Metadata
LABEL org.opencontainers.image.title="CNAP AI SIEM Copilot — RAG Agent"
LABEL org.opencontainers.image.description="Automated security log analysis with RAG"
LABEL org.opencontainers.image.source="https://github.com/your-org/cnap-ai-siem-copilot"

# Build arguments
ARG APP_USER=appuser
ARG APP_UID=1000

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root application user
RUN groupadd --gid "$APP_UID" "$APP_USER" \
    && useradd --uid "$APP_UID" --gid "$APP_USER" --shell /bin/bash --create-home "$APP_USER"

WORKDIR /app

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py ./
COPY *.yaml ./
COPY prompts/ ./prompts/ 2>/dev/null || true

# Create output directory with correct ownership
RUN mkdir -p /app/output /tmp/knowledge-cache \
    && chown -R "$APP_USER:$APP_USER" /app /tmp/knowledge-cache

# Drop to non-root user
USER $APP_USER

# Health check — verify output directory is writable
HEALTHCHECK --interval=60s --timeout=10s --start-period=120s --retries=3 \
    CMD python -c "import os; f=open('/app/output/.healthcheck','w'); f.write('ok'); f.close()" || exit 1

ENTRYPOINT ["python", "main.py"]
