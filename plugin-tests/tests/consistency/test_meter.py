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
    _write(tmp_path / "s.jsonl", [_record("a", "opus", 1, 2, 3, 4)])
    assert meter.main([str(tmp_path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["opus"]["output"] == 4
