# CNAP AI SIEM Copilot — Troubleshooting Guide

## Quick Diagnostic Commands

```bash
# Run full health check
./scripts/health-check.sh --verbose

# Check all container logs
docker compose logs --tail=50

# Check specific container
docker compose logs rag-agent --tail=100
docker compose logs ollama --tail=50
docker compose logs open-webui --tail=50
```

---

## Issue: Ollama Returns 404 / Model Not Found

**Symptoms:** Chat returns "model not found" or RAG agent logs show Ollama errors.

**Solution:**
```bash
# Pull required models
docker exec ollama ollama pull llama3.1:8b
docker exec ollama ollama pull nomic-embed-text

# Verify models are loaded
docker exec ollama ollama list

# Restart dependent services after models are ready
docker compose restart rag-agent open-webui
```

---

## Issue: RAG Agent Shows "OpenSearch Connection Failed"

**Symptoms:** `docker compose logs rag-agent` shows connectivity errors.

**Diagnosis:**
```bash
# Check if the instance has the correct IAM role
aws sts get-caller-identity
# Should show the SIEM Copilot role ARN

# Test OpenSearch endpoint (from EC2 instance)
curl -I "https://$OPENSEARCH_ENDPOINT"

# Check security group allows outbound HTTPS
aws ec2 describe-security-groups --group-ids $SG_ID
```

**Common Causes:**
1. EC2 instance launched without the IAM role (check instance profile)
2. OpenSearch domain has restrictive resource-based policy
3. Security group blocking outbound port 443

**Solution for IAM:**
```bash
# Verify instance profile is attached
aws ec2 describe-instances --instance-ids $INSTANCE_ID \
  --query 'Reservations[0].Instances[0].IamInstanceProfile'
```

---

## Issue: Open WebUI Blank Page / 502 Error

**Symptoms:** http://localhost:8080 shows a blank page or error.

**Solution:**
```bash
# Check if SSM port forward is still active (it may have timed out)
# Restart the port forward on your local machine:
aws ssm start-session --target $INSTANCE_ID \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["8080"],"localPortNumber":["8080"]}'

# Check container health
docker inspect open-webui --format='{{.State.Health.Status}}'

# Check for startup errors
docker compose logs open-webui --tail=50
```

---

## Issue: Reports Not Generating

**Symptoms:** No `analysis_*.json` files appearing in output directory.

**Diagnosis:**
```bash
docker compose logs rag-agent --tail=100 | grep -E "ERROR|WARNING|Starting analysis"
```

**Common Causes:**

| Cause | Resolution |
|-------|-----------|
| No logs in OpenSearch time window | Verify log ingestion is active; check index patterns |
| Ollama not responding | Run health check, verify model is loaded |
| S3 permission denied | Check IAM role has `s3:PutObject` on backup bucket |
| Python exception | Check full error message in logs |

---

## Issue: GPU Not Being Used (Slow Inference)

**Symptoms:** Inference takes > 60 seconds per response.

**Diagnosis:**
```bash
# Check if NVIDIA drivers are installed
docker exec ollama nvidia-smi

# Check Docker GPU runtime
docker info | grep -i runtime
```

**Solution:**
```bash
# If nvidia-smi fails, NVIDIA drivers may not be installed:
sudo apt-get install -y cuda-drivers
sudo reboot

# After reboot:
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
docker compose up -d
```

---

## Issue: nomic-embed-text Not Available (RAG Broken)

**Symptoms:** RAG agent logs show "Embedding generation failed".

**Solution:**
```bash
docker exec ollama ollama pull nomic-embed-text
docker compose restart rag-agent
```

---

## Issue: SSM Session Manager Connection Fails

**Symptoms:** `aws ssm start-session` times out or returns "TargetNotConnected".

**Diagnosis:**
```bash
# Check instance status
aws ec2 describe-instances --instance-ids $INSTANCE_ID \
  --query 'Reservations[0].Instances[0].State.Name'

# Check SSM agent status (on instance via EC2 console):
sudo systemctl status amazon-ssm-agent
sudo systemctl restart amazon-ssm-agent
```

**Common Causes:**
1. Instance in private subnet without VPC endpoint for SSM
2. Security group blocking outbound HTTPS (needed for SSM)
3. SSM agent not installed or running

**VPC Endpoints Required for SSM:**
- `com.amazonaws.REGION.ssm`
- `com.amazonaws.REGION.ssmmessages`
- `com.amazonaws.REGION.ec2messages`

---

## Issue: Out of Disk Space

**Symptoms:** Docker containers failing to write logs or reports.

**Solution:**
```bash
# Check disk usage
df -h

# Clean up old Docker images and stopped containers
docker system prune -f

# Clean up old reports (keep last 30 days)
find docker/rag-agent/output/ -name "analysis_*" -mtime +30 -delete

# Remove large Ollama models not in use
docker exec ollama ollama rm <unused-model>
```

---

## Logs Reference

| Container | Log Location | Key Events to Watch |
|-----------|-------------|-------------------|
| `rag-agent` | `docker compose logs rag-agent` | Analysis runs, OpenSearch errors, S3 uploads |
| `ollama` | `docker compose logs ollama` | Model load, inference errors |
| `open-webui` | `docker compose logs open-webui` | Auth events, filter errors |
| `dashboard` | `docker compose logs dashboard` | HTTP errors, report loading |
