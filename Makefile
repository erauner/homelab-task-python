.PHONY: help install dev lint format test clean build \
        e2e-up e2e-down e2e-build e2e-load e2e-run e2e-status e2e

help:
	@echo "Available targets:"
	@echo "  install     Install production dependencies"
	@echo "  dev         Install dev dependencies"
	@echo "  lint        Run linting (ruff check)"
	@echo "  format      Format code (ruff format)"
	@echo "  fix         Auto-fix linting issues"
	@echo "  check       Run all checks (lint + format check)"
	@echo "  test        Run tests with coverage"
	@echo "  clean       Remove build artifacts"
	@echo "  build       Build the package"
	@echo ""
	@echo "E2E Testing (kind + Argo Workflows):"
	@echo "  e2e-up      Create kind cluster with Argo + httpbin"
	@echo "  e2e-down    Delete kind cluster"
	@echo "  e2e-build   Build taskkit Docker image"
	@echo "  e2e-load    Load image into kind cluster"
	@echo "  e2e-run     Run all E2E smoke tests"
	@echo "  e2e-status  Check E2E environment status"
	@echo "  e2e         Full E2E cycle (up, build, load, run)"

install:
	uv sync

dev:
	uv sync --dev

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

fix:
	ruff check --fix src/ tests/
	ruff format src/ tests/

check:
	ruff check src/ tests/
	ruff format --check src/ tests/

test:
	pytest -v --cov=src/homelab_taskkit

clean:
	rm -rf dist/ build/ *.egg-info .pytest_cache .ruff_cache .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

build: clean
	uv build

# =============================================================================
# E2E Testing with kind + Argo Workflows
# =============================================================================

e2e-up:
	@./e2e/scripts/up.sh

e2e-down:
	@./e2e/scripts/down.sh

e2e-build:
	@./e2e/scripts/build.sh

e2e-load:
	@./e2e/scripts/load.sh

e2e-run:
	@./e2e/scripts/run.sh

e2e-status:
	@./e2e/scripts/status.sh

# Full E2E cycle: create cluster, build, load, and run tests
e2e: e2e-up e2e-build e2e-load e2e-run

# Run specific test: make e2e-test-echo, make e2e-test-pipeline, etc.
e2e-test-%:
	@./e2e/scripts/run.sh $*
