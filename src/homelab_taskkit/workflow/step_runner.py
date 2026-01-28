"""Step runner for executing workflow steps in Argo containers.

This is the main entry point for step execution in Argo Workflows.
It performs all contract obligations:
1. Parse environment variables
2. Set up logging
3. Read input files (params, vars)
4. Build StepInput and StepDeps
5. Resolve and execute step handler
6. Write output files (step_output, vars, flow_control)
7. Exit with appropriate code
"""

from __future__ import annotations

import logging
import os
import sys
import traceback
from typing import Any

import httpx

from homelab_taskkit.workflow.env import EnvParseError, RuntimeEnv, load_runtime_env
from homelab_taskkit.workflow.files import (
    FileReadError,
    build_error_output,
    build_step_output,
    ensure_directory,
    read_params_json,
    read_vars_yaml,
    write_flow_control,
    write_step_output,
    write_vars_yaml,
)
from homelab_taskkit.workflow.models import Severity, StepDeps, StepInput, StepResult
from homelab_taskkit.workflow.registry import get_step, has_step

# Logger for the runner itself
logger = logging.getLogger("homelab_taskkit.step_runner")


def configure_logging(working_dir: str, step_name: str, debug: bool = False) -> None:
    """Configure logging to write to step log file.

    Args:
        working_dir: Working directory path
        step_name: Step name for log file
        debug: Enable debug logging
    """
    # Ensure working directory exists
    ensure_directory(working_dir)

    log_file = os.path.join(working_dir, f"{step_name}.log")
    log_level = logging.DEBUG if debug else logging.INFO

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # File handler for step log
    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    # Also log to stderr for container logs
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(file_formatter)
    root_logger.addHandler(console_handler)


def build_step_input(env: RuntimeEnv, params: dict[str, Any], vars_data: dict[str, Any]) -> StepInput:
    """Build StepInput from parsed environment and files.

    Args:
        env: Parsed runtime environment
        params: Task parameters from params.json
        vars_data: Shared state from vars.yaml

    Returns:
        StepInput for the step handler
    """
    # Merge workflow params with step-specific params
    merged_params = {**params, **env.step_params}

    return StepInput(
        step_name=env.step_name,
        task_id=env.task_id,
        workflow_name=env.workflow_name,
        params=merged_params,
        vars=vars_data,
        attempt=env.retries,
        total_retries=env.total_retries,
        workflow_result=env.workflow_result,
    )


def build_step_deps(env: RuntimeEnv, timeout: float = 30.0) -> StepDeps:
    """Build StepDeps for step execution.

    Args:
        env: Runtime environment
        timeout: HTTP client timeout

    Returns:
        StepDeps for the step handler
    """
    return StepDeps(
        http=httpx.Client(timeout=timeout, follow_redirects=True),
        logger=logging.getLogger(f"homelab_taskkit.step.{env.step_name}"),
        env=dict(os.environ),
        workdir=env.working_dir,
    )


def run_step(env: RuntimeEnv, debug: bool = False) -> int:
    """Execute a step with full contract handling.

    Args:
        env: Parsed runtime environment
        debug: Enable debug logging

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    step_name = env.step_name
    task_id = env.task_id
    handler_name = env.handler_name

    # Configure logging
    configure_logging(env.working_dir, step_name, debug=debug)
    logger.info(f"Starting step: {step_name} (task: {task_id}, attempt: {env.retries})")
    logger.info(f"Handler: {handler_name}")

    try:
        # Import steps to trigger registrations
        _import_steps()

        # Check if handler exists
        if not has_step(handler_name):
            error_msg = f"Handler not found: {handler_name}"
            logger.error(error_msg)
            return _handle_error(env, error_msg, "taskkit")

        # Get step handler
        handler = get_step(handler_name)

        # Load input files
        params = read_params_json(env.params_file)
        vars_data = read_vars_yaml(env.vars_file_path)

        # Build step input and deps
        step_input = build_step_input(env, params, vars_data)
        deps = build_step_deps(env)

        # Execute step handler
        logger.info(f"Executing handler: {handler_name}")
        try:
            result = handler(step_input, deps)
        except Exception as e:
            logger.exception(f"Step handler raised exception: {e}")
            result = StepResult()
            result.add_error(f"Exception: {e}", system="taskkit")
        finally:
            deps.http.close()

        # Process result
        return _process_result(env, result, vars_data)

    except FileReadError as e:
        logger.error(f"File read error: {e}")
        return _handle_error(env, str(e), "taskkit")

    except Exception as e:
        logger.exception(f"Step execution failed: {e}")
        return _handle_error(env, str(e), "taskkit")


def _process_result(
    env: RuntimeEnv,
    result: StepResult,
    vars_data: dict[str, Any],
) -> int:
    """Process step result and write outputs.

    Args:
        env: Runtime environment
        result: Step result
        vars_data: Current vars data

    Returns:
        Exit code
    """
    step_name = env.step_name

    # Log messages
    for msg in result.messages:
        level = (
            logging.ERROR
            if msg.severity == Severity.ERROR
            else (logging.WARNING if msg.severity == Severity.WARNING else logging.INFO)
        )
        logger.log(level, f"[{step_name}] {msg.text}")

    # Build and write step_output.json
    output_payload = build_step_output(
        messages=[m.model_dump() for m in result.messages],
        output=result.output,
        context_updates=result.context_updates,
        flow_control=result.flow_control,
    )
    write_step_output(env.output_file, output_payload)
    logger.info(f"Wrote step output to {env.output_file}")

    # Write flow_control.json if provided (typically from init step)
    if result.flow_control:
        write_flow_control(env.flow_control_file, result.flow_control)
        logger.info(f"Wrote flow control to {env.flow_control_file}")

    # Update vars.yaml with context_updates
    if result.context_updates:
        merged_vars = {**vars_data, **result.context_updates}
        write_vars_yaml(env.vars_file_path, merged_vars)
        logger.info(f"Updated vars with keys: {list(result.context_updates.keys())}")

    # Determine exit code
    if result.has_errors:
        logger.error(f"Step {step_name} failed with errors")
        return 1

    logger.info(f"Step {step_name} completed successfully")
    return 0


def _handle_error(env: RuntimeEnv, error: str, system: str) -> int:
    """Handle step execution error.

    Args:
        env: Runtime environment
        error: Error message
        system: System that generated the error

    Returns:
        Exit code (always non-zero)
    """
    # Write error to step_output.json
    try:
        output_payload = build_error_output(error, system)
        write_step_output(env.output_file, output_payload)
    except Exception as e:
        logger.error(f"Failed to write error output: {e}")

    return 1


def _import_steps() -> None:
    """Import step modules to trigger step registrations.

    This is called once at the start of step execution.
    """
    try:
        import homelab_taskkit.steps  # noqa: F401

        logger.debug("Imported homelab_taskkit.steps")
    except ImportError:
        logger.debug("No homelab_taskkit.steps package found")

    try:
        import homelab_taskkit.tasks  # noqa: F401

        logger.debug("Imported homelab_taskkit.tasks")
    except ImportError:
        logger.debug("No homelab_taskkit.tasks package found")


def main(debug: bool = False) -> int:
    """Main entry point for the step runner.

    Args:
        debug: Enable debug logging

    Returns:
        Exit code
    """
    try:
        env = load_runtime_env()
        return run_step(env, debug=debug)
    except EnvParseError as e:
        # Can't configure logging yet, print to stderr
        print(f"Environment parse error: {e}", file=sys.stderr)
        # Try to write minimal error output
        output_file = os.environ.get("TASKKIT_OUTPUT_FILE", "/tmp/step_output.json")
        try:
            output_payload = build_error_output(str(e), "taskkit")
            write_step_output(output_file, output_payload)
        except Exception:
            pass
        return 1
    except Exception as e:
        print(f"Runner failed: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
