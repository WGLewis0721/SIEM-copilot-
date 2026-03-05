#!/usr/bin/env bash
# =============================================================================
# CNAP AI SIEM Copilot — Initialize Knowledge Base
# Uploads sample runbooks and SOPs from knowledge-base/ to S3
# Usage: ./init-knowledge-base.sh [BUCKET_NAME]
# =============================================================================

set -euo pipefail

AWS_REGION="${AWS_REGION:-us-gov-west-1}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
KB_DIR="${REPO_ROOT}/knowledge-base"

# Bucket from argument or environment
BUCKET="${1:-${S3_KNOWLEDGE_BUCKET:-}}"

if [[ -z "$BUCKET" ]]; then
    echo "Usage: $0 BUCKET_NAME"
    echo "   or: S3_KNOWLEDGE_BUCKET=my-bucket $0"
    exit 1
fi

log() { echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] [INIT-KB] $*"; }

log "Uploading knowledge base to s3://${BUCKET}"
log "Source directory: ${KB_DIR}"

UPLOAD_COUNT=0

# Upload all markdown files preserving directory structure
while IFS= read -r -d '' FILE; do
    RELATIVE="${FILE#${KB_DIR}/}"
    S3_KEY="runbooks/${RELATIVE}"

    log "Uploading: ${RELATIVE} → s3://${BUCKET}/${S3_KEY}"
    aws s3 cp "$FILE" "s3://${BUCKET}/${S3_KEY}" \
        --region "$AWS_REGION" \
        --content-type "text/markdown"
    ((UPLOAD_COUNT++))
done < <(find "$KB_DIR" -name "*.md" -not -name "README.md" -print0)

# Also upload any text files
while IFS= read -r -d '' FILE; do
    RELATIVE="${FILE#${KB_DIR}/}"
    S3_KEY="runbooks/${RELATIVE}"

    log "Uploading: ${RELATIVE} → s3://${BUCKET}/${S3_KEY}"
    aws s3 cp "$FILE" "s3://${BUCKET}/${S3_KEY}" \
        --region "$AWS_REGION" \
        --content-type "text/plain"
    ((UPLOAD_COUNT++))
done < <(find "$KB_DIR" -name "*.txt" -print0)

log "Uploaded ${UPLOAD_COUNT} knowledge base documents"
log ""
log "The RAG agent will automatically index these documents on its next run."
log "To trigger immediate indexing, restart the rag-agent container:"
log "  docker compose restart rag-agent"
