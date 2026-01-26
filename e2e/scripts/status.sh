#!/usr/bin/env bash
# Check E2E cluster and component status
set -euo pipefail

CLUSTER_NAME="taskkit-e2e"

echo "=== E2E Environment Status ==="
echo ""

# Check kind cluster
echo "Kind Cluster:"
if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    echo "  ✓ $CLUSTER_NAME exists"
else
    echo "  ✗ $CLUSTER_NAME not found"
    echo ""
    echo "Run 'make e2e-up' to create the cluster."
    exit 1
fi

# Check kubectl context
echo ""
echo "Kubectl Context:"
CURRENT_CONTEXT=$(kubectl config current-context 2>/dev/null || echo "none")
if [[ "$CURRENT_CONTEXT" == "kind-$CLUSTER_NAME" ]]; then
    echo "  ✓ Using kind-$CLUSTER_NAME"
else
    echo "  ⚠ Current context: $CURRENT_CONTEXT"
    echo "  Run: kubectl config use-context kind-$CLUSTER_NAME"
fi

# Switch to correct context for remaining checks
kubectl config use-context "kind-$CLUSTER_NAME" >/dev/null 2>&1 || true

# Check Argo Workflows
echo ""
echo "Argo Workflows:"
if kubectl get deployment argo-server -n argo-workflows >/dev/null 2>&1; then
    ARGO_READY=$(kubectl get deployment argo-server -n argo-workflows -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    if [[ "$ARGO_READY" -ge 1 ]]; then
        echo "  ✓ argo-server ready"
    else
        echo "  ⚠ argo-server not ready"
    fi
else
    echo "  ✗ argo-server not found"
fi

if kubectl get deployment workflow-controller -n argo-workflows >/dev/null 2>&1; then
    WC_READY=$(kubectl get deployment workflow-controller -n argo-workflows -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    if [[ "$WC_READY" -ge 1 ]]; then
        echo "  ✓ workflow-controller ready"
    else
        echo "  ⚠ workflow-controller not ready"
    fi
else
    echo "  ✗ workflow-controller not found"
fi

# Check httpbin
echo ""
echo "httpbin:"
if kubectl get deployment httpbin -n httpbin >/dev/null 2>&1; then
    HTTPBIN_READY=$(kubectl get deployment httpbin -n httpbin -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    if [[ "$HTTPBIN_READY" -ge 1 ]]; then
        echo "  ✓ httpbin ready"
    else
        echo "  ⚠ httpbin not ready"
    fi
else
    echo "  ✗ httpbin not found"
fi

# Check taskkit-base template
echo ""
echo "Taskkit Base Template:"
if kubectl get workflowtemplate taskkit-base -n argo-workflows >/dev/null 2>&1; then
    echo "  ✓ taskkit-base installed"
else
    echo "  ✗ taskkit-base not found"
fi

# Check if taskkit image is loaded
echo ""
echo "Taskkit Image:"
# This checks if the image exists on the node
NODE_NAME=$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')
if docker exec "$CLUSTER_NAME-control-plane" crictl images 2>/dev/null | grep -q "taskkit"; then
    echo "  ✓ taskkit:local loaded in cluster"
else
    echo "  ⚠ taskkit:local not found in cluster"
    echo "  Run: make e2e-build && make e2e-load"
fi

# Recent workflows
echo ""
echo "Recent Workflows:"
WORKFLOWS=$(kubectl get workflows -n argo-workflows --sort-by=.metadata.creationTimestamp -o custom-columns=NAME:.metadata.name,STATUS:.status.phase,AGE:.metadata.creationTimestamp --no-headers 2>/dev/null | tail -5)
if [[ -n "$WORKFLOWS" ]]; then
    echo "$WORKFLOWS" | while read -r line; do
        echo "  $line"
    done
else
    echo "  (none)"
fi

echo ""
echo "========================================="
echo ""
