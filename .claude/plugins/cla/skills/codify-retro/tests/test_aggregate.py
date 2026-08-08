"""Tests for aggregate.py — deterministic metrics over codify-runs JSONL."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "aggregate.py"


def _write_log(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


def _run(log: Path, limit: int = 10) -> tuple[dict, str]:
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--log", str(log), "--limit", str(limit)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout), r.stderr


def test_empty_log_returns_zero(tmp_path: Path) -> None:
    out, _ = _run(tmp_path / "missing.jsonl")
    assert out["runs_analyzed"] == 0


def test_suggestion_and_memory_rates(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"ts": "2026-06-24", "suggestions": {"proposed": 4, "applied": 3, "rejected": 1},
         "memory": {"proposed": 2, "applied": 2}},
        {"ts": "2026-06-25", "suggestions": {"proposed": 6, "applied": 3, "rejected": 3},
         "memory": {"proposed": 2, "applied": 1}},
    ])
    out, _ = _run(log)
    assert out["runs_analyzed"] == 2
    assert out["window"] == {"first_ts": "2026-06-24", "last_ts": "2026-06-25"}
    assert out["suggestions"] == {"proposed": 10, "applied": 6, "rejected": 4, "apply_rate": 0.6}
    assert out["memory"] == {"proposed": 4, "applied": 3, "apply_rate": 0.75}


def test_re_offenses_and_escalation_rungs(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"re_offenses": [{"lesson": "L1", "failing_artifact": "memory", "escalated_to": "hook"}]},
        {"re_offenses": [{"lesson": "L1", "failing_artifact": "memory", "escalated_to": "script"},
                         {"lesson": "L2", "failing_artifact": "checklist", "escalated_to": "memory"}]},
    ])
    out, _ = _run(log)
    # L1 re-offended twice → escalation isn't working; it must surface first.
    assert out["re_offenses"][0] == {"lesson": "L1", "count": 2}
    assert {"lesson": "L2", "count": 1} in out["re_offenses"]
    assert out["escalation_rungs"] == {"hook": 1, "script": 1, "memory": 1}


def test_rejected_lessons_repeat_count(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"rejected_lessons": ["symmetric-docs", "verbose-fix"]},
        {"rejected_lessons": ["symmetric-docs"]},
    ])
    out, _ = _run(log)
    # symmetric-docs rejected twice → candidate for retirement.
    assert out["rejected_lessons"][0] == {"lesson": "symmetric-docs", "count": 2}


def test_maintenance_trend_and_process_issue(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"maintenance": {"failure_modes_bullets": 58, "live_log_entries": 12, "trimmed": True},
         "process_issue": False},
        {"maintenance": {"failure_modes_bullets": 61, "live_log_entries": 12, "trimmed": True},
         "process_issue": True},
    ])
    out, _ = _run(log)
    assert out["maintenance"]["failure_modes_bullets_latest"] == 61
    assert out["maintenance"]["failure_modes_bullets_trend"] == [58, 61]
    assert out["maintenance"]["trim_runs"] == 2
    assert out["process_issue_runs"] == 1


def test_unknown_escalation_rung_surfaced(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"re_offenses": [{"lesson": "L1", "escalated_to": "telepathy"}]},
    ])
    out, err = _run(log)
    assert out["escalation_rungs_unknown"] == {"telepathy": 1}
    assert "not in" in err


def test_malformed_line_skipped_and_counted(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(
        json.dumps({"suggestions": {"proposed": 1, "applied": 1}}) + "\n"
        + "{ broken json\n"
        + json.dumps({"suggestions": {"proposed": 1, "applied": 0}}) + "\n",
        encoding="utf-8",
    )
    out, err = _run(log)
    assert out["runs_analyzed"] == 2
    assert out["skipped_records"] == 1
    assert "malformed" in err


def test_limit_slices_to_last_n(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [{"ts": f"2026-06-{d:02d}"} for d in range(1, 13)])  # 12 records
    out3, _ = _run(log, limit=3)
    assert out3["runs_analyzed"] == 3
    assert out3["window"] == {"first_ts": "2026-06-10", "last_ts": "2026-06-12"}
    out_all, _ = _run(log, limit=0)  # 0 = all
    assert out_all["runs_analyzed"] == 12
    assert out_all["window"]["first_ts"] == "2026-06-01"


def test_apply_rate_zero_denominator(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [{"ts": "2026-06-24"}])  # no suggestions/memory blocks at all
    out, _ = _run(log)
    assert out["suggestions"] == {"proposed": 0, "applied": 0, "rejected": 0, "apply_rate": 0.0}
    assert out["memory"] == {"proposed": 0, "applied": 0, "apply_rate": 0.0}


def test_bool_count_rejected_and_tallied(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    # bool is an int subclass — must NOT be counted as 1.
    _write_log(log, [{"suggestions": {"proposed": True, "applied": 1}}])
    out, err = _run(log)
    assert out["suggestions"]["proposed"] == 0
    assert out["coerced_fields"] == 1
    assert "is bool" in err


def test_non_dict_count_block_warned(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [{"suggestions": [1, 2]}])
    out, err = _run(log)
    assert out["suggestions"]["proposed"] == 0
    assert "not an object" in err


def test_non_string_lesson_and_escalated_to_warned(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"re_offenses": [{"lesson": None, "escalated_to": 7}]},
    ])
    out, err = _run(log)
    assert out["re_offenses"] == []          # null lesson not counted
    assert out["escalation_rungs"] == {}     # int rung not counted
    assert "lesson" in err and "escalated_to" in err


def test_string_container_not_iterated_per_char(tmp_path: Path) -> None:
    # Regression: a string where a list is expected must NOT iterate per character
    # (which would silently create single-char "lessons").
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"rejected_lessons": "symmetric-docs", "re_offenses": "L1"},
    ])
    out, err = _run(log)
    assert out["rejected_lessons"] == []
    assert out["re_offenses"] == []
    assert "`rejected_lessons` is str" in err
    assert "`re_offenses` is str" in err


def test_non_dict_maintenance_warned_not_swallowed(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [{"maintenance": "n/a"}])
    out, err = _run(log)
    assert out["maintenance"]["failure_modes_bullets_latest"] is None
    assert "`maintenance` is str" in err


def test_output_chars_trend_and_mean(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"output_chars": 1000},
        {"output_chars": 2000},
        {},  # no output_chars — excluded
    ])
    out, _ = _run(log)
    assert out["output_chars"] == {"latest": 2000, "trend": [1000, 2000], "mean": 1500.0}


def test_output_chars_negative_clamped_to_zero(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [{"output_chars": -5}])
    out, err = _run(log)
    assert "negative, clamped to 0" in err
    assert out["output_chars"] == {"latest": 0, "trend": [0], "mean": 0.0}


def test_output_chars_type_confused_warns_and_coerces(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [{"output_chars": "big"}])
    out, err = _run(log)
    assert "output_chars='big' not int" in err
    assert out["output_chars"] == {"latest": None, "trend": [], "mean": 0.0}
    assert out["coerced_fields"] == 1


def test_output_chars_bool_rejected(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [{"output_chars": True}])
    out, err = _run(log)
    assert "output_chars=True is bool" in err
    assert out["output_chars"] == {"latest": None, "trend": [], "mean": 0.0}
    assert out["coerced_fields"] == 1


def test_output_chars_latest_falls_back_to_last_valid_not_none(tmp_path: Path) -> None:
    # Pins the documented (surprising) semantics: `latest` is the most recent
    # VALID value, not the most recent record's value — a malformed newest
    # record does not reset `latest` to None.
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"output_chars": 1000},
        {"output_chars": "bad"},
    ])
    out, err = _run(log)
    assert "output_chars='bad' not int" in err
    assert out["output_chars"] == {"latest": 1000, "trend": [1000], "mean": 1000.0}
    assert out["coerced_fields"] == 1


def test_non_string_ts_excluded_with_warning(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [{"ts": 20260624, "suggestions": {"proposed": 1, "applied": 1}}])
    out, err = _run(log)
    assert out["window"] == {"first_ts": None, "last_ts": None}
    assert out["runs_analyzed"] == 1  # record still analyzed, only window excludes it
    assert "`ts`" in err


def test_missing_ledger_warns_and_reports_zero(tmp_path: Path, monkeypatch) -> None:
    # The "no file" branch must name where it looked (silent-misconfig guard).
    monkeypatch.setenv("CLAUDE_RETRO_DIR", str(tmp_path))
    r = subprocess.run(
        [sys.executable, str(SCRIPT)],  # no --log → default resolution
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        env={**__import__("os").environ, "CLAUDE_RETRO_DIR": str(tmp_path)},
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["runs_analyzed"] == 0
    assert out["log_path"] == str(tmp_path / "codify-runs.jsonl")
    assert "no ledger at" in r.stderr


def _import_default_log_path():
    # Load by explicit path under a unique name so codify-retro's and
    # spec-to-pr-retro's identically-named aggregate.py can't collide.
    import importlib.util
    spec = importlib.util.spec_from_file_location("_ut_codify_aggregate", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._default_log_path


def test_default_log_path_env_override(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_RETRO_DIR", str(tmp_path))
    assert _import_default_log_path()() == tmp_path / "codify-runs.jsonl"


def test_default_log_path_rejects_relative_override(monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_RETRO_DIR", "relative/dir")
    import pytest
    with pytest.raises(ValueError, match="absolute path"):
        _import_default_log_path()()


def test_default_log_path_default_is_claude_retro(monkeypatch) -> None:
    monkeypatch.delenv("CLAUDE_RETRO_DIR", raising=False)
    p = _import_default_log_path()()
    assert p.name == "codify-runs.jsonl"
    assert p.parent.name == "retro"
    assert p.parent.parent.name == "cla.io"
