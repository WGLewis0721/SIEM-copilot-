#!/usr/bin/env bash
# =============================================================================
# CNAP AI SIEM Copilot — Restore Script
# Restores Open WebUI data and RAG reports from S3 backup
# Usage: ./restore.sh --bucket BUCKET [--date YYYYMMDD] [--latest]
# =============================================================================

set -euo pipefail

BACKUP_BUCKET="${S3_BACKUP_BUCKET:-}"
AWS_REGION="${AWS_REGION:-us-gov-west-1}"
TARGET_DATE=""
USE_LATEST=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --bucket) BACKUP_BUCKET="$2"; shift 2 ;;
        --region) AWS_REGION="$2"; shift 2 ;;
        --date)   TARGET_DATE="$2"; shift 2 ;;
        --latest) USE_LATEST=true; shift ;;
        *) echo "Unknown argument: $1"; exit 1 ;;
    esac
done

if [[ -z "$BACKUP_BUCKET" ]]; then
    echo "ERROR: S3_BACKUP_BUCKET environment variable or --bucket flag required"
    exit 1
fi

log() { echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] [RESTORE] $*"; }

# ---------------------------------------------------------------------------
# Find backup to restore
# ---------------------------------------------------------------------------
if [[ "$USE_LATEST" == "true" ]]; then
    log "Finding latest backup..."
    BACKUP_PREFIX=$(aws s3 ls "s3://${BACKUP_BUCKET}/backups/" \
        --region "$AWS_REGION" \
        | awk '{print $2}' \
        | sort -r \
        | head -1 \
        | tr -d '/')
    BACKUP_PREFIX="backups/${BACKUP_PREFIX}"
elif [[ -n "$TARGET_DATE" ]]; then
    log "Finding backup for date: ${TARGET_DATE}"
    BACKUP_PREFIX=$(aws s3 ls "s3://${BACKUP_BUCKET}/backups/" \
        --region "$AWS_REGION" \
        | grep "$TARGET_DATE" \
        | awk '{print $2}' \
        | sort -r \
        | head -1 \
        | tr -d '/')
    BACKUP_PREFIX="backups/${BACKUP_PREFIX}"
else
    echo "ERROR: Specify --latest or --date YYYYMMDD"
    exit 1
fi

if [[ -z "${BACKUP_PREFIX}" || "${BACKUP_PREFIX}" == "backups/" ]]; then
    echo "ERROR: No backup found matching criteria"
    exit 1
fi

log "Restoring from: s3://${BACKUP_BUCKET}/${BACKUP_PREFIX}"

# ---------------------------------------------------------------------------
# Confirm before destructive operation
# ---------------------------------------------------------------------------
read -rp "This will OVERWRITE existing data. Continue? (yes/no): " CONFIRM
if [[ "$CONFIRM" != "yes" ]]; then
    log "Restore cancelled"
    exit 0
fi

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

# ---------------------------------------------------------------------------
# Restore Open WebUI data
# ---------------------------------------------------------------------------
log "Restoring Open WebUI data..."
aws s3 cp \
    "s3://${BACKUP_BUCKET}/${BACKUP_PREFIX}/openwebui-data.tar.gz" \
    "$TMPDIR/openwebui-data.tar.gz" \
    --region "$AWS_REGION"

# Stop Open WebUI container before restore
docker compose -f /opt/cnap-siem/docker/docker-compose.yml stop open-webui 2>/dev/null || true

docker run --rm \
    -v openwebui-data:/data \
    -v "$TMPDIR":/backup \
    alpine:latest \
    sh -c "rm -rf /data/* && tar xzf /backup/openwebui-data.tar.gz -C /data"

log "Open WebUI data restored"

# ---------------------------------------------------------------------------
# Restore RAG reports
# ---------------------------------------------------------------------------
log "Restoring RAG reports..."
aws s3 cp \
    "s3://${BACKUP_BUCKET}/${BACKUP_PREFIX}/rag-reports.tar.gz" \
    "$TMPDIR/rag-reports.tar.gz" \
    --region "$AWS_REGION"

docker run --rm \
    -v rag-output:/data \
    -v "$TMPDIR":/backup \
    alpine:latest \
    sh -c "tar xzf /backup/rag-reports.tar.gz -C /data"

log "RAG reports restored"

# ---------------------------------------------------------------------------
# Restart services
# ---------------------------------------------------------------------------
log "Restarting services..."
docker compose -f /opt/cnap-siem/docker/docker-compose.yml up -d open-webui

log "Restore complete from: ${BACKUP_PREFIX}"
