"""Tests for the http_request task."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from homelab_taskkit.tasks.http_request import run


class TestHttpRequestTask:
    """Tests for http_request task function."""

    def test_successful_get_request(self, fake_deps, sample_http_input):
        """Task should return success for 2xx responses."""
        result = run(sample_http_input, fake_deps)

        assert result["status_code"] == 200
        assert result["success"] is True
        assert result["body"] == {"test": "data"}
        assert "elapsed_ms" in result

    def test_calls_http_client(self, fake_deps, sample_http_input):
        """Task should call the injected HTTP client."""
        run(sample_http_input, fake_deps)

        fake_deps.http.request.assert_called_once_with(
            method="GET",
            url="https://api.example.com/data",
            headers={"Authorization": "Bearer test"},
            json=None,
            timeout=30.0,
        )

    def test_post_request_with_body(self, fake_deps):
        """Task should send JSON body for POST requests."""
        inputs = {
            "url": "https://api.example.com/data",
            "method": "POST",
            "body": {"key": "value"},
        }

        run(inputs, fake_deps)

        fake_deps.http.request.assert_called_once_with(
            method="POST",
            url="https://api.example.com/data",
            headers={},
            json={"key": "value"},
            timeout=30.0,
        )

    def test_custom_timeout(self, fake_deps):
        """Task should use custom timeout when provided."""
        inputs = {
            "url": "https://api.example.com/data",
            "timeout": 60.0,
        }

        run(inputs, fake_deps)

        _, kwargs = fake_deps.http.request.call_args
        assert kwargs["timeout"] == 60.0

    def test_error_response_not_success(self, fake_deps):
        """Task should mark non-2xx responses as not successful."""
        fake_deps.http.request.return_value = MagicMock(
            status_code=404,
            json=lambda: {"error": "not found"},
            text="not found",
            headers={},
            elapsed=MagicMock(total_seconds=lambda: 0.1),
        )

        result = run({"url": "https://api.example.com/missing"}, fake_deps)

        assert result["status_code"] == 404
        assert result["success"] is False

    def test_timeout_raises_runtime_error(self, fake_deps):
        """Task should raise RuntimeError on timeout."""
        fake_deps.http.request.side_effect = httpx.TimeoutException("timed out")

        with pytest.raises(RuntimeError, match="timed out"):
            run({"url": "https://api.example.com/slow"}, fake_deps)

    def test_network_error_raises_runtime_error(self, fake_deps):
        """Task should raise RuntimeError on network error."""
        fake_deps.http.request.side_effect = httpx.RequestError("connection failed")

        with pytest.raises(RuntimeError, match="failed"):
            run({"url": "https://api.example.com/unreachable"}, fake_deps)

    def test_text_response_when_not_json(self, fake_deps):
        """Task should fall back to text when response is not JSON."""
        fake_deps.http.request.return_value = MagicMock(
            status_code=200,
            json=MagicMock(side_effect=ValueError("not json")),
            text="plain text response",
            headers={},
            elapsed=MagicMock(total_seconds=lambda: 0.1),
        )

        result = run({"url": "https://api.example.com/text"}, fake_deps)

        assert result["body"] == "plain text response"
