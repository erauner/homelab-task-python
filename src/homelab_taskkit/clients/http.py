"""Resilient HTTP client wrapper.

Provides a clean interface for HTTP requests with:
- Typed response objects
- Consistent error handling
- Centralized logging
"""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from homelab_taskkit.errors import HTTPError, TimeoutError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HTTPResponse:
    """Structured HTTP response.

    Attributes:
        status_code: HTTP status code (200, 404, etc.)
        body: Response body as string
        json: Parsed JSON body (None if not JSON)
        headers: Response headers as dict
        elapsed_ms: Request duration in milliseconds
        ok: True if status code is 2xx
    """

    status_code: int
    body: str
    json: dict[str, Any] | list[Any] | None
    headers: dict[str, str]
    elapsed_ms: float

    @property
    def ok(self) -> bool:
        """True if response has 2xx status code."""
        return 200 <= self.status_code < 300


def request(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | list[Any] | None = None,
    timeout: float | None = None,
) -> HTTPResponse:
    """Make an HTTP request with consistent error handling.

    Args:
        client: httpx.Client instance (from deps.http)
        method: HTTP method (GET, POST, PUT, PATCH, DELETE)
        url: Target URL
        headers: Optional request headers
        json_body: Optional JSON body for POST/PUT/PATCH
        timeout: Optional timeout override (uses client default if not set)

    Returns:
        HTTPResponse with status, body, and parsed JSON

    Raises:
        HTTPError: If request fails with HTTP error status
        TimeoutError: If request times out
    """
    log_url = _redact_url(url)
    logger.debug(f"HTTP {method} {log_url}")

    try:
        response = client.request(
            method=method.upper(),
            url=url,
            headers=headers,
            json=json_body,
            timeout=timeout,
        )
    except httpx.TimeoutException as e:
        raise TimeoutError(
            f"Request timed out: {method} {log_url}",
            timeout_seconds=timeout or client.timeout.connect,
        ) from e
    except httpx.RequestError as e:
        raise HTTPError(
            f"Request failed: {e}",
            url=log_url,
            method=method,
        ) from e

    # Parse JSON if content-type indicates JSON
    json_data = None
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        with contextlib.suppress(ValueError):
            json_data = response.json()

    elapsed_ms = round(response.elapsed.total_seconds() * 1000, 2)

    result = HTTPResponse(
        status_code=response.status_code,
        body=response.text,
        json=json_data,
        headers=dict(response.headers),
        elapsed_ms=elapsed_ms,
    )

    logger.debug(f"HTTP {method} {log_url} -> {result.status_code} in {elapsed_ms}ms")
    return result


def _redact_url(url: str) -> str:
    """Redact sensitive parts of URLs for logging.

    Hides webhook tokens, API keys in query params, etc.
    """
    # Redact Discord/Slack webhook tokens
    if "discord.com/api/webhooks" in url or "discordapp.com/api/webhooks" in url:
        parts = url.split("/")
        if len(parts) >= 2:
            return "/".join(parts[:-1]) + "/***"
    if "hooks.slack.com" in url:
        parts = url.split("/")
        if len(parts) >= 2:
            return "/".join(parts[:-1]) + "/***"

    return url
