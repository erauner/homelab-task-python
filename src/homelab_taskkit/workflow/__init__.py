"""Workflow definitions and runners for homelab-taskkit.

This module provides:
- WorkflowDefinition: YAML-defined workflow structure with steps and dependencies
- LocalRunner: Execute workflows locally for testing without Argo/K8s
- StepRunner: Execute individual steps in Argo containers (step-per-container model)
- RuntimeEnv: Parse TASKKIT_* environment variables for Argo execution
- StepInput/StepResult: Clean I/O contracts for step handlers
- @register_step: Decorator for registering step handlers

Execution Models:
1. LocalRunner (single container): All steps run sequentially in one container
   - CLI: task-run workflow run -w workflows/my_workflow.yaml
   - Good for: Local testing, simple workflows

2. StepRunner (step-per-container): Each step is a separate Argo pod
   - CLI: task-run step run (with TASKKIT_* env vars)
   - Good for: Production, Argo-native parallelism and retries

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

from homelab_taskkit.workflow.env import (
    ENV_VARS,
    EnvParseError,
    RuntimeEnv,
    load_runtime_env,
)
from homelab_taskkit.workflow.files import (
    FileReadError,
    FileWriteError,
    build_error_output,
    build_step_output,
    read_params_json,
    read_vars_yaml,
    write_flow_control,
    write_step_output,
    write_vars_yaml,
)
from homelab_taskkit.workflow.local_runner import (
    LocalRunner,
    WorkflowExecutionResult,
)
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
    has_step,
    list_steps,
    register_step,
)
from homelab_taskkit.workflow.step_runner import main as step_runner_main
from homelab_taskkit.workflow.step_runner import run_step
from homelab_taskkit.workflow.workflow import (
    StepTemplate,
    WorkflowDefinition,
    WorkflowStep,
)

__all__ = [
    # Environment
    "RuntimeEnv",
    "load_runtime_env",
    "EnvParseError",
    "ENV_VARS",
    # Files
    "FileReadError",
    "FileWriteError",
    "read_params_json",
    "read_vars_yaml",
    "write_vars_yaml",
    "write_step_output",
    "write_flow_control",
    "build_step_output",
    "build_error_output",
    # Local Runner
    "LocalRunner",
    "WorkflowExecutionResult",
    # Step Runner
    "run_step",
    "step_runner_main",
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
    "has_step",
    "list_steps",
    "StepHandler",
    "StepAlreadyRegisteredError",
    "StepNotFoundError",
]
