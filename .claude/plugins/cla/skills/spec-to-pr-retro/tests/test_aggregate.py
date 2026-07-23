"""Tests for aggregate.py — deterministic metrics over JSONL run records."""

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
        capture_output=True, text=True, check=False,
    )
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout), r.stderr


def test_empty_log_returns_zero(tmp_path: Path) -> None:
    out, _ = _run(tmp_path / "missing.jsonl")
    assert out["runs_analyzed"] == 0


def test_phase_outcome_tally(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"phases": [{"name": "Test", "status": "ok"}]},
        {"phases": [{"name": "Test", "status": "warn", "reason": "flaky"}]},
        {"phases": [{"name": "Test", "status": "ok"}]},
    ])
    out, _ = _run(log)
    assert out["phase_outcomes"]["Test"] == {"ok": 2, "warn": 1}
    assert out["warn_reasons"] == [{"reason": "flaky", "count": 1}]


def test_cap_exhaustion_and_round_counts(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"phases": [{"name": "Revise", "status": "ok",
                     "rounds_used": 2, "rounds_cap": 2}]},
        {"phases": [{"name": "Revise", "status": "ok",
                     "rounds_used": 1, "rounds_cap": 2}]},
    ])
    out, _ = _run(log)
    assert out["cap_exhaustion"]["revise"] == {"hit": 1, "total": 2}
    assert out["round_counts"]["revise"] == 1.5


def test_revise_agent_dispatch_count_only(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"phases": [{"name": "Revise", "status": "ok",
                     "agents": ["code-reviewer", "silent-failure-hunter"],
                     "critical": 1, "important": 3}]},
        {"phases": [{"name": "Revise", "status": "ok",
                     "agents": ["code-reviewer"],
                     "critical": 0, "important": 2}]},
    ])
    out, _ = _run(log)
    assert out["revise_agents"]["code-reviewer"] == {"dispatches": 2}
    assert out["revise_agents"]["silent-failure-hunter"] == {"dispatches": 1}
    # `revise_agents` carries dispatch counts ONLY — per-agent finding yield
    # lives in the separate `revise_findings` block (fed by
    # routing.revise_findings_by_tier), never inline on the dispatch entry.
    assert "mean_critical" not in out["revise_agents"]["code-reviewer"]
    assert "found" not in out["revise_agents"]["code-reviewer"]
    # These records carry no routing.revise_findings_by_tier, so no yield data.
    assert out["revise_findings"] == {}
    assert out["revise_findings_records"] == 0


def test_revise_findings_per_agent_yield(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"phases": [{"name": "Revise", "status": "ok",
                     "agents": ["code-reviewer", "type-design-analyzer"]}],
         "routing": {"revise_findings_by_tier": {
             "code_reviewer": {"found": 2, "phantom": 0},
             "type_design_analyzer": {"found": 5, "phantom": 1}}}},
        {"phases": [{"name": "Revise", "status": "ok",
                     "agents": ["code-reviewer", "type-design-analyzer"]}],
         "routing": {"revise_findings_by_tier": {
             "code_reviewer": {"found": 0, "phantom": 0},
             "type_design_analyzer": {"found": 1, "phantom": 0}}}},
        # A LEGACY model-tier shape: must NOT be tallied as an agent, but must
        # be counted so the retro knows coverage is partial.
        {"phases": [{"name": "Revise", "status": "ok", "agents": ["code-reviewer"]}],
         "routing": {"revise_findings_by_tier": {
             "opus": {"found": 3, "phantom": 0}, "sonnet": {"found": 2, "phantom": 0}}}},
    ])
    out, _ = _run(log)
    # Underscore agent keys normalize to hyphens and join the dispatch names.
    assert out["revise_findings"]["code-reviewer"] == {"found": 2, "phantom": 0, "runs": 2}
    assert out["revise_findings"]["type-design-analyzer"] == {"found": 6, "phantom": 1, "runs": 2}
    # opus/sonnet are model tiers, not agents — never appear in revise_findings.
    assert "opus" not in out["revise_findings"]
    assert out["revise_findings_records"] == 2
    assert out["revise_findings_legacy_records"] == 1


def _rfbt_record(rfbt: object) -> dict:
    """A minimal Revise record carrying the given revise_findings_by_tier value."""
    return {"phases": [{"name": "Revise", "status": "ok", "agents": ["code-reviewer"]}],
            "routing": {"revise_findings_by_tier": rfbt}}


def test_empty_findings_by_tier_counts_as_neither(tmp_path: Path) -> None:
    # An empty {} = a Revise round that logged no findings. It is NOT a legacy
    # shape, and counting it as one would inflate the denominator the yield gate
    # reads ("if legacy dominates, sample too thin") and wrongly suppress it.
    log = tmp_path / "runs.jsonl"
    _write_log(log, [_rfbt_record({})])
    out, stderr = _run(log)
    assert out["revise_findings"] == {}
    assert out["revise_findings_records"] == 0
    assert out["revise_findings_legacy_records"] == 0
    assert out["revise_findings_malformed_records"] == 0
    assert stderr == ""  # empty is legitimate "no data", not drift — no warning


def test_routing_without_findings_by_tier_counts_as_neither(tmp_path: Path) -> None:
    # routing present (model tally logged) but no findings field — the common
    # real case; counted in no bucket, no warning.
    log = tmp_path / "runs.jsonl"
    _write_log(log, [{"phases": [{"name": "Revise", "status": "ok",
                                  "agents": ["code-reviewer"]}],
                      "routing": {"implement_delegated": True}}])
    out, stderr = _run(log)
    assert out["revise_findings_records"] == 0
    assert out["revise_findings_legacy_records"] == 0
    assert out["revise_findings_malformed_records"] == 0
    assert stderr == ""


def test_legacy_severity_shape_counted_as_legacy_not_agent(tmp_path: Path) -> None:
    # The severity legacy shape (scalar-int values, incl. phantom_rejected which
    # normalizes to phantom-rejected) is genuine pre-pin data → legacy, no drift.
    log = tmp_path / "runs.jsonl"
    _write_log(log, [_rfbt_record({"critical": 2, "important": 3, "phantom_rejected": 1})])
    out, stderr = _run(log)
    assert out["revise_findings"] == {}
    assert out["revise_findings_records"] == 0
    assert out["revise_findings_legacy_records"] == 1
    assert out["revise_findings_malformed_records"] == 0
    assert stderr == ""


def test_non_dict_findings_by_tier_is_malformed_and_warns(tmp_path: Path) -> None:
    # Present but wrong type (a producer regressing the field to a string/list).
    # Must NOT vanish silently — warn + count malformed, per the module contract.
    log = tmp_path / "runs.jsonl"
    _write_log(log, [_rfbt_record("n/a")])
    out, stderr = _run(log)
    assert out["revise_findings_records"] == 0
    assert out["revise_findings_legacy_records"] == 0
    assert out["revise_findings_malformed_records"] == 1
    assert "expected dict" in stderr


def test_unknown_agent_key_is_malformed_not_legacy(tmp_path: Path) -> None:
    # A renamed/misspelled agent must not masquerade as benign legacy history —
    # it's current-producer drift, so malformed + warn.
    log = tmp_path / "runs.jsonl"
    _write_log(log, [_rfbt_record({"brand-new-analyzer": {"found": 9, "phantom": 2}})])
    out, stderr = _run(log)
    assert out["revise_findings"] == {}
    assert out["revise_findings_records"] == 0
    assert out["revise_findings_legacy_records"] == 0
    assert out["revise_findings_malformed_records"] == 1
    assert "producer drift" in stderr


def test_agent_key_non_dict_value_is_malformed(tmp_path: Path) -> None:
    # A correct agent key with a corrupt scalar value is drift, not legacy.
    log = tmp_path / "runs.jsonl"
    _write_log(log, [_rfbt_record({"code_reviewer": 5})])
    out, stderr = _run(log)
    assert out["revise_findings"] == {}
    assert out["revise_findings_records"] == 0
    assert out["revise_findings_malformed_records"] == 1
    assert "expected dict" in stderr


def test_negative_found_phantom_clamped_to_zero(tmp_path: Path) -> None:
    # A negative count is nonsensical and would drag an agent's cumulative yield
    # below its true total — clamp to 0 rather than sum it.
    log = tmp_path / "runs.jsonl"
    _write_log(log, [_rfbt_record({"code_reviewer": {"found": -5, "phantom": -1}})])
    out, _ = _run(log)
    assert out["revise_findings"]["code-reviewer"] == {"found": 0, "phantom": 0, "runs": 1}
    assert out["revise_findings_records"] == 1


def test_duplicate_agent_spelling_counted_once(tmp_path: Path) -> None:
    # code_reviewer and code-reviewer both normalize to code-reviewer in one
    # record — runs must increment once, not twice (mirrors _tally_agents dedup).
    log = tmp_path / "runs.jsonl"
    _write_log(log, [_rfbt_record({"code_reviewer": {"found": 1, "phantom": 0},
                                   "code-reviewer": {"found": 2, "phantom": 0}})])
    out, stderr = _run(log)
    assert out["revise_findings"]["code-reviewer"]["runs"] == 1
    assert out["revise_findings"]["code-reviewer"]["found"] == 1  # first wins, second skipped
    assert "keyed twice" in stderr


def test_plugin_dev_colon_key_normalizes_and_matches(tmp_path: Path) -> None:
    # plugin-dev:skill-reviewer is the one canonical key whose colon must map to
    # a hyphen to join the whitelist.
    log = tmp_path / "runs.jsonl"
    _write_log(log, [_rfbt_record({"plugin-dev:skill-reviewer": {"found": 4, "phantom": 1}})])
    out, _ = _run(log)
    assert out["revise_findings"]["plugin-dev-skill-reviewer"] == {
        "found": 4, "phantom": 1, "runs": 1}
    assert out["revise_findings_records"] == 1


def test_mixed_agent_and_unknown_key_matches_but_warns(tmp_path: Path) -> None:
    # A valid agent alongside a stray key: counts as a per-agent record (agent
    # data is real) but the stray key must not be dropped silently.
    log = tmp_path / "runs.jsonl"
    _write_log(log, [_rfbt_record({"code_reviewer": {"found": 1, "phantom": 0},
                                   "mystery": {"found": 9, "phantom": 9}})])
    out, stderr = _run(log)
    assert out["revise_findings"]["code-reviewer"] == {"found": 1, "phantom": 0, "runs": 1}
    assert out["revise_findings_records"] == 1
    assert out["revise_findings_malformed_records"] == 0
    assert "stray keys ignored" in stderr


def test_limit_keeps_last_n(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [{"change": f"c{i}", "phases": []} for i in range(20)])
    out, _ = _run(log, limit=5)
    assert out["runs_analyzed"] == 5


def test_limit_zero_returns_all(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [{"change": f"c{i}", "phases": []} for i in range(7)])
    out, _ = _run(log, limit=0)
    assert out["runs_analyzed"] == 7


def test_malformed_line_skipped_and_counted(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    log.write_text('{"change":"ok","phases":[]}\nnot json\n{"change":"ok2","phases":[]}\n',
                   encoding="utf-8")
    out, stderr = _run(log)
    assert "skipping malformed" in stderr
    assert out["runs_analyzed"] == 2
    assert out["skipped_records"] == 1


def test_missing_phases_key_warns(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [{"change": "drifted"}])  # no phases key at all
    out, stderr = _run(log)
    assert "missing or non-list `phases`" in stderr
    assert out["runs_analyzed"] == 1
    assert out["phase_outcomes"] == {}


def test_report_chars_mean_per_phase(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"phases": [{"name": "Review", "status": "ok", "report_chars": 400}]},
        {"phases": [{"name": "Review", "status": "ok", "report_chars": 600}]},
        {"phases": [{"name": "Test", "status": "ok"}]},  # no report_chars — excluded
    ])
    out, _ = _run(log)
    assert out["report_chars"] == {"Review": {"mean": 500.0, "n": 2}}


def test_report_chars_two_phases_independent(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"phases": [
            {"name": "Review", "status": "ok", "report_chars": 400},
            {"name": "Test", "status": "ok", "report_chars": 900},
        ]},
    ])
    out, _ = _run(log)
    assert out["report_chars"] == {
        "Review": {"mean": 400.0, "n": 1},
        "Test": {"mean": 900.0, "n": 1},
    }


def test_report_chars_negative_clamped_to_zero(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"phases": [{"name": "Review", "status": "ok", "report_chars": -5}]},
    ])
    out, stderr = _run(log)
    assert "negative, clamped to 0" in stderr
    assert out["report_chars"] == {"Review": {"mean": 0.0, "n": 1}}


def test_report_chars_type_confused_warns_and_coerces(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"phases": [{"name": "Review", "status": "ok", "report_chars": "big"}]},
    ])
    out, stderr = _run(log)
    assert "report_chars='big' not int" in stderr
    assert out["report_chars"] == {}
    assert out["report_chars_coerced"] == 1


def test_report_chars_bool_rejected(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"phases": [{"name": "Review", "status": "ok", "report_chars": True}]},
    ])
    out, stderr = _run(log)
    assert "report_chars=True is bool" in stderr
    assert out["report_chars"] == {}
    assert out["report_chars_coerced"] == 1


def test_report_chars_mixed_valid_and_malformed_same_run(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"phases": [{"name": "Review", "status": "ok", "report_chars": 400}]},
        {"phases": [{"name": "Review", "status": "ok", "report_chars": "bad"}]},
    ])
    out, _ = _run(log)
    assert out["report_chars"] == {"Review": {"mean": 400.0, "n": 1}}
    assert out["report_chars_coerced"] == 1


def test_type_confused_rounds_used_warns(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"phases": [{"name": "Revise", "status": "ok",
                     "rounds_used": "2", "rounds_cap": 2}]},
    ])
    out, stderr = _run(log)
    assert "rounds_used='2' not int" in stderr
    assert out["cap_exhaustion"]["revise"] == {"hit": 0, "total": 0}


def test_type_confused_agents_warns(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"phases": [{"name": "Revise", "status": "ok",
                     "agents": "code-reviewer"}]},   # string, not list
    ])
    out, stderr = _run(log)
    assert "Revise `agents` not list" in stderr
    assert out["revise_agents"] == {}


def test_asks_distribution(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"phases": [], "asks": [{"header": "Scope split", "choice": "tight"}]},
        {"phases": [], "asks": [{"header": "Scope split", "choice": "tight"}]},
        {"phases": [], "asks": [{"header": "Scope split", "choice": "full"}]},
    ])
    out, _ = _run(log)
    assert out["asks"] == [{"header": "Scope split",
                            "choices": {"tight": 2, "full": 1}}]


def test_review_size_gate_and_verdicts(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"phases": [{"name": "Review", "status": "ok",
                     "size_gate": "small", "verdict": "READY",
                     "verified_claims_count": 5}]},
        {"phases": [{"name": "Review", "status": "ok",
                     "size_gate": "small", "verdict": "FIX FIRST",
                     "verified_claims_count": 4}]},
        {"phases": [{"name": "Review", "status": "warn",
                     "size_gate": "large", "verdict": "RETHINK",
                     "verified_claims_count": 8,
                     "agents": ["design", "task", "spec"]}]},
    ])
    out, _ = _run(log)
    assert out["review_size_gate"] == {"small": 2, "large": 1}
    assert out["review_verdicts"] == {"READY": 1, "FIX FIRST": 1, "RETHINK": 1}
    assert out["review_verified_claims"] == {"mean": round((5 + 4 + 8) / 3, 2), "n": 3}
    assert out["review_agents"] == {
        "design": {"dispatches": 1},
        "task": {"dispatches": 1},
        "spec": {"dispatches": 1},
    }
    assert out["review_gate_pair_mismatches"] == 0


def test_review_missing_optional_fields_emits_no_warnings(tmp_path: Path) -> None:
    """Happy-path small-mode entry without `agents` must NOT emit stderr noise —
    a future regression that warns on legitimate absence would mask real drift."""
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"phases": [{"name": "Review", "status": "ok"}]},
    ])
    out, stderr = _run(log)
    assert out["review_size_gate"] == {}
    assert out["review_verdicts"] == {}
    assert out["review_verified_claims"] == {"mean": 0.0, "n": 0}
    assert out["review_agents"] == {}
    assert out["review_gate_pair_mismatches"] == 0
    assert stderr == "", f"unexpected stderr: {stderr!r}"


def test_review_agents_type_confusion_warns(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"phases": [{"name": "Review", "status": "ok",
                     "size_gate": "large", "agents": "design"}]},
    ])
    out, stderr = _run(log)
    assert "Review `agents` not list" in stderr
    assert out["review_agents"] == {}


def test_review_size_gate_unknown_value_surfaced(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"phases": [{"name": "Review", "status": "ok", "size_gate": "medium"}]},
    ])
    out, stderr = _run(log)
    assert "'medium'" in stderr and "size_gate" in stderr
    assert out["review_size_gate"] == {}
    assert out["review_size_gate_unknown"] == {"medium": 1}


def test_review_verdict_unknown_value_surfaced(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"phases": [{"name": "Review", "status": "ok", "verdict": "ready"}]},  # lowercase typo
    ])
    out, stderr = _run(log)
    assert "'ready'" in stderr and "verdict" in stderr
    assert out["review_verdicts"] == {}
    assert out["review_verdicts_unknown"] == {"ready": 1}


def test_duplicate_agents_count_once_with_warning(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"phases": [{"name": "Review", "status": "ok", "size_gate": "large",
                     "agents": ["design", "design", "task"]}]},
    ])
    out, stderr = _run(log)
    assert out["review_agents"] == {"design": {"dispatches": 1}, "task": {"dispatches": 1}}
    assert "duplicates" in stderr


def test_size_gate_agents_pair_mismatch_detected(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        # small mode should have no agents — this is a producer bug
        {"phases": [{"name": "Review", "status": "ok", "size_gate": "small",
                     "agents": ["design"]}]},
        # large mode requires agents — empty list is a producer bug
        {"phases": [{"name": "Review", "status": "ok", "size_gate": "large",
                     "agents": []}]},
    ])
    out, stderr = _run(log)
    assert out["review_gate_pair_mismatches"] == 2
    assert "contradicts agents" in stderr


def test_review_and_revise_agents_independent(tmp_path: Path) -> None:
    """Renaming `agent_dispatches` → `revise_agent_dispatches` while adding
    `review_agent_dispatches` is the kind of refactor that could cross-wire
    the two counters. Lock the independence in."""
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"phases": [
            {"name": "Review", "status": "ok", "size_gate": "large",
             "agents": ["design"]},
            {"name": "Revise", "status": "ok", "agents": ["design", "silent-failure-hunter"]},
        ]},
    ])
    out, _ = _run(log)
    assert out["review_agents"] == {"design": {"dispatches": 1}}
    assert out["revise_agents"] == {
        "design": {"dispatches": 1},
        "silent-failure-hunter": {"dispatches": 1},
    }


def test_non_string_agent_entry_bucketed_by_type(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"phases": [{"name": "Review", "status": "ok", "size_gate": "large",
                     "agents": ["design", 42, None]}]},
    ])
    out, stderr = _run(log)
    assert out["review_agents"] == {"design": {"dispatches": 1}}
    assert out["review_agents_unknown_types"] == {"int": 1, "NoneType": 1}
    assert "non-string" in stderr


def test_version_bump_misses(tmp_path: Path) -> None:
    log = tmp_path / "runs.jsonl"
    _write_log(log, [
        {"phases": [{"name": "Ship", "status": "warn", "version_bumped": False}]},
        {"phases": [{"name": "Ship", "status": "ok", "version_bumped": True}]},
    ])
    out, _ = _run(log)
    assert out["version_bump_misses"] == 1


def test_missing_ledger_warns_and_reports_zero(tmp_path: Path) -> None:
    # The "no file" branch must name where it looked (silent-misconfig guard).
    import os
    r = subprocess.run(
        [sys.executable, str(SCRIPT)],  # no --log → default resolution
        capture_output=True, text=True, check=False,
        env={**os.environ, "CLAUDE_RETRO_DIR": str(tmp_path)},
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["runs_analyzed"] == 0
    assert out["log_path"] == str(tmp_path / "spec-to-pr-runs.jsonl")
    assert "no ledger at" in r.stderr


def _import_default_log_path():
    # Load by explicit path under a unique name so spec-to-pr-retro's and
    # codify-retro's identically-named aggregate.py can't collide.
    import importlib.util
    spec = importlib.util.spec_from_file_location("_ut_s2p_aggregate", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._default_log_path


def test_default_log_path_env_override(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_RETRO_DIR", str(tmp_path))
    assert _import_default_log_path()() == tmp_path / "spec-to-pr-runs.jsonl"


def test_default_log_path_rejects_relative_override(monkeypatch) -> None:
    monkeypatch.setenv("CLAUDE_RETRO_DIR", "relative/dir")
    import pytest
    with pytest.raises(ValueError, match="absolute path"):
        _import_default_log_path()()


def test_default_log_path_default_is_claude_retro(monkeypatch) -> None:
    monkeypatch.delenv("CLAUDE_RETRO_DIR", raising=False)
    p = _import_default_log_path()()
    assert p.name == "spec-to-pr-runs.jsonl"
    assert p.parent.name == "retro"
    assert p.parent.parent.name == "cla.io"
