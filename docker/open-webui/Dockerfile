# =============================================================================
# CNAP AI SIEM Copilot — Open WebUI Custom Dockerfile
# Extends the official Open WebUI image with boto3 and opensearch-py
# for AWS IAM authentication in custom filter functions
# =============================================================================

FROM ghcr.io/open-webui/open-webui:main

LABEL org.opencontainers.image.title="CNAP AI SIEM Copilot — Open WebUI"
LABEL org.opencontainers.image.description="Open WebUI with OpenSearch integration for security log analysis"

# Install additional Python packages needed by custom filter functions
COPY requirements.txt /tmp/webui-extra-requirements.txt
RUN pip install --no-cache-dir -r /tmp/webui-extra-requirements.txt \
    && rm /tmp/webui-extra-requirements.txt

# Copy custom filter functions to a directory the Open WebUI can access
COPY functions/ /app/backend/open_webui/functions/custom/

# Create directories for outputs
RUN mkdir -p /app/backend/data/outputs

EXPOSE 8080
