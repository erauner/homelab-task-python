"""JSON transformation task for data manipulation between pipeline steps.

Supports:
- Field extraction/mapping
- Filtering arrays
- Adding computed fields
- Merging multiple inputs
"""

from __future__ import annotations

from typing import Any

from homelab_taskkit.deps import Deps
from homelab_taskkit.registry import TaskDef, register_task


def run(inputs: dict[str, Any], deps: Deps) -> dict[str, Any]:
    """Transform JSON data using mappings and expressions.

    Input fields:
        data: The input data to transform (dict or list)
        mappings: Field mappings {output_field: input_path} using dot notation
        filter_expr: Optional filter for arrays (field.operator.value)
        merge_with: Optional additional data to merge
        wrap_key: Optional key to wrap the result in

    Output fields:
        result: The transformed data
        input_type: Type of input (dict/list)
        output_type: Type of output (dict/list)
        field_count: Number of fields in output (if dict)
        item_count: Number of items in output (if list)
    """
    data = inputs["data"]
    mappings = inputs.get("mappings", {})
    filter_expr = inputs.get("filter_expr")
    merge_with = inputs.get("merge_with", {})
    wrap_key = inputs.get("wrap_key")

    deps.logger.info(f"Transforming data (type: {type(data).__name__})")

    result: Any

    # Handle list input with optional filtering
    if isinstance(data, list):
        result = _filter_list(data, filter_expr, deps) if filter_expr else data

        # Apply mappings to each item if provided
        if mappings and result:
            result = [_apply_mappings(item, mappings) for item in result]

    # Handle dict input
    elif isinstance(data, dict):
        result = _apply_mappings(data, mappings) if mappings else data.copy()

        # Merge additional data
        if merge_with:
            result.update(merge_with)
    else:
        result = data

    # Optionally wrap in a key
    if wrap_key:
        result = {wrap_key: result}

    # Build output metadata
    output: dict[str, Any] = {
        "result": result,
        "input_type": type(data).__name__,
        "output_type": type(result).__name__,
    }

    if isinstance(result, dict):
        output["field_count"] = len(result)
    elif isinstance(result, list):
        output["item_count"] = len(result)

    deps.logger.info(f"Transform complete: {output['output_type']}")
    return output


def _apply_mappings(data: dict[str, Any], mappings: dict[str, str]) -> dict[str, Any]:
    """Apply field mappings to a dictionary.

    Mappings use dot notation for nested access:
    {"name": "user.profile.name"} extracts data["user"]["profile"]["name"]
    """
    result = {}
    for output_key, input_path in mappings.items():
        value = _get_nested(data, input_path)
        if value is not None:
            result[output_key] = value
    return result


def _get_nested(data: dict[str, Any], path: str) -> Any:
    """Get a nested value using dot notation."""
    keys = path.split(".")
    value = data
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return None
    return value


def _filter_list(data: list[dict[str, Any]], filter_expr: str, deps: Deps) -> list[dict[str, Any]]:
    """Filter a list using a simple expression.

    Format: field.operator.value
    Operators: eq, ne, gt, lt, gte, lte, contains, startswith, endswith
    """
    try:
        parts = filter_expr.split(".", 2)
        if len(parts) != 3:
            deps.logger.warning(f"Invalid filter expression: {filter_expr}")
            return data

        field, operator, value = parts

        def matches(item: dict[str, Any]) -> bool:
            item_value = item.get(field)
            if item_value is None:
                return False

            # Type coercion for comparison
            if isinstance(item_value, (int, float)):
                try:
                    value_cmp = float(value)
                except ValueError:
                    value_cmp = value
            else:
                value_cmp = value
                item_value = str(item_value)

            if operator == "eq":
                return item_value == value_cmp
            elif operator == "ne":
                return item_value != value_cmp
            elif operator == "gt":
                return item_value > value_cmp
            elif operator == "lt":
                return item_value < value_cmp
            elif operator == "gte":
                return item_value >= value_cmp
            elif operator == "lte":
                return item_value <= value_cmp
            elif operator == "contains":
                return value in str(item_value)
            elif operator == "startswith":
                return str(item_value).startswith(value)
            elif operator == "endswith":
                return str(item_value).endswith(value)
            else:
                deps.logger.warning(f"Unknown operator: {operator}")
                return True

        return [item for item in data if matches(item)]

    except Exception as e:
        deps.logger.warning(f"Filter failed: {e}")
        return data


register_task(
    TaskDef(
        name="json_transform",
        description="Transform and reshape JSON data for pipeline steps",
        input_schema="json_transform/input.json",
        output_schema="json_transform/output.json",
        run=run,
    )
)
