"""HTTP request task - make HTTP calls to external services.

This task demonstrates:
- Using injected HTTP client (testable with fake client)
- Structured error handling
- Converting external responses to validated outputs
"""

from __future__ import annotations

from typing import Any

import httpx

from homelab_taskkit.deps import Deps
from homelab_taskkit.registry import TaskDef, register_task


def run(inputs: dict[str, Any], deps: Deps) -> dict[str, Any]:
    """Make an HTTP request and return the response.

    Args:
        inputs: Dictionary containing:
            - url (required): The URL to request
            - method (optional): HTTP method, defaults to GET
            - headers (optional): Request headers
            - body (optional): Request body (for POST/PUT/PATCH)
            - timeout (optional): Request timeout in seconds

    Returns:
        Dictionary with:
            - status_code: HTTP status code
            - headers: Response headers
            - body: Response body (parsed as JSON if possible)
            - elapsed_ms: Request duration in milliseconds
            - success: True if 2xx status code

    Raises:
        Exception: If the request fails (network error, timeout, etc.)
    """
    url = inputs["url"]
    method = inputs.get("method", "GET").upper()
    headers = inputs.get("headers", {})
    body = inputs.get("body")
    timeout = inputs.get("timeout", 30.0)

    deps.logger.info(f"Making {method} request to {url}")

    try:
        response = deps.http.request(
            method=method,
            url=url,
            headers=headers,
            json=body if body and method in ("POST", "PUT", "PATCH") else None,
            timeout=timeout,
        )

        # Try to parse response as JSON, fall back to text
        try:
            response_body = response.json()
        except Exception:
            response_body = response.text

        elapsed_ms = response.elapsed.total_seconds() * 1000

        deps.logger.info(
            f"Response: {response.status_code} in {elapsed_ms:.2f}ms"
        )

        return {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": response_body,
            "elapsed_ms": round(elapsed_ms, 2),
            "success": 200 <= response.status_code < 300,
        }

    except httpx.TimeoutException as e:
        deps.logger.error(f"Request timed out: {e}")
        raise RuntimeError(f"HTTP request timed out after {timeout}s") from e

    except httpx.RequestError as e:
        deps.logger.error(f"Request failed: {e}")
        raise RuntimeError(f"HTTP request failed: {e}") from e


# Register the task
register_task(
    TaskDef(
        name="http_request",
        description="Make HTTP requests to external services",
        input_schema="http_request/input.json",
        output_schema="http_request/output.json",
        run=run,
    )
)
