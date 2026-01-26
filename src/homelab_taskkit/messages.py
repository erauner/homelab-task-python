"""Standardized messages artifact for step diagnostics.

Provides a uniform way for tasks to emit warnings/errors/info that:
- Gets surfaced via API endpoints
- Remains consistent across all task types
- Is separate from task-specific output schemas

Message format:
    {"version": "taskkit-messages/v1", "messages": [...]}

Message structure:
    {"level": "error|warning|info", "message": "...", "code": "...", "source": "...", "data": {...}}

Usage in tasks:
    def run(inputs, deps):
        return {
            "result": "...",
            **make_messages([
                {"level": "warning", "message": "Slow response", "code": "SLOW_RESPONSE"}
            ])
        }
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

# Constants
MESSAGES_VERSION = "taskkit-messages/v1"
DEFAULT_MESSAGES_OUT = "/outputs/messages.json"
MESSAGES_KEY = "__taskkit_messages__"

# Type alias for message levels
MessageLevel = Literal["info", "warning", "error"]


@dataclass(frozen=True)
class TaskkitMessage:
    """Single diagnostic message.

    Attributes:
        level: Severity level (info, warning, error).
        message: Human-readable description.
        code: Optional machine-readable error code.
        source: Task or component that generated the message.
        timestamp: When the message was created (ISO 8601).
        data: Optional structured data for debugging.
    """

    level: MessageLevel
    message: str
    code: str | None = None
    source: str | None = None
    timestamp: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result: dict[str, Any] = {
            "level": self.level,
            "message": self.message,
        }
        if self.code:
            result["code"] = self.code
        if self.source:
            result["source"] = self.source
        if self.timestamp:
            result["timestamp"] = self.timestamp
        if self.data:
            result["data"] = self.data
        return result

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], *, default_source: str | None = None
    ) -> TaskkitMessage:
        """Create from dictionary.

        Args:
            data: Message dictionary.
            default_source: Source to use if not specified in data.

        Returns:
            TaskkitMessage instance.
        """
        return cls(
            level=data.get("level", "info"),
            message=data.get("message", ""),
            code=data.get("code"),
            source=data.get("source", default_source),
            timestamp=data.get("timestamp"),
            data=data.get("data", {}),
        )


@dataclass
class TaskkitMessages:
    """Container for diagnostic messages.

    Attributes:
        version: Messages format version string.
        messages: List of diagnostic messages.
    """

    version: str = MESSAGES_VERSION
    messages: list[TaskkitMessage] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "version": self.version,
            "messages": [m.to_dict() for m in self.messages],
        }

    def add(
        self,
        level: MessageLevel,
        message: str,
        *,
        code: str | None = None,
        source: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Add a message to the container.

        Args:
            level: Severity level.
            message: Human-readable description.
            code: Optional machine-readable code.
            source: Component that generated the message.
            data: Optional structured data.
        """
        self.messages.append(
            TaskkitMessage(
                level=level,
                message=message,
                code=code,
                source=source,
                timestamp=datetime.now(UTC).isoformat(),
                data=data or {},
            )
        )

    def add_error(
        self,
        message: str,
        *,
        code: str | None = None,
        source: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Add an error message."""
        self.add("error", message, code=code, source=source, data=data)

    def add_warning(
        self,
        message: str,
        *,
        code: str | None = None,
        source: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Add a warning message."""
        self.add("warning", message, code=code, source=source, data=data)

    def add_info(
        self,
        message: str,
        *,
        code: str | None = None,
        source: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Add an info message."""
        self.add("info", message, code=code, source=source, data=data)

    @property
    def has_errors(self) -> bool:
        """Check if any error messages exist."""
        return any(m.level == "error" for m in self.messages)

    @property
    def has_warnings(self) -> bool:
        """Check if any warning messages exist."""
        return any(m.level == "warning" for m in self.messages)


def empty_messages() -> TaskkitMessages:
    """Create an empty messages container."""
    return TaskkitMessages(version=MESSAGES_VERSION, messages=[])


def extract_messages(
    task_output: dict[str, Any],
    *,
    task_name: str,
    messages_key: str = MESSAGES_KEY,
) -> tuple[dict[str, Any], list[TaskkitMessage]]:
    """Extract messages from task output.

    Removes the messages key from output if present, returning cleaned output
    and the parsed messages. Auto-fills source with task_name if not specified.

    Args:
        task_output: Raw task output dictionary.
        task_name: Name of the task (used as default source).
        messages_key: Key containing the messages list.

    Returns:
        Tuple of (cleaned_output, list_of_messages).

    Raises:
        ValueError: If messages has invalid structure.
    """
    if messages_key not in task_output:
        return task_output, []

    # Clone output and extract messages
    clean_output = dict(task_output)
    messages_data = clean_output.pop(messages_key)

    if messages_data is None:
        return clean_output, []

    if not isinstance(messages_data, list):
        raise ValueError(f"{messages_key} must be a list, got {type(messages_data).__name__}")

    # Parse messages
    parsed: list[TaskkitMessage] = []
    for item in messages_data:
        if not isinstance(item, dict):
            raise ValueError(f"Each message must be an object, got {type(item).__name__}")
        parsed.append(TaskkitMessage.from_dict(item, default_source=task_name))

    return clean_output, parsed


def write_messages(path: str | Path, messages: TaskkitMessages) -> None:
    """Write messages to a JSON file.

    Args:
        path: Path to write messages JSON.
        messages: Messages container to write.
    """
    path = Path(path)

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        json.dump(messages.to_dict(), f, indent=2, default=str)
        f.write("\n")  # Trailing newline for POSIX compliance
