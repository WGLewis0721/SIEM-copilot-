# CNAP AI SIEM Copilot — RAG Agent

The RAG (Retrieval-Augmented Generation) Agent is a Python service that runs on a 30-minute schedule to analyze security logs from OpenSearch and generate AI-powered security reports.

## How It Works

1. **Queries OpenSearch** for recent logs from Palo Alto, AppGate, and security indices
2. **Retrieves context** from the S3 knowledge base using vector similarity search
3. **Generates analysis** using Ollama (llama3.1:8b) with RAG-enhanced prompts
4. **Saves reports** to local filesystem (`/app/output/`) and S3 backup bucket

## Output Files

| File | Description |
|------|-------------|
| `analysis_YYYYMMDD_HHMMSS.txt` | Human-readable security analysis report |
| `analysis_YYYYMMDD_HHMMSS.json` | Structured data including log counts, citations |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENSEARCH_ENDPOINT` | ✅ | — | OpenSearch domain endpoint |
| `AWS_REGION` | ✅ | — | AWS region |
| `S3_KNOWLEDGE_BUCKET` | ✅ | — | S3 bucket with runbooks |
| `OLLAMA_BASE_URL` | ✅ | — | Ollama API URL |
| `MODEL_NAME` | | `llama3.1:8b` | LLM model name |
| `EMBEDDING_MODEL` | | `nomic-embed-text` | Embedding model |
| `TIME_RANGE_HOURS` | | `720` | Hours of logs to analyze |
| `INTERVAL_MINUTES` | | `30` | Analysis frequency |
| `ENABLE_RAG` | | `true` | Enable RAG context retrieval |
| `RAG_TOP_K` | | `3` | Number of RAG context docs |

## File Structure

```
rag-agent/
├── main.py              # Entry point and analysis loop
├── opensearch_client.py # OpenSearch queries with IAM auth
├── rag_pipeline.py      # RAG retrieval and LLM generation
├── s3_knowledge.py      # S3 document download and parsing
├── config.yaml          # Default configuration (overridden by env vars)
├── Dockerfile           # Container build definition
└── requirements.txt     # Python dependencies
```
