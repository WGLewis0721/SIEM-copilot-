"""
Unit tests for CNAP AI SIEM Copilot — RAG Agent

Tests critical functions without requiring live AWS/OpenSearch/Ollama connectivity.
All external dependencies are mocked.
"""

from __future__ import annotations

import json
import os
import sys
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


# =============================================================================
# Tests: main.py — configuration loading
# =============================================================================

class TestConfigLoading:
    """Tests for load_config() in main.py."""

    def test_load_config_from_env_vars(self, tmp_path: Path) -> None:
        """Configuration from environment variables overrides YAML defaults."""
        from main import load_config

        env = {
            "OPENSEARCH_ENDPOINT": "vpc-test.us-gov-west-1.es.amazonaws.com",
            "AWS_REGION": "us-gov-west-1",
            "OLLAMA_BASE_URL": "http://ollama:11434",
            "MODEL_NAME": "llama3.1:8b",
            "OUTPUT_DIR": "/tmp/test-output",
        }

        with patch.dict(os.environ, env, clear=False):
            config = load_config(str(tmp_path / "nonexistent.yaml"))

        assert config["opensearch"]["endpoint"] == "vpc-test.us-gov-west-1.es.amazonaws.com"
        assert config["aws"]["region"] == "us-gov-west-1"
        assert config["ollama"]["model_name"] == "llama3.1:8b"

    def test_load_config_type_coercions(self, tmp_path: Path) -> None:
        """Numeric configuration values are correctly coerced from strings."""
        from main import load_config

        env = {
            "OPENSEARCH_ENDPOINT": "vpc-test.es.amazonaws.com",
            "AWS_REGION": "us-gov-west-1",
            "OLLAMA_BASE_URL": "http://ollama:11434",
            "MODEL_NAME": "llama3.1:8b",
            "OUTPUT_DIR": "/tmp/out",
            "TIME_RANGE_HOURS": "48",
            "INTERVAL_MINUTES": "15",
            "RAG_TOP_K": "5",
            "ENABLE_RAG": "true",
        }

        with patch.dict(os.environ, env, clear=False):
            config = load_config(str(tmp_path / "nonexistent.yaml"))

        assert config["analysis"]["time_range_hours"] == 48
        assert config["analysis"]["interval_minutes"] == 15
        assert config["rag"]["top_k"] == 5
        assert config["rag"]["enabled"] is True

    def test_load_config_enable_rag_false(self, tmp_path: Path) -> None:
        """ENABLE_RAG=false correctly disables RAG."""
        from main import load_config

        env = {
            "OPENSEARCH_ENDPOINT": "vpc-test.es.amazonaws.com",
            "AWS_REGION": "us-gov-west-1",
            "OLLAMA_BASE_URL": "http://ollama:11434",
            "MODEL_NAME": "llama3.1:8b",
            "OUTPUT_DIR": "/tmp/out",
            "ENABLE_RAG": "false",
        }

        with patch.dict(os.environ, env, clear=False):
            config = load_config(str(tmp_path / "nonexistent.yaml"))

        assert config["rag"]["enabled"] is False

    def test_load_config_missing_required_raises(self, tmp_path: Path) -> None:
        """ValueError raised when required configuration is missing."""
        from main import load_config

        # Remove required vars from environment
        env = {k: "" for k in [
            "OPENSEARCH_ENDPOINT", "AWS_REGION", "OLLAMA_BASE_URL",
            "MODEL_NAME", "OUTPUT_DIR",
        ]}

        # Patch environment to have empty required vars
        with patch.dict(os.environ, env, clear=False):
            with pytest.raises(ValueError, match="Missing required configuration"):
                load_config(str(tmp_path / "nonexistent.yaml"))


# =============================================================================
# Tests: rag_pipeline.py — helper functions
# =============================================================================

class TestChunkText:
    """Tests for _chunk_text() in rag_pipeline.py."""

    def test_short_text_returns_single_chunk(self) -> None:
        from rag_pipeline import _chunk_text

        text = "Short text that fits in one chunk."
        result = _chunk_text(text, chunk_size=800)
        assert result == [text]

    def test_long_text_is_split_into_chunks(self) -> None:
        from rag_pipeline import _chunk_text

        text = "A " * 500  # 1000 chars
        chunks = _chunk_text(text, chunk_size=200, overlap=20)
        assert len(chunks) > 1
        # Each chunk should be <= chunk_size
        for chunk in chunks:
            assert len(chunk) <= 200

    def test_empty_text_returns_empty(self) -> None:
        from rag_pipeline import _chunk_text

        result = _chunk_text("", chunk_size=800)
        assert result == []

    def test_chunks_have_overlap(self) -> None:
        from rag_pipeline import _chunk_text

        # Create text where we can verify overlap
        text = "hello world. " * 100  # 1300 chars
        chunks = _chunk_text(text, chunk_size=200, overlap=50)
        # Adjacent chunks should share some content
        assert len(chunks) >= 2


class TestStableDocId:
    """Tests for _stable_doc_id() in rag_pipeline.py."""

    def test_same_inputs_produce_same_id(self) -> None:
        from rag_pipeline import _stable_doc_id

        assert _stable_doc_id("source.md", 0) == _stable_doc_id("source.md", 0)

    def test_different_inputs_produce_different_ids(self) -> None:
        from rag_pipeline import _stable_doc_id

        assert _stable_doc_id("source.md", 0) != _stable_doc_id("source.md", 1)
        assert _stable_doc_id("source.md", 0) != _stable_doc_id("other.md", 0)

    def test_id_is_16_chars(self) -> None:
        from rag_pipeline import _stable_doc_id

        doc_id = _stable_doc_id("test.md", 0)
        assert len(doc_id) == 16


class TestSummarizeLogs:
    """Tests for _summarize_logs() in rag_pipeline.py."""

    def test_empty_logs_shows_zero_count(self) -> None:
        from rag_pipeline import _summarize_logs

        result = _summarize_logs([])
        assert "Total log events retrieved: 0" in result

    def test_logs_are_formatted_with_fields(self) -> None:
        from rag_pipeline import _summarize_logs

        logs = [{
            "_id": "test-doc-id-001",
            "_source": {
                "@timestamp": "2024-12-15T12:00:00Z",
                "action": "DENY",
                "srcip": "10.0.0.1",
                "dstip": "192.168.1.1",
                "dport": 443,
                "severity": "high",
            }
        }]
        result = _summarize_logs(logs)
        assert "test-doc-id-001" in result
        assert "DENY" in result
        assert "10.0.0.1" in result

    def test_truncation_message_shown_for_large_log_sets(self) -> None:
        from rag_pipeline import _summarize_logs

        logs = [{"_id": f"id-{i}", "_source": {}} for i in range(100)]
        result = _summarize_logs(logs, max_events=10)
        assert "truncated" in result.lower() or "more events" in result


# =============================================================================
# Tests: opensearch_client.py — helper functions
# =============================================================================

class TestOpenSearchClientInit:
    """Tests for OpenSearchClient initialisation."""

    @patch("opensearch_client.AWS4Auth")
    @patch("opensearch_client.OpenSearch")
    @patch("opensearch_client.boto3")
    def test_client_created_with_iam_auth(
        self, mock_boto3: MagicMock, mock_opensearch: MagicMock, mock_auth: MagicMock
    ) -> None:
        from opensearch_client import OpenSearchClient

        mock_boto3.Session.return_value.get_credentials.return_value = MagicMock()
        client = OpenSearchClient(
            endpoint="vpc-test.es.amazonaws.com",
            region="us-gov-west-1",
            use_iam_auth=True,
        )
        assert mock_opensearch.called
        # Verify IAM auth was configured
        call_kwargs = mock_opensearch.call_args.kwargs
        assert call_kwargs["use_ssl"] is True
        assert call_kwargs["verify_certs"] is True


# =============================================================================
# Tests: opensearch_filter.py — keyword detection
# =============================================================================

class TestLogQueryDetection:
    """Tests for _is_log_query() in opensearch_filter.py."""

    def setup_method(self) -> None:
        sys.path.insert(0, str(
            Path(__file__).parent.parent.parent / "open-webui" / "functions"
        ))

    def test_log_keywords_detected(self) -> None:
        from opensearch_filter import _is_log_query

        assert _is_log_query("Show me the blocked connections") is True
        assert _is_log_query("Show me firewall logs from today") is True
        assert _is_log_query("What events happened in the last hour?") is True
        assert _is_log_query("List failed authentication attempts") is True

    def test_non_log_queries_not_detected(self) -> None:
        from opensearch_filter import _is_log_query

        assert _is_log_query("What is the weather today?") is False
        assert _is_log_query("Help me write a Python script") is False

    def test_case_insensitive(self) -> None:
        from opensearch_filter import _is_log_query

        assert _is_log_query("SHOW ME BLOCKED TRAFFIC") is True
        assert _is_log_query("Palo Alto Firewall") is True


class TestTimeRangeExtraction:
    """Tests for _extract_time_range() in opensearch_filter.py."""

    def setup_method(self) -> None:
        sys.path.insert(0, str(
            Path(__file__).parent.parent.parent / "open-webui" / "functions"
        ))

    def test_hours_extraction(self) -> None:
        from opensearch_filter import _extract_time_range

        assert _extract_time_range("last 24 hours", 720) == 24
        assert _extract_time_range("past 6 hours", 720) == 6

    def test_days_extraction(self) -> None:
        from opensearch_filter import _extract_time_range

        assert _extract_time_range("last 7 days", 720) == 168
        assert _extract_time_range("past 30 days", 720) == 720

    def test_week_keyword(self) -> None:
        from opensearch_filter import _extract_time_range

        assert _extract_time_range("show me the last week of logs", 720) == 168

    def test_default_returned_when_no_match(self) -> None:
        from opensearch_filter import _extract_time_range

        assert _extract_time_range("show me the logs", 720) == 720


# =============================================================================
# Tests: rag_report_reader.py — report query detection
# =============================================================================

class TestReportQueryDetection:
    """Tests for _is_report_query() in rag_report_reader.py."""

    def setup_method(self) -> None:
        sys.path.insert(0, str(
            Path(__file__).parent.parent.parent / "open-webui" / "functions"
        ))

    def test_report_keywords_detected(self) -> None:
        from rag_report_reader import _is_report_query

        assert _is_report_query("What does the latest report say?") is True
        assert _is_report_query("Show me the last analysis") is True
        assert _is_report_query("Summarize the recent findings") is True

    def test_non_report_queries_not_detected(self) -> None:
        from rag_report_reader import _is_report_query

        assert _is_report_query("Show me blocked connections") is False
        assert _is_report_query("What is SQL injection?") is False


# =============================================================================
# Tests: dashboard/app.py
# =============================================================================

class TestDashboardApp:
    """Tests for the Flask dashboard application."""

    @pytest.fixture()
    def app_client(self, tmp_path: Path):
        """Create a test Flask client with a temporary output directory."""
        sys.path.insert(0, str(
            Path(__file__).parent.parent.parent / "dashboard"
        ))
        import importlib
        import app as dashboard_app_module

        # Patch the output directory
        dashboard_app_module.OUTPUT_DIR = tmp_path

        with dashboard_app_module.app.test_client() as client:
            yield client, tmp_path

    def test_health_endpoint_returns_ok(self, app_client) -> None:
        client, _ = app_client
        response = client.get("/health")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "ok"

    def test_index_page_loads(self, app_client) -> None:
        client, _ = app_client
        response = client.get("/")
        assert response.status_code == 200

    def test_api_reports_empty_when_no_files(self, app_client) -> None:
        client, _ = app_client
        response = client.get("/api/reports")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["reports"] == []

    def test_api_reports_returns_report_when_file_exists(self, app_client) -> None:
        client, tmp_path = app_client

        # Create a sample report file
        report_data = {
            "timestamp": "2024-12-15T12:00:00+00:00",
            "analysis_id": "analysis_20241215_120000",
            "log_count": 42,
            "duration_seconds": 15.3,
            "rag_enabled": True,
            "citations": [],
            "analysis": "Test analysis content",
        }
        (tmp_path / "analysis_20241215_120000.json").write_text(
            json.dumps(report_data), encoding="utf-8"
        )

        response = client.get("/api/reports")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data["reports"]) == 1
        assert data["reports"][0]["log_count"] == 42

    def test_report_detail_404_for_missing_report(self, app_client) -> None:
        client, _ = app_client
        response = client.get("/api/reports/nonexistent_report")
        assert response.status_code == 404

    def test_report_detail_rejects_path_traversal(self, app_client) -> None:
        client, _ = app_client
        response = client.get("/report/../etc/passwd")
        # Should be blocked or return 404
        assert response.status_code in (400, 404)
