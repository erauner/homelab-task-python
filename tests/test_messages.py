"""Tests for messages artifact functionality."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from homelab_taskkit.messages import (
    MESSAGES_KEY,
    MESSAGES_VERSION,
    TaskkitMessage,
    TaskkitMessages,
    empty_messages,
    extract_messages,
    write_messages,
)


class TestTaskkitMessage:
    """Tests for TaskkitMessage dataclass."""

    def test_minimal_message(self) -> None:
        msg = TaskkitMessage(level="error", message="Something went wrong")
        assert msg.level == "error"
        assert msg.message == "Something went wrong"
        assert msg.code is None
        assert msg.source is None
        assert msg.data == {}

    def test_full_message(self) -> None:
        msg = TaskkitMessage(
            level="warning",
            message="Slow response",
            code="SLOW_RESPONSE",
            source="http_request",
            timestamp="2024-01-01T00:00:00Z",
            data={"elapsed_ms": 5000},
        )
        assert msg.level == "warning"
        assert msg.code == "SLOW_RESPONSE"
        assert msg.source == "http_request"
        assert msg.data["elapsed_ms"] == 5000

    def test_to_dict_minimal(self) -> None:
        msg = TaskkitMessage(level="info", message="test")
        d = msg.to_dict()
        assert d == {"level": "info", "message": "test"}
        assert "code" not in d
        assert "source" not in d
        assert "data" not in d

    def test_to_dict_full(self) -> None:
        msg = TaskkitMessage(
            level="error",
            message="Failed",
            code="ERR",
            source="runner",
            timestamp="2024-01-01T00:00:00Z",
            data={"x": 1},
        )
        d = msg.to_dict()
        assert d["level"] == "error"
        assert d["message"] == "Failed"
        assert d["code"] == "ERR"
        assert d["source"] == "runner"
        assert d["timestamp"] == "2024-01-01T00:00:00Z"
        assert d["data"] == {"x": 1}

    def test_from_dict_minimal(self) -> None:
        msg = TaskkitMessage.from_dict({"level": "info", "message": "test"})
        assert msg.level == "info"
        assert msg.message == "test"
        assert msg.source is None

    def test_from_dict_with_default_source(self) -> None:
        msg = TaskkitMessage.from_dict(
            {"level": "warning", "message": "test"},
            default_source="my_task",
        )
        assert msg.source == "my_task"

    def test_from_dict_source_overrides_default(self) -> None:
        msg = TaskkitMessage.from_dict(
            {"level": "warning", "message": "test", "source": "explicit"},
            default_source="default",
        )
        assert msg.source == "explicit"


class TestTaskkitMessages:
    """Tests for TaskkitMessages container."""

    def test_empty_messages(self) -> None:
        msgs = empty_messages()
        assert msgs.version == MESSAGES_VERSION
        assert msgs.messages == []

    def test_add_message(self) -> None:
        msgs = TaskkitMessages()
        msgs.add("warning", "Test warning")
        assert len(msgs.messages) == 1
        assert msgs.messages[0].level == "warning"
        assert msgs.messages[0].message == "Test warning"
        assert msgs.messages[0].timestamp is not None

    def test_add_error(self) -> None:
        msgs = TaskkitMessages()
        msgs.add_error("Something failed", code="ERR_01", source="test")
        assert len(msgs.messages) == 1
        assert msgs.messages[0].level == "error"
        assert msgs.messages[0].code == "ERR_01"

    def test_add_warning(self) -> None:
        msgs = TaskkitMessages()
        msgs.add_warning("Something to note")
        assert msgs.messages[0].level == "warning"

    def test_add_info(self) -> None:
        msgs = TaskkitMessages()
        msgs.add_info("FYI")
        assert msgs.messages[0].level == "info"

    def test_has_errors(self) -> None:
        msgs = TaskkitMessages()
        assert not msgs.has_errors
        msgs.add_warning("warn")
        assert not msgs.has_errors
        msgs.add_error("error")
        assert msgs.has_errors

    def test_has_warnings(self) -> None:
        msgs = TaskkitMessages()
        assert not msgs.has_warnings
        msgs.add_info("info")
        assert not msgs.has_warnings
        msgs.add_warning("warn")
        assert msgs.has_warnings

    def test_to_dict(self) -> None:
        msgs = TaskkitMessages()
        msgs.add_error("Error 1", code="E1")
        msgs.add_warning("Warning 1", code="W1")

        d = msgs.to_dict()
        assert d["version"] == MESSAGES_VERSION
        assert len(d["messages"]) == 2
        assert d["messages"][0]["level"] == "error"
        assert d["messages"][1]["level"] == "warning"


class TestExtractMessages:
    """Tests for extract_messages function."""

    def test_no_messages_key(self) -> None:
        output = {"result": "success"}
        clean, msgs = extract_messages(output, task_name="test")
        assert clean == {"result": "success"}
        assert msgs == []

    def test_extracts_messages(self) -> None:
        output = {
            "result": "success",
            MESSAGES_KEY: [
                {"level": "warning", "message": "Slow response"},
                {"level": "info", "message": "Using cache"},
            ],
        }
        clean, msgs = extract_messages(output, task_name="my_task")

        assert clean == {"result": "success"}
        assert MESSAGES_KEY not in clean
        assert len(msgs) == 2
        assert msgs[0].level == "warning"
        assert msgs[0].message == "Slow response"
        assert msgs[0].source == "my_task"  # default source applied
        assert msgs[1].level == "info"

    def test_none_messages_returns_empty(self) -> None:
        output = {"result": "ok", MESSAGES_KEY: None}
        clean, msgs = extract_messages(output, task_name="test")
        assert clean == {"result": "ok"}
        assert msgs == []

    def test_invalid_messages_type_raises(self) -> None:
        output = {MESSAGES_KEY: "not a list"}
        with pytest.raises(ValueError, match="must be a list"):
            extract_messages(output, task_name="test")

    def test_invalid_message_item_raises(self) -> None:
        output = {MESSAGES_KEY: ["not a dict"]}
        with pytest.raises(ValueError, match="must be an object"):
            extract_messages(output, task_name="test")


class TestWriteMessages:
    """Tests for write_messages function."""

    def test_writes_messages_to_file(self, tmp_path: Path) -> None:
        msgs = TaskkitMessages()
        msgs.add_error("Test error", code="ERR")
        msgs.add_warning("Test warning")

        out_path = tmp_path / "messages.json"
        write_messages(out_path, msgs)

        assert out_path.exists()
        with open(out_path) as f:
            data = json.load(f)

        assert data["version"] == MESSAGES_VERSION
        assert len(data["messages"]) == 2

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        msgs = TaskkitMessages()
        msgs.add_info("Test")

        out_path = tmp_path / "nested" / "dir" / "messages.json"
        write_messages(out_path, msgs)

        assert out_path.exists()

    def test_trailing_newline(self, tmp_path: Path) -> None:
        msgs = empty_messages()
        out_path = tmp_path / "messages.json"
        write_messages(out_path, msgs)

        content = out_path.read_text()
        assert content.endswith("\n")
