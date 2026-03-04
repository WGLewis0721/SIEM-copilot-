# CNAP AI SIEM Copilot — Open WebUI Custom Functions

This directory contains custom filter functions for Open WebUI.

## Available Functions

### 1. `opensearch_filter.py` — Real-Time Log Query

**Triggers when:** User message contains keywords like "logs", "blocked", "firewall", "events", etc.

**What it does:**
- Queries OpenSearch with AWS IAM authentication
- Returns up to 50 matching log events with Document IDs
- Injects results into LLM context before the AI response

**Configuration (Valves):**
| Setting | Description |
|---------|-------------|
| `OPENSEARCH_ENDPOINT` | Your OpenSearch domain endpoint |
| `AWS_REGION` | AWS region (default: us-gov-west-1) |
| `TIME_RANGE_HOURS` | Default time window (default: 720 = 30 days) |
| `MAX_RESULTS` | Max log events per query (default: 50) |
| `LOG_INDICES` | Index patterns (default: cwl-*,appgate-logs-*,security-logs-*) |

### 2. `rag_report_reader.py` — Analysis Report Context

**Triggers when:** User asks about "latest report", "recent analysis", "what threats were found", etc.

**What it does:**
- Reads the most recent report from `/app/backend/data/outputs/`
- Warns if report is older than 4 hours
- Injects the full report text into LLM context

**Configuration (Valves):**
| Setting | Description |
|---------|-------------|
| `REPORTS_DIR` | Path to report directory (auto-configured via volume mount) |
| `MAX_REPORT_AGE_HOURS` | Warn if report older than N hours (default: 4) |

## Installing Functions

1. Open http://localhost:8080 (via SSM port forward)
2. Go to **Workspace → Functions → +**
3. Paste the function code
4. Click **Save**
5. Go to **Admin Panel → Functions** and toggle the function **On**
6. Click the gear icon to configure Valve settings

## Example Queries After Installing

```
# Triggers opensearch_filter.py:
Show me blocked connections from Palo Alto in the last 24 hours.
List failed authentication attempts from AppGate.

# Triggers rag_report_reader.py:
What does the latest security report say?
Summarize the most recent analysis findings.
```
