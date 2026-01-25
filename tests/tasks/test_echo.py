"""Tests for the echo task."""

from __future__ import annotations

import pytest

from homelab_taskkit.tasks.echo import run


class TestEchoTask:
    """Tests for echo task function."""

    def test_echoes_message(self, fake_deps, sample_echo_input):
        """Task should echo the input message."""
        result = run(sample_echo_input, fake_deps)

        assert result["echoed_message"] == "Hello, World!"

    def test_includes_timestamp(self, fake_deps, sample_echo_input):
        """Task should include ISO timestamp."""
        result = run(sample_echo_input, fake_deps)

        assert result["timestamp"] == "2024-01-15T12:00:00+00:00"

    def test_passes_through_metadata(self, fake_deps, sample_echo_input):
        """Task should pass through metadata unchanged."""
        result = run(sample_echo_input, fake_deps)

        assert result["metadata"] == {"source": "test"}

    def test_empty_metadata_defaults(self, fake_deps):
        """Task should handle missing metadata."""
        result = run({"message": "test"}, fake_deps)

        assert result["metadata"] == {}

    def test_required_message_field(self, fake_deps):
        """Task should raise on missing message field."""
        with pytest.raises(KeyError):
            run({}, fake_deps)
