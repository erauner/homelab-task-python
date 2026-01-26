"""Task runner - orchestrates task execution with validation."""

from __future__ import annotations

import contextlib
import logging
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from homelab_taskkit.context import (
    DEFAULT_CONTEXT_IN,
    DEFAULT_CONTEXT_OUT,
    MAX_CONTEXT_BYTES,
    apply_patch,
    extract_context_patch,
    load_context,
    write_context,
)
from homelab_taskkit.deps import build_deps
from homelab_taskkit.errors import ContextError, ContextSizeError
from homelab_taskkit.fanout import (
    DEFAULT_FANOUT_OUT,
    TaskkitFanout,
    empty_fanout,
    extract_fanout,
    write_fanout,
)
from homelab_taskkit.io import read_input, write_output
from homelab_taskkit.messages import (
    DEFAULT_MESSAGES_OUT,
    TaskkitMessages,
    empty_messages,
    extract_messages,
    write_messages,
)
from homelab_taskkit.registry import TaskNotFoundError, get_task
from homelab_taskkit.schema import SchemaValidationError, load_schema, validate

logger = logging.getLogger(__name__)

# Exit codes
EXIT_SUCCESS = 0
EXIT_RUNTIME_ERROR = 1
EXIT_VALIDATION_ERROR = 2
EXIT_TASK_NOT_FOUND = 3
EXIT_CONTEXT_ERROR = 4


def run_task(
    task_name: str,
    input_source: str,
    output_path: str,
    *,
    schemas_root: str | Path = "schemas",
    env: Mapping[str, str] | None = None,
    context_enabled: bool | None = None,
    context_input_path: str | Path | None = None,
    context_output_path: str | Path | None = None,
    max_context_bytes: int = MAX_CONTEXT_BYTES,
    messages_enabled: bool | None = None,
    messages_output_path: str | Path | None = None,
    fanout_enabled: bool | None = None,
    fanout_output_path: str | Path | None = None,
) -> int:
    """Run a task with full validation and optional artifacts.

    This is the main orchestration function that:
    1. Resolves the task definition
    2. Loads context (if enabled)
    3. Loads and validates input against schema
    4. Builds dependencies with context
    5. Executes the task
    6. Extracts context patch, messages, and fanout from output
    7. Validates output against schema
    8. Writes output to file
    9. Merges and writes context (if enabled)
    10. Writes messages artifact (if enabled)
    11. Writes fanout artifact (if enabled)

    Args:
        task_name: Name of the task to run.
        input_source: Path to input JSON file or inline JSON string.
        output_path: Path to write the output JSON.
        schemas_root: Root directory containing task schemas.
        env: Environment variables (defaults to os.environ).
        context_enabled: Enable context artifacts (None=auto-detect).
        context_input_path: Path to input context JSON (default: /inputs/context.json).
        context_output_path: Path to write output context JSON (default: /outputs/context.json).
        max_context_bytes: Maximum context size in bytes (default: 32KB).
        messages_enabled: Enable messages artifact (None=auto-detect based on /outputs).
        messages_output_path: Path to write messages JSON (default: /outputs/messages.json).
        fanout_enabled: Enable fanout artifact (None=auto-detect based on /outputs).
        fanout_output_path: Path to write fanout JSON (default: /outputs/fanout.json).

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

    # Check for Argo environment
    inputs_dir_exists = Path("/inputs").is_dir()
    outputs_dir_exists = Path("/outputs").is_dir()

    # Determine if context artifacts are enabled
    # Auto-detect: enable if /inputs and /outputs directories exist (Argo environment)
    if context_enabled is None:
        context_enabled = inputs_dir_exists and outputs_dir_exists

    # Determine if messages/fanout artifacts are enabled
    # Auto-detect: enable if /outputs directory exists
    if messages_enabled is None:
        messages_enabled = outputs_dir_exists
    if fanout_enabled is None:
        fanout_enabled = outputs_dir_exists

    # Resolve context paths
    ctx_in_path = Path(context_input_path) if context_input_path else Path(DEFAULT_CONTEXT_IN)
    ctx_out_path = Path(context_output_path) if context_output_path else Path(DEFAULT_CONTEXT_OUT)

    # Resolve messages/fanout paths
    msgs_out_path = (
        Path(messages_output_path) if messages_output_path else Path(DEFAULT_MESSAGES_OUT)
    )
    fanout_out_path = Path(fanout_output_path) if fanout_output_path else Path(DEFAULT_FANOUT_OUT)

    if context_enabled:
        logger.info(f"Context artifacts enabled (in={ctx_in_path}, out={ctx_out_path})")
    if messages_enabled:
        logger.info(f"Messages artifact enabled (out={msgs_out_path})")
    if fanout_enabled:
        logger.info(f"Fanout artifact enabled (out={fanout_out_path})")

    # Initialize artifact containers
    messages: TaskkitMessages = empty_messages()
    fanout: TaskkitFanout = empty_fanout()

    # 1. Resolve task definition
    try:
        task = get_task(task_name)
    except TaskNotFoundError as e:
        logger.error(f"Task not found: {task_name}")
        logger.error(f"Available tasks: {', '.join(e.available)}")
        messages.add_error(
            f"Task not found: {task_name}",
            code="TASK_NOT_FOUND",
            source="runner",
            data={"available": e.available},
        )
        _write_artifacts_on_error(messages_enabled, msgs_out_path, messages)
        return EXIT_TASK_NOT_FOUND

    # 2. Load context (if enabled)
    context_data = None
    if context_enabled:
        try:
            context_data = load_context(ctx_in_path)
            logger.info(f"Context loaded: {len(context_data.vars)} vars")
        except ContextError as e:
            logger.error(f"Failed to load context: {e}")
            messages.add_error(str(e), code="CONTEXT_LOAD_ERROR", source="runner")
            _write_artifacts_on_error(messages_enabled, msgs_out_path, messages)
            return EXIT_CONTEXT_ERROR

    # 3. Load input and validate against schema
    try:
        input_data = read_input(input_source)
    except Exception as e:
        logger.error(f"Failed to read input: {e}")
        messages.add_error(f"Failed to read input: {e}", code="INPUT_READ_ERROR", source="runner")
        _write_artifacts_on_error(messages_enabled, msgs_out_path, messages)
        return EXIT_VALIDATION_ERROR

    input_schema_path = schemas_root / task.input_schema
    try:
        input_schema = load_schema(input_schema_path)
        validate(input_data, input_schema)
        logger.info("Input validation passed")
    except FileNotFoundError:
        logger.error(f"Input schema not found: {input_schema_path}")
        messages.add_error(
            f"Input schema not found: {input_schema_path}",
            code="SCHEMA_NOT_FOUND",
            source="runner",
        )
        _write_artifacts_on_error(messages_enabled, msgs_out_path, messages)
        return EXIT_VALIDATION_ERROR
    except SchemaValidationError as e:
        logger.error(f"Input validation failed: {e}")
        for err in e.errors:
            logger.error(f"  - {err}")
        messages.add_error(
            f"Input validation failed: {e}",
            code="INPUT_VALIDATION_ERROR",
            source="runner",
            data={"errors": e.errors},
        )
        _write_artifacts_on_error(messages_enabled, msgs_out_path, messages)
        return EXIT_VALIDATION_ERROR

    # 4. Build dependencies and execute task
    try:
        context_vars = context_data.vars if context_data else {}
        with build_deps(env, context=context_vars) as deps:
            logger.info("Executing task...")
            output_data_raw = task.run(input_data, deps)
    except Exception as e:
        logger.exception(f"Task execution failed: {e}")
        messages.add_error(
            f"Task execution failed: {e}", code="TASK_EXECUTION_ERROR", source="runner"
        )
        _write_artifacts_on_error(messages_enabled, msgs_out_path, messages)
        return EXIT_RUNTIME_ERROR

    # 5. Extract context patch from output (if present)
    try:
        output_data, context_patch = extract_context_patch(output_data_raw)
        if context_patch and context_enabled:
            logger.info(
                f"Context patch: set={len(context_patch.set)} keys, "
                f"unset={len(context_patch.unset)} keys"
            )
    except ContextError as e:
        logger.error(f"Invalid context patch: {e}")
        messages.add_error(str(e), code="CONTEXT_PATCH_ERROR", source="runner")
        _write_artifacts_on_error(messages_enabled, msgs_out_path, messages)
        return EXIT_CONTEXT_ERROR

    # 5a. Extract messages from output (if present)
    try:
        output_data, task_messages = extract_messages(output_data, task_name=task_name)
        messages.messages.extend(task_messages)
        if task_messages:
            logger.info(f"Task emitted {len(task_messages)} message(s)")
    except ValueError as e:
        logger.error(f"Invalid messages structure: {e}")
        messages.add_error(str(e), code="MESSAGES_PARSE_ERROR", source="runner")

    # 5b. Extract fanout from output (if present)
    try:
        output_data, extracted_fanout = extract_fanout(output_data)
        if extracted_fanout is not None:
            fanout = extracted_fanout
            logger.info(f"Task emitted fanout with {fanout.count} item(s)")
    except ValueError as e:
        logger.error(f"Invalid fanout structure: {e}")
        messages.add_error(str(e), code="FANOUT_PARSE_ERROR", source="runner")

    # 6. Validate output against schema
    output_schema_path = schemas_root / task.output_schema
    try:
        output_schema = load_schema(output_schema_path)
        validate(output_data, output_schema)
        logger.info("Output validation passed")
    except FileNotFoundError:
        logger.error(f"Output schema not found: {output_schema_path}")
        messages.add_error(
            f"Output schema not found: {output_schema_path}",
            code="SCHEMA_NOT_FOUND",
            source="runner",
        )
        _write_artifacts_on_error(messages_enabled, msgs_out_path, messages)
        return EXIT_VALIDATION_ERROR
    except SchemaValidationError as e:
        logger.error(f"Output validation failed: {e}")
        for err in e.errors:
            logger.error(f"  - {err}")
        messages.add_error(
            f"Output validation failed: {e}",
            code="OUTPUT_VALIDATION_ERROR",
            source="runner",
            data={"errors": e.errors},
        )
        _write_artifacts_on_error(messages_enabled, msgs_out_path, messages)
        return EXIT_VALIDATION_ERROR

    # 7. Write output
    try:
        write_output(output_path, output_data)
        logger.info(f"Output written to: {output_path}")
    except Exception as e:
        logger.error(f"Failed to write output: {e}")
        messages.add_error(
            f"Failed to write output: {e}", code="OUTPUT_WRITE_ERROR", source="runner"
        )
        _write_artifacts_on_error(messages_enabled, msgs_out_path, messages)
        return EXIT_RUNTIME_ERROR

    # 8. Merge and write context (if enabled)
    if context_enabled and context_data is not None:
        try:
            merged_context = apply_patch(context_data, context_patch)
            write_context(ctx_out_path, merged_context, max_bytes=max_context_bytes)
            logger.info(f"Context written to: {ctx_out_path} ({len(merged_context.vars)} vars)")
        except ContextSizeError as e:
            logger.error(f"Context size exceeded: {e}")
            messages.add_error(str(e), code="CONTEXT_SIZE_ERROR", source="runner")
            _write_artifacts_on_error(messages_enabled, msgs_out_path, messages)
            return EXIT_CONTEXT_ERROR
        except ContextError as e:
            logger.error(f"Failed to write context: {e}")
            messages.add_error(str(e), code="CONTEXT_WRITE_ERROR", source="runner")
            _write_artifacts_on_error(messages_enabled, msgs_out_path, messages)
            return EXIT_CONTEXT_ERROR

    # 9. Write messages artifact (if enabled)
    if messages_enabled:
        try:
            write_messages(msgs_out_path, messages)
            logger.info(
                f"Messages written to: {msgs_out_path} ({len(messages.messages)} message(s))"
            )
        except Exception as e:
            logger.warning(f"Failed to write messages artifact: {e}")
            # Don't fail the task for artifact write errors

    # 10. Write fanout artifact (if enabled)
    if fanout_enabled:
        try:
            write_fanout(fanout_out_path, fanout)
            logger.info(f"Fanout written to: {fanout_out_path} ({fanout.count} item(s))")
        except Exception as e:
            logger.warning(f"Failed to write fanout artifact: {e}")
            # Don't fail the task for artifact write errors

    logger.info(f"Task {task_name} completed successfully")
    return EXIT_SUCCESS


def _write_artifacts_on_error(
    messages_enabled: bool,
    msgs_out_path: Path,
    messages: TaskkitMessages,
) -> None:
    """Write messages artifact when exiting early due to error.

    This ensures diagnostic information is available even on failures.
    Silently ignores write errors since we're already in an error path.
    """
    if messages_enabled:
        with contextlib.suppress(Exception):
            write_messages(msgs_out_path, messages)


def _format_output(data: Any) -> str:
    """Format output data for logging."""
    import json

    return json.dumps(data, indent=2, default=str)
