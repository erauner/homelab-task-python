"""Tests for step registry."""

from __future__ import annotations

import logging

import httpx
import pytest

from homelab_taskkit.workflow.models import StepDeps, StepInput, StepResult
from homelab_taskkit.workflow.registry import (
    StepAlreadyRegisteredError,
    StepNotFoundError,
    _STEP_REGISTRY,
    get_step,
    has_step,
    list_steps,
    register_step,
)


class TestRegisterStep:
    """Tests for @register_step decorator."""

    def test_register_step_decorator(self):
        """Register a step handler with decorator."""
        # Use a unique name to avoid conflicts with other tests
        test_name = "test-registry-basic"

        @register_step(test_name)
        def my_handler(step_input: StepInput, deps: StepDeps) -> StepResult:
            result = StepResult()
            result.add_info("Handler called", system="test")
            return result

        assert has_step(test_name)
        assert get_step(test_name) is my_handler

        # Cleanup
        if test_name in _STEP_REGISTRY:
            del _STEP_REGISTRY[test_name]

    def test_register_step_duplicate_raises(self):
        """Registering duplicate step name raises error."""
        test_name = "test-registry-duplicate"

        @register_step(test_name)
        def handler1(step_input: StepInput, deps: StepDeps) -> StepResult:
            return StepResult()

        with pytest.raises(StepAlreadyRegisteredError):

            @register_step(test_name)
            def handler2(step_input: StepInput, deps: StepDeps) -> StepResult:
                return StepResult()

        # Cleanup
        if test_name in _STEP_REGISTRY:
            del _STEP_REGISTRY[test_name]

    def test_decorated_function_preserved(self):
        """Decorator preserves original function."""
        test_name = "test-registry-preserve"

        @register_step(test_name)
        def my_handler(step_input: StepInput, deps: StepDeps) -> StepResult:
            """My handler docstring."""
            return StepResult()

        assert my_handler.__name__ == "my_handler"
        assert my_handler.__doc__ == "My handler docstring."

        # Cleanup
        if test_name in _STEP_REGISTRY:
            del _STEP_REGISTRY[test_name]


class TestGetStep:
    """Tests for get_step function."""

    def test_get_registered_step(self):
        """Get a registered step handler."""
        test_name = "test-get-registered"

        @register_step(test_name)
        def my_handler(step_input: StepInput, deps: StepDeps) -> StepResult:
            return StepResult()

        handler = get_step(test_name)
        assert handler is my_handler

        # Cleanup
        if test_name in _STEP_REGISTRY:
            del _STEP_REGISTRY[test_name]

    def test_get_unregistered_step_raises(self):
        """Getting unregistered step raises StepNotFoundError."""
        with pytest.raises(StepNotFoundError, match="not-registered"):
            get_step("not-registered-step-name")


class TestHasStep:
    """Tests for has_step function."""

    def test_has_step_registered(self):
        """has_step returns True for registered step."""
        test_name = "test-has-registered"

        @register_step(test_name)
        def my_handler(step_input: StepInput, deps: StepDeps) -> StepResult:
            return StepResult()

        assert has_step(test_name) is True

        # Cleanup
        if test_name in _STEP_REGISTRY:
            del _STEP_REGISTRY[test_name]

    def test_has_step_unregistered(self):
        """has_step returns False for unregistered step."""
        assert has_step("definitely-not-registered-12345") is False


class TestListSteps:
    """Tests for list_steps function."""

    def test_list_steps_returns_list(self):
        """list_steps returns a list of step names."""
        steps = list_steps()
        assert isinstance(steps, list)

    def test_list_steps_includes_registered(self):
        """list_steps includes newly registered steps."""
        test_name = "test-list-included"

        @register_step(test_name)
        def my_handler(step_input: StepInput, deps: StepDeps) -> StepResult:
            return StepResult()

        steps = list_steps()
        assert test_name in steps

        # Cleanup
        if test_name in _STEP_REGISTRY:
            del _STEP_REGISTRY[test_name]


class TestStepExecution:
    """Tests for executing registered step handlers."""

    def test_execute_step_handler(self):
        """Execute a registered step handler."""
        test_name = "test-execute-handler"

        @register_step(test_name)
        def my_handler(step_input: StepInput, deps: StepDeps) -> StepResult:
            result = StepResult()
            result.add_info(f"Processed {step_input.step_name}", system="test")
            result.context_updates["processed"] = True
            return result

        handler = get_step(test_name)

        step_input = StepInput(
            step_name="test",
            task_id="task-123",
            workflow_name="TestWorkflow",
        )

        http_client = httpx.Client()
        try:
            deps = StepDeps(
                http=http_client,
                logger=logging.getLogger("test"),
                env={},
                workdir="/tmp",
            )

            result = handler(step_input, deps)

            assert not result.has_errors
            assert len(result.messages) == 1
            assert "Processed test" in result.messages[0].text
            assert result.context_updates["processed"] is True
        finally:
            http_client.close()

            # Cleanup
            if test_name in _STEP_REGISTRY:
                del _STEP_REGISTRY[test_name]
