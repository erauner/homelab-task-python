# homelab-task-python

Python task implementations for Argo Workflows. This repository provides a functional-first
task toolkit that integrates with the homelab automation platform.

## Quick Start

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# List available tasks
uv run task-run list

# Run a task
uv run task-run run echo --input '{"message": "hello"}' --output /tmp/result.json
```

## Docker Usage

```bash
# Pull from Nexus
docker pull docker.nexus.erauner.dev/homelab/taskkit:latest

# Run a task
docker run docker.nexus.erauner.dev/homelab/taskkit:latest \
    run echo --input '{"message": "test"}' --output /dev/stdout
```

## Architecture

Tasks are pure functions with JSON Schema-validated inputs/outputs:

```python
def run(inputs: dict[str, Any], deps: Deps) -> dict[str, Any]:
    """Process inputs, return outputs."""
    return {"result": inputs["message"]}
```

Dependencies are injected (not imported globally), making tasks testable.

See [CLAUDE.md](CLAUDE.md) for development guidelines.

## Available Tasks

| Task | Description |
|------|-------------|
| `echo` | Pass-through for testing - echoes message with timestamp |
| `http_request` | Make HTTP requests to external services |

## Related Repositories

- [homelab-tasks](https://github.com/erauner/homelab-tasks) - Go API for task orchestration
- [homelab-k8s](https://github.com/erauner/homelab-k8s) - Platform with WorkflowTemplates
