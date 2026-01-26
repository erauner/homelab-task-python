"""Contract tests for task definitions.

These tests verify structural invariants that all tasks must maintain,
ensuring the codebase stays consistent as new tasks are added.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Import tasks module to trigger registration
import homelab_taskkit.tasks  # noqa: F401
from homelab_taskkit.registry import list_tasks

# Root of the project
PROJECT_ROOT = Path(__file__).parent.parent
SCHEMAS_ROOT = PROJECT_ROOT / "schemas"


class TestSchemaContracts:
    """Verify all registered tasks have valid schema files."""

    @pytest.fixture
    def all_tasks(self):
        """Get all registered tasks."""
        return list_tasks()

    def test_all_tasks_have_schemas(self, all_tasks):
        """Every registered task must have input and output schema files."""
        missing = []

        for task in all_tasks:
            input_path = SCHEMAS_ROOT / task.input_schema
            output_path = SCHEMAS_ROOT / task.output_schema

            if not input_path.exists():
                missing.append(f"{task.name}: input schema missing at {input_path}")
            if not output_path.exists():
                missing.append(f"{task.name}: output schema missing at {output_path}")

        if missing:
            pytest.fail(
                "Missing schema files for registered tasks:\n"
                + "\n".join(f"  - {m}" for m in missing)
            )

    def test_schemas_are_valid_json(self, all_tasks):
        """All schema files must contain valid JSON."""
        invalid = []

        for task in all_tasks:
            input_path = SCHEMAS_ROOT / task.input_schema
            output_path = SCHEMAS_ROOT / task.output_schema

            for path, name in [(input_path, "input"), (output_path, "output")]:
                if path.exists():
                    try:
                        with open(path) as f:
                            json.load(f)
                    except json.JSONDecodeError as e:
                        invalid.append(f"{task.name} {name} schema: {e}")

        if invalid:
            pytest.fail("Invalid JSON in schema files:\n" + "\n".join(f"  - {i}" for i in invalid))

    def test_schemas_have_required_fields(self, all_tasks):
        """All schemas should have type and properties (for objects)."""
        incomplete = []

        for task in all_tasks:
            input_path = SCHEMAS_ROOT / task.input_schema
            output_path = SCHEMAS_ROOT / task.output_schema

            for path, name in [(input_path, "input"), (output_path, "output")]:
                if path.exists():
                    try:
                        with open(path) as f:
                            schema = json.load(f)

                        # Schemas should have $schema declaration
                        if "$schema" not in schema:
                            incomplete.append(f"{task.name} {name}: missing $schema declaration")

                        # Object schemas should have type and properties
                        if schema.get("type") == "object" and "properties" not in schema:
                            incomplete.append(
                                f"{task.name} {name}: object schema missing properties"
                            )

                    except json.JSONDecodeError:
                        pass  # Already caught by test_schemas_are_valid_json

        if incomplete:
            pytest.fail("Incomplete schemas:\n" + "\n".join(f"  - {i}" for i in incomplete))

    def test_at_least_one_task_registered(self, all_tasks):
        """Sanity check: at least one task should be registered."""
        assert len(all_tasks) > 0, "No tasks registered - check tasks/__init__.py imports"

    def test_task_names_match_schema_paths(self, all_tasks):
        """Task input/output schema paths should use task name as directory."""
        mismatched = []

        for task in all_tasks:
            # Schema paths should be like "task_name/input.json"
            expected_input = f"{task.name}/input.json"
            expected_output = f"{task.name}/output.json"

            if task.input_schema != expected_input:
                mismatched.append(
                    f"{task.name}: input_schema is '{task.input_schema}', expected '{expected_input}'"
                )
            if task.output_schema != expected_output:
                mismatched.append(
                    f"{task.name}: output_schema is '{task.output_schema}', expected '{expected_output}'"
                )

        if mismatched:
            pytest.fail(
                "Schema path conventions violated:\n" + "\n".join(f"  - {m}" for m in mismatched)
            )


class TestTaskContracts:
    """Verify all task definitions meet required contracts."""

    @pytest.fixture
    def all_tasks(self):
        """Get all registered tasks."""
        return list_tasks()

    def test_all_tasks_have_descriptions(self, all_tasks):
        """Every task must have a non-empty description."""
        missing = [task.name for task in all_tasks if not task.description.strip()]

        if missing:
            pytest.fail(f"Tasks missing descriptions: {', '.join(missing)}")

    def test_task_names_are_snake_case(self, all_tasks):
        """Task names should use snake_case convention."""
        import re

        pattern = re.compile(r"^[a-z][a-z0-9_]*$")
        invalid = [task.name for task in all_tasks if not pattern.match(task.name)]

        if invalid:
            pytest.fail(f"Task names not in snake_case: {', '.join(invalid)}")

    def test_task_functions_are_callable(self, all_tasks):
        """All task run functions must be callable."""
        not_callable = [task.name for task in all_tasks if not callable(task.run)]

        if not_callable:
            pytest.fail(f"Tasks with non-callable run functions: {', '.join(not_callable)}")
