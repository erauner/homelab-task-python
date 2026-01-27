"""Tests for workflow definition models."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from homelab_taskkit.workflow.workflow import (
    StepTemplate,
    WorkflowDefinition,
    WorkflowStep,
)


class TestStepTemplate:
    """Tests for StepTemplate enum."""

    def test_template_values(self):
        """Verify all template types exist."""
        assert StepTemplate.INIT == "init"
        assert StepTemplate.ACTION == "action"
        assert StepTemplate.FINALIZE == "finalize"
        assert StepTemplate.FANOUT_SOURCE == "fanout-source"
        assert StepTemplate.NO_RETRY == "no-retry"


class TestWorkflowStep:
    """Tests for WorkflowStep model."""

    def test_create_basic_step(self):
        """Create a basic workflow step."""
        step = WorkflowStep(name="test-step")
        assert step.name == "test-step"
        assert step.depends == []
        assert step.template == StepTemplate.ACTION
        assert step.params == {}
        assert step.when_flow_control is None

    def test_create_step_with_dependencies(self):
        """Create step with dependencies."""
        step = WorkflowStep(
            name="process-data",
            depends=["fetch-data", "validate-input"],
            template=StepTemplate.ACTION,
        )
        assert step.depends == ["fetch-data", "validate-input"]

    def test_create_init_step(self):
        """Create an init step."""
        step = WorkflowStep(name="init", template=StepTemplate.INIT)
        assert step.template == StepTemplate.INIT

    def test_create_finalize_step(self):
        """Create a finalize step."""
        step = WorkflowStep(
            name="cleanup",
            template=StepTemplate.FINALIZE,
            depends=["main-task"],
        )
        assert step.template == StepTemplate.FINALIZE

    def test_step_with_params(self):
        """Create step with parameters."""
        step = WorkflowStep(
            name="http-check",
            params={"url": "https://example.com", "timeout": 30},
        )
        assert step.params["url"] == "https://example.com"
        assert step.params["timeout"] == 30

    def test_step_with_flow_control(self):
        """Create step with flow control condition."""
        step = WorkflowStep(
            name="optional-step",
            when_flow_control="skip_optional != true",
        )
        assert step.when_flow_control == "skip_optional != true"


class TestWorkflowDefinition:
    """Tests for WorkflowDefinition model."""

    def test_create_basic_workflow(self):
        """Create a basic workflow definition."""
        workflow = WorkflowDefinition(
            name="TestWorkflow",
            platform="homelab",
            steps=[WorkflowStep(name="step1")],
        )
        assert workflow.name == "TestWorkflow"
        assert workflow.platform == "homelab"
        assert workflow.handler_prefix is None
        assert workflow.context == "local"
        assert len(workflow.steps) == 1
        assert workflow.default_retries == 3
        assert workflow.timeout_seconds == 3600

    def test_workflow_with_handler_prefix(self):
        """Create workflow with handler prefix."""
        workflow = WorkflowDefinition(
            name="SmokeTest",
            platform="homelab",
            handler_prefix="smoke-test",
            steps=[WorkflowStep(name="init")],
        )
        assert workflow.handler_prefix == "smoke-test"

    def test_get_step_handler_name_with_prefix(self):
        """Get handler name when prefix is set."""
        workflow = WorkflowDefinition(
            name="SmokeTest",
            platform="homelab",
            handler_prefix="smoke-test",
            steps=[
                WorkflowStep(name="init"),
                WorkflowStep(name="check-dns"),
            ],
        )
        assert workflow.get_step_handler_name(workflow.steps[0]) == "smoke-test-init"
        assert workflow.get_step_handler_name(workflow.steps[1]) == "smoke-test-check-dns"

    def test_get_step_handler_name_without_prefix(self):
        """Get handler name when no prefix is set."""
        workflow = WorkflowDefinition(
            name="SimpleWorkflow",
            platform="homelab",
            steps=[WorkflowStep(name="do-something")],
        )
        assert workflow.get_step_handler_name(workflow.steps[0]) == "do-something"

    def test_get_execution_order_simple(self):
        """Get execution order for simple linear workflow."""
        workflow = WorkflowDefinition(
            name="LinearWorkflow",
            platform="homelab",
            steps=[
                WorkflowStep(name="step1"),
                WorkflowStep(name="step2", depends=["step1"]),
                WorkflowStep(name="step3", depends=["step2"]),
            ],
        )
        order = workflow.get_execution_order()
        names = [s.name for s in order]
        assert names.index("step1") < names.index("step2")
        assert names.index("step2") < names.index("step3")

    def test_get_execution_order_parallel(self):
        """Get execution order for workflow with parallel steps."""
        workflow = WorkflowDefinition(
            name="ParallelWorkflow",
            platform="homelab",
            steps=[
                WorkflowStep(name="init"),
                WorkflowStep(name="task-a", depends=["init"]),
                WorkflowStep(name="task-b", depends=["init"]),
                WorkflowStep(name="finalize", depends=["task-a", "task-b"]),
            ],
        )
        order = workflow.get_execution_order()
        names = [s.name for s in order]

        # init must be first
        assert names[0] == "init"
        # task-a and task-b can be in any order but before finalize
        assert names.index("task-a") < names.index("finalize")
        assert names.index("task-b") < names.index("finalize")

    def test_get_execution_order_circular_dependency(self):
        """Circular dependencies should raise an error."""
        workflow = WorkflowDefinition(
            name="CircularWorkflow",
            platform="homelab",
            steps=[
                WorkflowStep(name="step1", depends=["step3"]),
                WorkflowStep(name="step2", depends=["step1"]),
                WorkflowStep(name="step3", depends=["step2"]),
            ],
        )
        with pytest.raises(ValueError, match="Circular dependency"):
            workflow.get_execution_order()

    def test_get_non_finalize_steps(self):
        """Get all non-finalize steps."""
        workflow = WorkflowDefinition(
            name="TestWorkflow",
            platform="homelab",
            steps=[
                WorkflowStep(name="init", template=StepTemplate.INIT),
                WorkflowStep(name="action", template=StepTemplate.ACTION),
                WorkflowStep(name="cleanup", template=StepTemplate.FINALIZE),
            ],
        )
        non_finalize = workflow.get_non_finalize_steps()
        names = [s.name for s in non_finalize]
        assert "init" in names
        assert "action" in names
        assert "cleanup" not in names

    def test_get_finalize_steps(self):
        """Get finalize steps only."""
        workflow = WorkflowDefinition(
            name="TestWorkflow",
            platform="homelab",
            steps=[
                WorkflowStep(name="init", template=StepTemplate.INIT),
                WorkflowStep(name="action", template=StepTemplate.ACTION),
                WorkflowStep(name="cleanup", template=StepTemplate.FINALIZE),
                WorkflowStep(name="notify", template=StepTemplate.FINALIZE),
            ],
        )
        finalize = workflow.get_finalize_steps()
        names = [s.name for s in finalize]
        assert names == ["cleanup", "notify"]

    def test_validate_dependencies_valid(self):
        """Validate dependencies for a valid workflow."""
        workflow = WorkflowDefinition(
            name="ValidWorkflow",
            platform="homelab",
            steps=[
                WorkflowStep(name="step1"),
                WorkflowStep(name="step2", depends=["step1"]),
            ],
        )
        errors = workflow.validate_dependencies()
        assert errors == []

    def test_validate_dependencies_missing(self):
        """Validate dependencies catches missing dependencies."""
        workflow = WorkflowDefinition(
            name="InvalidWorkflow",
            platform="homelab",
            steps=[
                WorkflowStep(name="step1"),
                WorkflowStep(name="step2", depends=["nonexistent"]),
            ],
        )
        errors = workflow.validate_dependencies()
        assert len(errors) == 1
        assert "nonexistent" in errors[0]

    def test_from_yaml(self):
        """Load workflow from YAML file."""
        yaml_content = """
name: TestWorkflow
platform: homelab
handler_prefix: test
context: local

steps:
  - name: init
    template: init
  - name: main
    template: action
    depends:
      - init
  - name: cleanup
    template: finalize
    depends:
      - main

default_retries: 2
timeout_seconds: 600
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_content)
            f.flush()

            workflow = WorkflowDefinition.from_yaml(f.name)

            assert workflow.name == "TestWorkflow"
            assert workflow.platform == "homelab"
            assert workflow.handler_prefix == "test"
            assert workflow.default_retries == 2
            assert workflow.timeout_seconds == 600
            assert len(workflow.steps) == 3
            assert workflow.steps[0].name == "init"
            assert workflow.steps[0].template == StepTemplate.INIT
            assert workflow.steps[1].depends == ["init"]

            # Cleanup
            Path(f.name).unlink()

    def test_from_yaml_file_not_found(self):
        """Loading non-existent YAML file raises error."""
        with pytest.raises(FileNotFoundError):
            WorkflowDefinition.from_yaml("/nonexistent/path.yaml")
