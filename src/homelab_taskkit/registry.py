"""Task registry - maps task names to their implementations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homelab_taskkit.deps import Deps


# Type alias for task run functions
TaskRunFn = Callable[[dict[str, Any], "Deps"], dict[str, Any]]


@dataclass(frozen=True)
class TaskDef:
    """Definition of a task.

    A task is a pure function with explicit inputs and outputs,
    backed by JSON schemas for validation.

    Attributes:
        name: Unique task identifier (e.g., "echo", "http_request").
        description: Human-readable description of what the task does.
        input_schema: Relative path to input JSON schema file.
        output_schema: Relative path to output JSON schema file.
        run: The task implementation function.
    """

    name: str
    description: str
    input_schema: str
    output_schema: str
    run: TaskRunFn


class TaskNotFoundError(Exception):
    """Raised when a requested task doesn't exist."""

    def __init__(self, name: str, available: list[str]) -> None:
        super().__init__(f"Task '{name}' not found. Available: {', '.join(available)}")
        self.name = name
        self.available = available


# The task registry - populated by tasks/__init__.py
_TASKS: dict[str, TaskDef] = {}


def register_task(task: TaskDef) -> TaskDef:
    """Register a task in the registry.

    Args:
        task: The task definition to register.

    Returns:
        The same task (for decorator chaining).

    Raises:
        ValueError: If a task with the same name is already registered.
    """
    if task.name in _TASKS:
        raise ValueError(f"Task '{task.name}' is already registered")
    _TASKS[task.name] = task
    return task


def get_task(name: str) -> TaskDef:
    """Get a task by name.

    Args:
        name: The task name to look up.

    Returns:
        The task definition.

    Raises:
        TaskNotFoundError: If the task doesn't exist.
    """
    if name not in _TASKS:
        raise TaskNotFoundError(name, list(_TASKS.keys()))
    return _TASKS[name]


def list_tasks() -> list[TaskDef]:
    """List all registered tasks.

    Returns:
        List of all task definitions, sorted by name.
    """
    return sorted(_TASKS.values(), key=lambda t: t.name)
