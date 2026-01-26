"""Context patch validation rules.

Enforces naming conventions and safety rules for context artifacts:
- Namespaced keys only (pipeline.*, <task_name>.*, idempotency.*)
- Only the owner writes its namespace
- Size limits enforced elsewhere (context.py)

These rules prevent context from becoming a dumping ground and
ensure predictable, maintainable step-to-step coordination.
"""

from __future__ import annotations

from typing import Any

from homelab_taskkit.context import ContextPatch

# Global namespace prefixes that any task can use
GLOBAL_PREFIXES = ("pipeline.", "idempotency.")


def validate_patch(task_name: str, patch: ContextPatch | dict[str, Any] | None) -> None:
    """Validate a context patch follows naming rules.

    Rules:
    1. Keys must be namespaced with either:
       - The task's own name: "<task_name>.*"
       - Global prefixes: "pipeline.*", "idempotency.*"
    2. Patch structure must be valid (set=dict, unset=list[str])

    Args:
        task_name: Name of the task producing the patch.
        patch: The context patch to validate.

    Raises:
        AssertionError: If any rule is violated.
    """
    if patch is None:
        return

    # Handle both ContextPatch and raw dict
    if isinstance(patch, dict):
        to_set = patch.get("set", {})
        to_unset = patch.get("unset", [])
    else:
        to_set = patch.set
        to_unset = patch.unset

    # Validate structure
    if not isinstance(to_set, dict):
        raise AssertionError("context_patch.set must be an object")

    if not isinstance(to_unset, list):
        raise AssertionError("context_patch.unset must be an array")

    # Build allowed prefixes for this task
    allowed_prefixes = (f"{task_name}.",) + GLOBAL_PREFIXES

    # Validate set keys
    for key in to_set:
        if not isinstance(key, str):
            raise AssertionError(f"context key must be a string, got {type(key).__name__}")
        if not any(key.startswith(prefix) for prefix in allowed_prefixes):
            raise AssertionError(
                f"context key '{key}' must be namespaced for task '{task_name}' "
                f"(allowed prefixes: {', '.join(allowed_prefixes)})"
            )

    # Validate unset keys
    for key in to_unset:
        if not isinstance(key, str):
            raise AssertionError("context_patch.unset values must be strings")
        if not any(key.startswith(prefix) for prefix in allowed_prefixes):
            raise AssertionError(
                f"context key '{key}' must be namespaced for task '{task_name}' "
                f"(allowed prefixes: {', '.join(allowed_prefixes)})"
            )


def validate_context_vars(context_vars: dict[str, Any]) -> list[str]:
    """Validate all context variables follow naming rules.

    This is a diagnostic function to check existing context.
    Returns list of warnings (not errors) for flexibility.

    Args:
        context_vars: The vars dict from a TaskkitContext.

    Returns:
        List of warning messages for any non-compliant keys.
    """
    warnings = []
    known_task_prefixes = {
        "echo.",
        "http_request.",
        "json_transform.",
        "conditional_check.",
        "webhook_notify.",
    }
    all_known_prefixes = known_task_prefixes | set(GLOBAL_PREFIXES)

    for key in context_vars:
        if not isinstance(key, str):
            warnings.append(f"Non-string key in context: {key!r}")
            continue

        # Check if key matches any known prefix
        has_known_prefix = any(key.startswith(prefix) for prefix in all_known_prefixes)
        # Warn if key has no known prefix and is not namespaced (missing dot)
        if not has_known_prefix and "." not in key:
            warnings.append(f"Context key '{key}' is not namespaced (missing '.')")

    return warnings
