# CNAP AI SIEM Copilot — Ollama LLM Runtime

Ollama provides the local LLM inference engine. No data leaves the instance.

## Models Used

| Model | Size | Purpose |
|-------|------|---------|
| `llama3.1:8b` | ~4.7 GB | Security log analysis and chat |
| `nomic-embed-text` | ~274 MB | RAG vector embeddings |

## Pulling Models

After starting the Ollama container:

```bash
# Pull main analysis model (~10 minutes on first run)
docker exec ollama ollama pull llama3.1:8b

# Pull embedding model for RAG
docker exec ollama ollama pull nomic-embed-text

# Verify models are available
docker exec ollama ollama list
```

## GPU Acceleration

The docker-compose.yml configures NVIDIA GPU support automatically when:
- The instance type is `g4dn.xlarge` (Tesla T4, 16GB VRAM)
- NVIDIA Container Toolkit is installed (done by EC2 user-data script)

To verify GPU is being used:
```bash
docker exec ollama nvidia-smi
```

## CPU Fallback

For `t3.xlarge` instances, remove or comment out the `deploy.resources.reservations.devices`
block in `docker-compose.yml`. Inference will be slower (~200 tok/s vs ~800 tok/s).

## Model Configuration

Models are stored in a named Docker volume (`ollama-data`) so they persist across
container restarts and don't need to be re-downloaded.

## Alternative Models

| Model | Size | Quality | Notes |
|-------|------|---------|-------|
| `llama3.1:8b` | 4.7GB | Good | Default, fits T4 GPU |
| `llama3.1:70b` | 40GB | Excellent | Needs p3.8xlarge |
| `mistral:7b` | 4.1GB | Good | Alternative to llama3 |
| `mixtral:8x7b` | 26GB | Very Good | Needs large GPU |
