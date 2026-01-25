"""JSON Schema validation utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator


class SchemaValidationError(Exception):
    """Raised when input or output fails schema validation."""

    def __init__(self, message: str, errors: list[str]) -> None:
        super().__init__(message)
        self.errors = errors


def load_schema(path: str | Path) -> dict[str, Any]:
    """Load a JSON schema from a file path.

    Args:
        path: Path to the JSON schema file.

    Returns:
        The parsed JSON schema as a dictionary.

    Raises:
        FileNotFoundError: If the schema file doesn't exist.
        json.JSONDecodeError: If the file contains invalid JSON.
    """
    with open(path) as f:
        return json.load(f)


def validate(instance: Any, schema: dict[str, Any]) -> None:
    """Validate an instance against a JSON schema.

    Args:
        instance: The data to validate.
        schema: The JSON schema to validate against.

    Raises:
        SchemaValidationError: If validation fails.
    """
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(instance))

    if errors:
        error_messages = [_format_validation_error(e) for e in errors]
        raise SchemaValidationError(
            f"Schema validation failed with {len(errors)} error(s)",
            error_messages,
        )


def _format_validation_error(error: jsonschema.ValidationError) -> str:
    """Format a validation error into a human-readable string."""
    path = ".".join(str(p) for p in error.absolute_path) or "(root)"
    return f"At '{path}': {error.message}"
