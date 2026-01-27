"""Smoke test DNS check step handler.

Checks DNS resolution for configured targets.
"""

from __future__ import annotations

import socket

from homelab_taskkit.workflow import (
    StepDeps,
    StepInput,
    StepResult,
    register_step,
)


@register_step("smoke-test-check-dns")
def handle_check_dns(step_input: StepInput, deps: StepDeps) -> StepResult:
    """Check DNS resolution for targets with dns_host configured.

    Updates context with DNS results for each target.
    """
    result = StepResult()

    targets = step_input.params.get("targets", [])
    smoke_test = dict(step_input.vars.get("smoke_test", {}))
    dns_results = dict(smoke_test.get("dns_results", {}))

    passed = 0
    failed = 0

    for target in targets:
        name = target.get("name", "unknown")
        dns_host = target.get("dns_host")

        if not dns_host:
            deps.logger.debug(f"Skipping DNS check for {name} (no dns_host configured)")
            continue

        try:
            # Attempt DNS resolution
            ip_addresses = socket.gethostbyname_ex(dns_host)[2]

            dns_results[name] = {
                "host": dns_host,
                "resolved": True,
                "addresses": ip_addresses,
                "error": None,
            }

            result.add_info(
                f"DNS resolved: {dns_host} -> {', '.join(ip_addresses)}",
                system="smoke-test",
            )
            passed += 1

        except socket.gaierror as e:
            dns_results[name] = {
                "host": dns_host,
                "resolved": False,
                "addresses": [],
                "error": str(e),
            }

            result.add_error(
                f"DNS resolution failed: {dns_host} - {e}",
                system="smoke-test",
            )
            failed += 1

    # Update context
    smoke_test["dns_results"] = dns_results
    smoke_test["passed_checks"] = smoke_test.get("passed_checks", 0) + passed
    smoke_test["failed_checks"] = smoke_test.get("failed_checks", 0) + failed

    result.context_updates["smoke_test"] = smoke_test

    if failed > 0:
        result.add_warning(
            f"DNS checks: {passed} passed, {failed} failed",
            system="smoke-test",
        )
    else:
        result.add_info(
            f"DNS checks: {passed} passed",
            system="smoke-test",
        )

    return result
