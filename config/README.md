# CNAP AI SIEM Copilot — Configuration Files

## Contents

| File | Purpose |
|------|---------|
| `opensearch-mappings.json` | Index mappings for OpenSearch (knowledge base, Palo Alto, AppGate) |
| `prompts/security-analysis.txt` | System prompt for automated RAG analysis |
| `prompts/log-query.txt` | System prompt for real-time chat queries |

## OpenSearch Mappings

Apply mappings to create properly typed indices:

```bash
# Create knowledge base index (required for RAG embeddings)
curl -XPUT "https://$OPENSEARCH_ENDPOINT/cnap-knowledge-base" \
  -H "Content-Type: application/json" \
  -d "@config/opensearch-mappings.json#/cnap-knowledge-base"
```

Note: The RAG agent automatically creates this index on startup if it doesn't exist.

## Prompts

The system prompts are mounted into the RAG agent container and loaded at startup.
To update prompts without rebuilding the container:

```bash
# Edit the prompt file
vim config/prompts/security-analysis.txt

# Restart the RAG agent to pick up changes
docker compose restart rag-agent
```
