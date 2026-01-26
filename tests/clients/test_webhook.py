"""Tests for webhook client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from homelab_taskkit.clients.http import HTTPResponse
from homelab_taskkit.clients.webhook import (
    WebhookPayload,
    _build_discord_payload,
    _build_slack_payload,
    detect_webhook_type,
    send_webhook,
)
from homelab_taskkit.errors import WebhookError


class TestDetectWebhookType:
    """Tests for webhook type detection."""

    def test_detects_discord(self):
        assert detect_webhook_type("https://discord.com/api/webhooks/123/token") == "discord"

    def test_detects_discordapp(self):
        assert detect_webhook_type("https://discordapp.com/api/webhooks/123/token") == "discord"

    def test_detects_slack(self):
        assert detect_webhook_type("https://hooks.slack.com/services/T00/B00/xxx") == "slack"

    def test_unknown_for_other_urls(self):
        assert detect_webhook_type("https://example.com/webhook") == "unknown"


class TestWebhookPayload:
    """Tests for WebhookPayload dataclass."""

    def test_minimal_payload(self):
        payload = WebhookPayload(message="Hello")
        assert payload.message == "Hello"
        assert payload.username == "Homelab Tasks"
        assert payload.title is None
        assert payload.color is None
        assert payload.fields == []

    def test_full_payload(self):
        payload = WebhookPayload(
            message="Test message",
            title="Test Title",
            color="#00ff00",
            fields=[{"name": "Field1", "value": "Value1"}],
            username="Bot",
            avatar_url="https://example.com/avatar.png",
        )
        assert payload.title == "Test Title"
        assert payload.color == "#00ff00"
        assert len(payload.fields) == 1


class TestBuildDiscordPayload:
    """Tests for Discord payload building."""

    def test_simple_message(self):
        payload = WebhookPayload(message="Hello world")
        result = _build_discord_payload(payload)

        assert result["username"] == "Homelab Tasks"
        assert result["content"] == "Hello world"
        assert "embeds" not in result

    def test_message_with_embed(self):
        payload = WebhookPayload(
            message="Description",
            title="Title",
            color="#ff0000",
        )
        result = _build_discord_payload(payload)

        assert "embeds" in result
        assert len(result["embeds"]) == 1
        embed = result["embeds"][0]
        assert embed["title"] == "Title"
        assert embed["description"] == "Description"
        assert embed["color"] == 0xFF0000  # Converted from hex

    def test_message_with_fields(self):
        payload = WebhookPayload(
            message="Test",
            fields=[
                {"name": "Status", "value": "OK", "inline": True},
                {"name": "Duration", "value": "5s"},
            ],
        )
        result = _build_discord_payload(payload)

        embed = result["embeds"][0]
        assert len(embed["fields"]) == 2
        assert embed["fields"][0]["inline"] is True
        assert embed["fields"][1]["inline"] is False

    def test_custom_avatar(self):
        payload = WebhookPayload(
            message="Test",
            avatar_url="https://example.com/avatar.png",
        )
        result = _build_discord_payload(payload)

        assert result["avatar_url"] == "https://example.com/avatar.png"


class TestBuildSlackPayload:
    """Tests for Slack payload building."""

    def test_simple_message(self):
        payload = WebhookPayload(message="Hello world")
        result = _build_slack_payload(payload)

        assert result["username"] == "Homelab Tasks"
        assert result["text"] == "Hello world"
        assert "attachments" not in result

    def test_message_with_attachment(self):
        payload = WebhookPayload(
            message="Description",
            title="Title",
            color="#ff0000",
        )
        result = _build_slack_payload(payload)

        assert "attachments" in result
        assert len(result["attachments"]) == 1
        attach = result["attachments"][0]
        assert attach["title"] == "Title"
        assert attach["text"] == "Description"
        assert attach["color"] == "ff0000"  # No # prefix for Slack

    def test_fields_use_short_instead_of_inline(self):
        payload = WebhookPayload(
            message="Test",
            fields=[{"name": "Status", "value": "OK", "inline": True}],
        )
        result = _build_slack_payload(payload)

        attach = result["attachments"][0]
        assert attach["fields"][0]["short"] is True


class TestSendWebhook:
    """Tests for send_webhook function."""

    @patch("homelab_taskkit.clients.webhook.request")
    def test_successful_send(self, mock_request):
        mock_response = HTTPResponse(
            status_code=204,
            body="",
            json=None,
            headers={},
            elapsed_ms=50.0,
        )
        mock_request.return_value = mock_response

        mock_client = MagicMock(spec=httpx.Client)
        payload = WebhookPayload(message="Test")

        result = send_webhook(
            mock_client,
            "https://discord.com/api/webhooks/123/token",
            payload,
        )

        assert result.status_code == 204
        mock_request.assert_called_once()

    @patch("homelab_taskkit.clients.webhook.request")
    def test_error_response_raises_webhook_error(self, mock_request):
        mock_response = HTTPResponse(
            status_code=400,
            body='{"message": "Invalid webhook"}',
            json={"message": "Invalid webhook"},
            headers={},
            elapsed_ms=25.0,
        )
        mock_request.return_value = mock_response

        mock_client = MagicMock(spec=httpx.Client)
        payload = WebhookPayload(message="Test")

        with pytest.raises(WebhookError) as exc_info:
            send_webhook(
                mock_client,
                "https://discord.com/api/webhooks/123/token",
                payload,
            )

        assert exc_info.value.status_code == 400
        assert exc_info.value.webhook_type == "discord"

    @patch("homelab_taskkit.clients.webhook.request")
    def test_request_exception_raises_webhook_error(self, mock_request):
        mock_request.side_effect = Exception("Network error")

        mock_client = MagicMock(spec=httpx.Client)
        payload = WebhookPayload(message="Test")

        with pytest.raises(WebhookError) as exc_info:
            send_webhook(
                mock_client,
                "https://hooks.slack.com/services/xxx",
                payload,
            )

        assert exc_info.value.webhook_type == "slack"
