"""Conditional check task for pipeline branching logic.

Supports:
- Single condition checks
- Multiple conditions with AND logic (all_conditions)
- Multiple conditions with OR logic (any_conditions)
- Various comparison operators

Note: If both all_conditions and any_conditions are provided,
all_conditions takes precedence (AND logic).
"""

from __future__ import annotations

import re
from typing import Any

from homelab_taskkit.deps import Deps
from homelab_taskkit.registry import TaskDef, register_task


def run(inputs: dict[str, Any], deps: Deps) -> dict[str, Any]:
    """Evaluate conditions for pipeline branching.

    Input fields:
        value: The value to check (for single condition)
        operator: Comparison operator (for single condition)
        compare_to: Value to compare against (for single condition)
        all_conditions: List of conditions that must ALL be true (AND)
        any_conditions: List of conditions where ANY can be true (OR)

    Output fields:
        result: Whether the condition(s) evaluated to true
        checks_performed: Number of individual checks performed
        checks_passed: Number of checks that passed
        details: Details of each check performed
        timestamp: When check was performed

    Precedence: all_conditions > any_conditions > single condition
    """
    # Collect all conditions to evaluate
    conditions_to_check: list[tuple[dict[str, Any], str]] = []  # (condition, source)

    # Single condition
    if "value" in inputs and "operator" in inputs:
        conditions_to_check.append(
            (
                {
                    "value": inputs["value"],
                    "operator": inputs["operator"],
                    "compare_to": inputs.get("compare_to"),
                },
                "single",
            )
        )

    # Multiple conditions
    for cond in inputs.get("all_conditions", []):
        conditions_to_check.append((cond, "all"))

    for cond in inputs.get("any_conditions", []):
        conditions_to_check.append((cond, "any"))

    # Evaluate each condition ONCE and store results
    details: list[dict[str, Any]] = []
    all_results: list[bool] = []  # Results for all_conditions
    any_results: list[bool] = []  # Results for any_conditions
    single_result: bool | None = None

    for cond, source in conditions_to_check:
        passed = _evaluate_condition(
            cond["value"],
            cond["operator"],
            cond.get("compare_to"),
            deps,
        )
        details.append(
            {
                "operator": cond["operator"],
                "passed": passed,
                "value_type": type(cond["value"]).__name__,
                "source": source,
            }
        )
        if source == "all":
            all_results.append(passed)
        elif source == "any":
            any_results.append(passed)
        else:
            single_result = passed

    # Determine overall result from stored values (no re-evaluation!)
    checks_performed = len(details)
    checks_passed = sum(1 for d in details if d["passed"])

    if checks_performed == 0:
        result = True
        deps.logger.warning("No conditions specified, defaulting to true")
    elif all_results:
        # AND logic takes precedence - all must pass
        result = all(all_results)
        deps.logger.info(f"AND conditions: {sum(all_results)}/{len(all_results)} passed")
    elif any_results:
        # OR logic - any can pass
        result = any(any_results)
        deps.logger.info(f"OR conditions: {sum(any_results)}/{len(any_results)} passed")
    else:
        # Single condition
        result = single_result if single_result is not None else True

    # Use injected time for testability
    timestamp = deps.now().isoformat()

    deps.logger.info(
        f"Conditional check result: {result} ({checks_passed}/{checks_performed} passed)"
    )

    return {
        "result": result,
        "checks_performed": checks_performed,
        "checks_passed": checks_passed,
        "details": details,
        "timestamp": timestamp,
    }


def _evaluate_condition(value: Any, operator: str, compare_to: Any, deps: Deps) -> bool:
    """Evaluate a single condition."""
    try:
        if operator == "eq":
            return value == compare_to
        elif operator == "ne":
            return value != compare_to
        elif operator == "gt":
            return value > compare_to
        elif operator == "lt":
            return value < compare_to
        elif operator == "gte":
            return value >= compare_to
        elif operator == "lte":
            return value <= compare_to
        elif operator == "contains":
            return compare_to in str(value)
        elif operator == "startswith":
            return str(value).startswith(str(compare_to))
        elif operator == "endswith":
            return str(value).endswith(str(compare_to))
        elif operator == "matches":
            return bool(re.search(str(compare_to), str(value)))
        elif operator == "exists":
            return value is not None
        elif operator == "empty":
            if value is None:
                return True
            if isinstance(value, (str, list, dict)):
                return len(value) == 0
            return False
        elif operator == "truthy":
            return bool(value)
        else:
            deps.logger.warning(f"Unknown operator: {operator}")
            return False
    except Exception as e:
        deps.logger.warning(f"Condition evaluation failed: {e}")
        return False


register_task(
    TaskDef(
        name="conditional_check",
        description="Evaluate conditions for pipeline branching",
        input_schema="conditional_check/input.json",
        output_schema="conditional_check/output.json",
        run=run,
    )
)
