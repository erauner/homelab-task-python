"""Smoke test workflow step handlers.

This package provides step handlers for the infrastructure smoke test workflow:
- smoke-test-init: Initialize the workflow and validate parameters
- smoke-test-check-dns: Verify DNS resolution
- smoke-test-check-http: Verify HTTP endpoint health
- smoke-test-finalize: Summarize results and cleanup
"""

# Import step modules to register handlers
from homelab_taskkit.steps.smoke_test import (
    step_check_dns,
    step_check_http,
    step_finalize,
    step_init,
)

__all__ = [
    "step_init",
    "step_check_dns",
    "step_check_http",
    "step_finalize",
]
