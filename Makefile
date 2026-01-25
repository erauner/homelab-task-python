.PHONY: help install dev lint format test clean build

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
