"""
CNAP AI SIEM Copilot — S3 Knowledge Base Loader

Handles downloading, parsing, and chunking of security runbooks and SOPs
from S3 for ingestion into the OpenSearch RAG vector index.

Supported file types: .md, .txt, .pdf (text extraction)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator

import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

# S3 prefixes to search for knowledge base documents
_KNOWLEDGE_PREFIXES = ["runbooks/", "sops/", "playbooks/", ""]
# Supported file extensions
_SUPPORTED_EXTENSIONS = {".md", ".txt", ".pdf"}
# Local cache directory for downloaded files
_CACHE_DIR = Path("/tmp/knowledge-cache")  # noqa: S108


class S3KnowledgeBase:
    """Downloads and parses knowledge base documents from S3.

    Args:
        bucket: S3 bucket name containing knowledge base documents.
        region: AWS region string.
    """

    def __init__(self, bucket: str, region: str) -> None:
        self._bucket = bucket
        self._region = region
        self._s3 = boto3.client("s3", region_name=region)
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        logger.info("S3KnowledgeBase initialised for bucket: s3://%s", bucket)

    def sync_documents(self) -> list[dict]:
        """Download all knowledge base documents from S3.

        Downloads only new or changed files (ETag-based cache validation).

        Returns:
            List of document dicts with keys 'source', 'content', 'metadata'.

        Raises:
            RuntimeError: If S3 access fails.
        """
        documents = []
        try:
            s3_keys = list(self._list_documents())
        except (BotoCoreError, ClientError) as exc:
            raise RuntimeError(f"Failed to list S3 knowledge base documents: {exc}") from exc

        logger.info("Found %d documents in S3 knowledge base", len(s3_keys))

        for key in s3_keys:
            try:
                content = self._download_document(key)
                if content:
                    documents.append({
                        "source": f"s3://{self._bucket}/{key}",
                        "content": content,
                        "metadata": {"s3_key": key, "bucket": self._bucket},
                    })
            except Exception as exc:
                logger.warning("Skipping document %s: %s", key, exc)
                continue

        logger.info("Loaded %d knowledge base documents", len(documents))
        return documents

    def _list_documents(self) -> Iterator[str]:
        """List all supported document keys in the S3 bucket.

        Yields:
            S3 object keys for supported document types.
        """
        paginator = self._s3.get_paginator("list_objects_v2")
        seen: set[str] = set()

        for page in paginator.paginate(Bucket=self._bucket):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                ext = Path(key).suffix.lower()
                if ext in _SUPPORTED_EXTENSIONS and key not in seen:
                    seen.add(key)
                    yield key

    def _download_document(self, key: str) -> str | None:
        """Download and extract text from an S3 document.

        Uses local cache to avoid re-downloading unchanged files.

        Args:
            key: S3 object key.

        Returns:
            Extracted text content, or None if extraction fails.
        """
        # Build cache path
        safe_name = key.replace("/", "_").replace(" ", "_")
        cache_path = _CACHE_DIR / safe_name

        # Check if cached version is current (compare ETag)
        etag_path = cache_path.with_suffix(cache_path.suffix + ".etag")
        try:
            head = self._s3.head_object(Bucket=self._bucket, Key=key)
            remote_etag = head.get("ETag", "").strip('"')
            if cache_path.exists() and etag_path.exists():
                local_etag = etag_path.read_text().strip()
                if local_etag == remote_etag:
                    logger.debug("Using cached document: %s", key)
                    return cache_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass  # Fall through to download

        # Download from S3
        logger.debug("Downloading document: s3://%s/%s", self._bucket, key)
        response = self._s3.get_object(Bucket=self._bucket, Key=key)
        raw_bytes = response["Body"].read()
        etag = response.get("ETag", "").strip('"')

        # Extract text based on file type
        ext = Path(key).suffix.lower()
        text: str | None = None

        if ext in (".md", ".txt"):
            text = raw_bytes.decode("utf-8", errors="replace")
        elif ext == ".pdf":
            text = _extract_pdf_text(raw_bytes, key)

        if text:
            # Cache to local filesystem
            cache_path.write_text(text, encoding="utf-8")
            etag_path.write_text(etag)

        return text


def _extract_pdf_text(raw_bytes: bytes, key: str) -> str | None:
    """Extract plain text from PDF bytes.

    Attempts to use pypdf first; falls back gracefully if not available.

    Args:
        raw_bytes: Raw PDF file bytes.
        key: S3 key (for logging only).

    Returns:
        Extracted text string, or None if extraction fails.
    """
    try:
        import io  # noqa: PLC0415

        from pypdf import PdfReader  # noqa: PLC0415

        reader = PdfReader(io.BytesIO(raw_bytes))
        pages = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                pages.append(page_text)
        return "\n\n".join(pages) or None
    except ImportError:
        logger.warning(
            "pypdf not installed; skipping PDF extraction for %s. Install with: pip install pypdf",
            key,
        )
        return None
    except Exception as exc:
        logger.warning("PDF extraction failed for %s: %s", key, exc)
        return None
