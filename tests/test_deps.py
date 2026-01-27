"""Tests for dependency injection functionality."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from homelab_taskkit.deps import TaskkitEnv, build_deps


class TestTaskkitEnv:
    """Tests for TaskkitEnv dataclass."""

    def test_from_env_parses_all_fields(self) -> None:
        env = {
            "TASKKIT_TASK_ID": "validate-input",
            "TASKKIT_RUN_ID": "abc-123",
            "TASKKIT_STEP_NAME": "init",
            "TASKKIT_STEP_RETRY": "2",
            "TASKKIT_TOTAL_RETRIES": "5",
            "TASKKIT_WORKFLOW_NAME": "my-workflow",
            "TASKKIT_WORKFLOW_NAMESPACE": "tasks",
            "TASKKIT_NODE_NAME": "my-workflow-node-1",
            "TASKKIT_WORKFLOW_RESULT": "Succeeded",
            "TASKKIT_API_URL": "https://api.example.com",
            "TASKKIT_API_TOKEN": "secret-token",
            "TASKKIT_STEP_PARAMS": '{"key": "value"}',
        }

        taskkit = TaskkitEnv.from_env(env)

        assert taskkit.task_id == "validate-input"
        assert taskkit.run_id == "abc-123"
        assert taskkit.step_name == "init"
        assert taskkit.step_retry == 2
        assert taskkit.total_retries == 5
        assert taskkit.workflow_name == "my-workflow"
        assert taskkit.workflow_namespace == "tasks"
        assert taskkit.node_name == "my-workflow-node-1"
        assert taskkit.workflow_result == "Succeeded"
        assert taskkit.api_url == "https://api.example.com"
        assert taskkit.api_token == "secret-token"
        assert taskkit.step_params == '{"key": "value"}'

    def test_from_env_handles_missing_fields(self) -> None:
        env: dict[str, str] = {}

        taskkit = TaskkitEnv.from_env(env)

        assert taskkit.task_id is None
        assert taskkit.run_id is None
        assert taskkit.step_retry == 0  # Default
        assert taskkit.total_retries == 3  # Default
        assert taskkit.workflow_result is None

    def test_is_finalize_step_when_result_present(self) -> None:
        taskkit = TaskkitEnv(workflow_result="Succeeded")
        assert taskkit.is_finalize_step is True

    def test_is_finalize_step_when_result_absent(self) -> None:
        taskkit = TaskkitEnv()
        assert taskkit.is_finalize_step is False

    def test_workflow_succeeded_true(self) -> None:
        taskkit = TaskkitEnv(workflow_result="Succeeded")
        assert taskkit.workflow_succeeded is True

    def test_workflow_succeeded_false(self) -> None:
        taskkit = TaskkitEnv(workflow_result="Failed")
        assert taskkit.workflow_succeeded is False

    def test_workflow_succeeded_false_for_error(self) -> None:
        taskkit = TaskkitEnv(workflow_result="Error")
        assert taskkit.workflow_succeeded is False

    def test_workflow_succeeded_none_when_unknown(self) -> None:
        taskkit = TaskkitEnv()
        assert taskkit.workflow_succeeded is None


class TestBuildDeps:
    """Tests for build_deps context manager."""

    def test_creates_deps_with_http_client(self) -> None:
        env = {"TEST_VAR": "test_value"}

        with build_deps(env) as deps:
            assert deps.http is not None
            assert deps.env == env

    def test_creates_deps_with_context(self) -> None:
        env = {"TEST_VAR": "test_value"}
        context = {"pipeline.run_id": "abc-123"}

        with build_deps(env, context=context) as deps:
            assert deps.context["pipeline.run_id"] == "abc-123"

    def test_context_is_read_only(self) -> None:
        env: dict[str, str] = {}
        context = {"key": "value"}

        with build_deps(env, context=context) as deps, pytest.raises(TypeError):
            # Should raise TypeError when trying to modify
            deps.context["key"] = "new_value"  # type: ignore[index]

    def test_creates_taskkit_env(self) -> None:
        env = {
            "TASKKIT_TASK_ID": "test-task",
            "TASKKIT_RUN_ID": "run-123",
        }

        with build_deps(env) as deps:
            assert deps.taskkit.task_id == "test-task"
            assert deps.taskkit.run_id == "run-123"

    def test_now_returns_utc_datetime(self) -> None:
        env: dict[str, str] = {}

        with build_deps(env) as deps:
            now = deps.now()
            assert now.tzinfo == UTC
            assert isinstance(now, datetime)

    def test_logger_is_available(self) -> None:
        env: dict[str, str] = {}

        with build_deps(env) as deps:
            assert deps.logger is not None
            # Should be able to log without error
            deps.logger.info("Test log message")

    def test_http_client_is_closed_after_context(self) -> None:
        env: dict[str, str] = {}

        with build_deps(env) as deps:
            http = deps.http

        # After context exits, client should be closed
        # (httpx raises RuntimeError if we try to use a closed client)
        with pytest.raises(RuntimeError):
            http.get("https://example.com")

    def test_custom_timeout(self) -> None:
        env: dict[str, str] = {}

        with build_deps(env, timeout=60.0) as deps:
            # Verify timeout was set (httpx stores this internally)
            assert deps.http.timeout.connect == 60.0
