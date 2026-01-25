"""Webhook notification task for Discord/Slack notifications.

Supports:
- Discord webhooks with embeds
- Slack webhooks with attachments
- Custom fields and colors
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from homelab_taskkit.deps import Deps
from homelab_taskkit.registry import TaskDef, register_task


def run(inputs: dict[str, Any], deps: Deps) -> dict[str, Any]:
    """Send a notification via webhook.

    Input fields:
        webhook_url: Webhook URL (Discord or Slack)
        message: Message text to send
        title: Optional title for embed/attachment
        color: Hex color for embed (e.g., '#00ff00')
        fields: Additional fields [{name, value, inline}]
        username: Override bot username
        avatar_url: Override bot avatar URL

    Output fields:
        success: Whether notification was sent successfully
        status_code: HTTP status code from webhook
        webhook_type: Detected type (discord/slack/unknown)
        timestamp: When notification was sent
        message_preview: Preview of the sent message
    """
    webhook_url = inputs["webhook_url"]
    message = inputs["message"]
    title = inputs.get("title")
    color = inputs.get("color")
    fields = inputs.get("fields", [])
    username = inputs.get("username", "Homelab Tasks")
    avatar_url = inputs.get("avatar_url")

    # Detect webhook type
    webhook_type = _detect_webhook_type(webhook_url)
    deps.logger.info(f"Sending {webhook_type} notification")

    # Build payload based on webhook type
    if webhook_type == "discord":
        payload = _build_discord_payload(message, title, color, fields, username, avatar_url)
    elif webhook_type == "slack":
        payload = _build_slack_payload(message, title, color, fields, username)
    else:
        # Generic JSON payload
        payload = {"text": message, "username": username}

    # Send the request
    import json
    import urllib.request

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            status_code = response.status
            success = 200 <= status_code < 300
    except urllib.error.HTTPError as e:
        status_code = e.code
        success = False
        deps.logger.warning(f"Webhook failed: HTTP {status_code}")
    except Exception as e:
        status_code = 0
        success = False
        deps.logger.error(f"Webhook failed: {e}")

    timestamp = datetime.now(UTC).isoformat()

    return {
        "success": success,
        "status_code": status_code,
        "webhook_type": webhook_type,
        "timestamp": timestamp,
        "message_preview": message[:100] + "..." if len(message) > 100 else message,
    }


def _detect_webhook_type(url: str) -> str:
    """Detect webhook type from URL."""
    if "discord.com/api/webhooks" in url or "discordapp.com/api/webhooks" in url:
        return "discord"
    elif "hooks.slack.com" in url:
        return "slack"
    return "unknown"


def _build_discord_payload(
    message: str,
    title: str | None,
    color: str | None,
    fields: list[dict[str, Any]],
    username: str,
    avatar_url: str | None,
) -> dict[str, Any]:
    """Build Discord webhook payload with embed."""
    payload: dict[str, Any] = {"username": username}

    if avatar_url:
        payload["avatar_url"] = avatar_url

    # Use embed if we have title, color, or fields
    if title or color or fields:
        embed: dict[str, Any] = {"description": message}

        if title:
            embed["title"] = title

        if color:
            # Convert hex color to integer
            color_int = int(color.lstrip("#"), 16)
            embed["color"] = color_int

        if fields:
            embed["fields"] = [
                {"name": f["name"], "value": f["value"], "inline": f.get("inline", False)}
                for f in fields
            ]

        embed["timestamp"] = datetime.now(UTC).isoformat()
        payload["embeds"] = [embed]
    else:
        payload["content"] = message

    return payload


def _build_slack_payload(
    message: str,
    title: str | None,
    color: str | None,
    fields: list[dict[str, Any]],
    username: str,
) -> dict[str, Any]:
    """Build Slack webhook payload with attachment."""
    payload: dict[str, Any] = {"username": username}

    # Use attachment if we have title, color, or fields
    if title or color or fields:
        attachment: dict[str, Any] = {"text": message}

        if title:
            attachment["title"] = title

        if color:
            # Slack uses hex without #
            attachment["color"] = color.lstrip("#")

        if fields:
            attachment["fields"] = [
                {"title": f["name"], "value": f["value"], "short": f.get("inline", False)}
                for f in fields
            ]

        payload["attachments"] = [attachment]
    else:
        payload["text"] = message

    return payload


register_task(
    TaskDef(
        name="webhook_notify",
        description="Send notifications via Discord or Slack webhooks",
        input_schema="webhook_notify/input.json",
        output_schema="webhook_notify/output.json",
        run=run,
    )
)
