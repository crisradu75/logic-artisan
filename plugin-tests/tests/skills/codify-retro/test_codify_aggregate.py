"""Tests for codify_aggregate.py — deterministic metrics over codify-runs JSONL."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[4] / ".claude" / "plugins" / "cla" / "skills" / "codify-retro" / "scripts" / "codify_aggregate.py"


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
    assert "`suggestions` is list, expected object" in err
    # Dropping the whole block loses both halves of apply_rate while
    # `runs_analyzed` still counts the record, so it is drift, not a coerced count.
    assert out["shape_drift_fields"] == {"suggestions": 1}
    assert out["shape_drift_records"] == 1
    assert out["coerced_fields"] == 0, "a dropped container is not a coerced field"


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
    # Load by explicit path: the aggregator is a `scripts/` file reached by
    # path, not a module on `sys.path`, so an explicit-path load is what makes
    # it importable at all here.
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


# --- Container-shape drift: warned about, and now tallied --------------------
#
# This module's own docstring already states the rule: a bad record is skipped
# with a stderr warning AND tallied, so the consumer sees the noise floor in
# structured output. `coerced_fields` covers a wrong-typed COUNT and
# `skipped_records` a whole unparseable line; a list or object field arriving as
# something else fell between them and was tallied nowhere.


def _run_multi(logs: list[Path], limit: int = 10) -> tuple[dict, str]:
    """`_run`, but for the multi-ledger form of --log."""
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--limit", str(limit), "--log", *[str(p) for p in logs]],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout), r.stderr


def test_non_list_re_offenses_is_tallied(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [{"re_offenses": 3}, {"re_offenses": []}])
    out, err = _run(log)
    assert out["runs_analyzed"] == 2, "the good record must still be analyzed"
    assert out["shape_drift_fields"] == {"re_offenses": 1}
    assert out["shape_drift_records"] == 1
    assert "`re_offenses` is int" in err


def test_non_list_rejected_lessons_is_tallied(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [{"rejected_lessons": "none"}])
    out, err = _run(log)
    assert out["shape_drift_fields"] == {"rejected_lessons": 1}
    assert "`rejected_lessons` is str" in err


def test_non_dict_maintenance_is_tallied(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [{"maintenance": 51}])
    out, err = _run(log)
    assert out["shape_drift_fields"] == {"maintenance": 1}
    assert "`maintenance` is int" in err


def test_one_record_drifting_twice_counts_once_as_a_record(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [{"re_offenses": 3, "rejected_lessons": "none"}])
    out, _ = _run(log)
    assert out["shape_drift_fields"] == {"re_offenses": 1, "rejected_lessons": 1}
    assert out["shape_drift_records"] == 1


def test_clean_records_are_not_flagged_as_drift(tmp_path: Path) -> None:
    """Well-formed input must read zero — the false-POSITIVE direction.

    Not a non-vacuity guard, despite an earlier name that said so: a review agent
    patched an `aggregate()` that kept both fields and never incremented them, and
    this test passed against it while every sibling `..._is_tallied` test failed.
    Those siblings are what make the counter non-vacuous. This one makes zero
    meaningful, which is the other half and is worth its own test — a counter that
    fires on clean records would make the alarm useless in the opposite way.
    """
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"re_offenses": [{"lesson": "x", "escalated_to": "hook"}],
         "rejected_lessons": ["y"],
         "maintenance": {"failure_modes_bullets": 51, "trimmed": False}},
    ])
    out, _ = _run(log)
    assert out["shape_drift_fields"] == {}
    assert out["shape_drift_records"] == 0
    assert out["re_offenses"] == [{"lesson": "x", "count": 1}]
    assert out["rejected_lessons"] == [{"lesson": "y", "count": 1}]


# --- Multi-ledger --log ------------------------------------------------------


def test_multiple_logs_aggregate_into_one_result(tmp_path: Path) -> None:
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    _write_log(a, [{"suggestions": {"proposed": 2, "applied": 2, "rejected": 0}}])
    _write_log(b, [{"suggestions": {"proposed": 3, "applied": 1, "rejected": 2}}])
    out, _ = _run_multi([a, b])
    assert out["runs_analyzed"] == 2
    assert out["suggestions"]["proposed"] == 5
    assert out["suggestions"]["rejected"] == 2
    assert out["log_paths"] == [str(a), str(b)]


def test_single_log_still_reports_log_path_as_a_string(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [{"process_issue": False}])
    out, _ = _run(log)
    assert out["log_path"] == str(log)
    assert out["log_paths"] == [str(log)]


def test_multiple_logs_omit_log_path_rather_than_naming_one(tmp_path: Path) -> None:
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    _write_log(a, [{"process_issue": False}])
    _write_log(b, [{"process_issue": False}])
    out, _ = _run_multi([a, b])
    assert "log_path" not in out
    assert out["log_paths"] == [str(a), str(b)]


def test_limit_applies_per_ledger(tmp_path: Path) -> None:
    # The contract is identical to spec-to-pr's and was untested here.
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    _write_log(a, [{"process_issue": False} for _ in range(5)])
    _write_log(b, [{"process_issue": False} for _ in range(5)])
    out, _ = _run_multi([a, b], limit=2)
    assert out["runs_analyzed"] == 4, "limit is the last N from EACH ledger, not overall"


def test_skipped_records_sum_across_ledgers(tmp_path: Path) -> None:
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    a.write_text(json.dumps({"process_issue": False}) + "\n{ broken\n", encoding="utf-8")
    b.write_text(json.dumps({"process_issue": False}) + "\nalso broken\n", encoding="utf-8")
    out, _ = _run_multi([a, b])
    assert out["runs_analyzed"] == 2
    assert out["skipped_records"] == 2


def test_ledgers_names_a_path_that_did_not_resolve(tmp_path: Path) -> None:
    good, missing = tmp_path / "a.jsonl", tmp_path / "nope.jsonl"
    _write_log(good, [{"process_issue": False}])
    out, _ = _run_multi([good, missing])
    assert out["ledgers"] == [
        {"path": str(good), "found": True, "records": 1, "skipped": 0},
        {"path": str(missing), "found": False, "records": 0, "skipped": 0},
    ]


def test_a_record_drifting_in_the_ts_loop_and_the_record_loop_counts_once(
        tmp_path: Path) -> None:
    """`shape_drift_records` must never exceed `runs_analyzed`.

    `ts` was validated in a SECOND loop that ran after the record loop closed, so
    it did a bare `shape_drift_records += 1` outside the per-record set. A record
    drifting in both places was counted twice, and a per-record counter larger than
    the record count contradicts the sentence both SKILL.md files use to explain
    the field — that it counts records whose metrics ran on less than they claim.
    """
    log = tmp_path / "runs.jsonl"
    _write_log(log, [{"ts": 123, "re_offenses": "not-a-list"}])
    out, _ = _run(log)
    assert out["runs_analyzed"] == 1
    assert out["shape_drift_records"] == 1, "one record, counted once"
    assert out["shape_drift_fields"] == {"re_offenses": 1, "ts": 1}
    assert out["shape_drift_records"] <= out["runs_analyzed"], \
        "a per-record counter can never exceed the record count"


def test_a_fleet_where_every_ledger_is_missing_does_not_crash(tmp_path: Path) -> None:
    """The suppression block consumed a key the empty-records return does not carry.

    `aggregate([])` returns a three-key skeleton with no `maintenance`, so a fleet
    run whose every path was mistyped died with `KeyError: 'maintenance'` and
    printed no JSON at all — in the one aggregator hardened to survive a malformed
    record, on the exact case the `ledgers` array exists to make visible.
    """
    out, _ = _run_multi([tmp_path / "nope-a.jsonl", tmp_path / "nope-b.jsonl"])
    assert out["runs_analyzed"] == 0
    assert [entry["found"] for entry in out["ledgers"]] == [False, False]
    assert out["shape_drift_records"] == 0


def test_per_repo_fields_are_suppressed_in_fleet_mode(tmp_path: Path) -> None:
    # These describe ONE repo's own files. Pooled across repos, `_latest` means
    # "whichever ledger was listed last" and `_trend` interleaves unrelated repos —
    # and this loop's SKILL.md gates directly on them.
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    _write_log(a, [{"maintenance": {"failure_modes_bullets": 40, "live_log_entries": 9},
                    "output_chars": 5000}])
    _write_log(b, [{"maintenance": {"failure_modes_bullets": 3, "live_log_entries": 1},
                    "output_chars": 100}])
    single, _ = _run(a)
    assert single["maintenance"]["failure_modes_bullets_latest"] == 40
    assert "per_repo_fields_suppressed" not in single

    fleet, _ = _run_multi([a, b])
    assert fleet["runs_analyzed"] == 2
    assert fleet["per_repo_fields_suppressed"] is True
    assert fleet["maintenance"]["failure_modes_bullets_latest"] is None
    assert fleet["maintenance"]["failure_modes_bullets_trend"] == []
    assert fleet["maintenance"]["live_log_entries_latest"] is None
    assert fleet["output_chars"] == {"latest": None, "trend": [], "mean": 0.0}


def test_explicit_null_optional_container_is_not_drift(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [{"re_offenses": None, "rejected_lessons": None, "maintenance": None}])
    out, _ = _run(log)
    assert out["shape_drift_fields"] == {}
    assert out["shape_drift_records"] == 0


def test_entry_level_drift_reaches_the_tally(tmp_path: Path) -> None:
    # Entry-level drift used to warn and be counted nowhere.
    log = tmp_path / "runs.jsonl"
    _write_log(log, [{"re_offenses": [{"lesson": None, "escalated_to": "hook"}]},
                     {"rejected_lessons": [7]}])
    out, _ = _run(log)
    assert out["shape_drift_fields"] == {"re_offenses": 1, "rejected_lessons": 1}
    assert out["shape_drift_records"] == 2


# --- effectiveness: the outcome metric (Step 2.5's tally) -------------------
# Every other block in this aggregate counts what a run WROTE. These count
# whether what earlier runs wrote actually HELD, which is the only question the
# loop exists to answer and the one it went years without asking.


def test_effectiveness_pools_and_computes_prevention_rate(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"effectiveness": {"prevented": 6, "re_offended": 2, "not_exercised": 40}},
        {"effectiveness": {"prevented": 2, "re_offended": 2, "not_exercised": 41}},
    ])
    out, _ = _run(log)
    # 8 held of 12 exercised.
    assert out["effectiveness"]["prevented"] == 8
    assert out["effectiveness"]["re_offended"] == 4
    assert out["effectiveness"]["prevention_rate"] == 0.67
    assert out["effectiveness"]["records"] == 2


def test_not_exercised_is_out_of_the_denominator(tmp_path: Path) -> None:
    """A rule the session never came near is evidence of nothing.

    Counting it would let the rate climb by merely growing the checklist —
    rewarding the exact bloat Step 2.6 exists to fight. Same exercised counts,
    wildly different `not_exercised`, and the rate must not move.
    """
    lean = tmp_path / "lean.jsonl"
    bloated = tmp_path / "bloated.jsonl"
    _write_log(lean, [{"effectiveness": {"prevented": 1, "re_offended": 1,
                                         "not_exercised": 0}}])
    _write_log(bloated, [{"effectiveness": {"prevented": 1, "re_offended": 1,
                                            "not_exercised": 500}}])
    lean_out, _ = _run(lean)
    bloated_out, _ = _run(bloated)
    assert lean_out["effectiveness"]["prevention_rate"] == 0.5
    assert bloated_out["effectiveness"]["prevention_rate"] == 0.5
    assert bloated_out["effectiveness"]["not_exercised"] == 500


def test_prevention_rate_is_none_not_zero_when_nothing_was_exercised(
        tmp_path: Path) -> None:
    """Diverges from `apply_rate`'s 0.0 on purpose — do not "fix" it to match.

    Low means BAD for this rate, so a 0.0 placeholder is an empty sample wearing
    a failing grade, and the SKILL.md heuristic gating on `< 0.5` would fire on a
    window that measured nothing at all.
    """
    log = tmp_path / "runs.jsonl"
    _write_log(log, [{"effectiveness": {"prevented": 0, "re_offended": 0,
                                        "not_exercised": 12}}])
    out, _ = _run(log)
    assert out["effectiveness"]["prevention_rate"] is None
    # The sibling rate on the same record set still uses 0.0 — the divergence is
    # between the two fields, and that is the point.
    assert out["suggestions"]["apply_rate"] == 0.0


def test_a_ledger_with_no_effectiveness_field_reports_zero_records(
        tmp_path: Path) -> None:
    """The whole existing corpus looks like this — the field is optional-additive."""
    log = tmp_path / "runs.jsonl"
    _write_log(log, [{"ts": "2026-06-24",
                      "suggestions": {"proposed": 4, "applied": 4, "rejected": 0}}])
    out, _ = _run(log)
    assert out["effectiveness"]["records"] == 0
    assert out["effectiveness"]["prevention_rate"] is None
    assert out["shape_drift_fields"] == {}


def test_records_counts_only_the_runs_that_carried_a_tally(tmp_path: Path) -> None:
    """A rate drawn from 1 of 3 runs must not read as one drawn from 3."""
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"effectiveness": {"prevented": 3, "re_offended": 1, "not_exercised": 9}},
        {},
        {"suggestions": {"proposed": 2, "applied": 1, "rejected": 1}},
    ])
    out, _ = _run(log)
    assert out["runs_analyzed"] == 3
    assert out["effectiveness"]["records"] == 1


def test_a_record_whose_every_count_is_malformed_is_not_counted_as_a_record(
        tmp_path: Path) -> None:
    """`_sum_counts` reports coercions, not usability — hence the separate probe."""
    log = tmp_path / "runs.jsonl"
    _write_log(log, [{"effectiveness": {"prevented": "six", "re_offended": None,
                                        "not_exercised": True}}])
    out, err = _run(log)
    assert out["effectiveness"]["records"] == 0
    assert out["effectiveness"]["prevention_rate"] is None
    assert out["coerced_fields"] >= 1
    assert "prevented='six' not int" in err


def test_a_partly_malformed_block_still_counts_and_warns_once(tmp_path: Path) -> None:
    """One usable count makes the record a contributor; the bad one is warned ONCE.

    The probe runs over the same block the sum then walks, so using the coercing
    form for both would report a single bad value twice and overstate the noise
    floor a reader is told to check first.
    """
    log = tmp_path / "runs.jsonl"
    _write_log(log, [{"effectiveness": {"prevented": 5, "re_offended": "two",
                                        "not_exercised": 3}}])
    out, err = _run(log)
    assert out["effectiveness"]["records"] == 1
    assert out["effectiveness"]["prevented"] == 5
    assert out["effectiveness"]["re_offended"] == 0
    assert out["effectiveness"]["prevention_rate"] == 1.0
    assert err.count("re_offended='two' not int") == 1


def test_bool_counts_are_rejected_like_every_other_count(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [{"effectiveness": {"prevented": True, "re_offended": 1,
                                        "not_exercised": 0}}])
    out, err = _run(log)
    assert out["effectiveness"]["prevented"] == 0
    assert "is bool, expected int" in err


def test_non_dict_effectiveness_is_shape_drift(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [{"effectiveness": "n/a"}])
    out, err = _run(log)
    assert out["shape_drift_fields"] == {"effectiveness": 1}
    assert out["shape_drift_records"] == 1
    assert out["effectiveness"]["records"] == 0
    assert "`effectiveness` is str" in err


def test_explicit_null_effectiveness_is_not_drift(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [{"effectiveness": None}])
    out, _ = _run(log)
    assert out["shape_drift_fields"] == {}
    assert out["effectiveness"]["records"] == 0


def test_effectiveness_is_pooled_across_repos_not_suppressed(tmp_path: Path) -> None:
    """Deliberately NOT in the per-repo suppression list beside `output_chars`.

    Those fields measure ONE repo's files, which do not add up. These count
    events — a rule was exercised and held, or failed — and events do.
    """
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    _write_log(a, [{"effectiveness": {"prevented": 3, "re_offended": 1,
                                      "not_exercised": 5}, "output_chars": 1000}])
    _write_log(b, [{"effectiveness": {"prevented": 1, "re_offended": 3,
                                      "not_exercised": 5}, "output_chars": 2000}])
    out, _ = _run_multi([a, b])
    assert out["per_repo_fields_suppressed"] is True
    assert out["output_chars"]["latest"] is None       # per-repo → suppressed
    assert out["effectiveness"]["prevented"] == 4      # events → pooled
    assert out["effectiveness"]["re_offended"] == 4
    assert out["effectiveness"]["prevention_rate"] == 0.5
    assert out["effectiveness"]["records"] == 2


def test_a_fleet_of_missing_ledgers_still_reports_no_effectiveness(
        tmp_path: Path) -> None:
    """The empty-record skeleton omits `effectiveness` entirely.

    Safe only because a consumer's `.get(...)` then yields None — the same value
    the populated path uses for "not measured" — rather than a 0.0 that reads as
    a failing grade. Pinning it so the skeleton is not "helpfully" filled with zeros.
    """
    out, _ = _run_multi([tmp_path / "nope-a.jsonl", tmp_path / "nope-b.jsonl"])
    assert out["runs_analyzed"] == 0
    assert out.get("effectiveness", {}).get("prevention_rate") is None
