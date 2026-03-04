#!/usr/bin/env bash
# =============================================================================
# CNAP AI SIEM Copilot — Backup Script
# Backs up Open WebUI data and RAG reports to S3
# Usage: ./backup.sh [--bucket BUCKET_NAME] [--region REGION]
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration (override with flags or environment variables)
# ---------------------------------------------------------------------------
BACKUP_BUCKET="${S3_BACKUP_BUCKET:-}"
AWS_REGION="${AWS_REGION:-us-gov-west-1}"
DOCKER_COMPOSE_DIR="${DOCKER_COMPOSE_DIR:-/opt/cnap-siem/docker}"
TIMESTAMP=$(date -u +"%Y%m%d_%H%M%S")
BACKUP_PREFIX="backups/${TIMESTAMP}"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case $1 in
        --bucket) BACKUP_BUCKET="$2"; shift 2 ;;
        --region) AWS_REGION="$2"; shift 2 ;;
        *) echo "Unknown argument: $1"; exit 1 ;;
    esac
done

# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------
if [[ -z "$BACKUP_BUCKET" ]]; then
    echo "ERROR: S3_BACKUP_BUCKET environment variable or --bucket flag required"
    exit 1
fi

log() { echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] [BACKUP] $*"; }

log "Starting backup to s3://${BACKUP_BUCKET}/${BACKUP_PREFIX}"

# ---------------------------------------------------------------------------
# Backup Open WebUI data volume
# ---------------------------------------------------------------------------
log "Backing up Open WebUI data..."
TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

docker run --rm \
    -v openwebui-data:/data:ro \
    -v "$TMPDIR":/backup \
    alpine:latest \
    tar czf /backup/openwebui-data.tar.gz -C /data .

aws s3 cp \
    "$TMPDIR/openwebui-data.tar.gz" \
    "s3://${BACKUP_BUCKET}/${BACKUP_PREFIX}/openwebui-data.tar.gz" \
    --region "$AWS_REGION"

log "Open WebUI data backed up"

# ---------------------------------------------------------------------------
# Backup RAG analysis reports
# ---------------------------------------------------------------------------
log "Backing up RAG reports..."
docker run --rm \
    -v rag-output:/data:ro \
    -v "$TMPDIR":/backup \
    alpine:latest \
    tar czf /backup/rag-reports.tar.gz -C /data .

aws s3 cp \
    "$TMPDIR/rag-reports.tar.gz" \
    "s3://${BACKUP_BUCKET}/${BACKUP_PREFIX}/rag-reports.tar.gz" \
    --region "$AWS_REGION"

log "RAG reports backed up"

# ---------------------------------------------------------------------------
# Save Docker Compose configuration (minus secrets)
# ---------------------------------------------------------------------------
if [[ -f "${DOCKER_COMPOSE_DIR}/docker-compose.yml" ]]; then
    log "Backing up Docker Compose configuration..."
    aws s3 cp \
        "${DOCKER_COMPOSE_DIR}/docker-compose.yml" \
        "s3://${BACKUP_BUCKET}/${BACKUP_PREFIX}/docker-compose.yml" \
        --region "$AWS_REGION"
fi

# ---------------------------------------------------------------------------
# Write backup manifest
# ---------------------------------------------------------------------------
MANIFEST_FILE="$TMPDIR/manifest.json"
cat > "$MANIFEST_FILE" <<EOF
{
  "backup_timestamp": "${TIMESTAMP}",
  "backup_prefix": "${BACKUP_PREFIX}",
  "aws_region": "${AWS_REGION}",
  "contents": [
    "openwebui-data.tar.gz",
    "rag-reports.tar.gz",
    "docker-compose.yml"
  ]
}
EOF

aws s3 cp \
    "$MANIFEST_FILE" \
    "s3://${BACKUP_BUCKET}/${BACKUP_PREFIX}/manifest.json" \
    --region "$AWS_REGION"

log "Backup complete: s3://${BACKUP_BUCKET}/${BACKUP_PREFIX}"
