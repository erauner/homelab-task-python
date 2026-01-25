# Multi-stage build for minimal production image
# Build stage: install dependencies with uv
FROM python:3.12-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml .
COPY uv.lock* .

# Install dependencies into a virtual environment
RUN uv venv /app/.venv && \
    uv pip install --python /app/.venv/bin/python -e .

# Copy source code
COPY src/ src/
COPY schemas/ schemas/

# Install the package
RUN uv pip install --python /app/.venv/bin/python -e .

# Runtime stage: minimal image
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/schemas /app/schemas
COPY --from=builder /app/pyproject.toml /app/pyproject.toml

# Add venv to path
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src:$PYTHONPATH"

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash taskuser
USER taskuser

# Default entrypoint
ENTRYPOINT ["task-run"]
CMD ["--help"]
