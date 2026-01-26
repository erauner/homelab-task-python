#!/usr/bin/env bash
# Delete kind cluster and cleanup
set -euo pipefail

CLUSTER_NAME="taskkit-e2e"

echo "=== Deleting kind cluster: $CLUSTER_NAME ==="

if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    kind delete cluster --name "$CLUSTER_NAME"
    echo ""
    echo "Cluster '$CLUSTER_NAME' deleted."
else
    echo "Cluster '$CLUSTER_NAME' not found (already deleted?)."
fi

echo ""
echo "========================================="
echo "  Cleanup complete"
echo "========================================="
echo ""
