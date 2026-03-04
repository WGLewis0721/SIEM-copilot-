# CNAP AI SIEM Copilot — Deployment Guide

Complete step-by-step guide to deploying the CNAP AI SIEM Copilot in AWS GovCloud.

---

## Prerequisites Checklist

Before beginning deployment, verify:

- [ ] AWS GovCloud account access with IL6 authorization
- [ ] IAM permissions: `ec2:*`, `iam:CreateRole`, `iam:AttachRolePolicy`, `s3:*`, `es:*`
- [ ] Existing VPC with at least one private subnet
- [ ] Existing OpenSearch domain reachable from the VPC
- [ ] AWS CLI v2 configured: `aws sts get-caller-identity --region us-gov-west-1`
- [ ] Terraform >= 1.6: `terraform version`
- [ ] Git: `git --version`
- [ ] SSM Session Manager plugin installed: `session-manager-plugin --version`

---

## Phase 1: AWS Infrastructure (Terraform)

### 1.1 Configure Variables

```bash
cd terraform/
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:
```hcl
# Required
aws_region          = "us-gov-west-1"
vpc_id              = "vpc-0123456789abcdef0"
subnet_id           = "subnet-0123456789abcdef0"
opensearch_endpoint = "vpc-my-domain-xxxx.us-gov-west-1.es.amazonaws.com"

# Recommended
environment         = "prod"
project_name        = "cnap-ai-siem"
instance_type       = "g4dn.xlarge"   # Use "t3.xlarge" for CPU-only

# Optional
ssh_key_name        = ""              # Leave empty — use SSM instead
```

### 1.2 Deploy Infrastructure

```bash
terraform init
terraform validate   # Check syntax
terraform plan -out=tfplan.out
terraform apply tfplan.out
```

Terraform will create:
- EC2 instance with NVIDIA drivers and Docker pre-installed
- IAM role with least-privilege policies
- Two S3 buckets (knowledge base + backups)
- Security group with SSM-only access
- Instance Profile attached to the EC2

### 1.3 Save Outputs

```bash
terraform output
```

```
instance_id        = "i-0123456789abcdef0"
knowledge_bucket   = "cnap-knowledge-base-prod-abc123"
backup_bucket      = "cnap-backup-prod-abc123"
iam_role_arn       = "arn:aws-us-gov:iam::123456789012:role/cnap-siem-role"
ssm_connect_cmd    = "aws ssm start-session --target i-0123456789abcdef0 ..."
```

---

## Phase 2: Connect and Deploy Docker

### 2.1 Connect via SSM Shell

```bash
INSTANCE_ID=$(terraform output -raw instance_id)
aws ssm start-session --target $INSTANCE_ID --region us-gov-west-1
```

### 2.2 Wait for User Data to Complete

The EC2 instance runs a user-data script that installs Docker, Docker Compose, and NVIDIA drivers. This takes 5–10 minutes after launch.

```bash
# On the EC2 instance (SSM shell):
sudo tail -f /var/log/cloud-init-output.log
# Wait until you see: "Cloud-init finished successfully"
```

### 2.3 Clone Repository on EC2

```bash
# On the EC2 instance:
cd /opt
sudo git clone https://github.com/your-org/cnap-ai-siem-copilot.git
sudo chown -R ubuntu:ubuntu cnap-ai-siem-copilot
cd cnap-ai-siem-copilot/docker
```

### 2.4 Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your values:
```bash
OPENSEARCH_ENDPOINT=vpc-your-domain.us-gov-west-1.es.amazonaws.com
OPENSEARCH_INDICES=cwl-*,appgate-logs-*,security-logs-*
AWS_REGION=us-gov-west-1
S3_KNOWLEDGE_BUCKET=cnap-knowledge-base-prod-abc123
S3_BACKUP_BUCKET=cnap-backup-prod-abc123
MODEL_NAME=llama3.1:8b
EMBEDDING_MODEL=nomic-embed-text
```

> ⚠️ **Never** add AWS credentials to .env — the EC2 instance uses its IAM role automatically.

### 2.5 Pull LLM Models

This step downloads ~5GB and may take 10–20 minutes:

```bash
docker compose up -d ollama
sleep 30

# Pull the main model
docker exec ollama ollama pull llama3.1:8b

# Pull the embedding model (for RAG)
docker exec ollama ollama pull nomic-embed-text
```

Verify models are loaded:
```bash
docker exec ollama ollama list
# Expected output:
# NAME              ID              SIZE   MODIFIED
# llama3.1:8b       f66fc8dc39ea    4.7 GB 1 minute ago
# nomic-embed-text  0a109f422b47    274 MB 30 seconds ago
```

### 2.6 Start All Services

```bash
docker compose up -d
```

Check all containers are running:
```bash
docker compose ps
# Expected:
# NAME         IMAGE                        STATUS
# ollama       ollama/ollama:latest         running (healthy)
# rag-agent    cnap/rag-agent:latest        running (healthy)
# open-webui   cnap/open-webui:latest       running (healthy)
# dashboard    cnap/dashboard:latest        running (healthy)
```

---

## Phase 3: Initial Configuration

### 3.1 Configure Open WebUI

From your local machine:
```bash
# Forward port 8080
INSTANCE_ID=$(cd terraform && terraform output -raw instance_id)
aws ssm start-session --target $INSTANCE_ID \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["8080"],"localPortNumber":["8080"]}'
```

Open http://localhost:8080 in your browser:
1. Create an admin account (first user becomes admin)
2. Go to Settings → Admin Panel → Users → Set signup policy to "Admin only"
3. Go to Settings → Connections → Verify Ollama is connected (green)
4. Go to Settings → Functions → Install custom functions (see below)

### 3.2 Install Custom Functions in Open WebUI

1. Go to **Workspace → Functions → +**
2. Import `docker/open-webui/functions/opensearch_filter.py`
3. Configure valves:
   - `OPENSEARCH_ENDPOINT`: your OpenSearch endpoint
   - `AWS_REGION`: us-gov-west-1
   - `TIME_RANGE_HOURS`: 720 (30 days)
4. Import `docker/open-webui/functions/rag_report_reader.py`
5. Enable both functions globally or per-chat

### 3.3 Set Security Preferences

In Open WebUI Admin Panel:
- **Session timeout**: 8 hours
- **Password minimum length**: 12 characters
- **HTTPS only**: Ensure access is only via SSM port forward

---

## Phase 4: Knowledge Base Population

### 4.1 Upload Sample Documents

```bash
# From your local machine
BUCKET=$(cd terraform && terraform output -raw knowledge_bucket)
./scripts/init-knowledge-base.sh $BUCKET
```

This uploads all documents from `knowledge-base/` to S3.

### 4.2 Verify Indexing

The RAG agent automatically indexes documents on startup. Verify with:
```bash
docker compose logs rag-agent | grep "Indexed"
# Expected: "Indexed 12 documents from S3 knowledge base"
```

### 4.3 Add Your Own Documents

Add runbooks, SOPs, and playbooks to S3:
```bash
aws s3 cp your-runbook.md s3://$BUCKET/runbooks/
aws s3 cp your-sop.pdf s3://$BUCKET/sops/
```

The RAG agent will automatically pick up new documents on the next 30-minute cycle.

---

## Phase 5: Verification Steps

### 5.1 Run Health Check

```bash
./scripts/health-check.sh
```

All checks must show `[OK]`.

### 5.2 Verify First Report

The RAG agent generates its first report within 5 minutes of startup:

```bash
# On EC2 instance:
ls -la docker/rag-agent/output/
# Expected: analysis_20241215_120000.txt and analysis_20241215_120000.json
```

### 5.3 Test OpenSearch Query

```bash
# Test direct OpenSearch connectivity (on EC2):
curl -H "Authorization: Bearer $(aws es describe-elasticsearch-domains --query 'DomainStatusList[0].Endpoint')" \
  https://$OPENSEARCH_ENDPOINT/cwl-*/_count
```

### 5.4 Test Chat Interface

Open http://localhost:8080 (via SSM port forward) and ask:
```
Show me the top 5 security events from the last hour.
```

You should see a response with actual log data and Document IDs.

---

## Phase 6: Backup / Restore Procedures

### Backup

Manual backup:
```bash
./scripts/backup.sh
```

Automated backup runs daily via cron (configured in docker-compose.yml).

What gets backed up:
- Open WebUI user data and chat history
- RAG analysis reports
- Custom function configurations

### Restore

```bash
./scripts/restore.sh --date 2024-12-15
```

Or restore latest:
```bash
./scripts/restore.sh --latest
```

---

## Upgrade Procedures

See [docs/upgrade-guide.md](docs/upgrade-guide.md) for:
- Upgrading Ollama models
- Upgrading Docker images
- Terraform state management

---

## Cleanup / Teardown

> ⚠️ This will **permanently delete** all resources and data.

```bash
# Stop Docker services first
# (via SSM): docker compose down -v

# Destroy AWS resources
cd terraform/
terraform destroy
```
