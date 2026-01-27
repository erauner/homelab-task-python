"""Smoke test init step handler.

Initializes the workflow by validating parameters and setting up context.
"""

from __future__ import annotations

from homelab_taskkit.workflow import (
    StepDeps,
    StepInput,
    StepResult,
    register_step,
)

REQUIRED_PARAMS = ["targets"]


def _validate_params(step_input: StepInput) -> list[str]:
    """Validate required parameters."""
    errors: list[str] = []
    params = step_input.params

    for param in REQUIRED_PARAMS:
        if param not in params:
            errors.append(f"Missing required parameter: {param}")

    # Validate targets structure
    targets = params.get("targets", [])
    if not isinstance(targets, list):
        errors.append("Parameter 'targets' must be a list")
    elif len(targets) == 0:
        errors.append("Parameter 'targets' must not be empty")
    else:
        for i, target in enumerate(targets):
            if not isinstance(target, dict):
                errors.append(f"Target {i} must be an object")
            elif "name" not in target:
                errors.append(f"Target {i} missing 'name' field")

    return errors


@register_step("smoke-test-init")
def handle_init(step_input: StepInput, deps: StepDeps) -> StepResult:
    """Initialize the smoke test workflow.

    Validates parameters and sets up context for subsequent steps.

    Required params:
        targets: List of targets to test, each with:
            - name: Target identifier
            - dns_host: Optional DNS hostname to resolve
            - http_url: Optional HTTP URL to check
            - expected_status: Optional expected HTTP status (default: 200)
    """
    result = StepResult()

    # Validate parameters
    errors = _validate_params(step_input)
    for error in errors:
        result.add_error(error, system="smoke-test")

    if result.has_errors:
        return result

    # Initialize context variables
    targets = step_input.params["targets"]
    result.context_updates["smoke_test"] = {
        "total_targets": len(targets),
        "passed_checks": 0,
        "failed_checks": 0,
        "dns_results": {},
        "http_results": {},
    }

    result.add_info(
        f"Workflow initialized with {len(targets)} targets",
        system="smoke-test",
    )

    return result
