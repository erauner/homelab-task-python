"""Echo task - simple pass-through for testing.

This task demonstrates the functional pattern:
- Pure function with explicit inputs/outputs
- Dependencies injected (not imported)
- No side effects beyond logging
"""

from __future__ import annotations

from typing import Any

from homelab_taskkit.deps import Deps
from homelab_taskkit.registry import TaskDef, register_task


def run(inputs: dict[str, Any], deps: Deps) -> dict[str, Any]:
    """Echo the input message back with metadata.

    Args:
        inputs: Dictionary containing 'message' (required) and optional 'metadata'.
        deps: Injected dependencies.

    Returns:
        Dictionary with 'echoed_message', 'timestamp', and optional 'metadata'.
    """
    message = inputs["message"]
    metadata = inputs.get("metadata", {})

    deps.logger.info(f"Echoing message: {message!r}")

    return {
        "echoed_message": message,
        "timestamp": deps.now().isoformat(),
        "metadata": metadata,
    }


# Register the task
register_task(
    TaskDef(
        name="echo",
        description="Echo input message back with timestamp - useful for testing",
        input_schema="echo/input.json",
        output_schema="echo/output.json",
        run=run,
    )
)
