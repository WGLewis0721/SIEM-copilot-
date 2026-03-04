"""
CNAP AI SIEM Copilot — OpenSearch Client

Handles all interaction with the AWS OpenSearch cluster:
  - AWS IAM authentication via boto3 (instance profile — no hardcoded credentials)
  - Connection pooling with retry/backoff
  - Time-range filtered log queries
  - Aggregation queries for pattern detection
  - Vector embedding search for RAG
"""

from __future__ import annotations

import logging
import time
from typing import Any

import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

logger = logging.getLogger(__name__)

# Maximum retries for transient failures
_MAX_RETRIES = 3
_RETRY_BACKOFF_BASE = 2.0  # seconds


class OpenSearchClient:
    """Client for querying AWS OpenSearch with IAM authentication.

    Uses AWS SigV4 signing via boto3 session credentials — compatible
    with EC2 instance profiles (no credentials needed in code).

    Args:
        endpoint: OpenSearch domain endpoint (without https://).
        region: AWS region string (e.g., 'us-gov-west-1').
        use_iam_auth: If True, sign requests with SigV4. Default True.
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        endpoint: str,
        region: str,
        use_iam_auth: bool = True,
        timeout: int = 30,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._region = region
        self._timeout = timeout
        self._client = self._build_client(use_iam_auth)
        logger.info(
            "OpenSearch client initialised",
            extra={"endpoint": self._endpoint, "region": region, "iam_auth": use_iam_auth},
        )

    def _build_client(self, use_iam_auth: bool) -> OpenSearch:
        """Build the OpenSearch HTTP client with optional IAM auth.

        Args:
            use_iam_auth: Whether to sign requests with AWS SigV4.

        Returns:
            Configured OpenSearch client instance.
        """
        kwargs: dict[str, Any] = {
            "hosts": [{"host": self._endpoint, "port": 443}],
            "use_ssl": True,
            "verify_certs": True,
            "connection_class": RequestsHttpConnection,
            "timeout": self._timeout,
            "max_retries": _MAX_RETRIES,
            "retry_on_timeout": True,
        }

        if use_iam_auth:
            session = boto3.Session()
            credentials = session.get_credentials()
            aws_auth = AWS4Auth(
                refreshable_credentials=credentials,
                region=self._region,
                service="es",
            )
            kwargs["http_auth"] = aws_auth

        return OpenSearch(**kwargs)

    def health_check(self) -> bool:
        """Verify OpenSearch cluster is reachable.

        Returns:
            True if cluster is healthy, False otherwise.
        """
        try:
            info = self._client.cluster.health(timeout="5s")
            status = info.get("status", "unknown")
            logger.debug("OpenSearch cluster health: %s", status)
            return status in ("green", "yellow")
        except Exception as exc:
            logger.error("OpenSearch health check failed: %s", exc)
            return False

    def query_logs(
        self,
        indices: str,
        time_range_hours: int = 720,
        query_string: str | None = None,
        max_results: int = 500,
    ) -> list[dict]:
        """Query logs from OpenSearch within the specified time range.

        Args:
            indices: Comma-separated index patterns (e.g., 'cwl-*,appgate-logs-*').
            time_range_hours: Number of hours of logs to retrieve.
            query_string: Optional Lucene query string to filter results.
            max_results: Maximum number of log documents to return.

        Returns:
            List of log event dictionaries from OpenSearch hits.

        Raises:
            RuntimeError: If the query fails after all retries.
        """
        query: dict[str, Any] = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "range": {
                                "@timestamp": {
                                    "gte": f"now-{time_range_hours}h",
                                    "lte": "now",
                                }
                            }
                        }
                    ]
                }
            },
            "sort": [{"@timestamp": {"order": "desc"}}],
            "size": max_results,
        }

        if query_string:
            query["query"]["bool"]["must"].append(
                {"query_string": {"query": query_string, "default_operator": "AND"}}
            )

        return self._execute_search(indices=indices, body=query, description="log query")

    def query_aggregations(
        self,
        indices: str,
        time_range_hours: int = 24,
        group_by_fields: list[str] | None = None,
        top_n: int = 10,
    ) -> dict:
        """Query aggregated statistics for pattern detection.

        Args:
            indices: Comma-separated index patterns.
            time_range_hours: Number of hours to aggregate over.
            group_by_fields: Fields to group by (default: action, srcip, dstport).
            top_n: Number of top values to return per aggregation.

        Returns:
            Dictionary of aggregation results keyed by field name.
        """
        fields = group_by_fields or ["action", "srcip", "dstport", "eventType"]
        aggs: dict[str, Any] = {}
        for field in fields:
            aggs[f"top_{field}"] = {
                "terms": {"field": f"{field}.keyword", "size": top_n}
            }

        body: dict[str, Any] = {
            "query": {
                "range": {
                    "@timestamp": {"gte": f"now-{time_range_hours}h", "lte": "now"}
                }
            },
            "aggs": aggs,
            "size": 0,  # Don't return individual documents
        }

        try:
            response = self._client.search(
                index=indices,
                body=body,
                request_timeout=self._timeout,
            )
            aggregations = response.get("aggregations", {})
            result = {}
            for key, agg_data in aggregations.items():
                field_name = key.replace("top_", "")
                result[field_name] = [
                    {"value": b["key"], "count": b["doc_count"]}
                    for b in agg_data.get("buckets", [])
                ]
            return result
        except Exception as exc:
            logger.error("Aggregation query failed: %s", exc)
            return {}

    def vector_search(
        self,
        index: str,
        embedding: list[float],
        k: int = 5,
        filter_query: dict | None = None,
    ) -> list[dict]:
        """Perform k-NN vector similarity search for RAG context retrieval.

        Args:
            index: Name of the OpenSearch vector index.
            embedding: Query embedding vector (float list).
            k: Number of nearest neighbours to return.
            filter_query: Optional pre-filter query to narrow candidates.

        Returns:
            List of matching documents with their scores.
        """
        knn_body: dict[str, Any] = {
            "size": k,
            "query": {
                "knn": {
                    "embedding": {
                        "vector": embedding,
                        "k": k,
                    }
                }
            },
        }

        if filter_query:
            knn_body["query"] = {
                "bool": {
                    "must": knn_body["query"],
                    "filter": filter_query,
                }
            }

        return self._execute_search(
            indices=index,
            body=knn_body,
            description="vector search",
            include_scores=True,
        )

    def index_document(self, index: str, doc_id: str, document: dict) -> bool:
        """Index or update a single document.

        Args:
            index: Target index name.
            doc_id: Unique document identifier.
            document: Document body to index.

        Returns:
            True if indexed successfully, False otherwise.
        """
        try:
            response = self._client.index(
                index=index,
                body=document,
                id=doc_id,
                refresh="false",
                request_timeout=self._timeout,
            )
            return response.get("result") in ("created", "updated")
        except Exception as exc:
            logger.error("Failed to index document %s in %s: %s", doc_id, index, exc)
            return False

    def ensure_index(self, index: str, mappings: dict) -> bool:
        """Create index with specified mappings if it does not exist.

        Args:
            index: Index name to create.
            mappings: OpenSearch index mappings and settings.

        Returns:
            True if index exists or was created successfully.
        """
        try:
            if self._client.indices.exists(index=index):
                return True
            self._client.indices.create(index=index, body=mappings)
            logger.info("Created OpenSearch index: %s", index)
            return True
        except Exception as exc:
            logger.error("Failed to create index %s: %s", index, exc)
            return False

    def _execute_search(
        self,
        indices: str,
        body: dict,
        description: str,
        include_scores: bool = False,
    ) -> list[dict]:
        """Execute a search query with retry logic and exponential backoff.

        Args:
            indices: Comma-separated index patterns.
            body: OpenSearch query DSL body.
            description: Human-readable description for log messages.
            include_scores: If True, include _score in returned documents.

        Returns:
            List of document dictionaries from search hits.

        Raises:
            RuntimeError: If all retries are exhausted.
        """
        last_exception: Exception | None = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = self._client.search(
                    index=indices,
                    body=body,
                    request_timeout=self._timeout,
                )
                hits = response.get("hits", {}).get("hits", [])
                if include_scores:
                    return [{"_id": h["_id"], "_source": h["_source"], "_score": h.get("_score")} for h in hits]
                return hits
            except Exception as exc:
                last_exception = exc
                wait = _RETRY_BACKOFF_BASE ** attempt
                logger.warning(
                    "OpenSearch %s attempt %d/%d failed: %s — retrying in %.1fs",
                    description,
                    attempt,
                    _MAX_RETRIES,
                    exc,
                    wait,
                )
                time.sleep(wait)

        raise RuntimeError(
            f"OpenSearch {description} failed after {_MAX_RETRIES} attempts: {last_exception}"
        ) from last_exception
