"""Webhook notification task for Discord/Slack notifications.

Supports:
- Discord webhooks with embeds
- Slack webhooks with attachments
- Custom fields and colors
"""

from __future__ import annotations

from typing import Any

from homelab_taskkit.clients.webhook import WebhookPayload, detect_webhook_type, send_webhook
from homelab_taskkit.deps import Deps
from homelab_taskkit.errors import WebhookError
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

    # Build structured payload
    payload = WebhookPayload(
        message=message,
        title=inputs.get("title"),
        color=inputs.get("color"),
        fields=inputs.get("fields", []),
        username=inputs.get("username", "Homelab Tasks"),
        avatar_url=inputs.get("avatar_url"),
    )

    webhook_type = detect_webhook_type(webhook_url)
    deps.logger.info(f"Sending {webhook_type} notification")

    timestamp = deps.now().isoformat()

    try:
        response = send_webhook(deps.http, webhook_url, payload)
        success = response.ok
        status_code = response.status_code
    except WebhookError as e:
        success = False
        status_code = e.status_code or 0
        deps.logger.warning(f"Webhook failed: {e}")
    except Exception as e:
        success = False
        status_code = 0
        deps.logger.error(f"Webhook failed unexpectedly: {e}")

    return {
        "success": success,
        "status_code": status_code,
        "webhook_type": webhook_type,
        "timestamp": timestamp,
        "message_preview": message[:100] + "..." if len(message) > 100 else message,
    }


register_task(
    TaskDef(
        name="webhook_notify",
        description="Send notifications via Discord or Slack webhooks",
        input_schema="webhook_notify/input.json",
        output_schema="webhook_notify/output.json",
        run=run,
    )
)
