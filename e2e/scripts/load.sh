#!/usr/bin/env bash
# Load taskkit image into kind cluster
set -euo pipefail

CLUSTER_NAME="taskkit-e2e"
IMAGE_NAME="${IMAGE_NAME:-taskkit:local}"

echo "=== Loading image into kind cluster ==="
echo "Cluster: $CLUSTER_NAME"
echo "Image: $IMAGE_NAME"
echo ""

# Check if cluster exists
if ! kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    echo "Error: Cluster '$CLUSTER_NAME' not found."
    echo "Run 'make e2e-up' first."
    exit 1
fi

# Load the image
kind load docker-image "$IMAGE_NAME" --name "$CLUSTER_NAME"

echo ""
echo "========================================="
echo "  Image loaded successfully"
echo "========================================="
echo ""
echo "The image is now available in the kind cluster."
echo "Workflows using 'taskkit:local' with imagePullPolicy: Never will use it."
echo ""
echo "Next: make e2e-run"
echo ""
