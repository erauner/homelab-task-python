"""Workflow definition models for YAML-based workflows.

This module provides the data structures for defining workflows:
- WorkflowStep: Individual step with dependencies
- WorkflowDefinition: Complete workflow loaded from YAML
- StepTemplate: Step execution templates (init, action, finalize, etc.)
"""

from __future__ import annotations

from collections import deque
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class StepTemplate(str, Enum):
    """Step execution templates.

    Controls how the runner handles each step type:
    - INIT: Runs first, typically validates params and initializes vars.
    - ACTION: Standard step with retry support.
    - FINALIZE: Always runs at the end, even if previous steps failed.
    - FANOUT_SOURCE: Produces a list for parallel fan-out (future).
    - NO_RETRY: Action that should not be retried on failure.
    """

    INIT = "init"
    ACTION = "action"
    FINALIZE = "finalize"
    FANOUT_SOURCE = "fanout-source"
    NO_RETRY = "no-retry"


class WorkflowStep(BaseModel):
    """Single step in a workflow.

    Attributes:
        name: Unique step identifier (used to build handler name).
        depends: List of step names that must complete before this step.
        template: Step execution template (affects retry/ordering behavior).
        params: Static parameters passed to the step handler.
        when_flow_control: Optional flow control condition (e.g., "skip_remaining != true").
    """

    name: str
    depends: list[str] = Field(default_factory=list)
    template: StepTemplate = Field(default=StepTemplate.ACTION)
    params: dict[str, Any] = Field(default_factory=dict)
    when_flow_control: str | None = None


class WorkflowDefinition(BaseModel):
    """Complete workflow definition loaded from YAML.

    Attributes:
        name: Workflow identifier.
        platform: Platform identifier (e.g., "homelab", "smoke-test").
        handler_prefix: Prefix for step handler names (e.g., "smoke-test" -> "smoke-test-init").
        context: Execution context ("local" or "argo").
        steps: Ordered list of workflow steps.
        default_retries: Default retry count for action steps.
        timeout_seconds: Maximum workflow execution time.
    """

    name: str
    platform: str
    handler_prefix: str | None = None
    context: str = "local"
    steps: list[WorkflowStep] = Field(default_factory=list)
    default_retries: int = 3
    timeout_seconds: int = 3600

    @classmethod
    def from_yaml(cls, path: str | Path) -> WorkflowDefinition:
        """Load workflow definition from a YAML file.

        Args:
            path: Path to the YAML file.

        Returns:
            WorkflowDefinition instance.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the YAML is invalid.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Workflow file not found: {path}")

        with open(path) as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise ValueError(f"Workflow file must contain a YAML object: {path}")

        return cls.model_validate(data)

    def get_step_handler_name(self, step: WorkflowStep) -> str:
        """Get the handler name for a step.

        Handler names follow the pattern: {handler_prefix}-{step_name}
        If no handler_prefix is set, uses just the step name.

        Args:
            step: The workflow step.

        Returns:
            Handler name to look up in the step registry.
        """
        if self.handler_prefix:
            return f"{self.handler_prefix}-{step.name}"
        return step.name

    def get_step_by_name(self, name: str) -> WorkflowStep | None:
        """Get a step by its name.

        Args:
            name: Step name to find.

        Returns:
            The step if found, None otherwise.
        """
        for step in self.steps:
            if step.name == name:
                return step
        return None

    def get_execution_order(self) -> list[WorkflowStep]:
        """Get steps in topological order (dependencies first).

        Uses Kahn's algorithm for topological sorting. Steps with
        no dependencies are sorted alphabetically for determinism.

        Returns:
            Steps ordered so that dependencies are always before dependents.

        Raises:
            ValueError: If there's a circular dependency.
        """
        # Build dependency graph
        in_degree: dict[str, int] = {}
        dependents: dict[str, list[str]] = {}
        step_map: dict[str, WorkflowStep] = {}

        for step in self.steps:
            step_map[step.name] = step
            in_degree[step.name] = len(step.depends)
            dependents.setdefault(step.name, [])
            for dep in step.depends:
                dependents.setdefault(dep, []).append(step.name)

        # Find all steps with no dependencies
        queue: deque[str] = deque()
        no_deps = sorted(name for name, deg in in_degree.items() if deg == 0)
        queue.extend(no_deps)

        # Process in topological order (Kahn's algorithm)
        result: list[WorkflowStep] = []
        while queue:
            name = queue.popleft()
            result.append(step_map[name])

            # Reduce in-degree of dependents
            next_ready: list[str] = []
            for dependent in dependents.get(name, []):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    next_ready.append(dependent)

            # Sort for deterministic ordering
            queue.extend(sorted(next_ready))

        # Check for cycles
        if len(result) != len(self.steps):
            processed = {s.name for s in result}
            remaining = [s.name for s in self.steps if s.name not in processed]
            raise ValueError(f"Circular dependency detected among steps: {remaining}")

        return result

    def get_non_finalize_steps(self) -> list[WorkflowStep]:
        """Get steps that are not finalize steps, in execution order.

        Returns:
            Non-finalize steps in topological order.
        """
        return [
            step
            for step in self.get_execution_order()
            if step.template != StepTemplate.FINALIZE
        ]

    def get_finalize_steps(self) -> list[WorkflowStep]:
        """Get finalize steps, in execution order.

        Returns:
            Finalize steps in topological order.
        """
        return [
            step
            for step in self.get_execution_order()
            if step.template == StepTemplate.FINALIZE
        ]

    def validate_dependencies(self) -> list[str]:
        """Validate that all dependencies reference existing steps.

        Returns:
            List of error messages (empty if valid).
        """
        errors: list[str] = []
        step_names = {step.name for step in self.steps}

        for step in self.steps:
            for dep in step.depends:
                if dep not in step_names:
                    errors.append(
                        f"Step '{step.name}' depends on unknown step '{dep}'"
                    )

        return errors
