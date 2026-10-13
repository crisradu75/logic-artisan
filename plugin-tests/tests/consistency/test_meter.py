"""Tests for meter.py."""

from __future__ import annotations

import json
from pathlib import Path

import meter


def _record(message_id: str, model: str, inp: int, write: int, read: int, out: int) -> str:
    usage = {
        "input_tokens": inp,
        "cache_creation_input_tokens": write,
        "cache_read_input_tokens": read,
        "output_tokens": out,
    }
    return json.dumps({"type": "assistant", "message": {"id": message_id, "model": model, "usage": usage}})


def _write(path: Path, lines: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_each_message_counts_once_though_written_per_content_block(tmp_path: Path) -> None:
    session = _write(
        tmp_path / "s.jsonl",
        [_record("m1", "opus", 2, 100, 50, 10)] * 3 + [_record("m2", "opus", 1, 0, 150, 20)],
    )
    totals = meter.collect([session])
    assert totals == {
        "opus": {"input": 3, "cache_write": 100, "cache_read": 200, "output": 30, "messages": 2},
    }


def test_the_last_copy_wins_when_copies_disagree(tmp_path: Path) -> None:
    session = _write(tmp_path / "s.jsonl", [_record("m1", "opus", 2, 0, 0, 5), _record("m1", "opus", 2, 0, 0, 40)])
    assert meter.collect([session])["opus"]["output"] == 40


def test_totals_split_by_model_across_main_chat_and_subagents(tmp_path: Path) -> None:
    _write(tmp_path / "main.jsonl", [_record("a", "opus", 1, 2, 3, 4)])
    _write(tmp_path / "main" / "subagents" / "agent-x.jsonl", [_record("a", "sonnet", 10, 20, 30, 40)])
    _write(tmp_path / "main" / "subagents" / "agent-y.jsonl", [_record("b", "sonnet", 1, 1, 1, 1)])
    totals = meter.collect(meter.transcript_files(tmp_path))
    assert totals["opus"]["messages"] == 1
    assert totals["sonnet"] == {"input": 11, "cache_write": 21, "cache_read": 31, "output": 41, "messages": 2}


def test_lines_without_usage_or_valid_json_are_skipped(tmp_path: Path) -> None:
    session = _write(
        tmp_path / "s.jsonl",
        ["not json", json.dumps({"type": "user", "message": {"content": "hi"}}), _record("m1", "opus", 1, 1, 1, 1)],
    )
    assert meter.collect([session])["opus"]["messages"] == 1


def test_odd_records_are_skipped_or_filed_without_crashing(tmp_path: Path) -> None:
    odd_usage = {"input_tokens": "7", "cache_creation_input_tokens": None, "cache_read_input_tokens": True, "output_tokens": 2.5}
    lines = [
        "[1]",
        "null",
        '"x"',
        json.dumps({"message": {"id": "u", "model": "opus", "usage": "bad"}}),
        json.dumps({"message": {"model": "opus", "usage": {"input_tokens": 1}}}),
        json.dumps({"message": {"model": "opus", "usage": {"input_tokens": 1}}}),
        json.dumps({"message": {"id": "n", "model": 5, "usage": odd_usage}}),
        '{"message": {"id": "cut", "usage": {"input_tok',
    ]
    session = _write(tmp_path / "s.jsonl", lines)
    assert meter.collect([session]) == {
        "opus": {"input": 2, "cache_write": 0, "cache_read": 0, "output": 0, "messages": 2},
        "<unknown>": {"input": 0, "cache_write": 0, "cache_read": 0, "output": 0, "messages": 1},
    }


def test_an_empty_folder_exits_non_zero_with_empty_stdout(tmp_path: Path, capsys) -> None:
    assert meter.main([str(tmp_path)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "0 transcript file(s)" in captured.err


def test_a_single_file_path_is_read_and_other_files_are_ignored(tmp_path: Path, capsys) -> None:
    session = _write(tmp_path / "s.jsonl", [_record("a", "opus", 1, 2, 3, 4)])
    _write(tmp_path / "other.txt", [_record("b", "opus", 100, 100, 100, 100)])
    assert meter.transcript_files(tmp_path) == [session]
    assert meter.main([str(session), "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "opus": {"input": 1, "cache_write": 2, "cache_read": 3, "output": 4, "messages": 1},
    }


def test_a_transcript_without_usage_exits_non_zero_with_a_message(tmp_path: Path, capsys) -> None:
    _write(tmp_path / "s.jsonl", [json.dumps({"type": "user", "message": {"content": "hi"}})])
    assert meter.main([str(tmp_path)]) == 1
    assert "no message with a `usage` field" in capsys.readouterr().err


def test_a_missing_path_exits_non_zero(tmp_path: Path, capsys) -> None:
    assert meter.main([str(tmp_path / "absent")]) == 1
    assert "does not exist" in capsys.readouterr().err


def test_the_table_total_equals_a_manual_sum_and_nothing_is_written(tmp_path: Path, capsys) -> None:
    _write(tmp_path / "s.jsonl", [_record("a", "opus", 1, 2, 3, 4), _record("b", "sonnet", 5, 6, 7, 8)])
    before = sorted(p.name for p in tmp_path.rglob("*"))
    assert meter.main([str(tmp_path)]) == 0
    out = capsys.readouterr().out
    total = next(line for line in out.splitlines() if line.startswith("TOTAL")).split()
    assert total[1:] == ["6", "8", "10", "12", "2"]
    assert sorted(p.name for p in tmp_path.rglob("*")) == before


def test_json_output_is_the_collected_totals(tmp_path: Path, capsys) -> None:
    _write(tmp_path / "s.jsonl", [_record("a", "opus", 1, 2, 3, 4), _record("b", "sonnet", 5, 6, 7, 8)])
    assert meter.main([str(tmp_path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "opus": {"input": 1, "cache_write": 2, "cache_read": 3, "output": 4, "messages": 1},
        "sonnet": {"input": 5, "cache_write": 6, "cache_read": 7, "output": 8, "messages": 1},
    }


def test_the_same_id_and_model_in_two_files_counts_twice(tmp_path: Path) -> None:
    """Message ids are keyed per file: a subagent transcript is its own conversation, so an id
    repeated in another file is another message, never a duplicate to drop."""
    _write(tmp_path / "main.jsonl", [_record("m1", "opus", 1, 2, 3, 4)])
    _write(tmp_path / "main" / "subagents" / "agent-x.jsonl", [_record("m1", "opus", 1, 2, 3, 4)])
    assert meter.collect(meter.transcript_files(tmp_path)) == {
        "opus": {"input": 2, "cache_write": 4, "cache_read": 6, "output": 8, "messages": 2},
    }


def test_the_table_has_one_row_per_model_sorted_by_name(tmp_path: Path, capsys) -> None:
    _write(
        tmp_path / "s.jsonl",
        [_record("a", "sonnet", 5, 6, 7, 8), _record("b", "haiku", 1, 1, 1, 1), _record("c", "opus", 1, 2, 3, 4)],
    )
    assert meter.main([str(tmp_path)]) == 0
    lines = capsys.readouterr().out.splitlines()
    rows = [line.split() for line in lines[2:-1]]
    assert [row[0] for row in rows] == ["haiku", "opus", "sonnet"], "model rows are missing or out of order"
    assert rows[1][1:] == ["1", "2", "3", "4", "1"], "the opus row does not carry its own totals"
    assert lines[-1].split()[0] == "TOTAL"
