# CNAP AI SIEM Copilot — Upgrade Guide

## Upgrading Ollama Models

### Upgrade llama3.1:8b to a newer version

```bash
# Pull the new model version
docker exec ollama ollama pull llama3.1:8b

# Verify it loaded
docker exec ollama ollama list

# No restart needed — model is hot-swapped
```

### Switch to a different model

```bash
# Pull new model
docker exec ollama ollama pull llama3.2:8b

# Update .env file
sed -i 's/MODEL_NAME=llama3.1:8b/MODEL_NAME=llama3.2:8b/' docker/.env

# Restart agent
docker compose restart rag-agent open-webui
```

---

## Upgrading Docker Images

### Open WebUI

Open WebUI releases frequently. To upgrade:

```bash
# Pull latest image
docker compose pull open-webui

# Recreate container (preserves named volume data)
docker compose up -d open-webui

# Verify
docker compose ps open-webui
```

### Ollama

```bash
docker compose pull ollama
docker compose up -d ollama
# Wait for health check to pass before restarting dependents
docker compose restart rag-agent
```

### Full Stack Upgrade

```bash
# Pull all updated images
docker compose pull

# Restart with new images
docker compose up -d

# Verify all healthy
./scripts/health-check.sh
```

---

## Upgrading Terraform / Infrastructure

### Update Terraform modules

```bash
cd terraform/
terraform init -upgrade
terraform plan   # Review changes before applying
terraform apply
```

### Change EC2 instance type

1. Update `instance_type` in `terraform.tfvars`
2. Run `terraform plan` — this will show instance replacement
3. **Warning:** Instance replacement causes downtime and data loss if volumes are not backed up first
4. Run `./scripts/backup.sh` before applying
5. `terraform apply`
6. Run `./scripts/restore.sh --latest` after new instance is up

---

## Terraform State Management

State is stored locally by default. For team environments:

```hcl
# terraform/main.tf — uncomment and configure:
backend "s3" {
  bucket         = "your-terraform-state-bucket"
  key            = "cnap-siem/terraform.tfstate"
  region         = "us-gov-west-1"
  encrypt        = true
  dynamodb_table = "terraform-state-lock"
}
```

---

## Version Compatibility Matrix

| Component | Tested Version | Notes |
|-----------|---------------|-------|
| Terraform | >= 1.6.0 | Use 1.9+ for best provider support |
| AWS Provider | >= 5.0.0 | Required for IMDSv2 support |
| Ollama | Latest | Monthly releases; models are backward compatible |
| Open WebUI | Latest | Frequent updates; always back up before upgrading |
| Python (RAG Agent) | 3.11 | 3.12 also supported |
| Ubuntu | 24.04 LTS | Next LTS due 2026 |

---

## Rollback Procedures

### Rollback Docker service

```bash
# View image history
docker images open-webui

# Rollback to specific image version
docker compose down open-webui
docker tag open-webui:previous open-webui:latest
docker compose up -d open-webui
```

### Rollback Terraform

> ⚠️ Terraform rollback is complex. Always back up state before applying.

```bash
# Restore previous state from S3
aws s3 cp s3://state-bucket/backups/terraform.tfstate.bak terraform/terraform.tfstate

# Apply previous state
cd terraform/
terraform plan   # Review what will change
terraform apply
```
