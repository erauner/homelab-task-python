"""HTTP request task - make HTTP calls to external services.

This task demonstrates:
- Using the shared HTTP client wrapper
- Consistent error handling via typed exceptions
- Converting external responses to validated outputs
"""

from __future__ import annotations

from typing import Any

from homelab_taskkit.clients.http import request
from homelab_taskkit.deps import Deps
from homelab_taskkit.errors import HTTPError, TimeoutError
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
        RuntimeError: If the request fails (network error, timeout, etc.)
    """
    url = inputs["url"]
    method = inputs.get("method", "GET").upper()
    headers = inputs.get("headers", {})
    body = inputs.get("body")
    timeout = inputs.get("timeout", 30.0)

    deps.logger.info(f"Making {method} request to {url}")

    try:
        response = request(
            deps.http,
            method,
            url,
            headers=headers,
            json_body=body if body and method in ("POST", "PUT", "PATCH") else None,
            timeout=timeout,
        )

        # Use JSON body if available, otherwise use text
        response_body = response.json if response.json is not None else response.body

        deps.logger.info(f"Response: {response.status_code} in {response.elapsed_ms}ms")

        return {
            "status_code": response.status_code,
            "headers": response.headers,
            "body": response_body,
            "elapsed_ms": response.elapsed_ms,
            "success": response.ok,
        }

    except TimeoutError as e:
        deps.logger.error(f"Request timed out: {e}")
        raise RuntimeError(f"HTTP request timed out after {timeout}s") from e

    except HTTPError as e:
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
