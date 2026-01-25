"""Input/output handling utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_input(source: str) -> Any:
    """Read input from a file path or inline JSON string.

    Args:
        source: Either a path to a JSON file, or an inline JSON string.

    Returns:
        The parsed JSON data.

    Raises:
        json.JSONDecodeError: If the input is not valid JSON.
        FileNotFoundError: If source looks like a path but file doesn't exist.
    """
    # Check if source looks like a file path and exists
    source_path = Path(source)
    if source_path.exists():
        with open(source_path) as f:
            return json.load(f)

    # Otherwise, treat as inline JSON
    return json.loads(source)


def write_output(dest: str | Path, obj: Any) -> None:
    """Write output to a JSON file.

    Args:
        dest: Path to write the JSON output.
        obj: The data to serialize as JSON.

    Raises:
        TypeError: If obj is not JSON serializable.
    """
    dest_path = Path(dest)

    # Ensure parent directory exists
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    with open(dest_path, "w") as f:
        json.dump(obj, f, indent=2, default=str)
        f.write("\n")  # Trailing newline for POSIX compliance
