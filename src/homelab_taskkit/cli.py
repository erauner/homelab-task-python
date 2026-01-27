"""Command-line interface for running tasks."""

from __future__ import annotations

import logging
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

workflow_app = typer.Typer(
    name="workflow",
    help="Workflow execution commands.",
    no_args_is_help=True,
)
app.add_typer(workflow_app, name="workflow")

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


@workflow_app.command("run")
def workflow_run_cmd(
    workflow_path: str = typer.Option(
        ...,
        "--workflow",
        "-w",
        help="Path to workflow YAML file",
    ),
    params_path: str | None = typer.Option(
        None,
        "--params",
        "-p",
        help="Path to params JSON file",
    ),
    workdir: str | None = typer.Option(
        None,
        "--workdir",
        help="Working directory for execution (default: auto-generated)",
    ),
    task_id: str | None = typer.Option(
        None,
        "--task-id",
        help="Task ID for the run (default: auto-generated)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging",
    ),
) -> None:
    """Run a workflow locally for testing.

    Example:
        task-run workflow run -w workflows/smoke_test.yaml -p params.json --workdir ./test-run
    """
    # Import step handlers to populate registry
    import homelab_taskkit.tasks  # noqa: F401

    # Also import any workflow steps
    try:
        import homelab_taskkit.steps  # noqa: F401
    except ImportError:
        pass  # steps package not yet created

    # Configure logging
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    from homelab_taskkit.workflow import LocalRunner

    try:
        runner = LocalRunner(
            workflow_path=workflow_path,
            params_path=params_path,
            workdir=workdir,
            task_id=task_id,
        )

        console.print(f"[cyan]Workflow:[/cyan] {runner.workflow.name}")
        console.print(f"[cyan]Task ID:[/cyan] {runner.task_id}")
        console.print(f"[cyan]Workdir:[/cyan] {runner.workdir}")
        console.print()

        result = runner.run()

        if result == "Succeeded":
            console.print(f"\n[green]✓ Workflow {result}[/green]")
            raise typer.Exit(code=0)
        elif result == "Failed":
            console.print(f"\n[red]✗ Workflow {result}[/red]")
            raise typer.Exit(code=1)
        else:
            console.print(f"\n[red]✗ Workflow {result}[/red]")
            raise typer.Exit(code=2)

    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from None
    except ValueError as e:
        console.print(f"[red]Validation Error:[/red] {e}")
        raise typer.Exit(code=1) from None


@workflow_app.command("validate")
def workflow_validate_cmd(
    workflow_path: str = typer.Option(
        ...,
        "--workflow",
        "-w",
        help="Path to workflow YAML file",
    ),
) -> None:
    """Validate a workflow definition without executing it.

    Checks:
    - YAML syntax
    - All handlers are registered
    - Dependencies are valid
    - No circular dependencies
    """
    # Import step handlers to populate registry
    import homelab_taskkit.tasks  # noqa: F401

    try:
        import homelab_taskkit.steps  # noqa: F401
    except ImportError:
        pass

    from homelab_taskkit.workflow import LocalRunner

    try:
        runner = LocalRunner(
            workflow_path=workflow_path,
            params_path=None,
            workdir=None,
        )

        errors = runner.validate()

        if errors:
            console.print("[red]Validation failed:[/red]")
            for error in errors:
                console.print(f"  • {error}")
            raise typer.Exit(code=1)
        else:
            console.print(f"[green]✓ Workflow '{runner.workflow.name}' is valid[/green]")
            raise typer.Exit(code=0)

    except FileNotFoundError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from None
    except ValueError as e:
        console.print(f"[red]Validation Error:[/red] {e}")
        raise typer.Exit(code=1) from None


@workflow_app.command("list-steps")
def workflow_list_steps_cmd() -> None:
    """List all registered step handlers."""
    # Import step handlers to populate registry
    import homelab_taskkit.tasks  # noqa: F401

    try:
        import homelab_taskkit.steps  # noqa: F401
    except ImportError:
        pass

    from homelab_taskkit.workflow import list_steps

    steps = list_steps()

    if not steps:
        console.print("[yellow]No step handlers registered.[/yellow]")
        return

    table = Table(title="Registered Step Handlers")
    table.add_column("Handler Name", style="cyan", no_wrap=True)

    for step_name in steps:
        table.add_row(step_name)

    console.print(table)


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
