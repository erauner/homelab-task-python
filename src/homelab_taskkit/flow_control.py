"""Flow control artifact for conditional step execution.

Enables tasks to control downstream step execution via boolean flags.
Works with Argo's when conditions for conditional DAG execution.

Flow control format:
    {"version": "taskkit-flow-control/v1", "vars": {"should_deploy": true}}

Usage in tasks:
    def run(inputs, deps):
        # Determine which downstream steps should run
        should_deploy = inputs.get("environment") == "production"
        return {
            "validated": True,
            **make_flow_control({
                "should_deploy": should_deploy,
                "skip_notifications": deps.env.get("SKIP_NOTIFY") == "true",
            })
        }

In Argo WorkflowTemplate:
    - name: deploy-to-production
      when: "{{tasks.init.outputs.parameters.flow-control-should_deploy}} == true"
      template: deploy
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Constants
FLOW_CONTROL_VERSION = "taskkit-flow-control/v1"
DEFAULT_FLOW_CONTROL_OUT = "/outputs/flow_control.json"
FLOW_CONTROL_KEY = "__taskkit_flow_control__"


@dataclass
class TaskkitFlowControl:
    """Container for flow control variables.

    Attributes:
        version: Flow control format version string.
        vars: Dictionary of flow control variables (typically booleans/strings).
    """

    version: str = FLOW_CONTROL_VERSION
    vars: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "version": self.version,
            "vars": self.vars,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskkitFlowControl:
        """Create from a dictionary.

        Args:
            data: Dictionary with optional 'version' and 'vars' keys.
                  If no 'vars' key, treats entire dict as vars.

        Returns:
            TaskkitFlowControl instance.
        """
        if "vars" in data:
            # Full format: {"version": "...", "vars": {...}} or just {"vars": {...}}
            return cls(
                version=data.get("version", FLOW_CONTROL_VERSION),
                vars=dict(data.get("vars", {})),
            )
        # Treat entire dict as vars (legacy/simple format)
        return cls(version=FLOW_CONTROL_VERSION, vars=dict(data))

    @classmethod
    def from_vars(cls, vars: dict[str, Any]) -> TaskkitFlowControl:
        """Create from a vars dictionary.

        Args:
            vars: Flow control variables.

        Returns:
            TaskkitFlowControl instance.
        """
        return cls(version=FLOW_CONTROL_VERSION, vars=dict(vars))

    @property
    def count(self) -> int:
        """Number of flow control variables."""
        return len(self.vars)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a flow control variable with optional default."""
        return self.vars.get(key, default)


def empty_flow_control() -> TaskkitFlowControl:
    """Create an empty flow control container."""
    return TaskkitFlowControl(version=FLOW_CONTROL_VERSION, vars={})


def make_flow_control(vars: dict[str, Any]) -> dict[str, Any]:
    """Helper to create flow control output from a task.

    Use this in task run() functions to embed flow control in output:

        return {
            "status": "validated",
            **make_flow_control({"should_deploy": True})
        }

    Args:
        vars: Flow control variables.

    Returns:
        Dictionary with the flow control key set.
    """
    return {FLOW_CONTROL_KEY: {"vars": vars}}


def extract_flow_control(
    task_output: dict[str, Any],
    *,
    flow_control_key: str = FLOW_CONTROL_KEY,
) -> tuple[dict[str, Any], TaskkitFlowControl | None]:
    """Extract flow control from task output.

    Removes the flow control key from output if present, returning cleaned output
    and the parsed flow control.

    Accepts either:
        - A dict with {"vars": {...}}
        - A raw dict (treated as vars)

    Args:
        task_output: Raw task output dictionary.
        flow_control_key: Key containing the flow control data.

    Returns:
        Tuple of (cleaned_output, flow_control or None).

    Raises:
        ValueError: If flow control has invalid structure.
    """
    if flow_control_key not in task_output:
        return task_output, None

    # Clone output and extract flow control
    clean_output = dict(task_output)
    flow_data = clean_output.pop(flow_control_key)

    if flow_data is None:
        return clean_output, None

    if isinstance(flow_data, dict):
        return clean_output, TaskkitFlowControl.from_dict(flow_data)

    raise ValueError(
        f"{flow_control_key} must be an object, got {type(flow_data).__name__}"
    )


def write_flow_control(path: str | Path, flow_control: TaskkitFlowControl) -> None:
    """Write flow control to a JSON file.

    Args:
        path: Path to write flow control JSON.
        flow_control: Flow control container to write.
    """
    path = Path(path)

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        json.dump(flow_control.to_dict(), f, indent=2, default=str)
        f.write("\n")  # Trailing newline for POSIX compliance


def write_flow_control_vars(path: str | Path, flow_control: TaskkitFlowControl) -> None:
    """Write just the flow control vars as a flat JSON object.

    Use this for simplified consumption without the envelope.

    Args:
        path: Path to write flow control vars JSON.
        flow_control: Flow control container to write.
    """
    path = Path(path)

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        json.dump(flow_control.vars, f, indent=2, default=str)
        f.write("\n")
