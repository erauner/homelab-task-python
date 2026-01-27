"""Workflow definitions and local runner for homelab-taskkit.

This module provides:
- WorkflowDefinition: YAML-defined workflow structure with steps and dependencies
- LocalRunner: Execute workflows locally for testing without Argo/K8s
- StepInput/StepResult: Clean I/O contracts for step handlers
- @register_step: Decorator for registering step handlers

Example CLI usage:
    task-run workflow run -w workflows/my_workflow.yaml -p params.json --workdir ./test-run

Example workflow YAML:
    name: InfrastructureSmokeTest
    platform: homelab
    handler_prefix: smoke-test
    steps:
      - name: init
        template: init
      - name: check-dns
        depends: [init]
      - name: finalize
        template: finalize
        depends: [check-dns]
    default_retries: 3
    timeout_seconds: 3600
"""

from homelab_taskkit.workflow.models import (
    Message,
    Severity,
    StepDeps,
    StepInput,
    StepResult,
)
from homelab_taskkit.workflow.registry import (
    StepAlreadyRegisteredError,
    StepHandler,
    StepNotFoundError,
    get_step,
    list_steps,
    register_step,
)
from homelab_taskkit.workflow.local_runner import (
    LocalRunner,
    WorkflowExecutionResult,
)
from homelab_taskkit.workflow.workflow import (
    StepTemplate,
    WorkflowDefinition,
    WorkflowStep,
)

__all__ = [
    # Local Runner
    "LocalRunner",
    "WorkflowExecutionResult",
    # Models
    "StepInput",
    "StepResult",
    "StepDeps",
    "Message",
    "Severity",
    # Workflow
    "WorkflowDefinition",
    "WorkflowStep",
    "StepTemplate",
    # Registry
    "register_step",
    "get_step",
    "list_steps",
    "StepHandler",
    "StepAlreadyRegisteredError",
    "StepNotFoundError",
]
