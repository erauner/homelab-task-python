#!/usr/bin/env bash
# Run E2E smoke tests
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
E2E_DIR="$(dirname "$SCRIPT_DIR")"
CLUSTER_NAME="taskkit-e2e"

# Which tests to run (default: all)
TESTS="${1:-all}"

echo "=== Running E2E smoke tests ==="
echo "Cluster: $CLUSTER_NAME"
echo "Tests: $TESTS"
echo ""

# Check if cluster exists
if ! kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    echo "Error: Cluster '$CLUSTER_NAME' not found."
    echo "Run 'make e2e-up' first."
    exit 1
fi

# Ensure we're using the right context
kubectl config use-context "kind-$CLUSTER_NAME" >/dev/null 2>&1 || true

# Function to run a workflow and wait for completion
run_workflow() {
    local workflow_file="$1"
    local workflow_name=$(basename "$workflow_file" .yaml)
    
    echo ""
    echo "----------------------------------------"
    echo "Running: $workflow_name"
    echo "----------------------------------------"
    
    # Submit workflow and capture the name (filter out warnings)
    WORKFLOW_NAME=$(argo submit "$workflow_file" -n argo-workflows -o name 2>/dev/null | grep -v "^time=" | tail -1)
    
    if [[ -z "$WORKFLOW_NAME" ]]; then
        echo "Error: Failed to submit workflow"
        return 1
    fi
    
    echo "Submitted: $WORKFLOW_NAME"
    
    # Wait for completion (poll-based since --timeout may not exist)
    local timeout=300
    local elapsed=0
    local interval=5
    
    while [[ $elapsed -lt $timeout ]]; do
        STATUS=$(argo get "$WORKFLOW_NAME" -n argo-workflows -o json 2>/dev/null | grep -o '"phase": *"[^"]*"' | head -1 | sed 's/.*"\([^"]*\)"$/\1/')
        
        if [[ "$STATUS" == "Succeeded" ]]; then
            echo "✓ $workflow_name PASSED"
            return 0
        elif [[ "$STATUS" == "Failed" || "$STATUS" == "Error" ]]; then
            echo "✗ $workflow_name FAILED (status: $STATUS)"
            argo logs "$WORKFLOW_NAME" -n argo-workflows 2>/dev/null || true
            return 1
        fi
        
        sleep $interval
        elapsed=$((elapsed + interval))
        echo "  Waiting... ($elapsed/${timeout}s) status=$STATUS"
    done
    
    echo "✗ $workflow_name TIMED OUT"
    argo logs "$WORKFLOW_NAME" -n argo-workflows 2>/dev/null || true
    return 1
}

# Track results
PASSED=0
FAILED=0
FAILED_TESTS=""

# Run tests based on selection
run_test() {
    local test_file="$1"
    if run_workflow "$test_file"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
        FAILED_TESTS="$FAILED_TESTS $(basename "$test_file" .yaml)"
    fi
}

case "$TESTS" in
    all)
        run_test "$E2E_DIR/workflows/smoke-echo.yaml"
        run_test "$E2E_DIR/workflows/smoke-http-request.yaml"
        run_test "$E2E_DIR/workflows/smoke-json-transform.yaml"
        run_test "$E2E_DIR/workflows/smoke-conditional-check.yaml"
        run_test "$E2E_DIR/workflows/smoke-pipeline.yaml"
        ;;
    echo)
        run_test "$E2E_DIR/workflows/smoke-echo.yaml"
        ;;
    http|http-request|http_request)
        run_test "$E2E_DIR/workflows/smoke-http-request.yaml"
        ;;
    json|json-transform|json_transform)
        run_test "$E2E_DIR/workflows/smoke-json-transform.yaml"
        ;;
    conditional|conditional-check|conditional_check)
        run_test "$E2E_DIR/workflows/smoke-conditional-check.yaml"
        ;;
    pipeline)
        run_test "$E2E_DIR/workflows/smoke-pipeline.yaml"
        ;;
    *)
        echo "Unknown test: $TESTS"
        echo "Available: all, echo, http-request, json-transform, conditional-check, pipeline"
        exit 1
        ;;
esac

echo ""
echo "========================================="
echo "  E2E Test Results"
echo "========================================="
echo ""
echo "Passed: $PASSED"
echo "Failed: $FAILED"

if [[ $FAILED -gt 0 ]]; then
    echo ""
    echo "Failed tests:$FAILED_TESTS"
    exit 1
fi

echo ""
echo "All E2E tests passed!"
echo ""
