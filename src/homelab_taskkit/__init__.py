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
from homelab_taskkit.deps import Deps, TaskkitEnv, build_deps
from homelab_taskkit.fanout import (
    FANOUT_KEY,
    TaskkitFanout,
    empty_fanout,
    extract_fanout,
    write_fanout,
)
from homelab_taskkit.flow_control import (
    FLOW_CONTROL_KEY,
    TaskkitFlowControl,
    empty_flow_control,
    extract_flow_control,
    make_flow_control,
    write_flow_control,
)
from homelab_taskkit.messages import (
    MESSAGES_KEY,
    TaskkitMessages,
    empty_messages,
    extract_messages,
    write_messages,
)
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
    "TaskkitEnv",
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
    # Messages artifacts
    "MESSAGES_KEY",
    "TaskkitMessages",
    "empty_messages",
    "extract_messages",
    "write_messages",
    # Fanout artifacts
    "FANOUT_KEY",
    "TaskkitFanout",
    "empty_fanout",
    "extract_fanout",
    "write_fanout",
    # Flow control artifacts
    "FLOW_CONTROL_KEY",
    "TaskkitFlowControl",
    "empty_flow_control",
    "extract_flow_control",
    "make_flow_control",
    "write_flow_control",
    # Testing utilities
    "chain_steps",
    "create_context_with_vars",
    "make_patch",
    "run_step_with_context",
]
