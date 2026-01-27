"""Local workflow runner for testing without Argo/K8s.

This module provides the LocalRunner class that executes workflows locally,
enabling end-to-end testing of workflow definitions before deployment.

Usage:
    runner = LocalRunner(
        workflow_path="workflows/my_workflow.yaml",
        params_path="params.json",
        workdir="./test-run",
    )
    result = runner.run()  # Returns "Succeeded" | "Failed" | "Error"
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import yaml

from homelab_taskkit.workflow.models import (
    Severity,
    StepDeps,
    StepInput,
    StepResult,
)
from homelab_taskkit.workflow.registry import get_step, has_step
from homelab_taskkit.workflow.workflow import (
    StepTemplate,
    WorkflowDefinition,
    WorkflowStep,
)

logger = logging.getLogger(__name__)


class WorkflowExecutionResult:
    """Result of a workflow execution.

    Attributes:
        result: Final status ("Succeeded" | "Failed" | "Error").
        task_id: Unique task identifier for the run.
        workflow_name: Name of the executed workflow.
        workdir: Working directory used for the run.
        step_results: Results from each step execution.
        duration_seconds: Total execution time.
        error: Error message if result is "Error".
    """

    def __init__(self, workflow_name: str, task_id: str, workdir: str) -> None:
        self.result: str = "Succeeded"
        self.task_id = task_id
        self.workflow_name = workflow_name
        self.workdir = workdir
        self.step_results: dict[str, dict[str, Any]] = {}
        self.duration_seconds: float = 0.0
        self.error: str | None = None
        self.start_time: datetime | None = None
        self.end_time: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "result": self.result,
            "task_id": self.task_id,
            "workflow_name": self.workflow_name,
            "workdir": self.workdir,
            "step_results": self.step_results,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }


class LocalRunner:
    """Execute workflows locally for testing.

    The LocalRunner:
    1. Loads workflow definition from YAML
    2. Loads params from JSON (optional)
    3. Sets up working directory with vars.yaml
    4. Executes steps in topological order
    5. Handles retries for failed steps
    6. Always runs finalize steps even on failure
    7. Produces a final result ("Succeeded" | "Failed" | "Error")

    Args:
        workflow_path: Path to workflow YAML file.
        params_path: Optional path to params JSON file.
        workdir: Working directory for execution (created if missing).
        task_id: Optional task ID (generated if not provided).
        timeout: HTTP client timeout in seconds.
    """

    def __init__(
        self,
        workflow_path: str | Path,
        params_path: str | Path | None = None,
        workdir: str | Path | None = None,
        task_id: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.workflow_path = Path(workflow_path)
        self.params_path = Path(params_path) if params_path else None
        self.task_id = task_id or str(uuid.uuid4())[:8]
        self.timeout = timeout

        # Load workflow definition
        self.workflow = WorkflowDefinition.from_yaml(self.workflow_path)

        # Validate workflow
        errors = self.workflow.validate_dependencies()
        if errors:
            raise ValueError(f"Workflow validation failed: {'; '.join(errors)}")

        # Load params
        self.params = self._load_params()

        # Setup working directory
        if workdir:
            self.workdir = Path(workdir)
        else:
            timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
            self.workdir = Path(f"./workflow-runs/{self.workflow.name}-{timestamp}")

        # Initialize vars before setup (needed for vars.yaml)
        self.vars: dict[str, Any] = {}

        self._setup_workdir()

        # Track execution state
        self._failed_steps: set[str] = set()
        self._skipped_steps: set[str] = set()
        self._flow_control: dict[str, Any] = {}

    def _load_params(self) -> dict[str, Any]:
        """Load parameters from JSON file."""
        if not self.params_path:
            return {}

        if not self.params_path.exists():
            logger.warning(f"Params file not found: {self.params_path}")
            return {}

        with open(self.params_path) as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError(f"Params file must contain a JSON object: {self.params_path}")

        return data

    def _setup_workdir(self) -> None:
        """Create working directory structure."""
        self.workdir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (self.workdir / "steps").mkdir(exist_ok=True)
        (self.workdir / "logs").mkdir(exist_ok=True)

        # Initialize vars.yaml if it doesn't exist
        vars_path = self.workdir / "vars.yaml"
        if not vars_path.exists():
            self._save_vars()

    def _load_vars(self) -> dict[str, Any]:
        """Load vars from workdir."""
        vars_path = self.workdir / "vars.yaml"
        if not vars_path.exists():
            return {}

        with open(vars_path) as f:
            data = yaml.safe_load(f)

        return data if isinstance(data, dict) else {}

    def _save_vars(self) -> None:
        """Save vars to workdir."""
        vars_path = self.workdir / "vars.yaml"
        with open(vars_path, "w") as f:
            yaml.dump(self.vars, f, default_flow_style=False)

    def _save_step_result(self, step: WorkflowStep, result: StepResult, attempt: int) -> None:
        """Save step result to workdir."""
        step_dir = self.workdir / "steps" / step.name
        step_dir.mkdir(parents=True, exist_ok=True)

        result_path = step_dir / f"result-attempt-{attempt}.json"
        with open(result_path, "w") as f:
            json.dump(result.model_dump(), f, indent=2, default=str)

    def _build_step_input(self, step: WorkflowStep, attempt: int) -> StepInput:
        """Build StepInput for a step execution."""
        # Merge workflow params with step-specific params
        merged_params = {**self.params, **step.params}

        return StepInput(
            step_name=step.name,
            task_id=self.task_id,
            workflow_name=self.workflow.name,
            params=merged_params,
            vars=dict(self.vars),  # Copy to prevent mutation
            attempt=attempt,
            total_retries=self.workflow.default_retries,
        )

    def _build_step_deps(self) -> StepDeps:
        """Build StepDeps for step execution."""
        return StepDeps(
            http=httpx.Client(timeout=self.timeout, follow_redirects=True),
            logger=logging.getLogger(f"homelab_taskkit.workflow.{self.workflow.name}"),
            env=dict(os.environ),
            workdir=str(self.workdir),
        )

    def _should_skip_step(self, step: WorkflowStep) -> bool:
        """Check if step should be skipped based on flow control."""
        # Check global flow control
        if self._flow_control.get("skip_remaining"):
            return True

        # Check step-specific when condition
        if step.when_flow_control:
            # Simple expression evaluation: "key != value" or "key == value"
            expr = step.when_flow_control.strip()

            if "!=" in expr:
                key, value = expr.split("!=", 1)
                key = key.strip()
                value = value.strip().strip("'\"")
                actual = str(self._flow_control.get(key, ""))
                if actual == value:
                    return True

            elif "==" in expr:
                key, value = expr.split("==", 1)
                key = key.strip()
                value = value.strip().strip("'\"")
                actual = str(self._flow_control.get(key, ""))
                if actual != value:
                    return True

        return False

    def _execute_step(self, step: WorkflowStep) -> bool:
        """Execute a single step with retry logic.

        Args:
            step: The step to execute.

        Returns:
            True if step succeeded, False otherwise.
        """
        handler_name = self.workflow.get_step_handler_name(step)
        logger.info(f"Executing step: {step.name} (handler: {handler_name})")

        # Check if handler exists
        if not has_step(handler_name):
            logger.error(f"Handler not found: {handler_name}")
            self._failed_steps.add(step.name)
            return False

        # Check if step should be skipped
        if self._should_skip_step(step):
            logger.info(f"Skipping step due to flow control: {step.name}")
            self._skipped_steps.add(step.name)
            return True

        # Determine max retries based on template
        if step.template in (StepTemplate.INIT, StepTemplate.FINALIZE, StepTemplate.NO_RETRY):
            max_retries = 0
        else:
            max_retries = self.workflow.default_retries

        # Execute with retries
        handler = get_step(handler_name)
        deps = self._build_step_deps()

        try:
            for attempt in range(max_retries + 1):
                step_input = self._build_step_input(step, attempt)

                logger.info(f"Step {step.name} attempt {attempt + 1}/{max_retries + 1}")

                try:
                    result = handler(step_input, deps)
                except Exception as e:
                    logger.exception(f"Step {step.name} raised exception: {e}")
                    result = StepResult()
                    result.add_error(f"Exception: {e}", system="local-runner")

                # Save result
                self._save_step_result(step, result, attempt)

                # Log messages
                for msg in result.messages:
                    level = (
                        logging.ERROR
                        if msg.severity == Severity.ERROR
                        else (logging.WARNING if msg.severity == Severity.WARNING else logging.INFO)
                    )
                    logger.log(level, f"[{step.name}] {msg.text}")

                # Update vars with context_updates
                if result.context_updates:
                    self.vars.update(result.context_updates)
                    self._save_vars()

                # Update flow control
                if result.flow_control:
                    self._flow_control.update(result.flow_control)

                # Check for success
                if not result.has_errors:
                    logger.info(f"Step {step.name} succeeded")
                    return True

                # Check if we should retry
                if attempt < max_retries:
                    logger.warning(f"Step {step.name} failed, retrying...")
                    time.sleep(1)  # Brief delay before retry
                else:
                    logger.error(f"Step {step.name} failed after {max_retries + 1} attempts")

            # All retries exhausted
            self._failed_steps.add(step.name)
            return False

        finally:
            deps.http.close()

    def run(self) -> str:
        """Execute the workflow.

        Returns:
            Final result: "Succeeded" | "Failed" | "Error"
        """
        execution = WorkflowExecutionResult(
            workflow_name=self.workflow.name,
            task_id=self.task_id,
            workdir=str(self.workdir),
        )
        execution.start_time = datetime.now(UTC)

        logger.info(f"Starting workflow: {self.workflow.name}")
        logger.info(f"Task ID: {self.task_id}")
        logger.info(f"Working directory: {self.workdir}")

        try:
            # Load any existing vars (for resumed runs)
            self.vars = self._load_vars()

            # Get execution order
            non_finalize_steps = self.workflow.get_non_finalize_steps()
            finalize_steps = self.workflow.get_finalize_steps()

            # Execute non-finalize steps
            for step in non_finalize_steps:
                success = self._execute_step(step)
                execution.step_results[step.name] = {
                    "success": success,
                    "skipped": step.name in self._skipped_steps,
                }

                # Stop on failure (but still run finalize)
                if not success and step.name not in self._skipped_steps:
                    logger.error(f"Workflow stopping due to step failure: {step.name}")
                    execution.result = "Failed"
                    break

            # Always run finalize steps
            for step in finalize_steps:
                success = self._execute_step(step)
                execution.step_results[step.name] = {
                    "success": success,
                    "skipped": step.name in self._skipped_steps,
                }

            # Determine final result
            if self._failed_steps or self._flow_control.get("mark_failed"):
                execution.result = "Failed"
            else:
                execution.result = "Succeeded"

        except Exception as e:
            logger.exception(f"Workflow execution error: {e}")
            execution.result = "Error"
            execution.error = str(e)

        finally:
            execution.end_time = datetime.now(UTC)
            execution.duration_seconds = (execution.end_time - execution.start_time).total_seconds()

            # Save execution result
            result_path = self.workdir / "execution-result.json"
            with open(result_path, "w") as f:
                json.dump(execution.to_dict(), f, indent=2, default=str)

            logger.info(f"Workflow completed: {execution.result}")
            logger.info(f"Duration: {execution.duration_seconds:.2f}s")

        return execution.result

    def validate(self) -> list[str]:
        """Validate workflow without executing it.

        Checks:
        - All handlers are registered
        - Dependencies are valid
        - No circular dependencies

        Returns:
            List of validation errors (empty if valid).
        """
        errors: list[str] = []

        # Check dependencies
        errors.extend(self.workflow.validate_dependencies())

        # Check handlers exist
        for step in self.workflow.steps:
            handler_name = self.workflow.get_step_handler_name(step)
            if not has_step(handler_name):
                errors.append(f"Handler not found for step '{step.name}': {handler_name}")

        # Check for circular dependencies (via get_execution_order)
        try:
            self.workflow.get_execution_order()
        except ValueError as e:
            errors.append(str(e))

        return errors
