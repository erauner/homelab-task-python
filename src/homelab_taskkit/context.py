"""Context artifact support for step-to-step coordination.

Context is read-only input to steps; steps return a patch (set/unset).
The runtime merges patches into context and writes the result.

Context format:
    {"version": "taskkit-context/v1", "vars": {...}}

Patch format:
    {"set": {"key": "value"}, "unset": ["old_key"]}

Naming rules (enforced by context_rules.py):
    - Keys must be namespaced: pipeline.*, <task_name>.*, idempotency.*
    - Only the owner writes its namespace
    - Context is small and stable (max 32KB)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from homelab_taskkit.errors import ContextError, ContextSizeError

# Constants
CONTEXT_VERSION = "taskkit-context/v1"
DEFAULT_CONTEXT_IN = "/inputs/context.json"
DEFAULT_CONTEXT_OUT = "/outputs/context.json"
CONTEXT_PATCH_KEY = "__taskkit_context_patch__"
MAX_CONTEXT_BYTES = 32 * 1024  # 32KB


@dataclass(frozen=True)
class TaskkitContext:
    """Immutable context container.

    Attributes:
        version: Context format version string.
        vars: The context variables (namespaced keys).
    """

    version: str = CONTEXT_VERSION
    vars: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {"version": self.version, "vars": self.vars}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskkitContext:
        """Create from dictionary."""
        return cls(
            version=data.get("version", CONTEXT_VERSION),
            vars=dict(data.get("vars", {})),
        )


@dataclass(frozen=True)
class ContextPatch:
    """Context patch with set/unset operations.

    Attributes:
        set: Keys to set (upsert).
        unset: Keys to remove.
    """

    set: dict[str, Any] = field(default_factory=dict)
    unset: list[str] = field(default_factory=list)


def empty_context() -> TaskkitContext:
    """Create an empty context with default version."""
    return TaskkitContext(version=CONTEXT_VERSION, vars={})


def load_context(path: str | Path) -> TaskkitContext:
    """Load context from a JSON file.

    Args:
        path: Path to context JSON file.

    Returns:
        TaskkitContext with loaded data, or empty context if file missing.

    Raises:
        ContextError: If file exists but contains invalid JSON or structure.
    """
    path = Path(path)

    if not path.exists():
        return empty_context()

    try:
        with open(path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ContextError(f"Invalid JSON in context file: {e}") from e

    if not isinstance(data, dict):
        raise ContextError(f"Context must be an object, got {type(data).__name__}")

    # Handle both formats: full context or just vars
    if "version" in data and "vars" in data:
        # Full context format
        if not isinstance(data["vars"], dict):
            raise ContextError("Context 'vars' must be an object")
        return TaskkitContext.from_dict(data)
    else:
        # Legacy/simple format: treat entire object as vars
        return TaskkitContext(version=CONTEXT_VERSION, vars=data)


def extract_context_patch(
    task_output: dict[str, Any],
    *,
    patch_key: str = CONTEXT_PATCH_KEY,
) -> tuple[dict[str, Any], ContextPatch | None]:
    """Extract context patch from task output.

    Removes the patch key from output if present, returning cleaned output
    and the parsed patch.

    Args:
        task_output: Raw task output dictionary.
        patch_key: Key containing the context patch.

    Returns:
        Tuple of (cleaned_output, patch or None).

    Raises:
        ContextError: If patch has invalid structure.
    """
    if patch_key not in task_output:
        return task_output, None

    # Clone output and extract patch
    clean_output = dict(task_output)
    patch_data = clean_output.pop(patch_key)

    if patch_data is None:
        return clean_output, None

    if not isinstance(patch_data, dict):
        raise ContextError(f"context_patch must be an object, got {type(patch_data).__name__}")

    # Validate and parse patch
    set_ops = patch_data.get("set", {})
    unset_ops = patch_data.get("unset", [])

    if not isinstance(set_ops, dict):
        raise ContextError("context_patch.set must be an object")

    if not isinstance(unset_ops, list):
        raise ContextError("context_patch.unset must be an array")

    # Validate unset values are strings
    for key in unset_ops:
        if not isinstance(key, str):
            raise ContextError(
                f"context_patch.unset values must be strings, got {type(key).__name__}"
            )

    return clean_output, ContextPatch(set=set_ops, unset=unset_ops)


def apply_patch(ctx: TaskkitContext, patch: ContextPatch | None) -> TaskkitContext:
    """Apply a patch to context, returning new context.

    Patch application order: unset first, then set (so set wins).

    Args:
        ctx: Current context.
        patch: Patch to apply (None = no-op).

    Returns:
        New TaskkitContext with patch applied.
    """
    if patch is None:
        return ctx

    new_vars = dict(ctx.vars)

    # Apply unset first
    for key in patch.unset:
        new_vars.pop(key, None)

    # Then apply set
    for key, value in patch.set.items():
        new_vars[key] = value

    return TaskkitContext(version=ctx.version, vars=new_vars)


def serialized_size_bytes(ctx: TaskkitContext) -> int:
    """Return UTF-8 byte length of compact JSON serialization."""
    return len(json.dumps(ctx.to_dict(), separators=(",", ":")).encode("utf-8"))


def write_context(
    path: str | Path,
    ctx: TaskkitContext,
    *,
    max_bytes: int = MAX_CONTEXT_BYTES,
) -> None:
    """Write context to a JSON file with size validation.

    Args:
        path: Path to write context JSON.
        ctx: Context to write.
        max_bytes: Maximum allowed size in bytes.

    Raises:
        ContextSizeError: If serialized context exceeds max_bytes.
    """
    path = Path(path)

    # Check size before writing
    size = serialized_size_bytes(ctx)
    if size > max_bytes:
        raise ContextSizeError(
            f"Context size {size} bytes exceeds limit of {max_bytes} bytes",
            size_bytes=size,
            max_bytes=max_bytes,
        )

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        json.dump(ctx.to_dict(), f, indent=2, default=str)
        f.write("\n")  # Trailing newline for POSIX compliance
