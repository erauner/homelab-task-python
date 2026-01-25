"""Dependency injection for task implementations."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


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
    """

    http: httpx.Client
    now: Callable[[], datetime]
    env: Mapping[str, str]
    logger: logging.Logger


@contextmanager
def build_deps(
    env: Mapping[str, str],
    *,
    timeout: float = 30.0,
) -> Iterator[Deps]:
    """Build dependencies for task execution.

    This is a context manager that properly cleans up resources.

    Args:
        env: Environment variables mapping (typically os.environ).
        timeout: HTTP client timeout in seconds.

    Yields:
        A Deps instance with all dependencies wired up.

    Example:
        with build_deps(os.environ) as deps:
            result = my_task(inputs, deps)
    """
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
        )
    finally:
        http_client.close()
