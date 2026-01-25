"""Tests for HTTP client wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from homelab_taskkit.clients.http import HTTPResponse, _redact_url, request
from homelab_taskkit.errors import HTTPError, TimeoutError


class TestHTTPResponse:
    """Tests for HTTPResponse dataclass."""

    def test_ok_true_for_200(self):
        response = HTTPResponse(
            status_code=200,
            body='{"ok": true}',
            json={"ok": True},
            headers={"content-type": "application/json"},
        )
        assert response.ok is True

    def test_ok_true_for_201(self):
        response = HTTPResponse(
            status_code=201,
            body='{"id": 123}',
            json={"id": 123},
            headers={},
        )
        assert response.ok is True

    def test_ok_false_for_404(self):
        response = HTTPResponse(
            status_code=404,
            body="Not found",
            json=None,
            headers={},
        )
        assert response.ok is False

    def test_ok_false_for_500(self):
        response = HTTPResponse(
            status_code=500,
            body="Internal error",
            json=None,
            headers={},
        )
        assert response.ok is False


class TestRequest:
    """Tests for request function."""

    def test_successful_get_request(self):
        mock_client = MagicMock(spec=httpx.Client)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"data": "value"}'
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"data": "value"}
        mock_client.request.return_value = mock_response

        result = request(mock_client, "GET", "https://api.example.com/data")

        assert result.status_code == 200
        assert result.ok is True
        assert result.json == {"data": "value"}
        mock_client.request.assert_called_once_with(
            method="GET",
            url="https://api.example.com/data",
            headers=None,
            json=None,
            timeout=None,
        )

    def test_post_with_json_body(self):
        mock_client = MagicMock(spec=httpx.Client)
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.text = '{"id": 1}'
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"id": 1}
        mock_client.request.return_value = mock_response

        result = request(
            mock_client,
            "POST",
            "https://api.example.com/items",
            json_body={"name": "test"},
        )

        assert result.status_code == 201
        mock_client.request.assert_called_once_with(
            method="POST",
            url="https://api.example.com/items",
            headers=None,
            json={"name": "test"},
            timeout=None,
        )

    def test_custom_headers(self):
        mock_client = MagicMock(spec=httpx.Client)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_response.headers = {}
        mock_client.request.return_value = mock_response

        request(
            mock_client,
            "GET",
            "https://api.example.com",
            headers={"Authorization": "Bearer token"},
        )

        mock_client.request.assert_called_once_with(
            method="GET",
            url="https://api.example.com",
            headers={"Authorization": "Bearer token"},
            json=None,
            timeout=None,
        )

    def test_timeout_raises_timeout_error(self):
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.request.side_effect = httpx.TimeoutException("Request timed out")
        mock_client.timeout = MagicMock(connect=30.0)

        with pytest.raises(TimeoutError) as exc_info:
            request(mock_client, "GET", "https://slow.example.com")

        assert "timed out" in str(exc_info.value)

    def test_request_error_raises_http_error(self):
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.request.side_effect = httpx.RequestError("Connection refused")

        with pytest.raises(HTTPError) as exc_info:
            request(mock_client, "GET", "https://unreachable.example.com")

        assert "Request failed" in str(exc_info.value)

    def test_non_json_response(self):
        mock_client = MagicMock(spec=httpx.Client)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>Hello</html>"
        mock_response.headers = {"content-type": "text/html"}
        mock_client.request.return_value = mock_response

        result = request(mock_client, "GET", "https://example.com")

        assert result.json is None
        assert result.body == "<html>Hello</html>"


class TestRedactUrl:
    """Tests for URL redaction."""

    def test_redacts_discord_webhook(self):
        url = "https://discord.com/api/webhooks/123456/abc123secret"
        redacted = _redact_url(url)
        assert "abc123secret" not in redacted
        assert "***" in redacted

    def test_redacts_discordapp_webhook(self):
        url = "https://discordapp.com/api/webhooks/123456/abc123secret"
        redacted = _redact_url(url)
        assert "abc123secret" not in redacted

    def test_redacts_slack_webhook(self):
        url = "https://hooks.slack.com/services/T00/B00/secret123"
        redacted = _redact_url(url)
        assert "secret123" not in redacted

    def test_non_webhook_urls_unchanged(self):
        url = "https://api.example.com/data?key=value"
        redacted = _redact_url(url)
        assert redacted == url
