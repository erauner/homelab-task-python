"""Standardized fanout artifact for parallel execution.

Enables tasks to spawn multiple parallel instances of downstream steps.
Works with Argo's withParam pattern for DAG fanout.

Fanout format:
    {"version": "taskkit-fanout/v1", "items": [...]}

Usage in tasks:
    def run(inputs, deps):
        # Generate targets for parallel execution
        targets = [{"cluster": c} for c in inputs["clusters"]]
        return {
            "generated_count": len(targets),
            **make_fanout(targets)
        }

In Argo WorkflowTemplate:
    - name: process-cluster
      dependencies: [generate-targets]
      withParam: "{{tasks.generate-targets.outputs.parameters.fanout}}"
      arguments:
        parameters:
          - name: item
            value: "{{item}}"
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Constants
FANOUT_VERSION = "taskkit-fanout/v1"
DEFAULT_FANOUT_OUT = "/outputs/fanout.json"
FANOUT_KEY = "__taskkit_fanout__"


@dataclass
class TaskkitFanout:
    """Container for fanout items.

    Attributes:
        version: Fanout format version string.
        items: List of items to fan out to parallel steps.
    """

    version: str = FANOUT_VERSION
    items: list[Any] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "version": self.version,
            "items": self.items,
        }

    def to_items_list(self) -> list[Any]:
        """Return just the items list (for Argo withParam)."""
        return self.items

    @classmethod
    def from_items(cls, items: list[Any]) -> TaskkitFanout:
        """Create from a list of items.

        Args:
            items: List of items for fanout.

        Returns:
            TaskkitFanout instance.
        """
        return cls(version=FANOUT_VERSION, items=list(items))

    @property
    def count(self) -> int:
        """Number of fanout items."""
        return len(self.items)


def empty_fanout() -> TaskkitFanout:
    """Create an empty fanout container."""
    return TaskkitFanout(version=FANOUT_VERSION, items=[])


def extract_fanout(
    task_output: dict[str, Any],
    *,
    fanout_key: str = FANOUT_KEY,
) -> tuple[dict[str, Any], TaskkitFanout | None]:
    """Extract fanout from task output.

    Removes the fanout key from output if present, returning cleaned output
    and the parsed fanout.

    Accepts either:
        - A dict with {"items": [...]}
        - A raw list (treated as items)

    Args:
        task_output: Raw task output dictionary.
        fanout_key: Key containing the fanout data.

    Returns:
        Tuple of (cleaned_output, fanout or None).

    Raises:
        ValueError: If fanout has invalid structure.
    """
    if fanout_key not in task_output:
        return task_output, None

    # Clone output and extract fanout
    clean_output = dict(task_output)
    fanout_data = clean_output.pop(fanout_key)

    if fanout_data is None:
        return clean_output, None

    # Accept either a list (raw items) or a dict with "items" key
    if isinstance(fanout_data, list):
        return clean_output, TaskkitFanout.from_items(fanout_data)

    if isinstance(fanout_data, dict):
        items = fanout_data.get("items", [])
        if not isinstance(items, list):
            raise ValueError(f"fanout.items must be a list, got {type(items).__name__}")
        return clean_output, TaskkitFanout(
            version=fanout_data.get("version", FANOUT_VERSION),
            items=items,
        )

    raise ValueError(f"{fanout_key} must be a list or object, got {type(fanout_data).__name__}")


def write_fanout(path: str | Path, fanout: TaskkitFanout) -> None:
    """Write fanout to a JSON file.

    Args:
        path: Path to write fanout JSON.
        fanout: Fanout container to write.
    """
    path = Path(path)

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        json.dump(fanout.to_dict(), f, indent=2, default=str)
        f.write("\n")  # Trailing newline for POSIX compliance


def write_fanout_items(path: str | Path, fanout: TaskkitFanout) -> None:
    """Write just the fanout items as a JSON array.

    Use this for direct Argo withParam consumption without the envelope.

    Args:
        path: Path to write fanout items JSON.
        fanout: Fanout container to write.
    """
    path = Path(path)

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        json.dump(fanout.items, f, indent=2, default=str)
        f.write("\n")
