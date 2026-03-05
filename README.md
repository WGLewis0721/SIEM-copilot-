# CNAP AI SIEM Copilot

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Terraform](https://img.shields.io/badge/terraform-1.6+-purple.svg)](https://www.terraform.io/)

A production-grade **AI-powered Security Information and Event Management (SIEM) Copilot** that analyzes logs from Palo Alto firewalls, AppGate SDP, and security events using a local LLM with Retrieval-Augmented Generation (RAG) capabilities.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Concepts Covered](#concepts-covered)
- [Prerequisites](#prerequisites)
- [Quick Start (30 minutes)](#quick-start)
- [Access Instructions](#access-instructions)
- [Example Queries](#example-queries)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [Build with AI Assistance](#build-with-ai-assistance)

---

## Architecture Overview

```
[Log Sources] ──────────────────────────────────────────────────────┐
  • Palo Alto Firewalls (cwl-*)                                      │
  • AppGate SDP (appgate-logs-*)                                     │
  • Security Events (security-logs-*)                                │
                                                                     ▼
                                                       ┌──────────────────────┐
                                                       │   AWS OpenSearch      │
                                                       │   (IL6 GovCloud)      │
                                                       └──────────┬───────────┘
                                                                  │
                               ┌──────────────────────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   AI Analysis Layer   │
                    │                      │
                    │  ┌────────────────┐  │       ┌──────────────────────┐
                    │  │ Ollama Runtime │  │◄──────│  RAG Knowledge Base  │
                    │  │ llama3.1:8b   │  │       │  (S3 + OpenSearch)   │
                    │  │ nomic-embed   │  │       └──────────────────────┘
                    │  └────────────────┘  │
                    │                      │
                    │  ┌────────────────┐  │       ┌──────────────────────┐
                    │  │   RAG Agent   │──┼───────►│   S3 Reports Bucket  │
                    │  │ (30-min cron) │  │       └──────────────────────┘
                    │  └────────────────┘  │
                    └──────────────────────┘
                               │
                    ┌──────────┴───────────┐
                    ▼                      ▼
          ┌──────────────────┐   ┌──────────────────┐
          │   Open WebUI     │   │    Dashboard      │
          │  (Chat Interface)│   │  (Report Viewer)  │
          │   Port 8080      │   │   Port 5000       │
          └──────────────────┘   └──────────────────┘
```

**Key components:**

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Log Storage | AWS OpenSearch (IL6 GovCloud) | Stores and indexes all security logs |
| LLM Runtime | Ollama + llama3.1:8b | Local AI inference, no data leaves the instance |
| Embeddings | nomic-embed-text | Vector embeddings for RAG |
| RAG Agent | Python 3.11 | Scheduled log analysis every 30 minutes |
| Chat UI | Open WebUI | Interactive natural-language log queries |
| Infrastructure | Terraform | EC2 on g4dn.xlarge or t3.xlarge |
| Auth | AWS IAM roles | Zero credentials in code |

---

## Concepts Covered

This repository is a working, production-grade reference for the following AI, DevOps, and Python programming concepts. Whether you are exploring the codebase to learn or to extend it, here is what you will find.

### 🤖 Artificial Intelligence

| Concept | Where it appears |
|---------|-----------------|
| **Retrieval-Augmented Generation (RAG)** | `docker/rag-agent/rag_pipeline.py` — the agent retrieves relevant runbook chunks from OpenSearch before calling the LLM, grounding responses in real operational context |
| **Large Language Models (LLMs)** | Ollama runs `llama3.1:8b` locally on the EC2 instance; all inference stays on-premise with no data leaving the boundary |
| **Vector Embeddings** | `nomic-embed-text` model converts security runbooks and log summaries into dense vectors stored in OpenSearch for similarity search |
| **k-NN / Vector Similarity Search** | OpenSearch k-NN index used to find the top-K most relevant knowledge-base documents for each analysis cycle |
| **Prompt Engineering** | `config/` prompt templates and the system prompt in `rag_pipeline.py` demonstrate how to structure LLM inputs for consistent, structured security reports |
| **Real-Time LLM Filtering** | `docker/open-webui/functions/` — a custom Open WebUI inlet function detects log-query keywords and injects live OpenSearch context into chat prompts before they reach the LLM |
| **Scheduled AI Analysis** | The RAG Agent runs on a configurable cron loop (default 30 minutes), demonstrating autonomous, event-driven AI workflows |

### ⚙️ DevOps & Cloud Engineering

| Concept | Where it appears |
|---------|-----------------|
| **Infrastructure as Code (IaC)** | `terraform/` — every AWS resource (EC2, IAM, S3, Security Groups) is defined in Terraform >= 1.6 with least-privilege policies |
| **Docker & Docker Compose** | `docker/` — all services (Ollama, RAG Agent, Open WebUI, Dashboard) run as isolated containers orchestrated with a single `docker compose up` |
| **Non-Root Container Security** | Every Dockerfile drops to a non-root `appuser` (UID 1000) before the entrypoint, following container hardening best practices |
| **AWS IAM Instance Profiles** | Zero static credentials — the EC2 instance role is the only auth mechanism, consumed automatically by `boto3`'s credential chain |
| **Zero-Trust Networking** | EC2 has no inbound Security Group rules; all operator access uses AWS SSM Session Manager port-forwarding (no SSH, no public IP) |
| **IMDSv2 Enforcement** | Terraform sets `http_tokens = "required"` on all EC2 instances to prevent SSRF-based credential theft |
| **AWS SigV4 Authentication** | OpenSearch requests are signed with AWS SigV4 via `opensearch-py` + `requests-aws4auth`, demonstrated in `opensearch_client.py` |
| **S3-Backed Knowledge Base** | Runbooks and SOPs are stored in S3 and synced at runtime (`s3_knowledge.py`), showing a pattern for managing AI context in cloud storage |
| **Health Checks & Observability** | `scripts/health-check.sh` shows how to validate multi-service Docker deployments; structured JSON logging is used throughout the Python services |

### 🐍 Python Programming

| Concept | Where it appears |
|---------|-----------------|
| **Python 3.11 Type Hints** | All function signatures use full type annotations (`from __future__ import annotations`), serving as a guide for modern, readable Python |
| **Google-Style Docstrings** | Every public function and class carries a Google-style docstring, demonstrating professional API documentation standards |
| **YAML + Environment Variable Configuration** | `config.yaml` provides defaults; environment variables always override them (see `env_map` in `main.py`), a common 12-factor app pattern |
| **boto3 (AWS SDK)** | `opensearch_client.py` and `s3_knowledge.py` show IAM-authenticated AWS API calls without hardcoded credentials |
| **OpenSearch Python Client** | Demonstrates index creation, k-NN mapping, bulk document indexing, and query DSL construction using dict structures (not string formatting) |
| **Flask Web Framework** | `docker/dashboard/app.py` is a minimal Flask app that serves generated reports with path-traversal protection, a clean example of safe file serving |
| **Structured JSON Logging** | `main.py`'s `JsonFormatter` shows how to emit machine-readable logs suitable for ingestion by log aggregators |
| **pytest & Mocking** | `docker/rag-agent/tests/` covers all major code paths using `unittest.mock.patch` and `MagicMock` — no live AWS services required |
| **Scheduled Background Tasks** | The main analysis loop in `main.py` demonstrates a production-safe Python scheduler pattern with configurable intervals and error recovery |
| **Ruff + Black Code Quality** | The project enforces `ruff` (linting) and `black` (formatting, line length 100) — runnable with a single command from `docker/rag-agent/` |

---

## Prerequisites

### AWS Requirements
- [ ] AWS GovCloud account with appropriate clearance
- [ ] IAM permissions to create: EC2, IAM roles, S3 buckets, Security Groups
- [ ] Existing OpenSearch domain (IL6 GovCloud) with endpoint URL
- [ ] VPC with private subnet (no public IP needed)
- [ ] SSM Session Manager enabled in your AWS account

### Local Requirements
- [ ] [Terraform](https://www.terraform.io/downloads) >= 1.6
- [ ] [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) configured for GovCloud
- [ ] [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for local testing only)

### Instance Requirements (auto-provisioned)
- g4dn.xlarge (Tesla T4 GPU, 16GB VRAM) — **recommended**
- t3.xlarge (CPU-only fallback, ~3x slower inference)

---

## Quick Start

### Step 1 — Clone and configure

```bash
git clone https://github.com/your-org/cnap-ai-siem-copilot.git
cd cnap-ai-siem-copilot

# Copy and edit Terraform variables
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
```

Edit `terraform/terraform.tfvars`:
```hcl
aws_region           = "us-gov-west-1"
vpc_id               = "vpc-xxxxxxxx"
subnet_id            = "subnet-xxxxxxxx"
opensearch_endpoint  = "vpc-your-domain.us-gov-west-1.es.amazonaws.com"
environment          = "prod"
instance_type        = "g4dn.xlarge"   # or "t3.xlarge" for CPU
```

### Step 2 — Deploy infrastructure

```bash
cd terraform
terraform init
terraform plan   # Review what will be created
terraform apply  # Type "yes" to confirm
```

> This creates: EC2 instance, IAM role, S3 buckets (knowledge base + backups), security groups.

### Step 3 — Connect via SSM

```bash
# Get instance ID from Terraform output
INSTANCE_ID=$(terraform output -raw instance_id)

# Start SSM session with port forwarding for Open WebUI
aws ssm start-session \
  --target $INSTANCE_ID \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["8080"],"localPortNumber":["8080"]}'
```

Open http://localhost:8080 in your browser.

### Step 4 — Initialize knowledge base (optional but recommended)

```bash
# Upload runbooks/SOPs to S3 for RAG context
./scripts/init-knowledge-base.sh
```

### Step 5 — Verify deployment

```bash
./scripts/health-check.sh
```

Expected output:
```
[OK] Ollama is running (llama3.1:8b loaded)
[OK] RAG Agent is healthy
[OK] Open WebUI is responding
[OK] OpenSearch connection successful
[OK] S3 knowledge base has 12 documents
[OK] Latest report: 3 minutes ago
```

---

## Access Instructions

All access is via **SSM Session Manager** — no SSH keys, no public IPs.

### Open WebUI (Chat Interface)
```bash
# Forward port 8080
aws ssm start-session --target $INSTANCE_ID \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["8080"],"localPortNumber":["8080"]}'
# Then open: http://localhost:8080
```

### Dashboard (Report Viewer)
```bash
# Forward port 5000
aws ssm start-session --target $INSTANCE_ID \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["5000"],"localPortNumber":["5000"]}'
# Then open: http://localhost:5000
```

### Ollama API (Debug)
```bash
# Forward port 11434
aws ssm start-session --target $INSTANCE_ID \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["11434"],"localPortNumber":["11434"]}'
```

---

## Example Queries

Open the chat interface at http://localhost:8080 and try:

### Real-time log queries (triggers OpenSearch filter)
```
Show me the top 10 blocked connections from Palo Alto in the last 24 hours.

List failed authentication attempts from AppGate SDP in the past hour.

Are there any critical security events with severity > 8?

Show denied traffic from external IPs to port 22 or 3389.
```

### Report analysis (uses cached RAG analysis)
```
What does the latest security report say about anomalies?

Summarize the threat patterns from the most recent analysis.

What runbook should I follow for the firewall policy violation found in the latest report?
```

### Knowledge base queries
```
What is the AppGate SDP authentication flow?

Show me the incident response playbook for a privilege escalation alert.

What are the Palo Alto firewall rules for DMZ traffic?
```

---

## Troubleshooting

See [docs/troubleshooting.md](docs/troubleshooting.md) for detailed troubleshooting steps.

**Quick fixes:**

| Issue | Solution |
|-------|----------|
| Ollama returns 404 | `docker compose restart ollama` and wait 2 minutes for model load |
| RAG agent shows "OpenSearch connection failed" | Verify the instance has the correct IAM role attached |
| Open WebUI blank page | Clear browser cache, check port forwarding is active |
| Reports not generating | Check `docker compose logs rag-agent` for errors |
| `nomic-embed-text` not found | SSH to instance, run `docker exec ollama ollama pull nomic-embed-text` |

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make changes following the coding standards in [docs/security-considerations.md](docs/security-considerations.md)
4. Run linting: `cd docker/rag-agent && pip install ruff black && ruff check . && black --check .`
5. Submit a pull request

**Code standards:**
- Python: type hints required, Google-style docstrings, `ruff` + `black` formatting
- Terraform: `terraform fmt` before committing
- No secrets/credentials in any committed file
- Every new directory needs a README.md

---

## Build with AI Assistance

Want to adapt, extend, or rebuild this project with the help of an AI assistant? Copy any of the prompts below into **Claude**, **ChatGPT**, or **GitHub Copilot Chat** to get a head start. Feel free to tweak the details (cloud provider, log sources, instance type, etc.) to match your environment.

---

### 🟣 Full project bootstrap prompt

Use this to ask an AI to scaffold the entire project from scratch, or to understand how all the pieces fit together.

```
I want to build a production-grade AI-powered SIEM Copilot that runs entirely on-premise inside AWS GovCloud (IL6).

The system should:
1. Ingest security logs from Palo Alto firewalls, AppGate SDP, and generic security event sources stored in AWS OpenSearch.
2. Run a Python 3.11 RAG Agent every 30 minutes that:
   - Queries OpenSearch for the latest logs using IAM/SigV4 authentication (no static credentials).
   - Retrieves relevant security runbooks from an S3-backed knowledge base via vector similarity search (nomic-embed-text embeddings stored in an OpenSearch k-NN index).
   - Calls a locally-hosted Ollama LLM (llama3.1:8b) to generate a structured threat-analysis report.
   - Writes the report as a JSON file to a local output directory.
3. Expose a Flask dashboard (port 5000) that serves the latest generated reports from the filesystem.
4. Expose an Open WebUI chat interface (port 8080) with a custom inlet filter that detects log-query keywords, queries OpenSearch in real time, and injects enriched context into prompts before they reach the LLM.
5. Deploy all services with Docker Compose; every container must run as a non-root user (UID 1000).
6. Provision all AWS infrastructure (EC2 g4dn.xlarge, IAM role with least-privilege inline policies, S3 buckets, Security Groups with zero inbound rules) using Terraform >= 1.6 with IMDSv2 enforced.
7. Provide operator access exclusively through AWS SSM Session Manager port-forwarding — no SSH keys, no public IPs.

Please generate:
- The complete directory structure.
- The Python source files (main.py, rag_pipeline.py, opensearch_client.py, s3_knowledge.py, config.yaml).
- Dockerfiles for the RAG Agent and Dashboard.
- A docker-compose.yml that wires all services together.
- Terraform files (main.tf, ec2.tf, iam.tf, s3.tf, security-groups.tf, variables.tf, outputs.tf).
- A health-check.sh script.
- pytest unit tests that mock all AWS/Ollama/OpenSearch calls.
- A README with quick-start instructions.

Follow these constraints:
- Python: type hints on every function, Google-style docstrings, black (line length 100) + ruff formatting, from __future__ import annotations in every module.
- No hardcoded credentials, endpoints, or secrets anywhere — use environment variables and IAM instance profiles.
- Structured JSON logging via a custom JsonFormatter.
- OpenSearch queries must use dict-based DSL (no raw string interpolation).
- S3 and EBS encrypted at rest (AES-256); TLS 1.2+ in transit.
```

---

### 🔵 Extend the RAG pipeline prompt

Use this when you want to add new capabilities to the existing RAG Agent.

```
I have a Python RAG Agent (rag_pipeline.py) that:
- Authenticates to AWS OpenSearch with SigV4.
- Retrieves the top-K most similar runbook chunks from a k-NN index using nomic-embed-text embeddings.
- Generates a security analysis report by calling Ollama (llama3.1:8b) with a structured prompt.

I want to extend it to:
[DESCRIBE YOUR EXTENSION HERE — for example:]
- Add a severity scoring step that rates each detected anomaly 1–10 before writing the report.
- Support a second LLM model (mistral:7b) as a fallback when llama3.1:8b is unavailable.
- Cache the last 5 reports in memory and include a trend comparison in the prompt.
- Emit Prometheus metrics (analysis duration, token count, anomaly count) to a /metrics endpoint.

Please show me:
1. The modified rag_pipeline.py with full type hints and Google-style docstrings.
2. Any new dependencies to add to requirements.txt (with pinned version ranges, e.g., >=x.y,<x+1.0).
3. Updated pytest unit tests in tests/test_rag_agent.py that mock all external calls.
```

---

### 🟢 Infrastructure customization prompt

Use this when you need to adapt the Terraform configuration for a different environment.

```
I have Terraform code that deploys an AI SIEM Copilot on AWS GovCloud with the following setup:
- EC2 g4dn.xlarge with IMDSv2 enforced, no public IP, SSM-only access.
- IAM instance profile with least-privilege inline policies for OpenSearch, S3, and SSM.
- S3 buckets for knowledge base and report backups (AES-256 encryption).
- Security Group with zero inbound rules.

I want to modify it to:
[DESCRIBE YOUR CHANGE HERE — for example:]
- Add a second EC2 instance in a different availability zone with an ALB in front (internal only).
- Replace S3 report storage with an EFS mount shared between both instances.
- Add a CloudWatch alarm that triggers an SNS notification when the RAG Agent log stream contains "ERROR".
- Tag all resources with CostCenter, Project, and Environment tags.

Please generate the updated Terraform files, run terraform fmt style, and explain any IAM policy changes needed.
```

---

### 🟡 Open WebUI filter customization prompt

Use this to modify the chat interface's real-time log enrichment behavior.

```
I have a custom Open WebUI inlet filter (Python) that:
- Detects log-query keywords in chat messages (e.g., "show logs", "blocked connections", "failed auth").
- Queries AWS OpenSearch with SigV4 authentication to retrieve matching log entries.
- Injects the retrieved log context into the LLM prompt before it is sent to Ollama.

I want to change it so that:
[DESCRIBE YOUR CHANGE HERE — for example:]
- It also detects threat-intelligence keywords and enriches the prompt with entries from a local MITRE ATT&CK JSON file.
- It limits injected log context to 2,000 tokens and summarizes longer results before injection.
- It adds a citation footer to the LLM response showing which log index and time range was queried.

Please provide the updated filter code with type hints, docstrings, and any necessary helper functions.
```

---

> **Tip:** After pasting a prompt, review the AI's output carefully — especially IAM policies, Dockerfile `USER` directives, and any hardcoded values — before deploying to a production or classified environment.
