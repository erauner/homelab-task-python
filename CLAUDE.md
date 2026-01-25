# CLAUDE.md - Development Guidelines for homelab-task-python

## Project Overview

This repository contains Python task implementations for Argo Workflows. Tasks are
pure functions with JSON Schema-validated inputs and outputs, designed for testability
and composability in GitOps-driven automation.

**Related Repositories:**
- `homelab-tasks` - Go API managing task runs (orchestration)
- `homelab-k8s` - WorkflowTemplates consuming this image
- `homelab-jenkins-library` - Shared Jenkins CI/CD library

## Architecture Principles

### Functional-First Design

Tasks are **pure functions**, not classes:

```python
# ✅ Correct - function with explicit dependencies
def run(inputs: dict[str, Any], deps: Deps) -> dict[str, Any]:
    response = deps.http.get(inputs["url"])
    return {"status": response.status_code}

# ❌ Wrong - class with inherited behavior
class MyTask(BaseTask):
    def execute(self):
        response = requests.get(self.url)  # Global import
```

### Dependency Injection

All external dependencies come through the `Deps` container:

```python
@dataclass(frozen=True)
class Deps:
    http: httpx.Client       # HTTP client (injectable for testing)
    now: Callable[[], datetime]  # Time function (injectable for testing)
    env: Mapping[str, str]   # Environment variables
    logger: logging.Logger   # Structured logging
```

**Why?** Makes testing trivial - inject fake deps with controlled behavior.

### JSON Schema Contracts

Every task has explicit input/output schemas:

```
schemas/
├── echo/
│   ├── input.json    # What the task accepts
│   └── output.json   # What the task returns
└── http_request/
    ├── input.json
    └── output.json
```

Validation happens automatically in the runner. Tasks never see invalid data.

## Directory Structure

```
homelab-task-python/
├── src/homelab_taskkit/
│   ├── __init__.py        # Package exports
│   ├── cli.py             # CLI entrypoint (task-run command)
│   ├── runner.py          # Orchestration (validate → execute → validate)
│   ├── registry.py        # Task registration (no inheritance)
│   ├── deps.py            # Dependency injection container
│   ├── schema.py          # JSON Schema validation
│   ├── io.py              # Input/output handling
│   └── tasks/
│       ├── __init__.py    # Imports all tasks to register them
│       ├── echo.py        # Example: pass-through task
│       └── http_request.py # Example: HTTP client task
├── schemas/               # JSON Schema definitions
│   ├── echo/
│   └── http_request/
├── tests/                 # Unit and contract tests
├── Dockerfile             # Single image for all tasks
├── Jenkinsfile            # CI/CD pipeline
└── pyproject.toml         # uv/pip config
```

## Adding a New Task

### 1. Create the Task Function

```python
# src/homelab_taskkit/tasks/my_task.py
from homelab_taskkit.deps import Deps
from homelab_taskkit.registry import TaskDef, register_task

def run(inputs: dict[str, Any], deps: Deps) -> dict[str, Any]:
    """Do something with inputs, return outputs."""
    # Use deps.http for HTTP requests
    # Use deps.now() for current time
    # Use deps.logger for logging
    # Use deps.env for environment variables

    return {"result": "..."}

# Register at module load time
register_task(TaskDef(
    name="my_task",
    description="Short description for CLI listing",
    input_schema="my_task/input.json",
    output_schema="my_task/output.json",
    run=run,
))
```

### 2. Create JSON Schemas

```json
// schemas/my_task/input.json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "required_field": { "type": "string" },
    "optional_field": { "type": "integer", "default": 10 }
  },
  "required": ["required_field"]
}
```

### 3. Register the Task

```python
# src/homelab_taskkit/tasks/__init__.py
from homelab_taskkit.tasks import echo, http_request, my_task  # Add import
```

### 4. Write Tests

```python
# tests/tasks/test_my_task.py
from homelab_taskkit.tasks.my_task import run
from tests.conftest import fake_deps

def test_my_task_success():
    deps = fake_deps()
    result = run({"required_field": "test"}, deps)
    assert "result" in result
```

## CLI Usage

```bash
# Run a task
task-run run echo --input '{"message": "hello"}' --output /tmp/out.json

# List available tasks
task-run list

# Show task schema
task-run schema echo --type input
task-run schema echo --type output
```

## Testing Guidelines

### Unit Tests
Test task functions in isolation with fake deps:

```python
def test_http_request_success(fake_deps, httpx_mock):
    httpx_mock.add_response(json={"data": "test"})
    result = run({"url": "https://api.example.com"}, fake_deps)
    assert result["success"] is True
```

### Contract Tests
Verify schemas match actual task behavior:

```python
def test_echo_output_matches_schema():
    result = run({"message": "test"}, fake_deps())
    validate(result, load_schema("schemas/echo/output.json"))
```

### Integration Tests
Test full runner flow with real schemas:

```python
def test_runner_echo_task(tmp_path):
    exit_code = run_task("echo", '{"message": "test"}', str(tmp_path / "out.json"))
    assert exit_code == 0
```

## Development Workflow

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install deps
uv sync

# Run tests
uv run pytest

# Run linter
uv run ruff check src/ tests/

# Format code
uv run ruff format src/ tests/

# Build package
uv build

# Test CLI locally
uv run task-run list
```

## Docker Usage

```bash
# Build image locally
docker build -t taskkit:local .

# Run a task
docker run taskkit:local run echo --input '{"message": "test"}' --output /dev/stdout

# In Argo Workflow
containers:
- name: task
  image: docker.nexus.erauner.dev/homelab/taskkit:latest
  command: ["task-run", "run", "echo"]
  args: ["--input", "/inputs/data.json", "--output", "/outputs/result.json"]
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Runtime error (task execution failed) |
| 2 | Validation error (schema violation) |
| 3 | Task not found |

## Anti-Patterns to Avoid

1. **Global imports for external services**
   ```python
   # ❌ Wrong
   import requests
   def run(inputs, deps):
       requests.get(...)  # Untestable

   # ✅ Correct
   def run(inputs, deps):
       deps.http.get(...)  # Injected, testable
   ```

2. **Class inheritance for task definition**
   ```python
   # ❌ Wrong
   class MyTask(BaseTask):
       pass

   # ✅ Correct
   def run(inputs, deps): ...
   register_task(TaskDef(name="my_task", run=run, ...))
   ```

3. **Side effects outside the run function**
   ```python
   # ❌ Wrong - module-level side effect
   API_TOKEN = os.environ["TOKEN"]

   # ✅ Correct - access via deps
   def run(inputs, deps):
       token = deps.env.get("TOKEN")
   ```

4. **Unvalidated inputs/outputs**
   ```python
   # ❌ Wrong - no schema
   def run(inputs, deps):
       return {"whatever": inputs.get("stuff")}

   # ✅ Correct - schema validates structure
   # schemas/my_task/input.json defines required fields
   # schemas/my_task/output.json defines return structure
   ```

## Relationship to Argo Workflows

This image runs as a **container step** in Argo Workflows:

```yaml
# In homelab-k8s WorkflowTemplate
apiVersion: argoproj.io/v1alpha1
kind: WorkflowTemplate
metadata:
  name: http-health-check
spec:
  templates:
  - name: check-endpoint
    inputs:
      parameters:
      - name: url
    container:
      image: docker.nexus.erauner.dev/homelab/taskkit:v0.1.0
      command: ["task-run", "run", "http_request"]
      args:
        - "--input"
        - '{"url": "{{inputs.parameters.url}}"}'
        - "--output"
        - "/outputs/result.json"
```

The `homelab-tasks` Go API orchestrates these workflows, tracking runs and steps.
