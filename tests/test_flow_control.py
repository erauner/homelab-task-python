"""Tests for flow control artifact functionality."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from homelab_taskkit.flow_control import (
    FLOW_CONTROL_KEY,
    FLOW_CONTROL_VERSION,
    TaskkitFlowControl,
    empty_flow_control,
    extract_flow_control,
    make_flow_control,
    write_flow_control,
    write_flow_control_vars,
)


class TestTaskkitFlowControl:
    """Tests for TaskkitFlowControl dataclass."""

    def test_empty_flow_control(self) -> None:
        fc = empty_flow_control()
        assert fc.version == FLOW_CONTROL_VERSION
        assert fc.vars == {}
        assert fc.count == 0

    def test_flow_control_with_vars(self) -> None:
        fc = TaskkitFlowControl(vars={"should_deploy": True, "skip_tests": False})
        assert fc.count == 2
        assert fc.vars["should_deploy"] is True
        assert fc.vars["skip_tests"] is False

    def test_from_vars(self) -> None:
        vars_dict = {"should_deploy": True, "environment": "production"}
        fc = TaskkitFlowControl.from_vars(vars_dict)
        assert fc.version == FLOW_CONTROL_VERSION
        assert fc.count == 2
        assert fc.vars == vars_dict

    def test_from_dict_full_format(self) -> None:
        data = {
            "version": "custom/v1",
            "vars": {"flag": True},
        }
        fc = TaskkitFlowControl.from_dict(data)
        assert fc.version == "custom/v1"
        assert fc.vars == {"flag": True}

    def test_from_dict_vars_only_format(self) -> None:
        data = {"should_deploy": True, "skip_tests": False}
        fc = TaskkitFlowControl.from_dict(data)
        assert fc.version == FLOW_CONTROL_VERSION
        assert fc.vars == data

    def test_to_dict(self) -> None:
        fc = TaskkitFlowControl(vars={"x": 1})
        d = fc.to_dict()
        assert d == {"version": FLOW_CONTROL_VERSION, "vars": {"x": 1}}

    def test_get_method(self) -> None:
        fc = TaskkitFlowControl(vars={"key": "value"})
        assert fc.get("key") == "value"
        assert fc.get("missing") is None
        assert fc.get("missing", "default") == "default"


class TestMakeFlowControl:
    """Tests for make_flow_control helper function."""

    def test_creates_flow_control_dict(self) -> None:
        result = make_flow_control({"should_deploy": True})
        assert FLOW_CONTROL_KEY in result
        assert result[FLOW_CONTROL_KEY] == {"vars": {"should_deploy": True}}

    def test_can_spread_into_output(self) -> None:
        output = {
            "status": "validated",
            **make_flow_control({"should_deploy": True}),
        }
        assert output["status"] == "validated"
        assert FLOW_CONTROL_KEY in output


class TestExtractFlowControl:
    """Tests for extract_flow_control function."""

    def test_no_flow_control_key(self) -> None:
        output = {"result": "success"}
        clean, fc = extract_flow_control(output)
        assert clean == {"result": "success"}
        assert fc is None

    def test_extracts_flow_control_from_vars_dict(self) -> None:
        output = {
            "status": "validated",
            FLOW_CONTROL_KEY: {"vars": {"should_deploy": True}},
        }
        clean, fc = extract_flow_control(output)

        assert clean == {"status": "validated"}
        assert FLOW_CONTROL_KEY not in clean
        assert fc is not None
        assert fc.count == 1
        assert fc.vars["should_deploy"] is True

    def test_extracts_flow_control_from_full_format(self) -> None:
        output = {
            FLOW_CONTROL_KEY: {
                "version": "custom/v1",
                "vars": {"flag": True},
            },
        }
        clean, fc = extract_flow_control(output)

        assert fc is not None
        assert fc.version == "custom/v1"
        assert fc.vars == {"flag": True}

    def test_extracts_flow_control_from_raw_dict(self) -> None:
        # When __taskkit_flow_control__ contains just the vars directly
        output = {
            FLOW_CONTROL_KEY: {"should_deploy": True, "skip_tests": False},
        }
        clean, fc = extract_flow_control(output)

        assert fc is not None
        assert fc.vars == {"should_deploy": True, "skip_tests": False}

    def test_none_flow_control_returns_none(self) -> None:
        output = {"result": "ok", FLOW_CONTROL_KEY: None}
        clean, fc = extract_flow_control(output)
        assert clean == {"result": "ok"}
        assert fc is None

    def test_invalid_flow_control_type_raises(self) -> None:
        output = {FLOW_CONTROL_KEY: "not a dict"}
        with pytest.raises(ValueError, match="must be an object"):
            extract_flow_control(output)


class TestWriteFlowControl:
    """Tests for write_flow_control function."""

    def test_writes_flow_control_to_file(self, tmp_path: Path) -> None:
        fc = TaskkitFlowControl(vars={"should_deploy": True, "skip_tests": False})

        out_path = tmp_path / "flow_control.json"
        write_flow_control(out_path, fc)

        assert out_path.exists()
        with open(out_path) as f:
            data = json.load(f)

        assert data["version"] == FLOW_CONTROL_VERSION
        assert data["vars"] == {"should_deploy": True, "skip_tests": False}

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        fc = empty_flow_control()

        out_path = tmp_path / "nested" / "dir" / "flow_control.json"
        write_flow_control(out_path, fc)

        assert out_path.exists()

    def test_trailing_newline(self, tmp_path: Path) -> None:
        fc = empty_flow_control()
        out_path = tmp_path / "flow_control.json"
        write_flow_control(out_path, fc)

        content = out_path.read_text()
        assert content.endswith("\n")


class TestWriteFlowControlVars:
    """Tests for write_flow_control_vars function (flat vars output)."""

    def test_writes_vars_as_flat_object(self, tmp_path: Path) -> None:
        fc = TaskkitFlowControl(vars={"should_deploy": True, "skip_tests": False})

        out_path = tmp_path / "flow_control_vars.json"
        write_flow_control_vars(out_path, fc)

        with open(out_path) as f:
            data = json.load(f)

        # Should be flat vars, not the envelope
        assert isinstance(data, dict)
        assert "version" not in data
        assert data == {"should_deploy": True, "skip_tests": False}

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        fc = TaskkitFlowControl(vars={"x": 1})

        out_path = tmp_path / "nested" / "flow_control_vars.json"
        write_flow_control_vars(out_path, fc)

        assert out_path.exists()
