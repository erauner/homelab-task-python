#!/usr/bin/env bash
# Build taskkit Docker image for E2E testing
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Use git SHA or 'local' as tag
GIT_SHA=$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || echo "local")
IMAGE_TAG="${IMAGE_TAG:-$GIT_SHA}"
IMAGE_NAME="taskkit:${IMAGE_TAG}"

echo "=== Building taskkit image ==="
echo "Image: $IMAGE_NAME"
echo "Context: $PROJECT_ROOT"
echo ""

docker build \
    -t "$IMAGE_NAME" \
    -t "taskkit:local" \
    -f "$PROJECT_ROOT/Dockerfile" \
    "$PROJECT_ROOT"

echo ""
echo "========================================="
echo "  Image built successfully"
echo "========================================="
echo ""
echo "Tagged as:"
echo "  - $IMAGE_NAME"
echo "  - taskkit:local"
echo ""
echo "Next: make e2e-load"
echo ""
