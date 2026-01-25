"""Conditional check task for pipeline branching logic.

Supports:
- Single condition checks
- Multiple conditions with AND logic (all_conditions)
- Multiple conditions with OR logic (any_conditions)
- Various comparison operators
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
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
    """
    details: list[dict[str, Any]] = []
    checks_passed = 0

    # Handle single condition
    if "value" in inputs and "operator" in inputs:
        passed = _evaluate_condition(
            inputs["value"],
            inputs["operator"],
            inputs.get("compare_to"),
            deps,
        )
        details.append(
            {
                "operator": inputs["operator"],
                "passed": passed,
                "value_type": type(inputs["value"]).__name__,
            }
        )
        if passed:
            checks_passed += 1

    # Handle all_conditions (AND logic)
    all_conditions = inputs.get("all_conditions", [])
    for cond in all_conditions:
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
            }
        )
        if passed:
            checks_passed += 1

    # Handle any_conditions (OR logic)
    any_conditions = inputs.get("any_conditions", [])
    for cond in any_conditions:
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
            }
        )
        if passed:
            checks_passed += 1

    # Determine overall result
    checks_performed = len(details)

    if checks_performed == 0:
        # No conditions specified
        result = True
        deps.logger.warning("No conditions specified, defaulting to true")
    elif all_conditions:
        # AND logic - all must pass
        all_cond_results = [
            _evaluate_condition(c["value"], c["operator"], c.get("compare_to"), deps)
            for c in all_conditions
        ]
        result = all(all_cond_results) if all_cond_results else True
        deps.logger.info(f"AND conditions: {sum(all_cond_results)}/{len(all_cond_results)} passed")
    elif any_conditions:
        # OR logic - any can pass
        any_cond_results = [
            _evaluate_condition(c["value"], c["operator"], c.get("compare_to"), deps)
            for c in any_conditions
        ]
        result = any(any_cond_results) if any_cond_results else True
        deps.logger.info(f"OR conditions: {sum(any_cond_results)}/{len(any_cond_results)} passed")
    else:
        # Single condition
        result = details[0]["passed"] if details else True

    timestamp = datetime.now(UTC).isoformat()

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
