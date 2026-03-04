"""
CNAP AI SIEM Copilot — RAG Agent Main Entry Point

Runs a scheduled security log analysis loop:
  1. Query OpenSearch for recent logs
  2. Retrieve relevant context from RAG knowledge base
  3. Generate analysis report with Ollama LLM
  4. Save report to local filesystem and S3

Usage:
    python main.py
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from opensearch_client import OpenSearchClient
from rag_pipeline import RAGPipeline

# ---------------------------------------------------------------------------
# Logging — structured JSON format
# ---------------------------------------------------------------------------

class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


def configure_logging(level: str = "INFO") -> None:
    """Configure root logger with JSON output to stdout.

    Args:
        level: Logging level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration loading
# ---------------------------------------------------------------------------

def load_config(config_path: str = "/app/config.yaml") -> dict:
    """Load YAML configuration and merge with environment variable overrides.

    Environment variables take precedence over YAML values.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        Merged configuration dictionary.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If required variables are missing.
    """
    # Load YAML defaults
    path = Path(config_path)
    if path.exists():
        with path.open() as f:
            config = yaml.safe_load(f) or {}
    else:
        logger.warning("Config file not found at %s, using environment variables only", config_path)
        config = {}

    # Environment variable overrides (always take priority)
    env_map = {
        "OPENSEARCH_ENDPOINT": ("opensearch", "endpoint"),
        "OPENSEARCH_INDICES": ("opensearch", "indices"),
        "AWS_REGION": ("aws", "region"),
        "S3_KNOWLEDGE_BUCKET": ("s3", "knowledge_bucket"),
        "S3_BACKUP_BUCKET": ("s3", "backup_bucket"),
        "OLLAMA_BASE_URL": ("ollama", "base_url"),
        "MODEL_NAME": ("ollama", "model_name"),
        "EMBEDDING_MODEL": ("ollama", "embedding_model"),
        "TIME_RANGE_HOURS": ("analysis", "time_range_hours"),
        "INTERVAL_MINUTES": ("analysis", "interval_minutes"),
        "ENABLE_RAG": ("rag", "enabled"),
        "RAG_TOP_K": ("rag", "top_k"),
        "OUTPUT_DIR": ("output", "dir"),
        "LOG_LEVEL": ("logging", "level"),
    }

    for env_var, (section, key) in env_map.items():
        value = os.environ.get(env_var)
        if value is not None:
            config.setdefault(section, {})[key] = value

    # Type coercions
    try:
        config.setdefault("analysis", {})["time_range_hours"] = int(
            config.get("analysis", {}).get("time_range_hours", 720)
        )
        config["analysis"]["interval_minutes"] = int(
            config.get("analysis", {}).get("interval_minutes", 30)
        )
        config.setdefault("rag", {})["top_k"] = int(config.get("rag", {}).get("top_k", 3))
        rag_enabled = config.get("rag", {}).get("enabled", "true")
        config["rag"]["enabled"] = str(rag_enabled).lower() in ("true", "1", "yes")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid numeric configuration value: {exc}") from exc

    # Validate required fields
    required = [
        ("opensearch", "endpoint"),
        ("aws", "region"),
        ("ollama", "base_url"),
        ("ollama", "model_name"),
        ("output", "dir"),
    ]
    missing = [f"{s}.{k}" for s, k in required if not config.get(s, {}).get(k)]
    if missing:
        raise ValueError(f"Missing required configuration values: {missing}")

    return config


# ---------------------------------------------------------------------------
# Analysis run
# ---------------------------------------------------------------------------

def run_analysis(
    opensearch_client: OpenSearchClient,
    rag_pipeline: RAGPipeline,
    config: dict,
) -> None:
    """Execute one full analysis cycle and save results.

    Args:
        opensearch_client: Initialised OpenSearch client.
        rag_pipeline: Initialised RAG pipeline.
        config: Configuration dictionary.
    """
    run_start = datetime.now(timezone.utc)
    timestamp = run_start.strftime("%Y%m%d_%H%M%S")
    output_dir = Path(config["output"]["dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Starting analysis run", extra={"timestamp": timestamp})

    # 1. Query logs from OpenSearch
    indices = config.get("opensearch", {}).get("indices", "cwl-*,appgate-logs-*,security-logs-*")
    time_range_hours = config["analysis"]["time_range_hours"]
    max_results = config.get("analysis", {}).get("max_results", 500)

    try:
        logs = opensearch_client.query_logs(
            indices=indices,
            time_range_hours=time_range_hours,
            max_results=max_results,
        )
        logger.info("Retrieved %d log entries from OpenSearch", len(logs))
    except Exception as exc:
        logger.error("Failed to query OpenSearch: %s", exc, exc_info=True)
        logs = []

    if not logs:
        logger.warning("No logs retrieved; skipping analysis run")
        return

    # 2. Retrieve RAG context
    rag_context = ""
    citations: list[dict] = []
    if config["rag"]["enabled"]:
        try:
            context_docs = rag_pipeline.retrieve_context(
                query=_build_rag_query(logs),
                k=config["rag"]["top_k"],
            )
            rag_context = "\n\n---\n\n".join(d["text"] for d in context_docs)
            citations = [{"source": d["source"], "score": d.get("score", 0.0)} for d in context_docs]
            logger.info("Retrieved %d RAG context documents", len(context_docs))
        except Exception as exc:
            logger.warning("RAG context retrieval failed (continuing without): %s", exc)

    # 3. Generate analysis with Ollama
    try:
        analysis_text = rag_pipeline.generate_analysis(
            logs=logs,
            rag_context=rag_context,
        )
        logger.info("Analysis generation completed (%d chars)", len(analysis_text))
    except Exception as exc:
        logger.error("LLM analysis generation failed: %s", exc, exc_info=True)
        return

    # 4. Build structured output
    duration_seconds = (datetime.now(timezone.utc) - run_start).total_seconds()
    report = {
        "timestamp": run_start.isoformat(),
        "analysis_id": timestamp,
        "duration_seconds": duration_seconds,
        "log_count": len(logs),
        "indices_queried": indices,
        "time_range_hours": time_range_hours,
        "rag_enabled": config["rag"]["enabled"],
        "citations": citations,
        "analysis": analysis_text,
    }

    # 5. Save to local filesystem
    txt_path = output_dir / f"analysis_{timestamp}.txt"
    json_path = output_dir / f"analysis_{timestamp}.json"

    txt_path.write_text(
        f"CNAP AI SIEM Security Analysis\n"
        f"Generated: {run_start.isoformat()}\n"
        f"Logs Analyzed: {len(logs)}\n"
        f"{'=' * 60}\n\n"
        + analysis_text
        + "\n\nCitations:\n"
        + "\n".join(f"  - {c['source']} (relevance: {c['score']:.2f})" for c in citations),
        encoding="utf-8",
    )
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Report saved: %s", txt_path)

    # 6. Upload to S3
    backup_bucket = config.get("s3", {}).get("backup_bucket")
    if backup_bucket:
        try:
            import boto3  # noqa: PLC0415
            s3 = boto3.client("s3", region_name=config["aws"]["region"])
            for local_path in (txt_path, json_path):
                s3.upload_file(
                    str(local_path),
                    backup_bucket,
                    f"reports/{local_path.name}",
                )
            logger.info("Report uploaded to s3://%s/reports/", backup_bucket)
        except Exception as exc:
            logger.warning("S3 upload failed (report saved locally): %s", exc)


def _build_rag_query(logs: list[dict]) -> str:
    """Build a natural-language RAG search query from recent log data.

    Args:
        logs: List of log event dictionaries from OpenSearch.

    Returns:
        A short query string for vector similarity search.
    """
    # Extract a sample of event types and actions for context
    event_types: set[str] = set()
    actions: set[str] = set()
    for log in logs[:50]:
        src = log.get("_source", {})
        if et := src.get("eventType") or src.get("event_type") or src.get("type"):
            event_types.add(str(et)[:50])
        if ac := src.get("action") or src.get("Action"):
            actions.add(str(ac)[:50])

    parts = ["Security log analysis"]
    if event_types:
        parts.append(f"event types: {', '.join(list(event_types)[:5])}")
    if actions:
        parts.append(f"actions: {', '.join(list(actions)[:5])}")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Signal handling for graceful shutdown
# ---------------------------------------------------------------------------

_shutdown_requested = False


def _handle_signal(signum: int, frame: object) -> None:  # noqa: ARG001
    global _shutdown_requested  # noqa: PLW0603
    logger.info("Shutdown signal %d received; will exit after current run", signum)
    _shutdown_requested = True


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> None:
    """Main entry point — initialise services and run analysis loop."""
    # Register shutdown handlers
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    # Load configuration
    try:
        config = load_config()
    except (FileNotFoundError, ValueError) as exc:
        print(f"FATAL: Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)

    configure_logging(config.get("logging", {}).get("level", "INFO"))
    logger.info("CNAP AI SIEM Copilot RAG Agent starting")
    logger.info(
        "Configuration loaded",
        extra={
            "opensearch_endpoint": config.get("opensearch", {}).get("endpoint", "NOT SET"),
            "model": config.get("ollama", {}).get("model_name"),
            "interval_minutes": config["analysis"]["interval_minutes"],
            "rag_enabled": config["rag"]["enabled"],
        },
    )

    # Initialise services
    opensearch_client = OpenSearchClient(
        endpoint=config["opensearch"]["endpoint"],
        region=config["aws"]["region"],
        use_iam_auth=True,
    )

    rag_pipeline = RAGPipeline(
        opensearch_client=opensearch_client,
        s3_bucket=config.get("s3", {}).get("knowledge_bucket"),
        ollama_base_url=config["ollama"]["base_url"],
        model_name=config["ollama"]["model_name"],
        embedding_model=config["ollama"]["embedding_model"],
        region=config["aws"]["region"],
        top_k=config["rag"]["top_k"],
    )

    # Sync knowledge base on startup
    if config["rag"]["enabled"]:
        try:
            rag_pipeline.sync_knowledge_base()
        except Exception as exc:
            logger.warning("Initial knowledge base sync failed: %s", exc)

    interval_seconds = config["analysis"]["interval_minutes"] * 60
    logger.info("Starting analysis loop (interval: %d minutes)", config["analysis"]["interval_minutes"])

    while not _shutdown_requested:
        try:
            run_analysis(opensearch_client, rag_pipeline, config)
        except Exception as exc:
            logger.error("Unhandled error in analysis run: %s", exc, exc_info=True)

        if _shutdown_requested:
            break

        logger.info("Sleeping for %d seconds until next run", interval_seconds)
        # Sleep in small increments to respond promptly to shutdown signals
        for _ in range(interval_seconds):
            if _shutdown_requested:
                break
            time.sleep(1)

    logger.info("RAG Agent shut down cleanly")


if __name__ == "__main__":
    main()
