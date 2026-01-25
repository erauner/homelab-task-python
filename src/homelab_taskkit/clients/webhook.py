"""Webhook client for Discord/Slack notifications.

Provides payload building and delivery for common webhook types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from homelab_taskkit.clients.http import HTTPResponse, request
from homelab_taskkit.errors import WebhookError


@dataclass
class WebhookPayload:
    """Structured webhook payload.

    Works with Discord, Slack, and generic webhooks.

    Attributes:
        message: Main message text
        title: Optional title for embed/attachment
        color: Hex color (e.g., '#00ff00')
        fields: List of {name, value, inline} dicts
        username: Bot username override
        avatar_url: Bot avatar URL (Discord only)
    """

    message: str
    title: str | None = None
    color: str | None = None
    fields: list[dict[str, Any]] = field(default_factory=list)
    username: str = "Homelab Tasks"
    avatar_url: str | None = None


def detect_webhook_type(url: str) -> str:
    """Detect webhook type from URL.

    Returns:
        'discord', 'slack', or 'unknown'
    """
    if "discord.com/api/webhooks" in url or "discordapp.com/api/webhooks" in url:
        return "discord"
    elif "hooks.slack.com" in url:
        return "slack"
    return "unknown"


def send_webhook(
    client: httpx.Client,
    url: str,
    payload: WebhookPayload,
    *,
    timeout: float = 30.0,
) -> HTTPResponse:
    """Send a webhook notification.

    Automatically detects webhook type and builds appropriate payload.

    Args:
        client: httpx.Client instance (from deps.http)
        url: Webhook URL (Discord, Slack, or generic)
        payload: WebhookPayload with message content
        timeout: Request timeout in seconds

    Returns:
        HTTPResponse from the webhook endpoint

    Raises:
        WebhookError: If webhook delivery fails
    """
    webhook_type = detect_webhook_type(url)

    if webhook_type == "discord":
        body = _build_discord_payload(payload)
    elif webhook_type == "slack":
        body = _build_slack_payload(payload)
    else:
        body = _build_generic_payload(payload)

    try:
        response = request(
            client,
            "POST",
            url,
            json_body=body,
            headers={"Content-Type": "application/json"},
            timeout=timeout,
        )
    except Exception as e:
        raise WebhookError(
            f"Failed to deliver {webhook_type} webhook: {e}",
            webhook_type=webhook_type,
        ) from e

    if not response.ok:
        raise WebhookError(
            "Webhook returned error status",
            webhook_type=webhook_type,
            status_code=response.status_code,
        )

    return response


def _build_discord_payload(payload: WebhookPayload) -> dict[str, Any]:
    """Build Discord webhook payload with embed."""
    result: dict[str, Any] = {"username": payload.username}

    if payload.avatar_url:
        result["avatar_url"] = payload.avatar_url

    # Use embed if we have title, color, or fields
    if payload.title or payload.color or payload.fields:
        embed: dict[str, Any] = {"description": payload.message}

        if payload.title:
            embed["title"] = payload.title

        if payload.color:
            # Convert hex color to integer
            embed["color"] = int(payload.color.lstrip("#"), 16)

        if payload.fields:
            embed["fields"] = [
                {"name": f["name"], "value": f["value"], "inline": f.get("inline", False)}
                for f in payload.fields
            ]

        embed["timestamp"] = datetime.now(UTC).isoformat()
        result["embeds"] = [embed]
    else:
        result["content"] = payload.message

    return result


def _build_slack_payload(payload: WebhookPayload) -> dict[str, Any]:
    """Build Slack webhook payload with attachment."""
    result: dict[str, Any] = {"username": payload.username}

    # Use attachment if we have title, color, or fields
    if payload.title or payload.color or payload.fields:
        attachment: dict[str, Any] = {"text": payload.message}

        if payload.title:
            attachment["title"] = payload.title

        if payload.color:
            # Slack uses hex without #
            attachment["color"] = payload.color.lstrip("#")

        if payload.fields:
            attachment["fields"] = [
                {"title": f["name"], "value": f["value"], "short": f.get("inline", False)}
                for f in payload.fields
            ]

        result["attachments"] = [attachment]
    else:
        result["text"] = payload.message

    return result


def _build_generic_payload(payload: WebhookPayload) -> dict[str, Any]:
    """Build generic webhook payload."""
    return {"text": payload.message, "username": payload.username}
