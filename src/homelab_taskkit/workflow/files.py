"""File I/O operations for the taskkit workflow runtime.

Encapsulates all file reads/writes. Steps never touch disk directly.
The runner uses these functions to load inputs and write outputs.
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any

import yaml


class FileReadError(Exception):
    """Raised when a file cannot be read."""

    pass


class FileWriteError(Exception):
    """Raised when a file cannot be written."""

    pass


def read_params_json(path: str) -> dict[str, Any]:
    """Read task runtime parameters from params.json.

    Args:
        path: Path to params.json file

    Returns:
        Parsed parameters as dict

    Raises:
        FileReadError: If file cannot be read or parsed
    """
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileReadError(f"Params file not found: {path}")
    except json.JSONDecodeError as e:
        raise FileReadError(f"Invalid JSON in params file {path}: {e}")
    except Exception as e:
        raise FileReadError(f"Failed to read params file {path}: {e}")


def read_vars_yaml(path: str) -> dict[str, Any]:
    """Read shared state from vars.yaml.

    Args:
        path: Path to vars.yaml file

    Returns:
        Parsed variables as dict (empty dict if file doesn't exist)
    """
    if not os.path.exists(path):
        return {}

    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except yaml.YAMLError as e:
        raise FileReadError(f"Invalid YAML in vars file {path}: {e}")
    except Exception as e:
        raise FileReadError(f"Failed to read vars file {path}: {e}")


def write_vars_yaml(path: str, data: dict[str, Any]) -> None:
    """Write shared state to vars.yaml atomically.

    Uses atomic write (write to temp + rename) to avoid partial writes.

    Args:
        path: Path to vars.yaml file
        data: Data to write (must be YAML-serializable primitives only)

    Raises:
        FileWriteError: If file cannot be written
    """
    try:
        # Ensure directory exists
        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        # Atomic write: write to temp file then rename
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=dir_name if dir_name else ".",
            delete=False,
            suffix=".tmp",
        ) as f:
            yaml.dump(dict(data), f, default_flow_style=False, allow_unicode=True)
            temp_path = f.name

        os.replace(temp_path, path)
    except Exception as e:
        raise FileWriteError(f"Failed to write vars file {path}: {e}")


def write_step_output(path: str, payload: dict[str, Any]) -> None:
    """Write step output to step_output.json.

    Args:
        path: Path to step_output.json file
        payload: Output payload dict (messages + optional output)

    Raises:
        FileWriteError: If file cannot be written
    """
    try:
        # Ensure directory exists
        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=False, default=str)
    except Exception as e:
        raise FileWriteError(f"Failed to write step output {path}: {e}")


def write_flow_control(path: str, control: dict[str, Any]) -> None:
    """Write flow control variables for conditional step execution.

    Used by init steps to control which downstream steps run.

    Args:
        path: Path to flow_control.json file
        control: Flow control variables dict

    Raises:
        FileWriteError: If file cannot be written
    """
    try:
        dir_name = os.path.dirname(path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(dict(control), f, indent=2)
    except Exception as e:
        raise FileWriteError(f"Failed to write flow control {path}: {e}")


def ensure_directory(path: str) -> None:
    """Ensure a directory exists, creating it if necessary.

    Args:
        path: Directory path to ensure exists
    """
    os.makedirs(path, exist_ok=True)


def build_step_output(
    messages: list[dict[str, Any]],
    output: dict[str, Any] | None = None,
    context_updates: dict[str, Any] | None = None,
    flow_control: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the step output JSON structure.

    Args:
        messages: List of message dicts
        output: Optional output data
        context_updates: Optional context/vars updates
        flow_control: Optional flow control variables

    Returns:
        Step output payload ready for JSON serialization
    """
    payload: dict[str, Any] = {"messages": messages}

    if output:
        payload["output"] = output

    if context_updates:
        payload["context_updates"] = context_updates

    if flow_control:
        payload["flow_control"] = flow_control

    return payload


def build_error_output(error: str, system: str = "taskkit") -> dict[str, Any]:
    """Build error output for step failures.

    Args:
        error: Error message
        system: System that generated the error

    Returns:
        Error output payload
    """
    return {
        "messages": [
            {
                "severity": "error",
                "text": error,
                "system": system,
            }
        ]
    }
