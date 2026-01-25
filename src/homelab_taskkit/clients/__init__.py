"""Shared client modules for homelab-taskkit.

These provide reusable HTTP and webhook functionality
that tasks can compose into their logic.
"""

from homelab_taskkit.clients.http import HTTPResponse, request
from homelab_taskkit.clients.webhook import WebhookPayload, send_webhook

__all__ = ["request", "HTTPResponse", "send_webhook", "WebhookPayload"]
