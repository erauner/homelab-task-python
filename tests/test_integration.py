"""Integration tests for the full task runner workflow."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Import tasks to register them before running tests
import homelab_taskkit.tasks  # noqa: F401
from homelab_taskkit.runner import (
    EXIT_SUCCESS,
    EXIT_TASK_NOT_FOUND,
    EXIT_VALIDATION_ERROR,
    run_task,
)


class TestRunnerIntegration:
    """End-to-end tests for the task runner."""

    @pytest.fixture
    def schemas_root(self) -> Path:
        """Return path to schemas directory."""
        return Path(__file__).parent.parent / "schemas"

    def test_echo_task_full_workflow(self, tmp_path: Path, schemas_root: Path):
        """Test complete echo task: input → validate → run → validate → output."""
        # Arrange
        input_file = tmp_path / "input.json"
        output_file = tmp_path / "output.json"
        input_data = {"message": "Integration test message", "metadata": {"test": True}}
        input_file.write_text(json.dumps(input_data))

        # Act
        exit_code = run_task(
            task_name="echo",
            input_source=str(input_file),
            output_path=str(output_file),
            schemas_root=str(schemas_root),
        )

        # Assert
        assert exit_code == EXIT_SUCCESS
        assert output_file.exists()

        output_data = json.loads(output_file.read_text())
        assert output_data["echoed_message"] == "Integration test message"
        assert output_data["metadata"] == {"test": True}
        assert "timestamp" in output_data

    def test_echo_task_inline_json_input(self, tmp_path: Path, schemas_root: Path):
        """Test echo task with inline JSON string as input."""
        output_file = tmp_path / "output.json"

        exit_code = run_task(
            task_name="echo",
            input_source='{"message": "inline test"}',
            output_path=str(output_file),
            schemas_root=str(schemas_root),
        )

        assert exit_code == EXIT_SUCCESS
        output_data = json.loads(output_file.read_text())
        assert output_data["echoed_message"] == "inline test"

    def test_invalid_input_fails_validation(self, tmp_path: Path, schemas_root: Path):
        """Test that invalid input is rejected before task execution."""
        input_file = tmp_path / "input.json"
        output_file = tmp_path / "output.json"
        # Missing required 'message' field
        input_file.write_text('{"wrong_field": "value"}')

        exit_code = run_task(
            task_name="echo",
            input_source=str(input_file),
            output_path=str(output_file),
            schemas_root=str(schemas_root),
        )

        assert exit_code == EXIT_VALIDATION_ERROR
        assert not output_file.exists()

    def test_unknown_task_returns_not_found(self, tmp_path: Path, schemas_root: Path):
        """Test that unknown task name returns appropriate exit code."""
        output_file = tmp_path / "output.json"

        exit_code = run_task(
            task_name="nonexistent_task",
            input_source='{"message": "test"}',
            output_path=str(output_file),
            schemas_root=str(schemas_root),
        )

        assert exit_code == EXIT_TASK_NOT_FOUND

    def test_output_directory_created_automatically(self, tmp_path: Path, schemas_root: Path):
        """Test that nested output directories are created."""
        output_file = tmp_path / "nested" / "deep" / "output.json"

        exit_code = run_task(
            task_name="echo",
            input_source='{"message": "nested test"}',
            output_path=str(output_file),
            schemas_root=str(schemas_root),
        )

        assert exit_code == EXIT_SUCCESS
        assert output_file.exists()


class TestCLIIntegration:
    """Integration tests for CLI commands."""

    def test_cli_list_shows_tasks(self, capsys):
        """Test that CLI list command shows registered tasks."""
        from typer.testing import CliRunner

        from homelab_taskkit.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "echo" in result.stdout
        assert "http_request" in result.stdout

    def test_cli_run_echo_task(self, tmp_path: Path):
        """Test running echo task via CLI."""
        from typer.testing import CliRunner

        from homelab_taskkit.cli import app

        input_file = tmp_path / "input.json"
        output_file = tmp_path / "output.json"
        input_file.write_text('{"message": "CLI test"}')

        runner = CliRunner()
        result = runner.invoke(
            app,
            [
                "run",
                "echo",
                "--input",
                str(input_file),
                "--output",
                str(output_file),
                "--schemas",
                str(Path(__file__).parent.parent / "schemas"),
            ],
        )

        assert result.exit_code == 0
        assert output_file.exists()
        output_data = json.loads(output_file.read_text())
        assert output_data["echoed_message"] == "CLI test"
