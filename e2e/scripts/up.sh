#!/usr/bin/env bash
# Create kind cluster and install Argo Workflows + dependencies
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
E2E_DIR="$(dirname "$SCRIPT_DIR")"
CLUSTER_NAME="taskkit-e2e"
ARGO_VERSION="${ARGO_VERSION:-v3.5.5}"

echo "=== Creating kind cluster: $CLUSTER_NAME ==="

# Check if cluster already exists
if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    echo "Cluster '$CLUSTER_NAME' already exists."
    echo "Use 'make e2e-down' to delete it first, or continue with existing cluster."
    read -p "Continue with existing cluster? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    kind create cluster --config "$E2E_DIR/cluster/kind-config.yaml"
fi

echo ""
echo "=== Installing Argo Workflows $ARGO_VERSION ==="

# Create namespace first
kubectl create namespace argo-workflows --dry-run=client -o yaml | kubectl apply -f -

# Install Argo Workflows (quick-start minimal)
kubectl apply -n argo-workflows -f "https://github.com/argoproj/argo-workflows/releases/download/${ARGO_VERSION}/quick-start-minimal.yaml"

# Apply our custom RBAC and config
kubectl apply -f "$E2E_DIR/cluster/argo-install.yaml"

echo ""
echo "=== Waiting for Argo Workflows to be ready ==="
kubectl wait --for=condition=available --timeout=120s \
    deployment/argo-server -n argo-workflows || true
kubectl wait --for=condition=available --timeout=120s \
    deployment/workflow-controller -n argo-workflows || true

echo ""
echo "=== Installing httpbin for HTTP testing ==="
kubectl apply -f "$E2E_DIR/cluster/httpbin.yaml"

echo ""
echo "=== Waiting for httpbin to be ready ==="
kubectl wait --for=condition=available --timeout=60s \
    deployment/httpbin -n httpbin

echo ""
echo "=== Installing E2E taskkit-base template ==="
kubectl apply -f "$E2E_DIR/workflows/taskkit-base.yaml"

echo ""
echo "========================================="
echo "  Kind cluster ready for E2E testing"
echo "========================================="
echo ""
echo "Cluster: $CLUSTER_NAME"
echo "Context: kind-$CLUSTER_NAME"
echo ""
echo "Next steps:"
echo "  make e2e-build   # Build taskkit image"
echo "  make e2e-load    # Load image into kind"
echo "  make e2e-run     # Run smoke tests"
echo ""
