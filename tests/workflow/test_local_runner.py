"""Tests for LocalRunner workflow execution."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from homelab_taskkit.workflow.local_runner import LocalRunner, WorkflowExecutionResult
from homelab_taskkit.workflow.models import StepDeps, StepInput, StepResult
from homelab_taskkit.workflow.registry import _STEP_REGISTRY, register_step


@pytest.fixture
def simple_workflow_yaml() -> str:
    """Create a simple workflow YAML."""
    return """
name: SimpleTestWorkflow
platform: test
handler_prefix: simple-test

steps:
  - name: init
    template: init
  - name: process
    template: action
    depends:
      - init
  - name: finalize
    template: finalize
    depends:
      - process

default_retries: 1
timeout_seconds: 60
"""


@pytest.fixture
def simple_params_json() -> str:
    """Create simple params JSON."""
    return '{"message": "Hello, Test!"}'


@pytest.fixture
def workflow_file(simple_workflow_yaml: str) -> Path:
    """Create temporary workflow file."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as f:
        f.write(simple_workflow_yaml)
        f.flush()
        yield Path(f.name)
        Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def params_file(simple_params_json: str) -> Path:
    """Create temporary params file."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as f:
        f.write(simple_params_json)
        f.flush()
        yield Path(f.name)
        Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def temp_workdir() -> Path:
    """Create temporary working directory."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def register_test_handlers():
    """Register test step handlers for the simple workflow."""
    handlers = []

    @register_step("simple-test-init")
    def init_handler(step_input: StepInput, deps: StepDeps) -> StepResult:
        result = StepResult()
        result.add_info("Init completed", system="test")
        result.context_updates["initialized"] = True
        return result

    handlers.append("simple-test-init")

    @register_step("simple-test-process")
    def process_handler(step_input: StepInput, deps: StepDeps) -> StepResult:
        result = StepResult()
        msg = step_input.params.get("message", "No message")
        result.add_info(f"Processing: {msg}", system="test")
        result.context_updates["processed"] = True
        return result

    handlers.append("simple-test-process")

    @register_step("simple-test-finalize")
    def finalize_handler(step_input: StepInput, deps: StepDeps) -> StepResult:
        result = StepResult()
        result.add_info("Finalize completed", system="test")
        return result

    handlers.append("simple-test-finalize")

    yield handlers

    # Cleanup
    for name in handlers:
        if name in _STEP_REGISTRY:
            del _STEP_REGISTRY[name]


class TestWorkflowExecutionResult:
    """Tests for WorkflowExecutionResult."""

    def test_create_result(self):
        """Create a workflow execution result."""
        result = WorkflowExecutionResult(
            workflow_name="TestWorkflow",
            task_id="task-123",
            workdir="/tmp/test",
        )
        assert result.result == "Succeeded"
        assert result.workflow_name == "TestWorkflow"
        assert result.task_id == "task-123"
        assert result.step_results == {}

    def test_to_dict(self):
        """Convert result to dictionary."""
        result = WorkflowExecutionResult(
            workflow_name="TestWorkflow",
            task_id="task-123",
            workdir="/tmp/test",
        )
        result.error = "Something went wrong"
        result.duration_seconds = 5.5

        data = result.to_dict()
        assert data["workflow_name"] == "TestWorkflow"
        assert data["task_id"] == "task-123"
        assert data["error"] == "Something went wrong"
        assert data["duration_seconds"] == 5.5


class TestLocalRunnerInit:
    """Tests for LocalRunner initialization."""

    def test_init_with_workflow_path(
        self, workflow_file: Path, register_test_handlers, temp_workdir: Path
    ):
        """Initialize runner with workflow path."""
        runner = LocalRunner(
            workflow_path=workflow_file,
            workdir=temp_workdir,
        )
        assert runner.workflow.name == "SimpleTestWorkflow"
        assert runner.workflow_path == workflow_file
        assert runner.params == {}

    def test_init_with_params(
        self,
        workflow_file: Path,
        params_file: Path,
        register_test_handlers,
        temp_workdir: Path,
    ):
        """Initialize runner with params file."""
        runner = LocalRunner(
            workflow_path=workflow_file,
            params_path=params_file,
            workdir=temp_workdir,
        )
        assert runner.params["message"] == "Hello, Test!"

    def test_init_creates_workdir(
        self, workflow_file: Path, register_test_handlers, temp_workdir: Path
    ):
        """Runner creates workdir if it doesn't exist."""
        workdir = temp_workdir / "nested" / "workdir"
        runner = LocalRunner(
            workflow_path=workflow_file,
            workdir=workdir,
        )
        assert workdir.exists()
        assert (workdir / "steps").exists()
        assert (workdir / "logs").exists()

    def test_init_with_custom_task_id(
        self, workflow_file: Path, register_test_handlers, temp_workdir: Path
    ):
        """Initialize runner with custom task ID."""
        runner = LocalRunner(
            workflow_path=workflow_file,
            workdir=temp_workdir,
            task_id="custom-task-id",
        )
        assert runner.task_id == "custom-task-id"

    def test_init_invalid_workflow_raises(self, temp_workdir: Path):
        """Invalid workflow validation raises error."""
        invalid_yaml = """
name: InvalidWorkflow
platform: test
steps:
  - name: step1
    depends:
      - nonexistent
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(invalid_yaml)
            f.flush()

            with pytest.raises(ValueError, match="validation failed"):
                LocalRunner(workflow_path=f.name, workdir=temp_workdir)

            Path(f.name).unlink()


class TestLocalRunnerValidate:
    """Tests for LocalRunner.validate()."""

    def test_validate_valid_workflow(
        self, workflow_file: Path, register_test_handlers, temp_workdir: Path
    ):
        """Validate a valid workflow."""
        runner = LocalRunner(
            workflow_path=workflow_file,
            workdir=temp_workdir,
        )
        errors = runner.validate()
        assert errors == []

    def test_validate_missing_handler(
        self, workflow_file: Path, temp_workdir: Path
    ):
        """Validate catches missing handlers."""
        # Don't register handlers
        runner = LocalRunner.__new__(LocalRunner)
        runner.workflow_path = workflow_file
        runner.params_path = None
        runner.task_id = "test"
        runner.timeout = 30.0
        runner.workdir = temp_workdir
        runner.vars = {}

        from homelab_taskkit.workflow.workflow import WorkflowDefinition

        runner.workflow = WorkflowDefinition.from_yaml(workflow_file)
        runner.params = {}
        runner._failed_steps = set()
        runner._skipped_steps = set()
        runner._flow_control = {}

        errors = runner.validate()
        assert len(errors) >= 1
        assert any("Handler not found" in e for e in errors)


class TestLocalRunnerRun:
    """Tests for LocalRunner.run()."""

    def test_run_successful_workflow(
        self,
        workflow_file: Path,
        params_file: Path,
        register_test_handlers,
        temp_workdir: Path,
    ):
        """Run a successful workflow."""
        runner = LocalRunner(
            workflow_path=workflow_file,
            params_path=params_file,
            workdir=temp_workdir,
        )
        result = runner.run()

        assert result == "Succeeded"

        # Check execution result file
        result_path = temp_workdir / "execution-result.json"
        assert result_path.exists()

        with open(result_path) as f:
            data = json.load(f)

        assert data["result"] == "Succeeded"
        assert "init" in data["step_results"]
        assert "process" in data["step_results"]
        assert "finalize" in data["step_results"]

    def test_run_updates_vars(
        self,
        workflow_file: Path,
        register_test_handlers,
        temp_workdir: Path,
    ):
        """Run updates vars.yaml with context updates."""
        runner = LocalRunner(
            workflow_path=workflow_file,
            workdir=temp_workdir,
        )
        runner.run()

        vars_path = temp_workdir / "vars.yaml"
        assert vars_path.exists()

        import yaml

        with open(vars_path) as f:
            vars_data = yaml.safe_load(f)

        assert vars_data.get("initialized") is True
        assert vars_data.get("processed") is True

    def test_run_failing_step(self, temp_workdir: Path):
        """Run workflow with failing step."""
        failing_yaml = """
name: FailingWorkflow
platform: test
handler_prefix: failing-test

steps:
  - name: init
    template: init
  - name: fail
    template: action
    depends:
      - init
  - name: finalize
    template: finalize
    depends:
      - fail

default_retries: 0
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(failing_yaml)
            f.flush()

            # Register handlers
            @register_step("failing-test-init")
            def init_handler(step_input: StepInput, deps: StepDeps) -> StepResult:
                return StepResult()

            @register_step("failing-test-fail")
            def fail_handler(step_input: StepInput, deps: StepDeps) -> StepResult:
                result = StepResult()
                result.add_error("Intentional failure", system="test")
                return result

            @register_step("failing-test-finalize")
            def finalize_handler(step_input: StepInput, deps: StepDeps) -> StepResult:
                return StepResult()

            try:
                runner = LocalRunner(
                    workflow_path=f.name,
                    workdir=temp_workdir,
                )
                result = runner.run()

                assert result == "Failed"

                # Finalize should still run
                result_path = temp_workdir / "execution-result.json"
                with open(result_path) as rf:
                    data = json.load(rf)

                assert "finalize" in data["step_results"]

            finally:
                # Cleanup
                Path(f.name).unlink()
                for name in ["failing-test-init", "failing-test-fail", "failing-test-finalize"]:
                    if name in _STEP_REGISTRY:
                        del _STEP_REGISTRY[name]

    def test_run_saves_step_results(
        self,
        workflow_file: Path,
        register_test_handlers,
        temp_workdir: Path,
    ):
        """Run saves individual step results."""
        runner = LocalRunner(
            workflow_path=workflow_file,
            workdir=temp_workdir,
        )
        runner.run()

        # Check step result files
        init_result = temp_workdir / "steps" / "init" / "result-attempt-0.json"
        assert init_result.exists()

        with open(init_result) as f:
            data = json.load(f)

        assert "messages" in data
        assert "context_updates" in data


class TestLocalRunnerFlowControl:
    """Tests for flow control in LocalRunner."""

    def test_skip_remaining_flow_control(self, temp_workdir: Path):
        """Flow control can skip remaining steps."""
        yaml_content = """
name: SkipWorkflow
platform: test
handler_prefix: skip-test

steps:
  - name: init
    template: init
  - name: decide
    template: action
    depends:
      - init
  - name: skipped
    template: action
    depends:
      - decide
  - name: finalize
    template: finalize
    depends:
      - skipped
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_content)
            f.flush()

            @register_step("skip-test-init")
            def init_handler(step_input: StepInput, deps: StepDeps) -> StepResult:
                return StepResult()

            @register_step("skip-test-decide")
            def decide_handler(step_input: StepInput, deps: StepDeps) -> StepResult:
                result = StepResult()
                result.flow_control = {"skip_remaining": True}
                return result

            @register_step("skip-test-skipped")
            def skipped_handler(step_input: StepInput, deps: StepDeps) -> StepResult:
                result = StepResult()
                result.add_info("This should be skipped", system="test")
                return result

            @register_step("skip-test-finalize")
            def finalize_handler(step_input: StepInput, deps: StepDeps) -> StepResult:
                return StepResult()

            try:
                runner = LocalRunner(
                    workflow_path=f.name,
                    workdir=temp_workdir,
                )
                result = runner.run()

                assert result == "Succeeded"
                assert "skipped" in runner._skipped_steps

            finally:
                Path(f.name).unlink()
                for name in [
                    "skip-test-init",
                    "skip-test-decide",
                    "skip-test-skipped",
                    "skip-test-finalize",
                ]:
                    if name in _STEP_REGISTRY:
                        del _STEP_REGISTRY[name]
