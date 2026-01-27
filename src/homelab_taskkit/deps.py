"""Dependency injection for task implementations."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Environment variable prefixes and keys
TASKKIT_ENV_PREFIX = "TASKKIT_"


@dataclass(frozen=True)
class TaskkitEnv:
    """Structured access to TASKKIT_* environment variables.

    These are injected by the workflow orchestrator to provide
    context about the current task execution.

    Attributes:
        task_id: Unique identifier for the task definition.
        run_id: Unique identifier for this workflow run.
        step_name: Name of the current step.
        step_retry: Current retry attempt (0-indexed).
        total_retries: Maximum retries configured.
        workflow_name: Argo Workflow name.
        workflow_namespace: Kubernetes namespace.
        node_name: Current Argo node name.
        workflow_result: Final workflow status (only in finalize step).
        api_url: Base URL for homelab-tasks API (optional).
        api_token: Bearer token for API callbacks (optional).
        step_params: JSON-encoded step parameters (optional alternative to file).
    """

    task_id: str | None = None
    run_id: str | None = None
    step_name: str | None = None
    step_retry: int = 0
    total_retries: int = 3
    workflow_name: str | None = None
    workflow_namespace: str | None = None
    node_name: str | None = None
    workflow_result: str | None = None  # "Succeeded" | "Failed" | "Error"
    api_url: str | None = None
    api_token: str | None = None
    step_params: str | None = None

    @property
    def is_finalize_step(self) -> bool:
        """Check if this is the finalize step (has workflow_result)."""
        return self.workflow_result is not None

    @property
    def workflow_succeeded(self) -> bool | None:
        """Return True if workflow succeeded, False if failed, None if unknown."""
        if self.workflow_result is None:
            return None
        return self.workflow_result == "Succeeded"

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> TaskkitEnv:
        """Build from environment variables.

        Args:
            env: Environment variables mapping (typically os.environ).

        Returns:
            TaskkitEnv with values parsed from TASKKIT_* variables.
        """
        return cls(
            task_id=env.get("TASKKIT_TASK_ID"),
            run_id=env.get("TASKKIT_RUN_ID"),
            step_name=env.get("TASKKIT_STEP_NAME"),
            step_retry=int(env.get("TASKKIT_STEP_RETRY", "0")),
            total_retries=int(env.get("TASKKIT_TOTAL_RETRIES", "3")),
            workflow_name=env.get("TASKKIT_WORKFLOW_NAME"),
            workflow_namespace=env.get("TASKKIT_WORKFLOW_NAMESPACE"),
            node_name=env.get("TASKKIT_NODE_NAME"),
            workflow_result=env.get("TASKKIT_WORKFLOW_RESULT"),
            api_url=env.get("TASKKIT_API_URL"),
            api_token=env.get("TASKKIT_API_TOKEN"),
            step_params=env.get("TASKKIT_STEP_PARAMS"),
        )


@dataclass(frozen=True)
class Deps:
    """Dependencies injected into task functions.

    This container holds all external dependencies that tasks need.
    Tasks receive this as a parameter, making them testable with fake deps.

    Attributes:
        http: HTTP client for making requests.
        now: Function returning current UTC time (injectable for testing).
        env: Environment variables mapping.
        logger: Logger instance for task output.
        context: Read-only context variables from previous steps.
        taskkit: Structured access to TASKKIT_* environment variables.
    """

    http: httpx.Client
    now: Callable[[], datetime]
    env: Mapping[str, str]
    logger: logging.Logger
    context: Mapping[str, Any]
    taskkit: TaskkitEnv


@contextmanager
def build_deps(
    env: Mapping[str, str],
    *,
    timeout: float = 30.0,
    context: Mapping[str, Any] | None = None,
) -> Iterator[Deps]:
    """Build dependencies for task execution.

    This is a context manager that properly cleans up resources.

    Args:
        env: Environment variables mapping (typically os.environ).
        timeout: HTTP client timeout in seconds.
        context: Read-only context variables (wrapped in MappingProxyType).

    Yields:
        A Deps instance with all dependencies wired up.

    Example:
        with build_deps(os.environ) as deps:
            result = my_task(inputs, deps)

        with build_deps(os.environ, context={"pipeline.run_id": "abc"}) as deps:
            result = my_task(inputs, deps)
    """
    # Wrap context in MappingProxyType for read-only access
    safe_context: Mapping[str, Any] = MappingProxyType(dict(context or {}))

    # Parse TASKKIT_* environment variables
    taskkit_env = TaskkitEnv.from_env(env)

    http_client = httpx.Client(
        timeout=timeout,
        follow_redirects=True,
    )

    try:
        yield Deps(
            http=http_client,
            now=lambda: datetime.now(UTC),
            env=env,
            logger=logging.getLogger("homelab_taskkit.task"),
            context=safe_context,
            taskkit=taskkit_env,
        )
    finally:
        http_client.close()
