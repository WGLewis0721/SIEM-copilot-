# CNAP AI SIEM Copilot — Utility Scripts

## Scripts Overview

| Script | Purpose |
|--------|---------|
| `backup.sh` | Backup Open WebUI data and RAG reports to S3 |
| `restore.sh` | Restore from a specific S3 backup |
| `health-check.sh` | Verify all system components are functioning |
| `init-knowledge-base.sh` | Upload sample runbooks from `knowledge-base/` to S3 |

## Usage

### Run Health Check
```bash
./scripts/health-check.sh
./scripts/health-check.sh --verbose   # More detailed output
```

### Backup to S3
```bash
export S3_BACKUP_BUCKET=cnap-ai-siem-prod-backup-abc123
./scripts/backup.sh

# Or specify bucket directly:
./scripts/backup.sh --bucket cnap-ai-siem-prod-backup-abc123
```

### Restore from Backup
```bash
# Restore the most recent backup:
./scripts/restore.sh --latest

# Restore from a specific date:
./scripts/restore.sh --date 20241215
```

### Initialize Knowledge Base
```bash
./scripts/init-knowledge-base.sh cnap-ai-siem-prod-knowledge-base-abc123
```

## Making Scripts Executable

```bash
chmod +x scripts/*.sh
```
