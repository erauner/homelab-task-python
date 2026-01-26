# E2E Testing with kind + Argo Workflows

This directory contains the E2E testing infrastructure for taskkit. It uses
[kind](https://kind.sigs.k8s.io/) to create a local Kubernetes cluster and
[Argo Workflows](https://argoproj.github.io/workflows/) to run actual workflow
executions.

## Quick Start

```bash
# Full E2E cycle (recommended for first run)
make e2e

# Or step by step:
make e2e-up      # Create kind cluster with Argo + httpbin
make e2e-build   # Build taskkit Docker image
make e2e-load    # Load image into kind cluster
make e2e-run     # Run all smoke tests

# Check environment status
make e2e-status

# Cleanup
make e2e-down
```

## Prerequisites

- Docker
- [kind](https://kind.sigs.k8s.io/docs/user/quick-start/#installation)
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [Argo CLI](https://github.com/argoproj/argo-workflows/releases) (for `argo submit/wait/logs`)

### Installing Prerequisites (macOS)

```bash
brew install kind kubectl argoproj/tap/argo
```

## Directory Structure

```
e2e/
├── cluster/
│   ├── kind-config.yaml    # Kind cluster configuration
│   ├── argo-install.yaml   # Argo Workflows RBAC and config
│   └── httpbin.yaml        # In-cluster HTTP testing service
├── workflows/
│   ├── taskkit-base.yaml   # E2E version of the base template
│   ├── smoke-echo.yaml     # Echo task smoke test
│   ├── smoke-http-request.yaml
│   ├── smoke-json-transform.yaml
│   ├── smoke-conditional-check.yaml
│   └── smoke-pipeline.yaml # Multi-step pipeline test
├── scripts/
│   ├── up.sh               # Create cluster and install deps
│   ├── build.sh            # Build Docker image
│   ├── load.sh             # Load image into kind
│   ├── run.sh              # Run smoke tests
│   ├── down.sh             # Delete cluster
│   └── status.sh           # Check environment status
└── README.md
```

## Running Individual Tests

```bash
# Run specific test
make e2e-test-echo
make e2e-test-http-request
make e2e-test-json-transform
make e2e-test-conditional-check
make e2e-test-pipeline

# Or directly
./e2e/scripts/run.sh echo
./e2e/scripts/run.sh pipeline
```

## What Gets Tested

### smoke-echo
- Basic input/output flow
- Schema validation (message, metadata, timestamp)
- Pass-through of metadata

### smoke-http-request
- GET requests against httpbin
- POST requests with JSON body
- Status code and success field validation
- Elapsed time tracking

### smoke-json-transform
- Field mappings with dot notation
- Merge with additional data
- Type detection (dict/list)

### smoke-conditional-check
- Equality operators (eq, ne)
- Comparison operators (gt, lt, gte, lte)
- String operators (contains, startswith, endswith)

### smoke-pipeline
- Multi-step DAG execution
- Parameter passing between steps
- Task dependencies
- Chaining: http_request → json_transform → conditional_check → echo

## Why httpbin?

The `http_request` task needs a reliable HTTP endpoint for testing. Using
public APIs (like jsonplaceholder) introduces flakiness. Instead, we deploy
[httpbin](https://httpbin.org/) inside the kind cluster:

- Predictable responses
- No network dependencies
- Fast (in-cluster traffic)
- Supports all HTTP methods and response types

The httpbin service is available at:
```
http://httpbin.httpbin.svc.cluster.local/
```

## Debugging Failed Tests

```bash
# Check recent workflow runs
kubectl get workflows -n argo-workflows

# Get workflow details
argo get <workflow-name> -n argo-workflows

# View logs
argo logs <workflow-name> -n argo-workflows

# Check pod status
kubectl get pods -n argo-workflows

# Describe a failed pod
kubectl describe pod <pod-name> -n argo-workflows
```

## Relationship to Production Templates

**Important:** These E2E workflows are a **test harness**, not the production
source of truth.

- Production `WorkflowTemplates` live in `homelab-k8s`
- E2E `Workflows` here validate the taskkit image works correctly
- The E2E `taskkit-base.yaml` uses `imagePullPolicy: Never` with a local image

If you change task behavior, run E2E tests before updating production templates:

```bash
# 1. Make code changes
vim src/homelab_taskkit/tasks/my_task/step.py

# 2. Run unit tests
make test

# 3. Run E2E tests (rebuild image automatically)
make e2e-build e2e-load e2e-run

# 4. If all pass, update production templates in homelab-k8s
```

## Troubleshooting

### Image not found in cluster

```bash
# Rebuild and reload
make e2e-build e2e-load
```

### Argo not ready

```bash
# Check status
make e2e-status

# Wait for pods
kubectl wait --for=condition=ready pod -l app=workflow-controller -n argo-workflows
```

### httpbin not responding

```bash
# Check httpbin is running
kubectl get pods -n httpbin

# Test connectivity
kubectl run test --rm -it --image=alpine --restart=Never -- \
    wget -qO- http://httpbin.httpbin.svc.cluster.local/get
```

### Workflow stuck in Pending

```bash
# Check for scheduling issues
kubectl describe pod <pod-name> -n argo-workflows

# Common causes:
# - Image not loaded (make e2e-load)
# - Resource limits too high
# - Node not ready
```
