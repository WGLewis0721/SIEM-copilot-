"""
title: CNAP OpenSearch Real-Time Log Query
id: cnap_opensearch_filter
version: 1.0.0
description: >
    Queries AWS OpenSearch on-demand when a user asks about security logs.
    Detects log-related questions, queries OpenSearch with IAM authentication,
    and injects matching log events (with Document IDs) into the LLM context.
author: CNAP Security Team
license: Apache-2.0

requirements: boto3, opensearch-py, requests-aws4auth
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from pydantic import BaseModel, Field
from requests_aws4auth import AWS4Auth

logger = logging.getLogger(__name__)

# Keywords that trigger the OpenSearch query
_LOG_QUERY_KEYWORDS = [
    "log", "logs", "event", "events", "alert", "alerts",
    "firewall", "blocked", "denied", "threat", "attack",
    "palo alto", "appgate", "sdp", "connection", "traffic",
    "authentication", "failed login", "brute force",
    "security event", "incident", "anomaly", "show me",
    "how many", "last hour", "last 24", "last week",
    "top 10", "top 5", "recent", "latest",
]

# Maximum number of log events to include in prompt context
_MAX_LOG_EVENTS = 50


class Filter:
    """OpenSearch real-time log query filter for Open WebUI.

    When the user sends a message containing log-related keywords, this filter
    queries OpenSearch and injects the matching log events as context into the
    LLM prompt, along with their Document IDs for traceability.
    """

    class Valves(BaseModel):
        """Configuration valves — set in Open WebUI Admin Panel."""

        OPENSEARCH_ENDPOINT: str = Field(
            default="",
            description="OpenSearch domain endpoint (without https://)",
        )
        AWS_REGION: str = Field(
            default="us-gov-west-1",
            description="AWS region for IAM authentication",
        )
        TIME_RANGE_HOURS: int = Field(
            default=720,
            description="Default time range in hours for log queries (default: 720 = 30 days)",
        )
        MAX_RESULTS: int = Field(
            default=50,
            description="Maximum number of log events to return per query",
        )
        LOG_INDICES: str = Field(
            default="cwl-*,appgate-logs-*,security-logs-*",
            description="Comma-separated OpenSearch index patterns to query",
        )
        ENABLED: bool = Field(
            default=True,
            description="Enable or disable this filter",
        )

    def __init__(self) -> None:
        self.valves = self.Valves(
            OPENSEARCH_ENDPOINT=os.environ.get("OPENSEARCH_ENDPOINT", ""),
            AWS_REGION=os.environ.get("AWS_REGION", "us-gov-west-1"),
        )

    def inlet(self, body: dict, user: dict | None = None) -> dict:  # noqa: ARG002
        """Pre-process the user message before sending to the LLM.

        If the message contains log-related keywords, queries OpenSearch
        and injects the results into the system context.

        Args:
            body: Open WebUI chat request body.
            user: Current user information (not used).

        Returns:
            Modified body with log context injected, or original body if no
            log keywords detected or query fails.
        """
        if not self.valves.ENABLED:
            return body

        messages = body.get("messages", [])
        if not messages:
            return body

        # Find the most recent user message
        user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                user_message = content if isinstance(content, str) else str(content)
                break

        if not user_message:
            return body

        # Check if this is a log-related query
        if not _is_log_query(user_message):
            return body

        # Validate endpoint is configured
        if not self.valves.OPENSEARCH_ENDPOINT:
            logger.warning("OPENSEARCH_ENDPOINT not configured; skipping log query")
            return body

        # Parse time range from the user message if specified
        time_range = _extract_time_range(user_message, self.valves.TIME_RANGE_HOURS)
        query_filter = _extract_query_filter(user_message)

        # Query OpenSearch
        try:
            log_events = self._query_opensearch(
                query_filter=query_filter,
                time_range_hours=time_range,
                max_results=min(self.valves.MAX_RESULTS, _MAX_LOG_EVENTS),
            )
        except Exception as exc:
            logger.error("OpenSearch query failed: %s", exc)
            # Don't block the LLM response — just continue without log context
            return body

        if not log_events:
            return body

        # Format logs as context and inject into system message
        log_context = _format_log_context(log_events, time_range)
        body = _inject_context(body, log_context)
        logger.info(
            "Injected %d log events into LLM context (time_range=%dh)",
            len(log_events),
            time_range,
        )

        return body

    def _query_opensearch(
        self,
        query_filter: str | None,
        time_range_hours: int,
        max_results: int,
    ) -> list[dict]:
        """Query OpenSearch with IAM authentication.

        Uses boto3 credential chain (instance profile — no hardcoded keys).

        Args:
            query_filter: Optional Lucene query string.
            time_range_hours: Hours of logs to retrieve.
            max_results: Maximum number of results.

        Returns:
            List of log event hit dictionaries.
        """
        session = boto3.Session()
        credentials = session.get_credentials()
        aws_auth = AWS4Auth(
            refreshable_credentials=credentials,
            region=self.valves.AWS_REGION,
            service="es",
        )

        client = OpenSearch(
            hosts=[{"host": self.valves.OPENSEARCH_ENDPOINT, "port": 443}],
            use_ssl=True,
            verify_certs=True,
            http_auth=aws_auth,
            connection_class=RequestsHttpConnection,
            timeout=15,
        )

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

        if query_filter:
            query["query"]["bool"]["must"].append(
                {"query_string": {"query": query_filter, "default_operator": "AND"}}
            )

        response = client.search(
            index=self.valves.LOG_INDICES,
            body=query,
            request_timeout=15,
        )
        return response.get("hits", {}).get("hits", [])


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _is_log_query(message: str) -> bool:
    """Check if the user message is asking about logs or security events.

    Args:
        message: User message text.

    Returns:
        True if the message appears to be a log query.
    """
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in _LOG_QUERY_KEYWORDS)


def _extract_time_range(message: str, default_hours: int) -> int:
    """Parse time range from natural language user message.

    Supports patterns like '24 hours', 'last 7 days', 'past week', etc.

    Args:
        message: User message text.
        default_hours: Default time range if none found.

    Returns:
        Time range in hours.
    """
    msg_lower = message.lower()
    patterns = [
        (r"last\s+(\d+)\s+hour", 1),
        (r"past\s+(\d+)\s+hour", 1),
        (r"(\d+)\s+hour", 1),
        (r"last\s+(\d+)\s+day", 24),
        (r"past\s+(\d+)\s+day", 24),
        (r"(\d+)\s+day", 24),
        (r"last\s+week", None),
        (r"past\s+week", None),
        (r"last\s+month", None),
    ]
    for pattern, multiplier in patterns:
        match = re.search(pattern, msg_lower)
        if match:
            if multiplier is None:
                if "month" in pattern:
                    return 720
                return 168  # 1 week
            return int(match.group(1)) * multiplier
    return default_hours


def _extract_query_filter(message: str) -> str | None:
    """Extract a Lucene query string from the user message.

    Args:
        message: User message text.

    Returns:
        Lucene query string or None.
    """
    msg_lower = message.lower()
    filters = []

    if any(kw in msg_lower for kw in ["block", "blocked", "denied", "deny"]):
        filters.append("action:(DENY OR BLOCK OR REJECT OR DROP)")
    if any(kw in msg_lower for kw in ["critical", "high severity", "severe"]):
        filters.append("severity:(critical OR high OR CRITICAL OR HIGH)")
    if any(kw in msg_lower for kw in ["palo alto", "firewall"]):
        filters.append("_index:cwl-*")
    if any(kw in msg_lower for kw in ["appgate", "sdp", "authentication"]):
        filters.append("_index:appgate-logs-*")
    if any(kw in msg_lower for kw in ["failed", "failure", "error"]):
        filters.append("(action:FAIL* OR status:error OR status:failed)")

    return " AND ".join(filters) if filters else None


def _format_log_context(events: list[dict], time_range_hours: int) -> str:
    """Format log events as structured text for LLM context.

    Args:
        events: List of OpenSearch hit dictionaries.
        time_range_hours: Time range used for the query.

    Returns:
        Formatted string with log events and Document IDs.
    """
    lines = [
        f"## Real-Time Security Log Data (last {time_range_hours}h from OpenSearch)",
        f"Retrieved {len(events)} log events at {_now_utc()}:",
        "",
    ]

    for i, event in enumerate(events):
        doc_id = event.get("_id", "unknown")
        index = event.get("_index", "unknown")
        src: dict = event.get("_source", {})

        ts = src.get("@timestamp") or src.get("timestamp", "N/A")
        event_type = src.get("eventType") or src.get("event_type") or src.get("type", "N/A")
        action = src.get("action") or src.get("Action", "N/A")
        src_ip = src.get("srcip") or src.get("src_ip") or src.get("sourceIp", "N/A")
        dst_ip = src.get("dstip") or src.get("dst_ip") or src.get("destinationIp", "N/A")
        dst_port = src.get("dport") or src.get("dst_port") or src.get("destinationPort", "N/A")
        severity = src.get("severity") or src.get("Severity", "N/A")
        message = src.get("message") or src.get("msg", "")

        lines.append(
            f"[{i + 1}] DocID={doc_id} | Index={index} | ts={ts}"
        )
        lines.append(
            f"     Type={event_type} | Action={action} | Severity={severity}"
        )
        lines.append(
            f"     Src={src_ip} → Dst={dst_ip}:{dst_port}"
        )
        if message:
            lines.append(f"     Message: {str(message)[:200]}")
        lines.append("")

    lines.append("--- End of log data ---")
    lines.append(
        "When referencing specific events in your response, cite them by DocID."
    )
    return "\n".join(lines)


def _inject_context(body: dict, context: str) -> dict:
    """Inject context text as a system message at the start of the conversation.

    Args:
        body: Open WebUI request body.
        context: Context text to inject.

    Returns:
        Modified body with context injected.
    """
    messages = body.get("messages", [])
    context_message = {"role": "system", "content": context}

    # Insert after any existing system message
    if messages and messages[0].get("role") == "system":
        messages.insert(1, context_message)
    else:
        messages.insert(0, context_message)

    body["messages"] = messages
    return body


def _now_utc() -> str:
    """Return current UTC time as ISO 8601 string."""
    from datetime import datetime, timezone  # noqa: PLC0415
    return datetime.now(timezone.utc).isoformat()
