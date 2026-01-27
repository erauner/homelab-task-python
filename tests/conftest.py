"""Pytest fixtures for homelab-taskkit tests."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from homelab_taskkit.deps import Deps, TaskkitEnv


@pytest.fixture
def fake_taskkit_env() -> TaskkitEnv:
    """Create a fake TaskkitEnv for testing."""
    return TaskkitEnv(
        task_id="test-task",
        run_id="test-run-123",
        step_name="test-step",
        step_retry=0,
        total_retries=3,
        workflow_name="test-workflow",
        workflow_namespace="default",
        node_name="test-node",
    )


@pytest.fixture
def fake_deps(fake_taskkit_env: TaskkitEnv) -> Deps:
    """Create a Deps instance with fake/mock dependencies for testing.

    Includes an empty context by default. Use fake_deps_with_context()
    or manually override for context-aware testing.
    """
    mock_http = MagicMock()
    mock_http.request.return_value = MagicMock(
        status_code=200,
        json=lambda: {"test": "data"},
        text="test response",
        headers={"content-type": "application/json"},
        elapsed=MagicMock(total_seconds=lambda: 0.1),
    )

    return Deps(
        http=mock_http,
        now=lambda: datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
        env={"TEST_VAR": "test_value"},
        logger=logging.getLogger("test"),
        context={},  # Empty context by default
        taskkit=fake_taskkit_env,
    )


@pytest.fixture
def fake_deps_with_context(fake_taskkit_env: TaskkitEnv) -> Deps:
    """Create a Deps instance with sample context for context-aware testing."""
    mock_http = MagicMock()
    mock_http.request.return_value = MagicMock(
        status_code=200,
        json=lambda: {"test": "data"},
        text="test response",
        headers={"content-type": "application/json"},
        elapsed=MagicMock(total_seconds=lambda: 0.1),
    )

    return Deps(
        http=mock_http,
        now=lambda: datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
        env={"TEST_VAR": "test_value"},
        logger=logging.getLogger("test"),
        context={
            "pipeline.run_id": "test-run-123",
            "pipeline.step": 1,
        },
        taskkit=fake_taskkit_env,
    )


@pytest.fixture
def sample_echo_input() -> dict[str, Any]:
    """Sample valid input for echo task."""
    return {
        "message": "Hello, World!",
        "metadata": {"source": "test"},
    }


@pytest.fixture
def sample_http_input() -> dict[str, Any]:
    """Sample valid input for http_request task."""
    return {
        "url": "https://api.example.com/data",
        "method": "GET",
        "headers": {"Authorization": "Bearer test"},
    }
