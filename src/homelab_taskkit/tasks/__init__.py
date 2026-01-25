"""Task implementations - imported to register tasks."""

# Import all tasks to register them
from homelab_taskkit.tasks import echo, http_request

__all__ = ["echo", "http_request"]
