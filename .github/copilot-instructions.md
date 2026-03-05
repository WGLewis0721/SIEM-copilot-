# GitHub Copilot Instructions — CNAP AI SIEM Copilot

## Project Overview

This is a **production-grade AI-powered SIEM (Security Information and Event Management) Copilot** designed for deployment in AWS GovCloud (IL6). It analyzes logs from Palo Alto firewalls, AppGate SDP, and security event sources using a locally-hosted LLM with Retrieval-Augmented Generation (RAG).

**This system processes sensitive security data in a classified environment. Security is the top priority in all code changes.**

---

## Repository Structure

```
SIEM-copilot/
├── .github/                  # GitHub configuration (workflows, Copilot instructions)
├── terraform/                # AWS infrastructure as code (EC2, IAM, S3, Security Groups)
├── docker/                   # Docker Compose services
│   ├── ollama/               # Ollama LLM runtime config
│   ├── rag-agent/            # Python 3.11 automated analysis service (main service)
│   │   ├── main.py           # Entry point and analysis loop
│   │   ├── opensearch_client.py  # OpenSearch IAM-authenticated client
│   │   ├── rag_pipeline.py   # RAG retrieval + LLM generation
│   │   ├── s3_knowledge.py   # S3 knowledge base sync
│   │   ├── config.yaml       # Default YAML configuration
│   │   ├── requirements.txt  # Python dependencies
│   │   └── tests/            # pytest unit tests (all external deps mocked)
│   ├── open-webui/           # Chat UI with custom OpenSearch filter functions
│   └── dashboard/            # Flask report viewer (port 5000)
├── scripts/                  # Operational bash scripts (health-check, backup, restore)
├── knowledge-base/           # Sample security runbooks for RAG context
├── config/                   # Shared config (OpenSearch mappings, prompt templates)
└── docs/                     # Extended documentation
```

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Language (primary) | Python 3.11 |
| LLM runtime | Ollama (`llama3.1:8b`, `nomic-embed-text`) |
| Log storage | AWS OpenSearch (IL6 GovCloud, IAM auth) |
| Infrastructure | Terraform >= 1.6 |
| Containerization | Docker Compose |
| Web UI | Open WebUI (chat), Flask (dashboard) |
| Auth | AWS IAM Instance Profile (no static credentials) |
| Testing | pytest |
| Linting/Formatting | `ruff` + `black` (Python), `terraform fmt` (Terraform) |

---

## Coding Conventions

### Python

- **Python 3.11+** syntax only; use `from __future__ import annotations` in every module.
- **Type hints are required** on all function signatures and return types.
- **Google-style docstrings** for all public functions, classes, and modules.
- Formatting: **`black`** (line length 100) + **`ruff`** (flake8-compatible linting).
- All new code must pass: `ruff check . && black --check .` from `docker/rag-agent/`.
- Prefer `pathlib.Path` over `os.path` for file operations.
- Use structured **JSON logging** via the existing `JsonFormatter` (see `main.py`).
- No bare `except:` clauses — always catch specific exception types.

### Security-critical Python rules

- **Never hardcode credentials, keys, tokens, or endpoint URLs** in source code.
- Always use `boto3`'s automatic credential chain (IAM instance profile) — never pass `aws_access_key_id` explicitly.
- Input from users or external systems must be sanitised before use in OpenSearch queries or file paths.
- File path operations that use user-supplied input must be validated against a known safe base directory (see path-traversal protection in `dashboard/app.py`).

### Terraform

- Run `terraform fmt` before every commit.
- Use `aws_iam_role_policy` with least-privilege inline policies (not `AdministratorAccess`).
- All EC2 instances must have `http_tokens = "required"` (IMDSv2 enforced).
- No public IPs; all access via AWS SSM Session Manager.

### Docker / Containers

- All Python containers must run as a **non-root user** (`appuser`, UID 1000). See the `USER` directive pattern in `docker/rag-agent/Dockerfile`.
- Pin base image versions (e.g., `python:3.11-slim`, not `python:latest`).
- Use multi-stage builds where appropriate to minimise image size.

### Shell scripts

- All scripts in `scripts/` must start with `#!/usr/bin/env bash` and `set -euo pipefail`.
- Quote all variable expansions to prevent word-splitting.

---

## Security Requirements (Non-negotiable)

1. **Zero credentials in code**: No AWS keys, passwords, tokens, or secrets in any file.
   - `.env` is git-ignored; use `.env.example` with placeholder values only.
2. **Zero inbound ports**: EC2 Security Groups must have zero inbound rules; access is SSM-only.
3. **Least privilege IAM**: Grant only the specific actions on specific resource ARNs needed.
4. **Encrypted at rest and in transit**: S3 (AES-256), EBS (AES-256), TLS 1.2+ everywhere.
5. **IMDSv2 required**: Always set `http_tokens = "required"` in EC2 Terraform resources.
6. **Non-root containers**: Every Docker container must drop to a non-root user before the ENTRYPOINT.
7. **No PII/secrets in logs**: Application logs must not emit credentials, tokens, or PII.

---

## Testing

- Tests live in `docker/rag-agent/tests/test_rag_agent.py`.
- All external dependencies (AWS, OpenSearch, Ollama) are **mocked** — no live services required.
- Run tests from the `docker/rag-agent/` directory:
  ```bash
  cd docker/rag-agent
  pip install pytest pytest-mock
  python -m pytest tests/ -v
  ```
- New features in `main.py`, `rag_pipeline.py`, `opensearch_client.py`, or `dashboard/app.py` should have corresponding pytest unit tests.
- Use `unittest.mock.patch` and `MagicMock` to mock external clients and AWS services.

---

## Linting and Formatting

```bash
# Python — from docker/rag-agent/
cd docker/rag-agent
pip install ruff black
ruff check .
black --check .

# Terraform
cd terraform
terraform fmt -check

# Auto-fix Python formatting
black .
ruff check --fix .
```

---

## Configuration Pattern

The RAG Agent uses a **YAML + environment variable** config pattern:
- Default values come from `docker/rag-agent/config.yaml`.
- Environment variables always **override** YAML values (see `env_map` in `main.py`).
- Required fields: `opensearch.endpoint`, `aws.region`, `ollama.base_url`, `ollama.model_name`, `output.dir`.
- Never add default values for secrets or endpoints — they must be explicitly configured.

---

## Architecture Notes for Copilot

- The **RAG Agent** (`docker/rag-agent/`) is the core service. It runs on a 30-minute cron loop, queries OpenSearch for recent logs, retrieves relevant runbook context via vector similarity search, and calls Ollama to generate a security analysis report.
- The **Open WebUI filter** (`docker/open-webui/functions/`) intercepts user chat messages, detects log-query keywords, queries OpenSearch in real time, and injects enriched context into the LLM prompt.
- The **Dashboard** (`docker/dashboard/`) is a read-only Flask app that serves the latest generated analysis reports from the local filesystem.
- **OpenSearch authentication** always uses AWS SigV4 (IAM) — never basic auth or API keys.
- **Ollama** runs locally on the EC2 instance — no data leaves the instance boundary.

---

## Common Pitfalls to Avoid

- Do not use `os.environ["VAR"]` without a fallback in non-critical paths — prefer `os.environ.get("VAR")`.
- Do not construct OpenSearch query DSL with raw string formatting (use dict structures to avoid injection).
- Do not add new Python dependencies without updating `requirements.txt` with pinned version ranges (e.g., `>=x.y,<x+1.0`).
- Do not expose port-level access without SSM tunneling — the Security Group has zero inbound rules by design.
- Do not write files outside of the configured `output.dir` or `/tmp` — respect the container filesystem layout.
