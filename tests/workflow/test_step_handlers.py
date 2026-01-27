"""Tests for smoke test step handlers."""

from __future__ import annotations

import json
import logging
import socket
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from homelab_taskkit.workflow.models import StepDeps, StepInput, StepResult

# Import step handlers to register them
import homelab_taskkit.steps  # noqa: F401

from homelab_taskkit.workflow.registry import get_step, has_step


@pytest.fixture
def http_client():
    """Create a real HTTP client for testing."""
    client = httpx.Client()
    yield client
    client.close()


@pytest.fixture
def step_deps(http_client, tmp_path: Path) -> StepDeps:
    """Create StepDeps for testing."""
    return StepDeps(
        http=http_client,
        logger=logging.getLogger("test"),
        env={},
        workdir=str(tmp_path),
    )


@pytest.fixture
def basic_step_input() -> StepInput:
    """Create basic StepInput for testing."""
    return StepInput(
        step_name="test",
        task_id="task-123",
        workflow_name="TestWorkflow",
    )


class TestSmokeTestHandlersRegistered:
    """Verify smoke test handlers are registered."""

    def test_init_handler_registered(self):
        """smoke-test-init handler is registered."""
        assert has_step("smoke-test-init")

    def test_check_dns_handler_registered(self):
        """smoke-test-check-dns handler is registered."""
        assert has_step("smoke-test-check-dns")

    def test_check_http_handler_registered(self):
        """smoke-test-check-http handler is registered."""
        assert has_step("smoke-test-check-http")

    def test_finalize_handler_registered(self):
        """smoke-test-finalize handler is registered."""
        assert has_step("smoke-test-finalize")


class TestSmokeTestInit:
    """Tests for smoke-test-init handler."""

    def test_init_with_targets(self, step_deps: StepDeps):
        """Init handler initializes context with targets."""
        handler = get_step("smoke-test-init")

        step_input = StepInput(
            step_name="init",
            task_id="task-123",
            workflow_name="SmokeTest",
            params={
                "targets": [
                    {"name": "target1", "dns_host": "example.com"},
                    {"name": "target2", "dns_host": "test.com"},
                ]
            },
        )

        result = handler(step_input, step_deps)

        assert not result.has_errors
        assert "smoke_test" in result.context_updates
        assert result.context_updates["smoke_test"]["total_targets"] == 2
        assert result.context_updates["smoke_test"]["passed_checks"] == 0
        assert result.context_updates["smoke_test"]["failed_checks"] == 0

    def test_init_without_targets(self, step_deps: StepDeps):
        """Init handler returns errors when targets are missing."""
        handler = get_step("smoke-test-init")

        step_input = StepInput(
            step_name="init",
            task_id="task-123",
            workflow_name="SmokeTest",
            params={},
        )

        result = handler(step_input, step_deps)

        # Init handler requires targets and returns errors when missing
        assert result.has_errors
        assert any("Missing required parameter: targets" in m.text for m in result.messages)


class TestSmokeTestCheckDns:
    """Tests for smoke-test-check-dns handler."""

    def test_check_dns_success(self, step_deps: StepDeps):
        """Check DNS succeeds for valid hosts."""
        handler = get_step("smoke-test-check-dns")

        step_input = StepInput(
            step_name="check-dns",
            task_id="task-123",
            workflow_name="SmokeTest",
            params={
                "targets": [
                    {"name": "google", "dns_host": "dns.google"},
                ]
            },
            vars={
                "smoke_test": {
                    "total_targets": 1,
                    "passed_checks": 0,
                    "failed_checks": 0,
                }
            },
        )

        with patch("socket.gethostbyname_ex") as mock_resolve:
            mock_resolve.return_value = ("dns.google", [], ["8.8.8.8"])
            result = handler(step_input, step_deps)

        assert not result.has_errors
        smoke_test = result.context_updates["smoke_test"]
        assert smoke_test["passed_checks"] == 1
        assert smoke_test["failed_checks"] == 0
        assert "google" in smoke_test["dns_results"]
        assert smoke_test["dns_results"]["google"]["resolved"] is True

    def test_check_dns_failure(self, step_deps: StepDeps):
        """Check DNS handles resolution failures."""
        handler = get_step("smoke-test-check-dns")

        step_input = StepInput(
            step_name="check-dns",
            task_id="task-123",
            workflow_name="SmokeTest",
            params={
                "targets": [
                    {"name": "invalid", "dns_host": "invalid.nonexistent.test"},
                ]
            },
            vars={
                "smoke_test": {
                    "total_targets": 1,
                    "passed_checks": 0,
                    "failed_checks": 0,
                }
            },
        )

        with patch("socket.gethostbyname_ex") as mock_resolve:
            mock_resolve.side_effect = socket.gaierror("Name resolution failed")
            result = handler(step_input, step_deps)

        # DNS failures are logged but don't cause step errors
        smoke_test = result.context_updates["smoke_test"]
        assert smoke_test["failed_checks"] == 1
        assert smoke_test["dns_results"]["invalid"]["resolved"] is False

    def test_check_dns_skips_missing_host(self, step_deps: StepDeps):
        """Check DNS skips targets without dns_host."""
        handler = get_step("smoke-test-check-dns")

        step_input = StepInput(
            step_name="check-dns",
            task_id="task-123",
            workflow_name="SmokeTest",
            params={
                "targets": [
                    {"name": "http-only", "http_url": "https://example.com"},
                ]
            },
            vars={
                "smoke_test": {
                    "total_targets": 1,
                    "passed_checks": 0,
                    "failed_checks": 0,
                }
            },
        )

        result = handler(step_input, step_deps)

        assert not result.has_errors
        # No DNS check performed
        smoke_test = result.context_updates["smoke_test"]
        assert smoke_test["passed_checks"] == 0
        assert smoke_test["failed_checks"] == 0


class TestSmokeTestCheckHttp:
    """Tests for smoke-test-check-http handler."""

    def test_check_http_success(self, step_deps: StepDeps):
        """Check HTTP succeeds for valid endpoints."""
        handler = get_step("smoke-test-check-http")

        step_input = StepInput(
            step_name="check-http",
            task_id="task-123",
            workflow_name="SmokeTest",
            params={
                "targets": [
                    {
                        "name": "example",
                        "http_url": "https://example.com",
                        "expected_status": 200,
                    },
                ]
            },
            vars={
                "smoke_test": {
                    "total_targets": 1,
                    "passed_checks": 0,
                    "failed_checks": 0,
                    "dns_results": {},
                }
            },
        )

        # Mock the HTTP client's get method
        with patch.object(step_deps.http, "get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.elapsed.total_seconds.return_value = 0.1
            mock_get.return_value = mock_response

            result = handler(step_input, step_deps)

        assert not result.has_errors
        smoke_test = result.context_updates["smoke_test"]
        assert smoke_test["passed_checks"] == 1
        assert smoke_test["http_results"]["example"]["success"] is True
        assert smoke_test["http_results"]["example"]["status_code"] == 200

    def test_check_http_wrong_status(self, step_deps: StepDeps):
        """Check HTTP reports wrong status code."""
        handler = get_step("smoke-test-check-http")

        step_input = StepInput(
            step_name="check-http",
            task_id="task-123",
            workflow_name="SmokeTest",
            params={
                "targets": [
                    {
                        "name": "failing",
                        "http_url": "https://failing.example.com",
                        "expected_status": 200,
                    },
                ]
            },
            vars={
                "smoke_test": {
                    "total_targets": 1,
                    "passed_checks": 0,
                    "failed_checks": 0,
                    "dns_results": {},
                }
            },
        )

        # Mock the HTTP client's get method
        with patch.object(step_deps.http, "get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.elapsed.total_seconds.return_value = 0.2
            mock_get.return_value = mock_response

            result = handler(step_input, step_deps)

        # Wrong status is an error
        assert result.has_errors
        smoke_test = result.context_updates["smoke_test"]
        assert smoke_test["failed_checks"] == 1
        assert smoke_test["http_results"]["failing"]["success"] is False
        assert smoke_test["http_results"]["failing"]["status_code"] == 500

    def test_check_http_skips_missing_url(self, step_deps: StepDeps):
        """Check HTTP skips targets without http_url."""
        handler = get_step("smoke-test-check-http")

        step_input = StepInput(
            step_name="check-http",
            task_id="task-123",
            workflow_name="SmokeTest",
            params={
                "targets": [
                    {"name": "dns-only", "dns_host": "example.com"},
                ]
            },
            vars={
                "smoke_test": {
                    "total_targets": 1,
                    "passed_checks": 0,
                    "failed_checks": 0,
                    "dns_results": {},
                }
            },
        )

        result = handler(step_input, step_deps)

        assert not result.has_errors
        smoke_test = result.context_updates["smoke_test"]
        assert smoke_test["passed_checks"] == 0
        assert smoke_test["failed_checks"] == 0


class TestSmokeTestFinalize:
    """Tests for smoke-test-finalize handler."""

    def test_finalize_success(self, step_deps: StepDeps):
        """Finalize reports success when no failures."""
        handler = get_step("smoke-test-finalize")

        step_input = StepInput(
            step_name="finalize",
            task_id="task-123",
            workflow_name="SmokeTest",
            vars={
                "smoke_test": {
                    "total_targets": 2,
                    "passed_checks": 4,
                    "failed_checks": 0,
                    "dns_results": {
                        "target1": {"success": True},
                        "target2": {"success": True},
                    },
                    "http_results": {
                        "target1": {"success": True},
                        "target2": {"success": True},
                    },
                }
            },
        )

        result = handler(step_input, step_deps)

        assert not result.has_errors
        assert result.output["overall_status"] == "passed"
        assert result.flow_control is None

        # Check report was written
        report_path = Path(step_deps.workdir) / "smoke-test-report.json"
        assert report_path.exists()

    def test_finalize_with_failures(self, step_deps: StepDeps):
        """Finalize reports failure when checks failed."""
        handler = get_step("smoke-test-finalize")

        step_input = StepInput(
            step_name="finalize",
            task_id="task-123",
            workflow_name="SmokeTest",
            vars={
                "smoke_test": {
                    "total_targets": 2,
                    "passed_checks": 2,
                    "failed_checks": 2,
                    "dns_results": {
                        "target1": {"success": True},
                        "target2": {"success": False},
                    },
                    "http_results": {
                        "target1": {"success": True},
                        "target2": {"success": False},
                    },
                }
            },
        )

        result = handler(step_input, step_deps)

        assert not result.has_errors  # finalize itself doesn't error
        assert result.output["overall_status"] == "failed"
        assert result.flow_control == {"mark_failed": True}

    def test_finalize_empty_context(self, step_deps: StepDeps):
        """Finalize handles empty context gracefully."""
        handler = get_step("smoke-test-finalize")

        step_input = StepInput(
            step_name="finalize",
            task_id="task-123",
            workflow_name="SmokeTest",
            vars={},
        )

        result = handler(step_input, step_deps)

        assert not result.has_errors
        assert result.output["total_targets"] == 0
        assert result.output["overall_status"] == "passed"
