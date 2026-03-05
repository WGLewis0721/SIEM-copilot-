# CNAP AI SIEM Copilot — Open WebUI

This directory contains the custom Open WebUI build for the CNAP AI SIEM Copilot.

## Overview

Open WebUI provides the interactive chat interface for security analysts to:
- Ask natural language questions about security logs
- Get AI-powered analysis with log evidence
- Review and discuss automated analysis reports
- Access the RAG knowledge base

## Custom Features

The `Dockerfile` extends the official Open WebUI image with:
- `boto3` + `requests-aws4auth` — AWS IAM authentication for OpenSearch
- Custom filter functions in `functions/` — OpenSearch queries and report reading

## Access

Via SSM port forwarding:
```bash
aws ssm start-session --target $INSTANCE_ID \
  --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["8080"],"localPortNumber":["8080"]}'
# Then open: http://localhost:8080
```

## Configuration

All configuration is done through the Open WebUI Admin Panel:
1. **Users** — Create accounts, set admin access
2. **Functions** — Install and configure custom filters
3. **Models** — Select default model (llama3.1:8b)

## Data Persistence

User data (accounts, chat history, settings) is stored in the `openwebui-data` Docker volume.
