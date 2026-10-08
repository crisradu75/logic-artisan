"""Tests for migrate_run_records.py — the one-off rewrite of old-shape spec-to-pr records.

Each fixture below is a real off-shape form from a fleet ledger, cut down and with
its change renamed: the shapes are what matter. Every one must come out passing the
writer's own shape check with every other field kept, and a second pass must change
nothing.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import log_run
import migrate_run_records as mig

_REPO = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO / "plugin-tests" / "scripts" / "migrate_run_records.py"
_SHAPE = log_run.SHAPES["spec-to-pr-runs.jsonl"]

# A dict-era record written at the end of a two-PR split: lower-case phase keys,
# `partial`, a warn with no reason, per-phase detail in side blocks, caps, a dict
# `asks`, no `ts` at all.
DICT_WITH_SIDE_BLOCKS = {
    "skill": "spec-to-pr", "change": "change-a", "mode": "description", "pr": 225,
    "caps": {"review_rounds": 1, "test_rounds": 3, "pr_rounds": 2},
    "phases": {"precheck": "ok", "propose": "ok", "review": "warn", "implement": "partial",
               "test": "ok", "ship": "ok", "revise": "ok", "archive": "skip", "handoff": "ok"},
    "review": {"size_gate": "large", "agents": ["design", "task", "spec"], "rounds_used": 2,
               "verdict": "RETHINK",
               "findings_by_round": [{"round": 1, "found": 17, "applied": 17}]},
    "implement": {"tasks_total": 55, "tasks_done": 15},
    "test": {"rounds_used": 1, "passed": 1821},
    "revise": {"rounds_used": 2, "agents_round1": ["code-reviewer", "silent-failure-hunter"],
               "findings_by_round": [{"round": 1, "found": 12, "sibling_instance": None},
                                     {"round": 2, "found": 1, "sibling_instance": 1}]},
    "asks": {"count": 3, "choices": ["inject-the-layer", "fix-the-design-here", "split"]},
    "routing": {"session_model": "opus", "escalate_up_fired": False},
}

# A chain-era record: `date` instead of `ts`, `rounds` instead of `rounds_used`,
# round-1 and round-2 agent lists, a `verdict` spelled with an underscore.
DATED_CHAIN = {
    "skill": "spec-to-pr", "change": "change-b", "date": "2026-09-27", "mode": "existing-change",
    "caps": {"review_rounds": 1, "pr_rounds": 2, "test_rounds": 3},
    "phases": {"propose": "ok", "review": "ok", "implement": "ok", "test": "ok",
               "ship": "ok", "revise": "ok", "archive": "ok", "handoff": "ok"},
    "review": {"verdict": "FIX_FIRST", "size_gate": "large", "agents": ["design", "task", "spec"]},
    "test": {"rounds": 1, "gate": "npm run verify"},
    "revise": {"rounds": 2,
               "findings_by_round": [{"round": 1, "found": 5, "sibling_instance": None},
                                     {"round": 2, "found": 3, "sibling_instance": 3}],
               "agents_round1": ["code-reviewer", "comment-analyzer"],
               "agents_round2": ["code-reviewer", "pr-test-analyzer"]},
    "inherits": {"supplied": 2, "honoured": 2},
    "routing": {"implement_delegated": True, "escalate_up_fired": False},
}

# Dict values per phase, `change_name`, `asks` as a bare count, no caps — so an
# inner `rounds_used` has no cap to pair with and must be kept beside the phase.
DICT_VALUES = {
    "ts": "2026-07-29T10:00:00Z", "change_name": "change-c", "mode": "existing-change",
    "phases": {"propose": "ok",
               "review": {"status": "ok", "verdict": "RETHINK", "size_gate": "large",
                          "agents": ["design", "task", "spec"], "rounds_used": 1,
                          "critical_found": 3},
               "implement": "ok", "test": "ok", "ship": "ok",
               "revise": {"status": "warn", "rounds_used": 1, "important_deferred": 5},
               "archive": "ok"},
    "asks": 2,
    "routing": {"revise_findings_by_tier": {"code-reviewer": 3, "comment-analyzer": 0}},
}

# Side blocks carrying `rounds` but no `caps` anywhere: a round count with no cap
# cannot be read, so nothing is lifted and the side block keeps it.
NO_CAPS = {
    "change": "change-j", "mode": "existing-change", "date": "2026-08-12",
    "phases": {"propose": "ok", "review": "ok", "revise": "ok"},
    "review": {"size_gate": "large", "agents": ["design", "task", "spec"],
               "verdict": "FIX FIRST", "rounds": 1},
    "revise": {"rounds": 1, "applied": 2},
}

# A list record with `phase` for `name`, lower-case, and the legacy severity shape.
PHASE_KEYED = {
    "ts": "2026-07-17T00:59:32Z", "change": "change-d", "mode": "existing-change",
    "phases": [{"phase": "propose", "status": "ok"},
               {"phase": "review", "status": "ok", "rounds_used": 1, "rounds_cap": 1,
                "size_gate": "large", "verdict": "FIX FIRST", "agents": ["design"]},
               {"phase": "revise", "status": "ok", "rounds_used": 1, "rounds_cap": 2}],
    "asks": [],
    "routing": {"revise_findings_by_tier": {"critical": 0, "important": 15,
                                            "phantom_rejected": 1}},
}

# Mixed: canonical agents, an underscore spelling, a retired agent name, a model
# tier, an agent with severity keys inside, and one with nothing inside.
MIXED_FINDINGS = {
    "ts": "2026-09-19T08:00:00Z", "change": "change-e", "mode": "existing-change",
    "phases": [{"name": "Propose", "status": "ok"}],
    "routing": {"models": {"opus": 2}, "revise_findings_by_tier": {
        "silent-failure-hunter": {"found": 4, "phantom": 0},
        "pr_test_analyzer": {"found": 2, "phantom": 1},
        "skill-reviewer": {"found": 1, "phantom": 0},
        "opus": {"found": 3, "phantom": 0},
        "type-design-analyzer": {"important": 1, "suggestion": 2},
        "comment-analyzer": {}}},
}

# A `started` date and nothing else to date it by; a date-only `ts`; a Review
# size gate outside the two values; a large gate with no agents listed.
STARTED_ONLY = {"change": "change-f", "mode": "existing-change", "started": "2026-08-30",
                "phases": [{"name": "Propose", "status": "ok"}]}
DATE_ONLY_TS = {"ts": "2026-09-28", "change": "change-g", "mode": "existing-change",
                "phases": [{"name": "Propose", "status": "ok"}]}
MEDIUM_GATE = {"ts": "2026-09-20T08:00:00Z", "change": "change-h", "mode": "existing-change",
               "phases": [{"name": "Review", "status": "ok", "rounds_used": 1, "rounds_cap": 1,
                           "size_gate": "medium", "agents": ["design"]}]}
LARGE_NO_AGENTS = {"ts": "2026-07-28T01:00:00Z", "change": "change-i", "mode": "existing-change",
                   "phases": [{"name": "Review", "status": "ok", "rounds_used": 1, "rounds_cap": 1,
                               "size_gate": "large", "agents": []}]}

FORMS = {
    "dict-with-side-blocks": DICT_WITH_SIDE_BLOCKS, "dated-chain": DATED_CHAIN,
    "dict-values": DICT_VALUES, "phase-keyed": PHASE_KEYED, "mixed-findings": MIXED_FINDINGS,
    "started-only": STARTED_ONLY, "date-only-ts": DATE_ONLY_TS, "medium-gate": MEDIUM_GATE,
    "large-no-agents": LARGE_NO_AGENTS, "no-caps": NO_CAPS,
}
_RUN_TIME = "2026-09-07T13:30:49Z"


def _migrate(rec: dict) -> tuple[dict, list[str]]:
    return mig.migrate(json.loads(json.dumps(rec)), lambda: _RUN_TIME)


def _phase(rec: dict, name: str) -> dict:
    return next(p for p in rec["phases"] if p["name"] == name)


@pytest.mark.parametrize("form", sorted(FORMS))
def test_every_fleet_form_maps_to_a_record_the_writer_accepts(form: str) -> None:
    assert log_run.shape_problem(FORMS[form], _SHAPE), "fixture should start off-shape"
    new, notes = _migrate(FORMS[form])
    assert log_run.shape_problem(new, _SHAPE) is None
    assert notes, "a migrated record says what changed"


# Fields a form renames or replaces; every other top-level field must survive as is.
_REPLACED = {"date", "change_name", "phases", "asks", "routing"}


@pytest.mark.parametrize("form", sorted(FORMS))
def test_every_other_field_is_kept(form: str) -> None:
    old = FORMS[form]
    new, _ = _migrate(old)
    for key, value in old.items():
        if key not in _REPLACED and not (key == "ts" and form == "date-only-ts"):
            assert new[key] == value, key
    if "routing" in old:
        for key, value in old["routing"].items():
            if key != "revise_findings_by_tier":
                assert new["routing"][key] == value


@pytest.mark.parametrize("form", sorted(FORMS))
def test_a_second_pass_changes_nothing(form: str) -> None:
    once, _ = _migrate(FORMS[form])
    twice, notes = mig.migrate(json.loads(json.dumps(once)), lambda: "2000-01-01T00:00:00Z")
    assert twice == once and notes == []


def test_a_dict_of_phases_becomes_the_list_in_its_own_order() -> None:
    new, _ = _migrate(DICT_WITH_SIDE_BLOCKS)
    assert [p["name"] for p in new["phases"]] == [
        "Precheck", "Propose", "Review", "Implement", "Test", "Ship", "Revise", "Archive", "Handoff"]
    review = _phase(new, "Review")
    # Lifted from the side block, with the cap from `caps`.
    assert review["rounds_used"] == 2 and review["rounds_cap"] == 1
    assert review["size_gate"] == "large" and review["verdict"] == "RETHINK"
    # A warn the record gave no reason for says so, rather than inventing one.
    assert review["reason"] == mig.NO_REASON
    # Review's own findings_by_round lacks `sibling_instance`, so it stays in the side block.
    assert "findings_by_round" not in review
    assert _phase(new, "Implement") == {"name": "Implement", "status": "warn",
                                        "reason": "partial (migrated record)"}
    assert _phase(new, "Test")["rounds_cap"] == 3
    revise = _phase(new, "Revise")
    assert revise["rounds_cap"] == 2
    assert revise["agents"] == ["code-reviewer", "silent-failure-hunter"]
    assert revise["findings_by_round"] == DICT_WITH_SIDE_BLOCKS["revise"]["findings_by_round"]
    assert _phase(new, "Archive") == {"name": "Archive", "status": "skip"}
    # No date anywhere in the record: the time the line entered git.
    assert new["ts"] == _RUN_TIME and next(iter(new)) == "ts"


def test_a_chain_record_takes_its_date_rounds_and_both_rounds_of_agents() -> None:
    new, notes = _migrate(DATED_CHAIN)
    assert new["ts"] == "2026-09-27T00:00:00Z" and "date" not in new
    assert list(new)[:3] == ["skill", "change", "ts"], "ts takes date's place"
    assert _phase(new, "Test")["rounds_used"] == 1
    revise = _phase(new, "Revise")
    assert (revise["rounds_used"], revise["rounds_cap"]) == (2, 2)
    assert revise["agents"] == ["code-reviewer", "comment-analyzer", "pr-test-analyzer"]
    # An off-list verdict is not lifted; it is still in the side block.
    assert "verdict" not in _phase(new, "Review")
    assert new["review"]["verdict"] == "FIX_FIRST"
    assert "ts from date (2026-09-27T00:00:00Z)" in notes


def test_dict_values_keep_an_unpaired_round_count_beside_the_phase() -> None:
    new, _ = _migrate(DICT_VALUES)
    assert new["change"] == "change-c" and "change_name" not in new
    review = _phase(new, "Review")
    assert review["rounds_used_unmapped"] == 1 and "rounds_used" not in review
    assert review["critical_found"] == 3
    assert _phase(new, "Revise")["reason"] == mig.NO_REASON
    assert new["asks"] == [{"header": mig.NOT_RECORDED, "choice": mig.NOT_RECORDED}] * 2
    assert new["routing"]["revise_findings_by_tier"] == {}
    assert new["routing"]["revise_findings_unmapped"] == {"code-reviewer": 3, "comment-analyzer": 0}


def test_a_round_count_with_no_cap_stays_in_its_side_block() -> None:
    new, _ = _migrate(NO_CAPS)
    for name in ("Review", "Revise"):
        assert not {k for k in _phase(new, name) if k.startswith("rounds")}, name
    assert new["review"]["rounds"] == 1 and new["revise"]["rounds"] == 1
    assert _phase(new, "Review")["verdict"] == "FIX FIRST"


def test_dict_asks_keep_their_choices() -> None:
    new, _ = _migrate(DICT_WITH_SIDE_BLOCKS)
    assert [a["choice"] for a in new["asks"]] == ["inject-the-layer", "fix-the-design-here", "split"]
    assert {a["header"] for a in new["asks"]} == {mig.NOT_RECORDED}


def test_a_phase_key_becomes_name_first_and_capitalised() -> None:
    new, _ = _migrate(PHASE_KEYED)
    assert [list(p)[0] for p in new["phases"]] == ["name"] * 3
    assert [p["name"] for p in new["phases"]] == ["Propose", "Review", "Revise"]
    assert new["routing"]["revise_findings_unmapped"] == {
        "critical": 0, "important": 15, "phantom_rejected": 1}


def test_findings_keep_the_canonical_agents_and_move_the_rest_aside() -> None:
    new, _ = _migrate(MIXED_FINDINGS)
    assert new["routing"]["revise_findings_by_tier"] == {
        "silent-failure-hunter": {"found": 4, "phantom": 0},
        "pr-test-analyzer": {"found": 2, "phantom": 1}}
    assert new["routing"]["revise_findings_unmapped"] == {
        "skill-reviewer": {"found": 1, "phantom": 0}, "opus": {"found": 3, "phantom": 0},
        "type-design-analyzer": {"important": 1, "suggestion": 2}, "comment-analyzer": {}}


def test_dates_come_from_the_record_before_git() -> None:
    new, _ = _migrate(STARTED_ONLY)
    assert new["ts"] == "2026-08-30T00:00:00Z" and new["started"] == "2026-08-30"
    new, _ = _migrate(DATE_ONLY_TS)
    assert new["ts"] == "2026-09-28T00:00:00Z"


@pytest.mark.parametrize("form", ["medium-gate", "large-no-agents"])
def test_a_size_gate_that_cannot_be_true_is_moved_aside(form: str) -> None:
    new, _ = _migrate(FORMS[form])
    review = _phase(new, "Review")
    assert "size_gate" not in review
    assert review["size_gate_unmapped"] == FORMS[form]["phases"][0]["size_gate"]


# --------------------------------------------------------------------------- #
# The script over a file
# --------------------------------------------------------------------------- #

def _main(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(_SCRIPT), *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", check=False,
                          cwd=None if cwd is None else str(cwd))


def _line(rec: dict) -> str:
    return json.dumps(rec, separators=(",", ":")) + "\n"


VALID = {"ts": "2026-10-06T21:34:01Z", "change": "change-ok", "mode": "description",
         "phases": [{"name": "Propose", "status": "ok"}]}
UNMAPPABLE = {"ts": "2026-10-01T00:00:00Z", "change": "change-x", "mode": "existing-change",
              "phases": [{"name": "Review", "status": "running"}]}


def test_the_file_is_rewritten_once_and_then_left_alone(tmp_path: Path) -> None:
    ledger = tmp_path / "spec-to-pr-runs.jsonl"
    # A valid line in a spacing no writer produces, to prove it is not re-serialised.
    valid_text = json.dumps(VALID) + "\n"
    ledger.write_text(valid_text + _line(DATED_CHAIN) + _line(UNMAPPABLE), encoding="utf-8")

    first = _main(str(ledger))
    assert first.returncode == 0, first.stderr
    assert "1 already in shape, 1 migrated, 1 cannot map" in first.stdout
    assert "line 3 (change-x): cannot map: `phases[0].status` must be one of" in first.stdout
    lines = ledger.read_text(encoding="utf-8").splitlines(keepends=True)
    assert lines[0] == valid_text, "a line already in shape is left byte for byte"
    assert lines[2] == _line(UNMAPPABLE), "a line it cannot map is left byte for byte"
    assert log_run.shape_problem(json.loads(lines[1]), _SHAPE) is None
    assert not list(tmp_path.glob("*.migrating"))

    after_first = ledger.read_bytes()
    second = _main(str(ledger))
    assert "0 migrated" in second.stdout
    assert ledger.read_bytes() == after_first


def test_a_dry_run_writes_nothing(tmp_path: Path) -> None:
    ledger = tmp_path / "spec-to-pr-runs.jsonl"
    ledger.write_text(_line(DATED_CHAIN), encoding="utf-8")
    before = ledger.read_bytes()
    r = _main(str(ledger), "--dry-run")
    assert "1 migrated" in r.stdout and "dry run, nothing written" in r.stdout
    assert ledger.read_bytes() == before


def _git(repo: Path, *args: str, when: str | None = None) -> None:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    if when:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = when
    subprocess.run(["git", *args], cwd=repo, env=env, check=True, capture_output=True)


def test_an_undated_record_takes_the_time_its_line_first_entered_git(tmp_path: Path) -> None:
    # The line is committed, then rewritten by a later commit — the case where
    # `git blame` names the rewrite and a run three weeks early gets its date.
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    ledger = repo / "spec-to-pr-runs.jsonl"
    undated = {k: v for k, v in STARTED_ONLY.items() if k != "started"}
    ledger.write_text(_line(VALID) + _line(undated), encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "run", when="2026-08-09T11:42:25+03:00")
    undated["note"] = "edited later"
    ledger.write_text(_line(VALID) + _line(undated), encoding="utf-8")
    _git(repo, "commit", "-qam", "rewrite", when="2026-09-04T01:22:08+03:00")

    copy = tmp_path / "copy.jsonl"
    copy.write_bytes(ledger.read_bytes())
    r = _main(str(copy), "--history-from", str(ledger))
    assert "ts from git history (2026-08-09T08:42:25Z)" in r.stdout, r.stdout

    # A working copy whose line differs from HEAD's borrows nothing.
    ledger.write_text(_line(VALID) + _line({**undated, "note": "uncommitted"}), encoding="utf-8")
    r = _main(str(ledger), "--dry-run")
    assert "cannot map: `ts` is required" in r.stdout, r.stdout


def test_a_missing_file_is_an_error(tmp_path: Path) -> None:
    r = _main(str(tmp_path / "absent.jsonl"))
    assert r.returncode == 1 and "no file at" in r.stderr


def test_this_repos_ledgers_pass_the_writers_check() -> None:
    # The migration's acceptance condition, held from here on: nothing in this
    # repo's own ledgers is off-shape, so a reader needs no path for old shapes.
    for name in ("spec-to-pr-runs.jsonl", "codify-runs.jsonl"):
        path = _REPO / "cla.io" / "retro" / name
        if not path.exists():
            continue
        for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                problem = log_run.shape_problem(json.loads(line), log_run.SHAPES[name])
                assert problem is None, f"{name}:{no}: {problem}"
