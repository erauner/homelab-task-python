"""Tests for fanout artifact functionality."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from homelab_taskkit.fanout import (
    FANOUT_KEY,
    FANOUT_VERSION,
    TaskkitFanout,
    empty_fanout,
    extract_fanout,
    write_fanout,
    write_fanout_items,
)


class TestTaskkitFanout:
    """Tests for TaskkitFanout dataclass."""

    def test_empty_fanout(self) -> None:
        fanout = empty_fanout()
        assert fanout.version == FANOUT_VERSION
        assert fanout.items == []
        assert fanout.count == 0

    def test_fanout_with_items(self) -> None:
        fanout = TaskkitFanout(items=[{"a": 1}, {"a": 2}, {"a": 3}])
        assert fanout.count == 3
        assert fanout.items[0] == {"a": 1}

    def test_from_items(self) -> None:
        items = [{"cluster": "c1"}, {"cluster": "c2"}]
        fanout = TaskkitFanout.from_items(items)
        assert fanout.version == FANOUT_VERSION
        assert fanout.count == 2
        assert fanout.items == items

    def test_to_dict(self) -> None:
        fanout = TaskkitFanout(items=[{"x": 1}])
        d = fanout.to_dict()
        assert d == {"version": FANOUT_VERSION, "items": [{"x": 1}]}

    def test_to_items_list(self) -> None:
        fanout = TaskkitFanout(items=[{"a": 1}, {"a": 2}])
        assert fanout.to_items_list() == [{"a": 1}, {"a": 2}]


class TestExtractFanout:
    """Tests for extract_fanout function."""

    def test_no_fanout_key(self) -> None:
        output = {"result": "success"}
        clean, fanout = extract_fanout(output)
        assert clean == {"result": "success"}
        assert fanout is None

    def test_extracts_fanout_from_list(self) -> None:
        output = {
            "generated_count": 2,
            FANOUT_KEY: [{"cluster": "c1"}, {"cluster": "c2"}],
        }
        clean, fanout = extract_fanout(output)

        assert clean == {"generated_count": 2}
        assert FANOUT_KEY not in clean
        assert fanout is not None
        assert fanout.count == 2
        assert fanout.items[0] == {"cluster": "c1"}

    def test_extracts_fanout_from_dict_with_items(self) -> None:
        output = {
            FANOUT_KEY: {
                "version": "custom/v1",
                "items": [{"target": "t1"}],
            },
        }
        clean, fanout = extract_fanout(output)

        assert fanout is not None
        assert fanout.version == "custom/v1"
        assert fanout.items == [{"target": "t1"}]

    def test_none_fanout_returns_none(self) -> None:
        output = {"result": "ok", FANOUT_KEY: None}
        clean, fanout = extract_fanout(output)
        assert clean == {"result": "ok"}
        assert fanout is None

    def test_invalid_fanout_type_raises(self) -> None:
        output = {FANOUT_KEY: "not a list or dict"}
        with pytest.raises(ValueError, match="must be a list or object"):
            extract_fanout(output)

    def test_invalid_items_type_raises(self) -> None:
        output = {FANOUT_KEY: {"items": "not a list"}}
        with pytest.raises(ValueError, match="must be a list"):
            extract_fanout(output)


class TestWriteFanout:
    """Tests for write_fanout function."""

    def test_writes_fanout_to_file(self, tmp_path: Path) -> None:
        fanout = TaskkitFanout(items=[{"target": "t1"}, {"target": "t2"}])

        out_path = tmp_path / "fanout.json"
        write_fanout(out_path, fanout)

        assert out_path.exists()
        with open(out_path) as f:
            data = json.load(f)

        assert data["version"] == FANOUT_VERSION
        assert len(data["items"]) == 2

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        fanout = empty_fanout()

        out_path = tmp_path / "nested" / "dir" / "fanout.json"
        write_fanout(out_path, fanout)

        assert out_path.exists()

    def test_trailing_newline(self, tmp_path: Path) -> None:
        fanout = empty_fanout()
        out_path = tmp_path / "fanout.json"
        write_fanout(out_path, fanout)

        content = out_path.read_text()
        assert content.endswith("\n")


class TestWriteFanoutItems:
    """Tests for write_fanout_items function (raw array output)."""

    def test_writes_items_as_array(self, tmp_path: Path) -> None:
        fanout = TaskkitFanout(items=[{"cluster": "c1"}, {"cluster": "c2"}])

        out_path = tmp_path / "fanout.json"
        write_fanout_items(out_path, fanout)

        with open(out_path) as f:
            data = json.load(f)

        # Should be a raw array, not the envelope
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0] == {"cluster": "c1"}

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        fanout = TaskkitFanout(items=[{"x": 1}])

        out_path = tmp_path / "nested" / "fanout.json"
        write_fanout_items(out_path, fanout)

        assert out_path.exists()
