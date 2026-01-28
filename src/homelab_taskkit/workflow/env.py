"""Environment variable parsing for the taskkit workflow runtime.

Parses all environment variables into a typed RuntimeEnv object.
This is the only place where env vars are read for step execution.
"""

from __future__ import annotations

import json
import os
from typing import Any

from pydantic import BaseModel, Field, field_validator


class RuntimeEnv(BaseModel):
    """Parsed environment variables from the Argo workflow container.

    All TASKKIT_* environment variables are captured here.
    The step runner uses this to build StepInput.
    """

    # Task Identity
    task_id: str = Field(description="TASKKIT_TASK_ID - Unique task/workflow run identifier")
    task_type: str = Field(default="", description="TASKKIT_TASK_TYPE - Task type (e.g., 'smoke-test')")
    task_variant: str = Field(default="", description="TASKKIT_TASK_VARIANT - Task variant")

    # Workflow Metadata
    workflow_name: str = Field(description="TASKKIT_WORKFLOW_NAME - Workflow definition name")
    platform: str = Field(default="homelab", description="TASKKIT_PLATFORM - Platform identifier")
    context: str = Field(default="local", description="TASKKIT_CONTEXT - Execution context")

    # File System Paths
    working_dir: str = Field(description="TASKKIT_WORKING_DIR - Working directory for step execution")
    params_file: str = Field(description="TASKKIT_PARAMS_FILE - Path to params.json")
    output_file: str = Field(description="TASKKIT_OUTPUT_FILE - Path to write step_output.json")
    vars_file: str = Field(default="", description="TASKKIT_VARS_FILE - Path to vars.yaml (optional)")
    flow_control_file: str = Field(
        default="/tmp/flow_control.json", description="TASKKIT_FLOW_CONTROL_FILE"
    )

    # Step Context
    step_name: str = Field(description="TASKKIT_STEP_NAME - Current step name")
    step_template: str = Field(default="action", description="TASKKIT_STEP_TEMPLATE - Step template type")
    step_params: dict[str, Any] = Field(
        default_factory=dict, description="TASKKIT_STEP_PARAMS - Step-specific params (JSON)"
    )
    handler_prefix: str = Field(default="", description="TASKKIT_HANDLER_PREFIX - Step handler prefix")

    # Retry Tracking
    retries: int = Field(default=0, description="TASKKIT_RETRIES - Current attempt (0-based)")
    total_retries: int = Field(default=3, description="TASKKIT_TOTAL_RETRIES - Max retry attempts")

    # Finalize Step Only
    workflow_result: str | None = Field(
        default=None, description="TASKKIT_WORKFLOW_RESULT - Result for finalize step"
    )

    @field_validator("step_params", mode="before")
    @classmethod
    def parse_step_params(cls, v: Any) -> dict[str, Any]:
        """Parse JSON string into dict."""
        if isinstance(v, dict):
            return v
        if isinstance(v, str) and v:
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {}
        return {}

    @field_validator("retries", "total_retries", mode="before")
    @classmethod
    def parse_int(cls, v: Any) -> int:
        """Parse string to int."""
        if isinstance(v, int):
            return v
        if isinstance(v, str) and v:
            try:
                return int(v)
            except ValueError:
                return 0
        return 0

    @property
    def vars_file_path(self) -> str:
        """Path to vars.yaml - uses explicit var or defaults to working_dir/vars.yaml."""
        if self.vars_file:
            return self.vars_file
        return os.path.join(self.working_dir, "vars.yaml")

    @property
    def is_first_attempt(self) -> bool:
        """Check if this is the first execution attempt."""
        return self.retries == 0

    @property
    def is_finalize_step(self) -> bool:
        """Check if this is the finalize step."""
        return self.step_template == "finalize"

    @property
    def handler_name(self) -> str:
        """Get the full handler name for step registry lookup."""
        if self.handler_prefix:
            return f"{self.handler_prefix}-{self.step_name}"
        return self.step_name


# Environment variable names (single source of truth)
ENV_VARS = {
    "task_id": "TASKKIT_TASK_ID",
    "task_type": "TASKKIT_TASK_TYPE",
    "task_variant": "TASKKIT_TASK_VARIANT",
    "workflow_name": "TASKKIT_WORKFLOW_NAME",
    "platform": "TASKKIT_PLATFORM",
    "context": "TASKKIT_CONTEXT",
    "working_dir": "TASKKIT_WORKING_DIR",
    "params_file": "TASKKIT_PARAMS_FILE",
    "output_file": "TASKKIT_OUTPUT_FILE",
    "vars_file": "TASKKIT_VARS_FILE",
    "flow_control_file": "TASKKIT_FLOW_CONTROL_FILE",
    "step_name": "TASKKIT_STEP_NAME",
    "step_template": "TASKKIT_STEP_TEMPLATE",
    "step_params": "TASKKIT_STEP_PARAMS",
    "handler_prefix": "TASKKIT_HANDLER_PREFIX",
    "retries": "TASKKIT_RETRIES",
    "total_retries": "TASKKIT_TOTAL_RETRIES",
    "workflow_result": "TASKKIT_WORKFLOW_RESULT",
}

# Required environment variables (must be present)
REQUIRED_ENV_VARS = [
    "TASKKIT_STEP_NAME",
    "TASKKIT_TASK_ID",
    "TASKKIT_WORKFLOW_NAME",
    "TASKKIT_WORKING_DIR",
    "TASKKIT_PARAMS_FILE",
    "TASKKIT_OUTPUT_FILE",
]


class EnvParseError(Exception):
    """Raised when required environment variables are missing or invalid."""

    pass


def load_runtime_env(environ: dict[str, str] | None = None) -> RuntimeEnv:
    """Load and parse all environment variables into RuntimeEnv.

    Args:
        environ: Environment mapping (defaults to os.environ)

    Returns:
        Parsed RuntimeEnv object

    Raises:
        EnvParseError: If required variables are missing
    """
    if environ is None:
        environ = dict(os.environ)

    # Check required variables
    missing = [var for var in REQUIRED_ENV_VARS if not environ.get(var)]
    if missing:
        raise EnvParseError(f"Missing required environment variables: {', '.join(missing)}")

    # Build kwargs from environment
    kwargs: dict[str, Any] = {}
    for field_name, env_var in ENV_VARS.items():
        value = environ.get(env_var)
        if value is not None:
            kwargs[field_name] = value

    return RuntimeEnv(**kwargs)
