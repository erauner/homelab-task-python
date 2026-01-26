"""Typed exceptions for homelab-taskkit.

All task-related errors should inherit from TaskError.
These provide structured error information for logging and debugging.
"""

from __future__ import annotations

from typing import Any


class TaskError(Exception):
    """Base exception for all task errors."""

    def __init__(self, message: str, *, context: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}

    def __str__(self) -> str:
        if self.context:
            ctx = ", ".join(f"{k}={v!r}" for k, v in self.context.items())
            return f"{self.message} ({ctx})"
        return self.message


class HTTPError(TaskError):
    """HTTP request failed."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        url: str | None = None,
        method: str = "GET",
    ):
        context = {"status_code": status_code, "url": url, "method": method}
        super().__init__(message, context={k: v for k, v in context.items() if v is not None})
        self.status_code = status_code
        self.url = url
        self.method = method


class WebhookError(TaskError):
    """Webhook delivery failed."""

    def __init__(
        self,
        message: str,
        *,
        webhook_type: str | None = None,
        status_code: int | None = None,
    ):
        context = {"webhook_type": webhook_type, "status_code": status_code}
        super().__init__(message, context={k: v for k, v in context.items() if v is not None})
        self.webhook_type = webhook_type
        self.status_code = status_code


class ValidationError(TaskError):
    """Input or output validation failed."""

    def __init__(self, message: str, *, field: str | None = None, value: Any = None):
        context: dict[str, Any] = {}
        if field:
            context["field"] = field
        if value is not None:
            # Truncate long values for readability
            str_val = str(value)
            context["value"] = str_val[:100] + "..." if len(str_val) > 100 else str_val
        super().__init__(message, context=context)
        self.field = field
        self.value = value


class TimeoutError(TaskError):
    """Operation timed out."""

    def __init__(self, message: str, *, timeout_seconds: float | None = None):
        context = {"timeout_seconds": timeout_seconds} if timeout_seconds else {}
        super().__init__(message, context=context)
        self.timeout_seconds = timeout_seconds


class RetryableError(TaskError):
    """Error that may succeed on retry.

    Tasks can catch this to implement retry logic.
    """

    def __init__(self, message: str, *, attempts: int = 1, max_attempts: int | None = None):
        context = {"attempts": attempts}
        if max_attempts:
            context["max_attempts"] = max_attempts
        super().__init__(message, context=context)
        self.attempts = attempts
        self.max_attempts = max_attempts


class ContextError(TaskError):
    """Context loading, parsing, or patch application failed."""

    def __init__(self, message: str, *, path: str | None = None):
        context: dict[str, Any] = {}
        if path:
            context["path"] = path
        super().__init__(message, context=context)
        self.path = path


class ContextSizeError(ContextError):
    """Context exceeds maximum allowed size."""

    def __init__(self, message: str, *, size_bytes: int, max_bytes: int):
        super().__init__(message)
        self.context["size_bytes"] = size_bytes
        self.context["max_bytes"] = max_bytes
        self.size_bytes = size_bytes
        self.max_bytes = max_bytes
