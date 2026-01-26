"""Command-line interface for running tasks."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from homelab_taskkit.registry import list_tasks
from homelab_taskkit.runner import run_task

app = typer.Typer(
    name="task-run",
    help="Run homelab tasks with schema validation.",
    no_args_is_help=True,
)

console = Console()


@app.command("run")
def run_cmd(
    task_name: str = typer.Argument(..., help="Name of the task to run"),
    input_source: str = typer.Option(
        ...,
        "--input",
        "-i",
        help="Path to input JSON file or inline JSON string",
    ),
    output_path: str = typer.Option(
        ...,
        "--output",
        "-o",
        help="Path to write the output JSON",
    ),
    schemas_root: str = typer.Option(
        "schemas",
        "--schemas",
        "-s",
        help="Root directory containing task schemas",
    ),
    context_enabled: bool | None = typer.Option(
        None,
        "--context/--no-context",
        help="Enable/disable context artifacts (default: auto-detect)",
    ),
    context_in: str | None = typer.Option(
        None,
        "--context-in",
        help="Path to input context JSON (default: /inputs/context.json)",
    ),
    context_out: str | None = typer.Option(
        None,
        "--context-out",
        help="Path to output context JSON (default: /outputs/context.json)",
    ),
    max_context_bytes: int = typer.Option(
        32 * 1024,
        "--max-context-bytes",
        help="Maximum context size in bytes (default: 32KB)",
    ),
    messages_enabled: bool | None = typer.Option(
        None,
        "--messages/--no-messages",
        help="Enable/disable messages artifact (default: auto-detect based on /outputs)",
    ),
    messages_out: str | None = typer.Option(
        None,
        "--messages-out",
        help="Path to write messages JSON (default: /outputs/messages.json)",
    ),
    fanout_enabled: bool | None = typer.Option(
        None,
        "--fanout/--no-fanout",
        help="Enable/disable fanout artifact (default: auto-detect based on /outputs)",
    ),
    fanout_out: str | None = typer.Option(
        None,
        "--fanout-out",
        help="Path to write fanout JSON (default: /outputs/fanout.json)",
    ),
) -> None:
    """Run a task with input/output validation and optional artifacts."""
    # Import tasks to populate registry
    import homelab_taskkit.tasks  # noqa: F401

    exit_code = run_task(
        task_name=task_name,
        input_source=input_source,
        output_path=output_path,
        schemas_root=schemas_root,
        context_enabled=context_enabled,
        context_input_path=context_in,
        context_output_path=context_out,
        max_context_bytes=max_context_bytes,
        messages_enabled=messages_enabled,
        messages_output_path=messages_out,
        fanout_enabled=fanout_enabled,
        fanout_output_path=fanout_out,
    )
    raise typer.Exit(code=exit_code)


@app.command("list")
def list_cmd() -> None:
    """List all available tasks."""
    # Import tasks to populate registry
    import homelab_taskkit.tasks  # noqa: F401

    tasks = list_tasks()

    if not tasks:
        console.print("[yellow]No tasks registered.[/yellow]")
        return

    table = Table(title="Available Tasks")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Description", style="green")
    table.add_column("Input Schema", style="dim")
    table.add_column("Output Schema", style="dim")

    for task in tasks:
        table.add_row(
            task.name,
            task.description,
            task.input_schema,
            task.output_schema,
        )

    console.print(table)


@app.command("schema")
def schema_cmd(
    task_name: str = typer.Argument(..., help="Name of the task"),
    schema_type: str = typer.Option(
        "input",
        "--type",
        "-t",
        help="Schema type: 'input' or 'output'",
    ),
    schemas_root: str = typer.Option(
        "schemas",
        "--schemas",
        "-s",
        help="Root directory containing task schemas",
    ),
) -> None:
    """Print the JSON schema for a task."""
    import json

    # Import tasks to populate registry
    import homelab_taskkit.tasks  # noqa: F401
    from homelab_taskkit.registry import TaskNotFoundError, get_task
    from homelab_taskkit.schema import load_schema

    try:
        task = get_task(task_name)
    except TaskNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from None

    schema_path = Path(schemas_root) / (
        task.input_schema if schema_type == "input" else task.output_schema
    )

    try:
        schema = load_schema(schema_path)
        console.print_json(json.dumps(schema, indent=2))
    except FileNotFoundError:
        console.print(f"[red]Error:[/red] Schema not found: {schema_path}")
        raise typer.Exit(code=1) from None


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
