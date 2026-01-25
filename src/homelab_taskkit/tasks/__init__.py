"""Task implementations - imported to register tasks."""

# Import all tasks to register them
from homelab_taskkit.tasks import (
    conditional_check,
    echo,
    http_request,
    json_transform,
    webhook_notify,
)

__all__ = [
    "conditional_check",
    "echo",
    "http_request",
    "json_transform",
    "webhook_notify",
]
