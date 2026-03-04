"""
CNAP AI SIEM Copilot — RAG Pipeline

Manages the full Retrieval-Augmented Generation workflow:
  1. Sync knowledge base documents from S3
  2. Generate vector embeddings with Ollama nomic-embed-text
  3. Store embeddings in OpenSearch kNN index
  4. Retrieve top-K relevant documents for a query
  5. Construct LLM prompts and generate security analysis
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

import httpx

from opensearch_client import OpenSearchClient
from s3_knowledge import S3KnowledgeBase

logger = logging.getLogger(__name__)

# OpenSearch index for knowledge base embeddings
_KNOWLEDGE_INDEX = "cnap-knowledge-base"
_KNOWLEDGE_INDEX_MAPPINGS = {
    "settings": {
        "index": {
            "knn": True,
            "knn.algo_param.ef_search": 100,
        }
    },
    "mappings": {
        "properties": {
            "embedding": {
                "type": "knn_vector",
                "dimension": 768,  # nomic-embed-text dimension
                "method": {
                    "name": "hnsw",
                    "space_type": "cosinesimil",
                    "engine": "nmslib",
                    "parameters": {"ef_construction": 128, "m": 24},
                },
            },
            "text": {"type": "text"},
            "source": {"type": "keyword"},
            "chunk_index": {"type": "integer"},
            "indexed_at": {"type": "date"},
        }
    },
}

# System prompt loaded from config at runtime
_ANALYSIS_SYSTEM_PROMPT_PATH = Path("/app/prompts/security-analysis.txt")
_FALLBACK_SYSTEM_PROMPT = (
    "You are a senior cybersecurity analyst. Analyze the provided security logs "
    "and identify threats, anomalies, and patterns. Cite specific log entries. "
    "Reference any provided runbook procedures. Format your response with clear "
    "sections: Summary, Threats Detected, Anomalies, Recommendations."
)


class RAGPipeline:
    """Orchestrates RAG-based security log analysis.

    Args:
        opensearch_client: Configured OpenSearch client.
        s3_bucket: S3 bucket name containing knowledge base documents.
        ollama_base_url: Base URL for Ollama API (e.g., 'http://ollama:11434').
        model_name: Name of the Ollama chat model for analysis.
        embedding_model: Name of the Ollama embedding model.
        region: AWS region string.
        top_k: Number of knowledge base chunks to retrieve per query.
    """

    def __init__(
        self,
        opensearch_client: OpenSearchClient,
        s3_bucket: str | None,
        ollama_base_url: str,
        model_name: str,
        embedding_model: str,
        region: str,
        top_k: int = 3,
    ) -> None:
        self._os = opensearch_client
        self._ollama_url = ollama_base_url.rstrip("/")
        self._model = model_name
        self._embed_model = embedding_model
        self._top_k = top_k
        self._system_prompt = self._load_system_prompt()

        self._knowledge_base: S3KnowledgeBase | None = None
        if s3_bucket:
            self._knowledge_base = S3KnowledgeBase(
                bucket=s3_bucket,
                region=region,
            )

        # Ensure kNN index exists in OpenSearch
        self._os.ensure_index(_KNOWLEDGE_INDEX, _KNOWLEDGE_INDEX_MAPPINGS)

    def _load_system_prompt(self) -> str:
        """Load the analysis system prompt from file, or use fallback.

        Returns:
            System prompt string.
        """
        if _ANALYSIS_SYSTEM_PROMPT_PATH.exists():
            return _ANALYSIS_SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
        return _FALLBACK_SYSTEM_PROMPT

    def sync_knowledge_base(self) -> int:
        """Download and index all knowledge base documents from S3.

        Returns:
            Number of document chunks indexed.

        Raises:
            RuntimeError: If S3 sync fails critically.
        """
        if not self._knowledge_base:
            logger.info("No S3 knowledge bucket configured; skipping sync")
            return 0

        documents = self._knowledge_base.sync_documents()
        indexed_count = 0

        for doc in documents:
            chunks = _chunk_text(doc["content"], chunk_size=800, overlap=100)
            for i, chunk_text in enumerate(chunks):
                chunk_id = _stable_doc_id(doc["source"], i)
                embedding = self._embed_text(chunk_text)
                if embedding is None:
                    logger.warning("Skipping chunk %s/%d — embedding failed", doc["source"], i)
                    continue

                from datetime import datetime, timezone  # noqa: PLC0415
                document = {
                    "text": chunk_text,
                    "source": doc["source"],
                    "chunk_index": i,
                    "embedding": embedding,
                    "indexed_at": datetime.now(timezone.utc).isoformat(),
                }
                if self._os.index_document(_KNOWLEDGE_INDEX, chunk_id, document):
                    indexed_count += 1

        logger.info("Indexed %d chunks from knowledge base", indexed_count)
        return indexed_count

    def retrieve_context(self, query: str, k: int | None = None) -> list[dict]:
        """Retrieve top-K relevant knowledge base chunks for a query.

        Args:
            query: Natural language query describing the security context.
            k: Number of results (defaults to self._top_k).

        Returns:
            List of dicts with keys 'text', 'source', 'score'.
        """
        k = k or self._top_k
        embedding = self._embed_text(query)
        if embedding is None:
            logger.warning("Could not generate embedding for RAG query; returning empty context")
            return []

        hits = self._os.vector_search(
            index=_KNOWLEDGE_INDEX,
            embedding=embedding,
            k=k,
        )

        results = []
        for hit in hits:
            source = hit.get("_source", {})
            results.append({
                "text": source.get("text", ""),
                "source": source.get("source", "unknown"),
                "score": hit.get("_score") or 0.0,
            })

        logger.debug("RAG retrieved %d context documents", len(results))
        return results

    def generate_analysis(self, logs: list[dict], rag_context: str = "") -> str:
        """Generate a security analysis report using the LLM.

        Args:
            logs: List of log event dictionaries.
            rag_context: Optional RAG context text to include in the prompt.

        Returns:
            Generated analysis text from the LLM.

        Raises:
            RuntimeError: If Ollama API call fails.
        """
        # Summarize logs for the prompt (avoid sending raw JSON > context window)
        log_summary = _summarize_logs(logs, max_events=50)
        prompt = _build_analysis_prompt(log_summary, rag_context)

        url = f"{self._ollama_url}/api/generate"
        payload = {
            "model": self._model,
            "prompt": prompt,
            "system": self._system_prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,  # Low temperature for deterministic analysis
                "num_predict": 2048,
            },
        }

        try:
            with httpx.Client(timeout=300.0) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("response", "").strip()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Ollama API error during analysis: {exc}") from exc

    def _embed_text(self, text: str) -> list[float] | None:
        """Generate a vector embedding for the given text.

        Args:
            text: Input text to embed.

        Returns:
            List of float values (embedding vector), or None on failure.
        """
        url = f"{self._ollama_url}/api/embeddings"
        payload = {"model": self._embed_model, "prompt": text}

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("embedding")
        except Exception as exc:
            logger.error("Embedding generation failed: %s", exc)
            return None


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """Split text into overlapping chunks for embedding.

    Args:
        text: Full document text.
        chunk_size: Maximum number of characters per chunk.
        overlap: Number of characters to overlap between consecutive chunks.

    Returns:
        List of text chunk strings.
    """
    if not text.strip():
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        # Try to break at a sentence boundary
        if end < len(text):
            boundary = text.rfind(". ", start, end)
            if boundary > start:
                end = boundary + 1
        chunks.append(text[start:end].strip())
        start = end - overlap

    return [c for c in chunks if c]


def _stable_doc_id(source: str, chunk_index: int) -> str:
    """Generate a stable, deterministic document ID for deduplication.

    Args:
        source: Document source path/name.
        chunk_index: Chunk index within the document.

    Returns:
        SHA-256 hex digest (first 16 chars) as document ID.
    """
    raw = f"{source}::{chunk_index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _summarize_logs(logs: list[dict], max_events: int = 50) -> str:
    """Create a concise text summary of log events for the LLM prompt.

    Args:
        logs: List of raw log documents from OpenSearch.
        max_events: Maximum number of log events to include.

    Returns:
        Formatted string summary of log events.
    """
    lines = [f"Total log events retrieved: {len(logs)}", ""]
    for i, log in enumerate(logs[:max_events]):
        src: dict[str, Any] = log.get("_source", {})
        doc_id = log.get("_id", "unknown")
        ts = src.get("@timestamp") or src.get("timestamp", "N/A")
        event_type = src.get("eventType") or src.get("event_type") or src.get("type", "N/A")
        action = src.get("action") or src.get("Action", "N/A")
        src_ip = src.get("srcip") or src.get("src_ip") or src.get("sourceIp", "N/A")
        dst_ip = src.get("dstip") or src.get("dst_ip") or src.get("destinationIp", "N/A")
        dst_port = src.get("dport") or src.get("dst_port") or src.get("destinationPort", "N/A")
        severity = src.get("severity") or src.get("Severity", "N/A")

        lines.append(
            f"[{i + 1}] ID={doc_id} ts={ts} type={event_type} "
            f"action={action} src={src_ip} dst={dst_ip}:{dst_port} severity={severity}"
        )

    if len(logs) > max_events:
        lines.append(f"\n... and {len(logs) - max_events} more events (truncated for prompt)")

    return "\n".join(lines)


def _build_analysis_prompt(log_summary: str, rag_context: str) -> str:
    """Build the final LLM analysis prompt.

    Args:
        log_summary: Concise log summary text.
        rag_context: RAG-retrieved knowledge base context.

    Returns:
        Formatted prompt string.
    """
    parts = ["## Security Log Analysis Request\n"]
    parts.append("### Log Events:\n")
    parts.append(log_summary)

    if rag_context:
        parts.append("\n\n### Relevant Runbooks and Procedures (cite these in your analysis):\n")
        parts.append(rag_context)

    parts.append(
        "\n\n### Analysis Request:\n"
        "Please analyze the above security logs and provide:\n"
        "1. **Executive Summary** — key findings in 3-5 sentences\n"
        "2. **Threats Detected** — specific threats with log evidence (include Document IDs)\n"
        "3. **Anomalies** — unusual patterns, volumes, or behaviours\n"
        "4. **Runbook References** — cite relevant procedures from the knowledge base\n"
        "5. **Recommendations** — prioritized action items with urgency level\n"
    )

    return "\n".join(parts)
