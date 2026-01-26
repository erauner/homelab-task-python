"""Testing utilities for context-aware step testing.

Provides helpers to test steps with context input/output:
- run_step_with_context(): Execute a step and capture context changes
- Pipeline chain testing for multi-step WorkflowTemplate behavior
- make_messages(): Create messages output for embedding in task returns
- make_fanout(): Create fanout output for embedding in task returns

Usage:
    from homelab_taskkit.testing import run_step_with_context, make_messages, make_fanout
    from homelab_taskkit.context import TaskkitContext

    def test_http_request_sets_last_status(fake_deps):
        initial = TaskkitContext(version="taskkit-context/v1", vars={})

        out, new_ctx = run_step_with_context(
            step_fn=run,
            inputs={"url": "https://example.com"},
            deps=fake_deps,
            context=initial,
        )

        assert out["status_code"] == 200
        assert new_ctx.vars["http_request.last_status"] == 200

    def test_task_emits_warnings():
        # A task can emit messages by including them in its output
        result = {
            "data": "...",
            **make_messages([
                {"level": "warning", "message": "Something to note"}
            ])
        }
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from homelab_taskkit.context import (
    CONTEXT_PATCH_KEY,
    TaskkitContext,
    apply_patch,
    empty_context,
    extract_context_patch,
)
from homelab_taskkit.deps import Deps
from homelab_taskkit.fanout import FANOUT_KEY, TaskkitFanout, extract_fanout
from homelab_taskkit.messages import MESSAGES_KEY, TaskkitMessage, extract_messages


def run_step_with_context(
    *,
    step_fn: Callable[[dict[str, Any], Deps], dict[str, Any]],
    inputs: dict[str, Any],
    deps: Deps,
    context: TaskkitContext | None = None,
) -> tuple[dict[str, Any], TaskkitContext]:
    """Run a step function with context injection and patch extraction.

    This helper enables unit testing of context-aware steps:
    1. Injects context into deps (via deps.context)
    2. Executes the step function
    3. Extracts context_patch from output (if present)
    4. Returns cleaned output and new context

    Args:
        step_fn: The task's run() function.
        inputs: Task input dictionary.
        deps: Dependencies (will be rebuilt with context).
        context: Initial context (defaults to empty).

    Returns:
        Tuple of (output_without_patch, new_context).
    """
    ctx = context or empty_context()

    # Rebuild deps with context injected
    # Note: Deps is frozen, so we create a new instance
    deps_with_context = Deps(
        http=deps.http,
        now=deps.now,
        env=deps.env,
        logger=deps.logger,
        context=deepcopy(ctx.vars),
    )

    # Execute step
    raw_output = step_fn(inputs, deps_with_context)

    # Extract patch from output
    clean_output, patch = extract_context_patch(raw_output)

    # Apply patch to get new context
    new_ctx = apply_patch(ctx, patch)

    return clean_output, new_ctx


def chain_steps(
    *,
    steps: list[tuple[Callable[[dict[str, Any], Deps], dict[str, Any]], dict[str, Any]]],
    deps: Deps,
    initial_context: TaskkitContext | None = None,
) -> tuple[list[dict[str, Any]], TaskkitContext]:
    """Chain multiple steps, passing context between them.

    Useful for testing multi-step WorkflowTemplate behavior locally
    without requiring Argo.

    Args:
        steps: List of (step_fn, inputs) tuples.
        deps: Dependencies (shared across all steps).
        initial_context: Starting context (defaults to empty).

    Returns:
        Tuple of (list_of_outputs, final_context).

    Example:
        outputs, final_ctx = chain_steps(
            steps=[
                (http_request_run, {"url": "https://api.example.com/data"}),
                (json_transform_run, {"data": "...", "mappings": {...}}),
            ],
            deps=fake_deps,
        )
    """
    ctx = initial_context or empty_context()
    outputs = []

    for step_fn, inputs in steps:
        output, ctx = run_step_with_context(
            step_fn=step_fn,
            inputs=inputs,
            deps=deps,
            context=ctx,
        )
        outputs.append(output)

    return outputs, ctx


def create_context_with_vars(vars: dict[str, Any]) -> TaskkitContext:
    """Create a TaskkitContext with the given vars.

    Convenience function for tests.

    Args:
        vars: The context variables to set.

    Returns:
        A new TaskkitContext with the specified vars.
    """
    return TaskkitContext(version="taskkit-context/v1", vars=dict(vars))


def make_patch(
    *,
    set: dict[str, Any] | None = None,
    unset: list[str] | None = None,
) -> dict[str, Any]:
    """Create a context patch dict for embedding in task output.

    Convenience function for tasks that want to emit context changes.

    Args:
        set: Keys to set/upsert.
        unset: Keys to remove.

    Returns:
        A dict suitable for task output under CONTEXT_PATCH_KEY.

    Example:
        def run(inputs, deps):
            return {
                "status_code": 200,
                **make_patch(set={"http_request.last_status": 200}),
            }
    """
    patch = {}
    if set:
        patch["set"] = set
    if unset:
        patch["unset"] = unset

    if not patch:
        return {}

    return {CONTEXT_PATCH_KEY: patch}


def make_messages(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Create a messages dict for embedding in task output.

    Convenience function for tasks that want to emit diagnostic messages.

    Args:
        messages: List of message dicts with keys: level, message, code (optional),
                  source (optional), data (optional).

    Returns:
        A dict suitable for task output under MESSAGES_KEY.

    Example:
        def run(inputs, deps):
            return {
                "result": "...",
                **make_messages([
                    {"level": "warning", "message": "Slow response", "code": "SLOW"},
                    {"level": "info", "message": "Using cached value"},
                ]),
            }
    """
    if not messages:
        return {}
    return {MESSAGES_KEY: messages}


def make_fanout(items: list[Any]) -> dict[str, Any]:
    """Create a fanout dict for embedding in task output.

    Convenience function for fanout-source tasks that spawn parallel steps.

    Args:
        items: List of items for parallel execution.

    Returns:
        A dict suitable for task output under FANOUT_KEY.

    Example:
        def run(inputs, deps):
            targets = [{"cluster": c} for c in inputs["clusters"]]
            return {
                "generated_count": len(targets),
                **make_fanout(targets),
            }
    """
    if not items:
        return {}
    return {FANOUT_KEY: items}


def run_step_with_artifacts(
    *,
    step_fn: Callable[[dict[str, Any], Deps], dict[str, Any]],
    inputs: dict[str, Any],
    deps: Deps,
    context: TaskkitContext | None = None,
) -> tuple[dict[str, Any], TaskkitContext, list[TaskkitMessage], TaskkitFanout | None]:
    """Run a step function with full artifact extraction.

    Extends run_step_with_context to also extract messages and fanout.

    Args:
        step_fn: The task's run() function.
        inputs: Task input dictionary.
        deps: Dependencies (will be rebuilt with context).
        context: Initial context (defaults to empty).

    Returns:
        Tuple of (output_without_artifacts, new_context, messages, fanout_or_none).

    Example:
        out, ctx, msgs, fanout = run_step_with_artifacts(
            step_fn=run,
            inputs={"url": "..."},
            deps=fake_deps,
        )
        assert any(m.level == "warning" for m in msgs)
        assert fanout is None  # Non-fanout step
    """
    ctx = context or empty_context()

    # Rebuild deps with context injected
    deps_with_context = Deps(
        http=deps.http,
        now=deps.now,
        env=deps.env,
        logger=deps.logger,
        context=deepcopy(ctx.vars),
    )

    # Execute step
    raw_output = step_fn(inputs, deps_with_context)

    # Extract context patch
    clean_output, patch = extract_context_patch(raw_output)
    new_ctx = apply_patch(ctx, patch)

    # Extract messages
    clean_output, task_messages = extract_messages(clean_output, task_name="test")

    # Extract fanout
    clean_output, extracted_fanout = extract_fanout(clean_output)

    return clean_output, new_ctx, task_messages, extracted_fanout
