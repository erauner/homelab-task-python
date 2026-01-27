"""Step registry for workflow handlers.

This module provides the @register_step decorator pattern for registering
step handlers that can be invoked by workflow definitions.

Usage:
    from homelab_taskkit.workflow import register_step, StepInput, StepResult, StepDeps

    @register_step("smoke-test-init")
    def handle_init(step_input: StepInput, deps: StepDeps) -> StepResult:
        result = StepResult()
        result.add_info("Workflow initialized", system="smoke-test")
        result.context_updates["initialized"] = True
        return result
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, overload

if TYPE_CHECKING:
    from homelab_taskkit.workflow.models import StepDeps, StepInput, StepResult

# Type alias for step handler functions
StepHandler = Callable[["StepInput", "StepDeps"], "StepResult"]

# The step registry - maps normalized names to handlers
_STEP_REGISTRY: dict[str, StepHandler] = {}


class StepAlreadyRegisteredError(Exception):
    """Raised when attempting to register a step that already exists."""

    def __init__(self, step_name: str) -> None:
        super().__init__(f"Step '{step_name}' is already registered")
        self.step_name = step_name


class StepNotFoundError(Exception):
    """Raised when a requested step handler doesn't exist."""

    def __init__(self, step_name: str, available: list[str]) -> None:
        available_str = ", ".join(sorted(available)) if available else "(none)"
        super().__init__(f"Step '{step_name}' not found. Available: {available_str}")
        self.step_name = step_name
        self.available = available


def normalize_step_name(name: str) -> str:
    """Normalize a step name for registry lookup.

    Converts to lowercase and replaces underscores with hyphens.

    Args:
        name: Step name to normalize.

    Returns:
        Normalized step name.
    """
    return name.lower().replace("_", "-")


@overload
def register_step(step_name: str) -> Callable[[StepHandler], StepHandler]: ...


@overload
def register_step(
    step_name: str,
    handler: StepHandler,
    *,
    allow_override: bool = False,
) -> None: ...


def register_step(
    step_name: str,
    handler: StepHandler | None = None,
    *,
    allow_override: bool = False,
) -> Callable[[StepHandler], StepHandler] | None:
    """Register a step handler in the registry.

    Can be used as a decorator or called directly:

        # As decorator
        @register_step("my-step")
        def handle_my_step(step_input, deps):
            return StepResult()

        # Direct registration
        register_step("my-step", handle_my_step)

    Args:
        step_name: Unique identifier for the step handler.
        handler: Optional handler function (if not using as decorator).
        allow_override: If True, allows replacing existing handlers.

    Returns:
        Decorator function if handler not provided, None otherwise.

    Raises:
        StepAlreadyRegisteredError: If step already registered and allow_override=False.
    """
    normalized_name = normalize_step_name(step_name)

    def _register(h: StepHandler) -> StepHandler:
        if normalized_name in _STEP_REGISTRY and not allow_override:
            raise StepAlreadyRegisteredError(step_name)
        _STEP_REGISTRY[normalized_name] = h
        return h

    if handler is None:
        # Used as decorator
        return _register
    else:
        # Direct registration
        _register(handler)
        return None


def get_step(step_name: str) -> StepHandler:
    """Get a step handler by name.

    Args:
        step_name: The step name to look up.

    Returns:
        The registered step handler.

    Raises:
        StepNotFoundError: If the step doesn't exist.
    """
    normalized_name = normalize_step_name(step_name)
    if normalized_name not in _STEP_REGISTRY:
        raise StepNotFoundError(step_name, list_steps())
    return _STEP_REGISTRY[normalized_name]


def list_steps() -> list[str]:
    """List all registered step names.

    Returns:
        Sorted list of registered step handler names.
    """
    return sorted(_STEP_REGISTRY.keys())


def clear_steps() -> None:
    """Clear all registered steps.

    Primarily used for testing to reset state between tests.
    """
    _STEP_REGISTRY.clear()


def has_step(step_name: str) -> bool:
    """Check if a step is registered.

    Args:
        step_name: The step name to check.

    Returns:
        True if the step is registered, False otherwise.
    """
    normalized_name = normalize_step_name(step_name)
    return normalized_name in _STEP_REGISTRY
