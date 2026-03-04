# CNAP AI SIEM Copilot

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Terraform](https://img.shields.io/badge/terraform-1.6+-purple.svg)](https://www.terraform.io/)

A production-grade **AI-powered Security Information and Event Management (SIEM) Copilot** that analyzes logs from Palo Alto firewalls, AppGate SDP, and security events using a local LLM with Retrieval-Augmented Generation (RAG) capabilities.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [Quick Start (30 minutes)](#quick-start)
- [Access Instructions](#access-instructions)
- [Example Queries](#example-queries)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

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
