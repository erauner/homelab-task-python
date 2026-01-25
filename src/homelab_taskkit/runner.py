"""Task runner - orchestrates task execution with validation."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from homelab_taskkit.deps import build_deps
from homelab_taskkit.io import read_input, write_output
from homelab_taskkit.registry import TaskNotFoundError, get_task
from homelab_taskkit.schema import SchemaValidationError, load_schema, validate

logger = logging.getLogger(__name__)

# Exit codes
EXIT_SUCCESS = 0
EXIT_RUNTIME_ERROR = 1
EXIT_VALIDATION_ERROR = 2
EXIT_TASK_NOT_FOUND = 3


def run_task(
    task_name: str,
    input_source: str,
    output_path: str,
    *,
    schemas_root: str | Path = "schemas",
    env: Mapping[str, str] | None = None,
) -> int:
    """Run a task with full validation.

    This is the main orchestration function that:
    1. Resolves the task definition
    2. Loads and validates input against schema
    3. Builds dependencies
    4. Executes the task
    5. Validates output against schema
    6. Writes output to file

    Args:
        task_name: Name of the task to run.
        input_source: Path to input JSON file or inline JSON string.
        output_path: Path to write the output JSON.
        schemas_root: Root directory containing task schemas.
        env: Environment variables (defaults to os.environ).

    Returns:
        Exit code (0 for success, non-zero for errors).
    """
    if env is None:
        env = os.environ

    schemas_root = Path(schemas_root)

    # Configure logging for task output
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
        stream=sys.stderr,
    )

    logger.info(f"Starting task: {task_name}")

    # 1. Resolve task definition
    try:
        task = get_task(task_name)
    except TaskNotFoundError as e:
        logger.error(f"Task not found: {task_name}")
        logger.error(f"Available tasks: {', '.join(e.available)}")
        return EXIT_TASK_NOT_FOUND

    # 2. Load input and validate against schema
    try:
        input_data = read_input(input_source)
    except Exception as e:
        logger.error(f"Failed to read input: {e}")
        return EXIT_VALIDATION_ERROR

    input_schema_path = schemas_root / task.input_schema
    try:
        input_schema = load_schema(input_schema_path)
        validate(input_data, input_schema)
        logger.info("Input validation passed")
    except FileNotFoundError:
        logger.error(f"Input schema not found: {input_schema_path}")
        return EXIT_VALIDATION_ERROR
    except SchemaValidationError as e:
        logger.error(f"Input validation failed: {e}")
        for err in e.errors:
            logger.error(f"  - {err}")
        return EXIT_VALIDATION_ERROR

    # 3. Build dependencies and execute task
    try:
        with build_deps(env) as deps:
            logger.info("Executing task...")
            output_data = task.run(input_data, deps)
    except Exception as e:
        logger.exception(f"Task execution failed: {e}")
        return EXIT_RUNTIME_ERROR

    # 4. Validate output against schema
    output_schema_path = schemas_root / task.output_schema
    try:
        output_schema = load_schema(output_schema_path)
        validate(output_data, output_schema)
        logger.info("Output validation passed")
    except FileNotFoundError:
        logger.error(f"Output schema not found: {output_schema_path}")
        return EXIT_VALIDATION_ERROR
    except SchemaValidationError as e:
        logger.error(f"Output validation failed: {e}")
        for err in e.errors:
            logger.error(f"  - {err}")
        return EXIT_VALIDATION_ERROR

    # 5. Write output
    try:
        write_output(output_path, output_data)
        logger.info(f"Output written to: {output_path}")
    except Exception as e:
        logger.error(f"Failed to write output: {e}")
        return EXIT_RUNTIME_ERROR

    logger.info(f"Task {task_name} completed successfully")
    return EXIT_SUCCESS


def _format_output(data: Any) -> str:
    """Format output data for logging."""
    import json

    return json.dumps(data, indent=2, default=str)
