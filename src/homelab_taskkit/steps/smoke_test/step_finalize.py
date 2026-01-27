"""Smoke test finalize step handler.

Summarizes results and sets final workflow status.
"""

from __future__ import annotations

import json
from pathlib import Path

from homelab_taskkit.workflow import (
    StepDeps,
    StepInput,
    StepResult,
    register_step,
)


@register_step("smoke-test-finalize")
def handle_finalize(step_input: StepInput, deps: StepDeps) -> StepResult:
    """Finalize the smoke test workflow.

    Summarizes all check results and writes a final report.
    This step always runs, even if previous steps failed.
    """
    result = StepResult()

    smoke_test = step_input.vars.get("smoke_test", {})

    total_targets = smoke_test.get("total_targets", 0)
    passed_checks = smoke_test.get("passed_checks", 0)
    failed_checks = smoke_test.get("failed_checks", 0)
    dns_results = smoke_test.get("dns_results", {})
    http_results = smoke_test.get("http_results", {})

    # Build summary
    summary = {
        "total_targets": total_targets,
        "passed_checks": passed_checks,
        "failed_checks": failed_checks,
        "dns_results": dns_results,
        "http_results": http_results,
        "overall_status": "passed" if failed_checks == 0 else "failed",
    }

    # Write summary report to workdir
    workdir = Path(deps.workdir)
    report_path = workdir / "smoke-test-report.json"

    with open(report_path, "w") as f:
        json.dump(summary, f, indent=2)

    result.add_info(
        f"Report written to: {report_path}",
        system="smoke-test",
    )

    # Log summary
    if failed_checks == 0:
        result.add_info(
            f"Smoke test completed: {passed_checks}/{passed_checks + failed_checks} checks passed",
            system="smoke-test",
        )
    else:
        result.add_warning(
            f"Smoke test completed with failures: {passed_checks} passed, {failed_checks} failed",
            system="smoke-test",
        )

        # Set flow control to mark the workflow as failed
        result.flow_control = {"mark_failed": True}

    # Store summary in output
    result.output = summary

    return result
