"""Tests for context artifact functionality."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from homelab_taskkit.context import (
    CONTEXT_PATCH_KEY,
    CONTEXT_VERSION,
    ContextPatch,
    TaskkitContext,
    apply_patch,
    empty_context,
    extract_context_patch,
    load_context,
    serialized_size_bytes,
    write_context,
)
from homelab_taskkit.context_rules import validate_patch
from homelab_taskkit.errors import ContextError, ContextSizeError


class TestTaskkitContext:
    """Tests for TaskkitContext dataclass."""

    def test_empty_context(self) -> None:
        ctx = empty_context()
        assert ctx.version == CONTEXT_VERSION
        assert ctx.vars == {}

    def test_to_dict(self) -> None:
        ctx = TaskkitContext(
            version="taskkit-context/v1",
            vars={"pipeline.run_id": "test123"},
        )
        d = ctx.to_dict()
        assert d == {
            "version": "taskkit-context/v1",
            "vars": {"pipeline.run_id": "test123"},
        }

    def test_from_dict(self) -> None:
        data = {
            "version": "taskkit-context/v1",
            "vars": {"key": "value"},
        }
        ctx = TaskkitContext.from_dict(data)
        assert ctx.version == "taskkit-context/v1"
        assert ctx.vars == {"key": "value"}

    def test_from_dict_defaults(self) -> None:
        ctx = TaskkitContext.from_dict({})
        assert ctx.version == CONTEXT_VERSION
        assert ctx.vars == {}


class TestLoadContext:
    """Tests for load_context function."""

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        ctx = load_context(tmp_path / "nonexistent.json")
        assert ctx.vars == {}
        assert ctx.version == CONTEXT_VERSION

    def test_loads_full_context_format(self, tmp_path: Path) -> None:
        ctx_file = tmp_path / "context.json"
        ctx_file.write_text(json.dumps({
            "version": "taskkit-context/v1",
            "vars": {"pipeline.run_id": "abc123"},
        }))

        ctx = load_context(ctx_file)
        assert ctx.version == "taskkit-context/v1"
        assert ctx.vars == {"pipeline.run_id": "abc123"}

    def test_loads_legacy_format_as_vars(self, tmp_path: Path) -> None:
        ctx_file = tmp_path / "context.json"
        ctx_file.write_text(json.dumps({
            "some_key": "some_value",
        }))

        ctx = load_context(ctx_file)
        assert ctx.version == CONTEXT_VERSION
        assert ctx.vars == {"some_key": "some_value"}

    def test_invalid_json_raises_error(self, tmp_path: Path) -> None:
        ctx_file = tmp_path / "context.json"
        ctx_file.write_text("not valid json")

        with pytest.raises(ContextError, match="Invalid JSON"):
            load_context(ctx_file)

    def test_non_object_raises_error(self, tmp_path: Path) -> None:
        ctx_file = tmp_path / "context.json"
        ctx_file.write_text(json.dumps(["array", "not", "object"]))

        with pytest.raises(ContextError, match="must be an object"):
            load_context(ctx_file)


class TestExtractContextPatch:
    """Tests for extract_context_patch function."""

    def test_no_patch_returns_none(self) -> None:
        output = {"result": "success", "data": [1, 2, 3]}
        clean, patch = extract_context_patch(output)
        assert clean == output
        assert patch is None

    def test_extracts_patch_from_output(self) -> None:
        output = {
            "result": "success",
            CONTEXT_PATCH_KEY: {
                "set": {"http_request.last_status": 200},
                "unset": ["old_key"],
            },
        }
        clean, patch = extract_context_patch(output)

        assert CONTEXT_PATCH_KEY not in clean
        assert clean == {"result": "success"}
        assert patch is not None
        assert patch.set == {"http_request.last_status": 200}
        assert patch.unset == ["old_key"]

    def test_none_patch_returns_none(self) -> None:
        output = {"result": "success", CONTEXT_PATCH_KEY: None}
        clean, patch = extract_context_patch(output)
        assert patch is None

    def test_invalid_patch_type_raises_error(self) -> None:
        output = {"result": "success", CONTEXT_PATCH_KEY: "not an object"}
        with pytest.raises(ContextError, match="must be an object"):
            extract_context_patch(output)

    def test_invalid_set_type_raises_error(self) -> None:
        output = {"result": "success", CONTEXT_PATCH_KEY: {"set": ["not", "object"]}}
        with pytest.raises(ContextError, match="set must be an object"):
            extract_context_patch(output)

    def test_invalid_unset_type_raises_error(self) -> None:
        output = {"result": "success", CONTEXT_PATCH_KEY: {"unset": "not array"}}
        with pytest.raises(ContextError, match="unset must be an array"):
            extract_context_patch(output)

    def test_invalid_unset_value_raises_error(self) -> None:
        output = {"result": "success", CONTEXT_PATCH_KEY: {"unset": [123]}}
        with pytest.raises(ContextError, match="must be strings"):
            extract_context_patch(output)


class TestApplyPatch:
    """Tests for apply_patch function."""

    def test_none_patch_returns_same_context(self) -> None:
        ctx = TaskkitContext(vars={"existing": "value"})
        result = apply_patch(ctx, None)
        assert result.vars == {"existing": "value"}

    def test_set_adds_keys(self) -> None:
        ctx = TaskkitContext(vars={"existing": "value"})
        patch = ContextPatch(set={"new": "key"})
        result = apply_patch(ctx, patch)
        assert result.vars == {"existing": "value", "new": "key"}

    def test_set_overwrites_keys(self) -> None:
        ctx = TaskkitContext(vars={"key": "old"})
        patch = ContextPatch(set={"key": "new"})
        result = apply_patch(ctx, patch)
        assert result.vars == {"key": "new"}

    def test_unset_removes_keys(self) -> None:
        ctx = TaskkitContext(vars={"keep": "value", "remove": "me"})
        patch = ContextPatch(unset=["remove"])
        result = apply_patch(ctx, patch)
        assert result.vars == {"keep": "value"}

    def test_unset_nonexistent_key_is_noop(self) -> None:
        ctx = TaskkitContext(vars={"keep": "value"})
        patch = ContextPatch(unset=["nonexistent"])
        result = apply_patch(ctx, patch)
        assert result.vars == {"keep": "value"}

    def test_set_wins_over_unset(self) -> None:
        """If a key is in both set and unset, set wins (applied last)."""
        ctx = TaskkitContext(vars={"key": "original"})
        patch = ContextPatch(set={"key": "new"}, unset=["key"])
        result = apply_patch(ctx, patch)
        assert result.vars == {"key": "new"}


class TestWriteContext:
    """Tests for write_context function."""

    def test_writes_context_to_file(self, tmp_path: Path) -> None:
        ctx = TaskkitContext(vars={"test": "value"})
        out_path = tmp_path / "output" / "context.json"

        write_context(out_path, ctx)

        assert out_path.exists()
        data = json.loads(out_path.read_text())
        assert data["version"] == CONTEXT_VERSION
        assert data["vars"] == {"test": "value"}

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        ctx = empty_context()
        out_path = tmp_path / "deep" / "nested" / "path" / "context.json"

        write_context(out_path, ctx)

        assert out_path.exists()

    def test_exceeds_size_raises_error(self, tmp_path: Path) -> None:
        # Create context with large data
        large_vars = {f"key_{i}": "x" * 1000 for i in range(100)}
        ctx = TaskkitContext(vars=large_vars)
        out_path = tmp_path / "context.json"

        with pytest.raises(ContextSizeError, match="exceeds limit"):
            write_context(out_path, ctx, max_bytes=1024)


class TestSerializedSizeBytes:
    """Tests for serialized_size_bytes function."""

    def test_empty_context_size(self) -> None:
        ctx = empty_context()
        size = serialized_size_bytes(ctx)
        # {"version":"taskkit-context/v1","vars":{}}
        assert size < 100

    def test_context_with_data(self) -> None:
        ctx = TaskkitContext(vars={"key": "value"})
        size = serialized_size_bytes(ctx)
        assert size > 0


class TestValidatePatch:
    """Tests for validate_patch function."""

    def test_none_patch_is_valid(self) -> None:
        validate_patch("echo", None)

    def test_empty_patch_is_valid(self) -> None:
        patch = ContextPatch()
        validate_patch("echo", patch)

    def test_task_namespace_is_valid(self) -> None:
        patch = ContextPatch(set={"echo.last_message": "hello"})
        validate_patch("echo", patch)

    def test_pipeline_namespace_is_valid(self) -> None:
        patch = ContextPatch(set={"pipeline.run_id": "abc123"})
        validate_patch("echo", patch)

    def test_idempotency_namespace_is_valid(self) -> None:
        patch = ContextPatch(set={"idempotency.key": "hash123"})
        validate_patch("http_request", patch)

    def test_wrong_task_namespace_raises_error(self) -> None:
        patch = ContextPatch(set={"other_task.key": "value"})
        with pytest.raises(AssertionError, match="must be namespaced"):
            validate_patch("echo", patch)

    def test_unnamespaced_key_raises_error(self) -> None:
        patch = ContextPatch(set={"bare_key": "value"})
        with pytest.raises(AssertionError, match="must be namespaced"):
            validate_patch("echo", patch)

    def test_unset_namespacing_is_validated(self) -> None:
        patch = ContextPatch(unset=["wrong_namespace.key"])
        with pytest.raises(AssertionError, match="must be namespaced"):
            validate_patch("echo", patch)

    def test_dict_patch_format_is_valid(self) -> None:
        patch = {
            "set": {"echo.key": "value"},
            "unset": ["echo.old_key"],
        }
        validate_patch("echo", patch)


class TestContextIntegration:
    """Integration tests for context workflow."""

    def test_full_context_workflow(self, tmp_path: Path) -> None:
        # 1. Start with empty context
        ctx_in = tmp_path / "context_in.json"
        ctx_out = tmp_path / "context_out.json"

        # Write initial context
        initial = empty_context()
        write_context(ctx_in, initial)

        # 2. Load context
        loaded = load_context(ctx_in)
        assert loaded.vars == {}

        # 3. Simulate task output with patch
        task_output = {
            "result": "success",
            CONTEXT_PATCH_KEY: {
                "set": {"http_request.last_status": 200},
            },
        }
        clean_output, patch = extract_context_patch(task_output)

        # 4. Validate patch
        validate_patch("http_request", patch)

        # 5. Apply patch
        merged = apply_patch(loaded, patch)
        assert merged.vars == {"http_request.last_status": 200}

        # 6. Write merged context
        write_context(ctx_out, merged)

        # 7. Load and verify
        final = load_context(ctx_out)
        assert final.vars == {"http_request.last_status": 200}

    def test_context_chain_across_steps(self, tmp_path: Path) -> None:
        """Simulate passing context through multiple steps."""
        ctx_file = tmp_path / "context.json"

        # Step 1: http_request sets status
        ctx = empty_context()
        patch1 = ContextPatch(set={"http_request.last_status": 200})
        ctx = apply_patch(ctx, patch1)
        write_context(ctx_file, ctx)

        # Step 2: json_transform reads and adds its own
        ctx = load_context(ctx_file)
        assert ctx.vars["http_request.last_status"] == 200
        patch2 = ContextPatch(set={"json_transform.output_count": 5})
        ctx = apply_patch(ctx, patch2)
        write_context(ctx_file, ctx)

        # Step 3: conditional_check reads both
        ctx = load_context(ctx_file)
        assert ctx.vars["http_request.last_status"] == 200
        assert ctx.vars["json_transform.output_count"] == 5
