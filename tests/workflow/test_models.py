"""Tests for workflow step models."""

from __future__ import annotations

import logging

import httpx
import pytest

from homelab_taskkit.workflow.models import (
    Message,
    Severity,
    StepDeps,
    StepInput,
    StepResult,
)


class TestSeverity:
    """Tests for Severity enum."""

    def test_severity_values(self):
        """Verify all severity levels exist."""
        assert Severity.DEBUG == "debug"
        assert Severity.INFO == "info"
        assert Severity.WARNING == "warning"
        assert Severity.ERROR == "error"


class TestMessage:
    """Tests for Message model."""

    def test_create_message(self):
        """Create a basic message."""
        msg = Message(text="Test message", severity=Severity.INFO, system="test")
        assert msg.text == "Test message"
        assert msg.severity == Severity.INFO
        assert msg.system == "test"
        assert msg.data == {}

    def test_message_with_data(self):
        """Create message with extra data."""
        msg = Message(
            text="Error occurred",
            severity=Severity.ERROR,
            system="http",
            data={"url": "https://example.com", "status": 500},
        )
        assert msg.data["url"] == "https://example.com"
        assert msg.data["status"] == 500


class TestStepInput:
    """Tests for StepInput model."""

    def test_create_step_input(self):
        """Create basic step input."""
        step_input = StepInput(
            step_name="test-step",
            task_id="task-123",
            workflow_name="TestWorkflow",
        )
        assert step_input.step_name == "test-step"
        assert step_input.task_id == "task-123"
        assert step_input.workflow_name == "TestWorkflow"
        assert step_input.params == {}
        assert step_input.vars == {}
        assert step_input.attempt == 0
        assert step_input.total_retries == 3

    def test_step_input_with_params_and_vars(self):
        """Create step input with params and vars."""
        step_input = StepInput(
            step_name="check-dns",
            task_id="task-456",
            workflow_name="SmokeTest",
            params={"targets": [{"name": "google"}]},
            vars={"smoke_test": {"total_targets": 1}},
            attempt=1,
            total_retries=2,
        )
        assert step_input.params["targets"][0]["name"] == "google"
        assert step_input.vars["smoke_test"]["total_targets"] == 1
        assert step_input.attempt == 1
        assert step_input.total_retries == 2


class TestStepResult:
    """Tests for StepResult model."""

    def test_create_empty_result(self):
        """Create an empty step result."""
        result = StepResult()
        assert result.messages == []
        assert result.output is None
        assert result.context_updates == {}
        assert result.flow_control is None
        assert not result.has_errors

    def test_add_info(self):
        """Add an info message."""
        result = StepResult()
        result.add_info("Operation completed", system="test")

        assert len(result.messages) == 1
        assert result.messages[0].text == "Operation completed"
        assert result.messages[0].severity == Severity.INFO
        assert result.messages[0].system == "test"
        assert not result.has_errors

    def test_add_warning(self):
        """Add a warning message."""
        result = StepResult()
        result.add_warning("Deprecated API used", system="http")

        assert len(result.messages) == 1
        assert result.messages[0].severity == Severity.WARNING
        assert not result.has_errors

    def test_add_error(self):
        """Add an error message."""
        result = StepResult()
        result.add_error("Connection failed", system="dns")

        assert len(result.messages) == 1
        assert result.messages[0].severity == Severity.ERROR
        assert result.has_errors

    def test_add_message_with_data(self):
        """Add message with extra data."""
        result = StepResult()
        result.add_error(
            "HTTP request failed",
            system="http",
            url="https://example.com",
            status_code=500,
        )

        msg = result.messages[0]
        assert msg.data["url"] == "https://example.com"
        assert msg.data["status_code"] == 500

    def test_has_errors_multiple_messages(self):
        """has_errors should return True if any message is an error."""
        result = StepResult()
        result.add_info("Starting check", system="test")
        result.add_warning("Minor issue", system="test")
        assert not result.has_errors

        result.add_error("Critical failure", system="test")
        assert result.has_errors

    def test_context_updates(self):
        """Set context updates."""
        result = StepResult()
        result.context_updates["smoke_test"] = {
            "total_targets": 3,
            "passed_checks": 2,
        }

        assert result.context_updates["smoke_test"]["total_targets"] == 3

    def test_flow_control(self):
        """Set flow control."""
        result = StepResult()
        result.flow_control = {"skip_remaining": True}

        assert result.flow_control["skip_remaining"] is True

    def test_output(self):
        """Set output data."""
        result = StepResult()
        result.output = {"results": [{"name": "test", "passed": True}]}

        assert result.output["results"][0]["passed"] is True


class TestStepDeps:
    """Tests for StepDeps model."""

    def test_create_step_deps(self):
        """Create step dependencies."""
        http_client = httpx.Client()
        test_logger = logging.getLogger("test")

        try:
            deps = StepDeps(
                http=http_client,
                logger=test_logger,
                env={"PATH": "/usr/bin"},
                workdir="/tmp/test",
            )

            assert deps.http is http_client
            assert deps.logger is test_logger
            assert deps.env["PATH"] == "/usr/bin"
            assert deps.workdir == "/tmp/test"
        finally:
            http_client.close()

    def test_step_deps_requires_http_client(self):
        """StepDeps requires an httpx.Client instance."""
        test_logger = logging.getLogger("test")

        with pytest.raises(Exception):  # Pydantic validation error
            StepDeps(
                http="not-a-client",
                logger=test_logger,
                env={},
                workdir="/tmp",
            )
