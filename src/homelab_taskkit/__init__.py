"""homelab-taskkit: Functional-first task implementations for Argo Workflows."""

__version__ = "0.1.0"

from homelab_taskkit.deps import Deps, build_deps
from homelab_taskkit.registry import TaskDef, get_task, list_tasks
from homelab_taskkit.runner import run_task

__all__ = [
    "Deps",
    "TaskDef",
    "build_deps",
    "get_task",
    "list_tasks",
    "run_task",
]
