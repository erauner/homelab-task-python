"""homelab-taskkit: Functional-first task implementations for Argo Workflows."""

__version__ = "0.1.0"

from homelab_taskkit.context import (
    CONTEXT_PATCH_KEY,
    ContextPatch,
    TaskkitContext,
    apply_patch,
    empty_context,
    extract_context_patch,
    load_context,
    write_context,
)
from homelab_taskkit.context_rules import validate_patch
from homelab_taskkit.deps import Deps, build_deps
from homelab_taskkit.registry import TaskDef, get_task, list_tasks
from homelab_taskkit.runner import run_task
from homelab_taskkit.testing import (
    chain_steps,
    create_context_with_vars,
    make_patch,
    run_step_with_context,
)

__all__ = [
    # Core
    "Deps",
    "TaskDef",
    "build_deps",
    "get_task",
    "list_tasks",
    "run_task",
    # Context artifacts
    "CONTEXT_PATCH_KEY",
    "ContextPatch",
    "TaskkitContext",
    "apply_patch",
    "empty_context",
    "extract_context_patch",
    "load_context",
    "validate_patch",
    "write_context",
    # Testing utilities
    "chain_steps",
    "create_context_with_vars",
    "make_patch",
    "run_step_with_context",
]
