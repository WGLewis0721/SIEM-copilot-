#!/usr/bin/env bash
# =============================================================================
# CNAP AI SIEM Copilot — Health Check Script
# Verifies all system components are working correctly
# Usage: ./health-check.sh [--verbose]
# =============================================================================

set -uo pipefail

VERBOSE=false
PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

while [[ $# -gt 0 ]]; do
    case $1 in
        --verbose|-v) VERBOSE=true; shift ;;
        *) echo "Unknown argument: $1"; exit 1 ;;
    esac
done

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
ok()   { echo "[OK]   $*"; ((PASS_COUNT++)); }
fail() { echo "[FAIL] $*" >&2; ((FAIL_COUNT++)); }
warn() { echo "[WARN] $*"; ((WARN_COUNT++)); }
info() { [[ "$VERBOSE" == "true" ]] && echo "[INFO] $*" || true; }

echo "============================================"
echo " CNAP AI SIEM Copilot — Health Check"
echo " $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
echo "============================================"
echo ""

# ---------------------------------------------------------------------------
# 1. Docker services
# ---------------------------------------------------------------------------
echo "=== Docker Services ==="

for SERVICE in ollama rag-agent open-webui dashboard; do
    STATUS=$(docker inspect --format='{{.State.Status}}' "$SERVICE" 2>/dev/null || echo "not found")
    HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "$SERVICE" 2>/dev/null || echo "N/A")

    if [[ "$STATUS" == "running" ]]; then
        if [[ "$HEALTH" == "healthy" || "$HEALTH" == "N/A" ]]; then
            ok "Container '$SERVICE' is running (health: ${HEALTH})"
        else
            warn "Container '$SERVICE' is running but health is '${HEALTH}'"
        fi
    else
        fail "Container '$SERVICE' status: $STATUS"
    fi
done

# ---------------------------------------------------------------------------
# 2. Ollama model availability
# ---------------------------------------------------------------------------
echo ""
echo "=== Ollama LLM ==="

OLLAMA_URL="http://localhost:11434"
if curl -sf "${OLLAMA_URL}/api/tags" > /tmp/ollama-tags.json 2>&1; then
    MODELS=$(python3 -c "import json,sys; data=json.load(open('/tmp/ollama-tags.json')); print([m['name'] for m in data.get('models',[])])" 2>/dev/null || echo "[]")
    info "Available models: $MODELS"

    if echo "$MODELS" | grep -q "llama3.1:8b"; then
        ok "Ollama model 'llama3.1:8b' is loaded"
    else
        fail "Ollama model 'llama3.1:8b' not found — run: docker exec ollama ollama pull llama3.1:8b"
    fi

    if echo "$MODELS" | grep -q "nomic-embed-text"; then
        ok "Ollama embedding model 'nomic-embed-text' is loaded"
    else
        warn "Embedding model 'nomic-embed-text' not found — RAG context retrieval will not work"
    fi
else
    fail "Ollama API not responding at ${OLLAMA_URL}"
fi

# ---------------------------------------------------------------------------
# 3. RAG Agent reports
# ---------------------------------------------------------------------------
echo ""
echo "=== RAG Agent ==="

REPORT_DIR="/opt/cnap-siem/docker/rag-agent/output"
if command -v docker &> /dev/null; then
    REPORT_COUNT=$(docker exec rag-agent sh -c "ls /app/output/analysis_*.json 2>/dev/null | wc -l" 2>/dev/null || echo "0")
    if [[ "$REPORT_COUNT" -gt 0 ]]; then
        LATEST_REPORT=$(docker exec rag-agent sh -c "ls -t /app/output/analysis_*.json 2>/dev/null | head -1" 2>/dev/null || echo "")
        if [[ -n "$LATEST_REPORT" ]]; then
            REPORT_AGE=$(docker exec rag-agent sh -c "
                MTIME=\$(stat -c %Y '$LATEST_REPORT' 2>/dev/null || echo 0)
                NOW=\$(date +%s)
                echo \$(( (NOW - MTIME) / 60 ))
            " 2>/dev/null || echo "999")
            ok "Latest report: ${LATEST_REPORT##*/} (${REPORT_AGE} minutes ago)"
            if [[ "$REPORT_AGE" -gt 90 ]]; then
                warn "Latest report is more than 90 minutes old — RAG agent may be stuck"
            fi
        fi
    else
        warn "No reports generated yet — RAG agent may still be initializing"
    fi
fi

# ---------------------------------------------------------------------------
# 4. Open WebUI
# ---------------------------------------------------------------------------
echo ""
echo "=== Open WebUI ==="

if curl -sf "http://localhost:8080/health" > /dev/null 2>&1; then
    ok "Open WebUI is responding at http://localhost:8080"
else
    fail "Open WebUI not responding — check: docker compose logs open-webui"
fi

# ---------------------------------------------------------------------------
# 5. Dashboard
# ---------------------------------------------------------------------------
echo ""
echo "=== Dashboard ==="

if curl -sf "http://localhost:5000/health" > /tmp/dashboard-health.json 2>&1; then
    REPORT_COUNT_DASH=$(python3 -c "import json; d=json.load(open('/tmp/dashboard-health.json')); print(d.get('report_count',0))" 2>/dev/null || echo "0")
    ok "Dashboard is responding at http://localhost:5000 (${REPORT_COUNT_DASH} reports visible)"
else
    fail "Dashboard not responding — check: docker compose logs dashboard"
fi

# ---------------------------------------------------------------------------
# 6. OpenSearch connectivity
# ---------------------------------------------------------------------------
echo ""
echo "=== OpenSearch ==="

OS_ENDPOINT="${OPENSEARCH_ENDPOINT:-}"
if [[ -n "$OS_ENDPOINT" ]]; then
    if curl -sf --max-time 5 "https://${OS_ENDPOINT}/_cluster/health" > /dev/null 2>&1; then
        ok "OpenSearch cluster is reachable"
    else
        # Try with AWS auth (expected when running on the EC2 instance)
        if docker exec rag-agent python3 -c "
import sys
from opensearch_client import OpenSearchClient
import os
client = OpenSearchClient(
    endpoint=os.environ.get('OPENSEARCH_ENDPOINT',''),
    region=os.environ.get('AWS_REGION','us-gov-west-1'),
)
sys.exit(0 if client.health_check() else 1)
" 2>/dev/null; then
            ok "OpenSearch cluster is reachable (via IAM auth)"
        else
            fail "OpenSearch cluster is not reachable at ${OS_ENDPOINT}"
        fi
    fi
else
    warn "OPENSEARCH_ENDPOINT not set — skipping OpenSearch check"
fi

# ---------------------------------------------------------------------------
# 7. GPU (optional)
# ---------------------------------------------------------------------------
echo ""
echo "=== GPU (optional) ==="

if docker exec ollama nvidia-smi > /dev/null 2>&1; then
    GPU_NAME=$(docker exec ollama nvidia-smi --query-gpu=gpu_name --format=csv,noheader 2>/dev/null | head -1 || echo "unknown")
    ok "NVIDIA GPU available: ${GPU_NAME}"
else
    warn "NVIDIA GPU not detected — inference running on CPU (slower)"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "============================================"
echo " Summary: ${PASS_COUNT} OK  |  ${WARN_COUNT} Warnings  |  ${FAIL_COUNT} Failures"
echo "============================================"

if [[ "$FAIL_COUNT" -gt 0 ]]; then
    exit 1
fi

exit 0
