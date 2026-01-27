"""Smoke test HTTP check step handler.

Checks HTTP endpoint health for configured targets.
"""

from __future__ import annotations

import httpx

from homelab_taskkit.workflow import (
    StepDeps,
    StepInput,
    StepResult,
    register_step,
)


@register_step("smoke-test-check-http")
def handle_check_http(step_input: StepInput, deps: StepDeps) -> StepResult:
    """Check HTTP endpoints for targets with http_url configured.

    Updates context with HTTP results for each target.
    """
    result = StepResult()

    targets = step_input.params.get("targets", [])
    smoke_test = dict(step_input.vars.get("smoke_test", {}))
    http_results = dict(smoke_test.get("http_results", {}))

    passed = 0
    failed = 0

    for target in targets:
        name = target.get("name", "unknown")
        http_url = target.get("http_url")

        if not http_url:
            deps.logger.debug(f"Skipping HTTP check for {name} (no http_url configured)")
            continue

        expected_status = target.get("expected_status", 200)
        timeout = target.get("timeout", 10.0)

        try:
            # Make HTTP request
            response = deps.http.get(http_url, timeout=timeout)

            is_success = response.status_code == expected_status

            http_results[name] = {
                "url": http_url,
                "success": is_success,
                "status_code": response.status_code,
                "expected_status": expected_status,
                "response_time_ms": response.elapsed.total_seconds() * 1000,
                "error": None,
            }

            if is_success:
                result.add_info(
                    f"HTTP check passed: {http_url} -> {response.status_code} "
                    f"({response.elapsed.total_seconds() * 1000:.0f}ms)",
                    system="smoke-test",
                )
                passed += 1
            else:
                result.add_error(
                    f"HTTP check failed: {http_url} -> {response.status_code} "
                    f"(expected {expected_status})",
                    system="smoke-test",
                )
                failed += 1

        except httpx.TimeoutException as e:
            http_results[name] = {
                "url": http_url,
                "success": False,
                "status_code": None,
                "expected_status": expected_status,
                "response_time_ms": None,
                "error": f"Timeout: {e}",
            }

            result.add_error(
                f"HTTP timeout: {http_url} - {e}",
                system="smoke-test",
            )
            failed += 1

        except httpx.RequestError as e:
            http_results[name] = {
                "url": http_url,
                "success": False,
                "status_code": None,
                "expected_status": expected_status,
                "response_time_ms": None,
                "error": str(e),
            }

            result.add_error(
                f"HTTP request error: {http_url} - {e}",
                system="smoke-test",
            )
            failed += 1

    # Update context
    smoke_test["http_results"] = http_results
    smoke_test["passed_checks"] = smoke_test.get("passed_checks", 0) + passed
    smoke_test["failed_checks"] = smoke_test.get("failed_checks", 0) + failed

    result.context_updates["smoke_test"] = smoke_test

    if failed > 0:
        result.add_warning(
            f"HTTP checks: {passed} passed, {failed} failed",
            system="smoke-test",
        )
    else:
        result.add_info(
            f"HTTP checks: {passed} passed",
            system="smoke-test",
        )

    return result
