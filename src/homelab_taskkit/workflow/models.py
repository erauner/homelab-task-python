"""Step I/O models for workflow execution.

This module defines the contracts between steps and the workflow runner:
- StepInput: What each step receives
- StepResult: What each step returns
- Message/Severity: Structured diagnostics
- StepDeps: Dependencies injected into step handlers
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import httpx
from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Message severity levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Message(BaseModel):
    """Single diagnostic message from a step.

    Attributes:
        system: Subsystem that generated the message (e.g., "smoke-test", "internal").
        severity: Message severity level.
        text: Human-readable message content.
        timestamp: When the message was created (ISO 8601).
        data: Optional structured data for debugging.
    """

    system: str = "internal"
    severity: Severity = Severity.INFO
    text: str
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    data: dict[str, Any] = Field(default_factory=dict)


class StepInput(BaseModel):
    """Input provided to each step handler.

    Attributes:
        step_name: Name of the current step.
        task_id: Unique identifier for the task definition.
        workflow_name: Name of the workflow being executed.
        params: Static parameters passed to the workflow.
        vars: Accumulated variables from previous steps (mutable context).
        attempt: Current attempt number (0-indexed).
        total_retries: Maximum retry attempts configured.
    """

    step_name: str
    task_id: str
    workflow_name: str
    params: dict[str, Any] = Field(default_factory=dict)
    vars: dict[str, Any] = Field(default_factory=dict)
    attempt: int = 0
    total_retries: int = 3


class StepResult(BaseModel):
    """Result returned by each step handler.

    Attributes:
        messages: Diagnostic messages (info/warning/error).
        output: Optional step-specific output data.
        context_updates: Updates to merge into vars for subsequent steps.
        flow_control: Optional flow control flags (skip_remaining, mark_failed, etc.).
    """

    messages: list[Message] = Field(default_factory=list)
    output: dict[str, Any] | None = None
    context_updates: dict[str, Any] = Field(default_factory=dict)
    flow_control: dict[str, Any] | None = None

    # Convenience methods for adding messages
    def add_message(
        self,
        text: str,
        *,
        severity: Severity = Severity.INFO,
        system: str = "internal",
        data: dict[str, Any] | None = None,
    ) -> None:
        """Add a message to the result."""
        self.messages.append(
            Message(
                system=system,
                severity=severity,
                text=text,
                data=data or {},
            )
        )

    def add_debug(self, text: str, system: str = "internal", **data: Any) -> None:
        """Add a debug message."""
        self.add_message(text, severity=Severity.DEBUG, system=system, data=data)

    def add_info(self, text: str, system: str = "internal", **data: Any) -> None:
        """Add an info message."""
        self.add_message(text, severity=Severity.INFO, system=system, data=data)

    def add_warning(self, text: str, system: str = "internal", **data: Any) -> None:
        """Add a warning message."""
        self.add_message(text, severity=Severity.WARNING, system=system, data=data)

    def add_error(self, text: str, system: str = "internal", **data: Any) -> None:
        """Add an error message."""
        self.add_message(text, severity=Severity.ERROR, system=system, data=data)

    @property
    def has_errors(self) -> bool:
        """Check if any error messages exist."""
        return any(m.severity == Severity.ERROR for m in self.messages)

    @property
    def has_warnings(self) -> bool:
        """Check if any warning messages exist."""
        return any(m.severity == Severity.WARNING for m in self.messages)

    @property
    def error_count(self) -> int:
        """Count of error messages."""
        return sum(1 for m in self.messages if m.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        """Count of warning messages."""
        return sum(1 for m in self.messages if m.severity == Severity.WARNING)


class StepDeps(BaseModel):
    """Dependencies injected into step handlers.

    Unlike the task-level Deps, this is Pydantic-based and workflow-aware.
    The LocalRunner builds this for each step execution.

    Attributes:
        http: HTTP client for making requests.
        logger: Logger instance for step output.
        env: Environment variables mapping.
        workdir: Working directory path for the workflow execution.
    """

    http: httpx.Client
    logger: logging.Logger
    env: Mapping[str, str]
    workdir: str

    class Config:
        arbitrary_types_allowed = True


# Type alias for step handler functions
StepHandler = Callable[[StepInput, StepDeps], StepResult]
