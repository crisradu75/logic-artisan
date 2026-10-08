"""Tests for the shared log_run.py — atomic JSONL append into a run ledger.

Ported from the two per-skill copies this replaced (spec-to-pr's and
codify-learnings's `tests/test_log_run.py`, which were themselves near-identical),
plus the cases the new `<ledger>` argument introduces, plus the record-shape check
for the two ledgers that have one. The plumbing tests write to `example-runs.jsonl`,
a ledger with no shape, so they test the writer and not the shapes. The ledger dir is
redirected to a tmp dir via CLAUDE_RETRO_DIR; the tests that must exercise the
NO-override path instead run inside a throwaway git repo (`scratch_repo`), so
no test touches a real ledger.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "lib" / "log_run.py"

LEDGER = "example-runs.jsonl"


def _run(stdin: str, retro_dir: Path | None, ledger: str | None = LEDGER,
         args: list[str] | None = None, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ}
    if retro_dir is None:
        env.pop("CLAUDE_RETRO_DIR", None)
    else:
        env["CLAUDE_RETRO_DIR"] = str(retro_dir)
    # Refuse the one combination that writes into a REAL ledger: no usable
    # override AND no cwd, which sends `git rev-parse --show-toplevel` at
    # whatever repo the suite happens to run in — this one. Enforced here rather
    # than asserted per-test, because the per-test assertion is exactly what a
    # future edit drops without any test noticing (measured: that mutant
    # survived).
    if not (retro_dir is not None and str(retro_dir).strip()) and cwd is None:
        raise AssertionError(
            "_run without a usable CLAUDE_RETRO_DIR must pass cwd=<scratch repo>; "
            "otherwise the append lands in this repo's own cla.io/retro/"
        )
    argv = args if args is not None else ([ledger] if ledger is not None else [])
    return subprocess.run(
        [sys.executable, str(SCRIPT), *argv],
        input=stdin, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
        cwd=None if cwd is None else str(cwd), check=False,
    )


@pytest.fixture
def scratch_repo(tmp_path: Path) -> Path:
    """A throwaway git repo to run the script INSIDE.

    Required by every test that exercises the no-override path: with
    CLAUDE_RETRO_DIR unset the script resolves its ledger dir from `git
    rev-parse --show-toplevel`, which inherits the child's cwd. Run from the
    default cwd, that is THIS repo — and two such tests duly appended a junk
    record to `cla.io/retro/spec-to-pr-runs.jsonl` on every suite run, six of
    which reached a commit before anyone noticed. The docstring above claimed
    no test touches a real ledger; it does now.
    """
    repo = tmp_path / "scratch-repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
    return repo


# --------------------------------------------------------------------------- #
# Appending
# --------------------------------------------------------------------------- #

# requirement: run-ledgers / Ledger files
def test_appends_one_line_per_call(tmp_path: Path) -> None:
    retro = tmp_path / "retro"

    r1 = _run('{"change":"a","phases":[]}', retro)
    r2 = _run('{"change":"b","phases":[]}', retro)

    assert r1.returncode == 0, r1.stderr
    assert r2.returncode == 0, r2.stderr

    log_path = Path(r1.stdout.strip())
    assert log_path == retro / LEDGER
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["change"] == "a"
    assert json.loads(lines[1])["change"] == "b"


def test_two_ledgers_stay_separate(tmp_path: Path) -> None:
    # The whole point of the `<ledger>` argument: one writer, several ledgers.
    # If the argument were ignored, both records would land in one file.
    retro = tmp_path / "retro"
    _run('{"a":1}', retro, ledger="a-runs.jsonl")
    _run('{"b":2}', retro, ledger="b-runs.jsonl")

    assert json.loads((retro / "a-runs.jsonl").read_text(encoding="utf-8")) == {"a": 1}
    assert json.loads((retro / "b-runs.jsonl").read_text(encoding="utf-8")) == {"b": 2}


def test_creates_deeply_missing_parent_dirs(tmp_path: Path) -> None:
    retro = tmp_path / "nested" / "deep" / "retro"
    r = _run('{"change":"x","phases":[]}', retro)
    assert r.returncode == 0, r.stderr
    assert Path(r.stdout.strip()).exists()


def test_preserves_unicode(tmp_path: Path) -> None:
    retro = tmp_path / "retro"
    r = _run('{"note":"café — ✓"}', retro)
    assert r.returncode == 0, r.stderr
    written = Path(r.stdout.strip()).read_text(encoding="utf-8")
    assert "café — ✓" in written, "record must not be escaped to ASCII"


# --------------------------------------------------------------------------- #
# Rejected input
# --------------------------------------------------------------------------- #

def test_rejects_non_object_json(tmp_path: Path) -> None:
    r = _run('["not","an","object"]', tmp_path / "retro")
    assert r.returncode == 1
    assert "must be an object" in r.stderr


def test_rejects_malformed_json(tmp_path: Path) -> None:
    r = _run("{not json", tmp_path / "retro")
    assert r.returncode == 1
    assert "invalid JSON" in r.stderr


def test_rejects_oversize_record(tmp_path: Path) -> None:
    r = _run(json.dumps({"prose": "x" * 5000}), tmp_path / "retro")
    assert r.returncode == 1
    assert "4 KiB" in r.stderr


# requirement: run-ledgers / Ledger files
def test_nothing_is_written_when_the_record_is_rejected(tmp_path: Path) -> None:
    # A rejected record must not leave a partial line behind for the retro to
    # trip over — the ledger is append-only and nothing repairs it.
    retro = tmp_path / "retro"
    _run("{not json", retro)
    assert not (retro / LEDGER).exists()


# --------------------------------------------------------------------------- #
# The ledger argument
# --------------------------------------------------------------------------- #

def test_missing_ledger_argument_is_refused(tmp_path: Path) -> None:
    r = _run('{"a":1}', tmp_path / "retro", args=[])
    assert r.returncode == 1
    assert "usage" in r.stderr


def test_extra_arguments_are_refused(tmp_path: Path) -> None:
    r = _run('{"a":1}', tmp_path / "retro", args=[LEDGER, "extra.jsonl"])
    assert r.returncode == 1


@pytest.mark.parametrize("bad", [
    "../escape.jsonl",
    "sub/dir.jsonl",
    "sub\\dir.jsonl",
    "runs.txt",
    ".hidden.jsonl",
    "",
])
def test_a_ledger_name_that_is_not_a_bare_filename_is_refused(tmp_path: Path, bad: str) -> None:
    # The caller is a model assembling a command line, so a path-shaped argument
    # writing outside the ledger dir is a real shape, not a hypothetical one.
    r = _run('{"a":1}', tmp_path / "retro", ledger=bad)
    assert r.returncode == 1, f"{bad!r} was accepted"
    assert not (tmp_path / "escape.jsonl").exists()


# --------------------------------------------------------------------------- #
# Resolving the ledger dir
# --------------------------------------------------------------------------- #

# requirement: run-ledgers / Ledger files
def test_runs_dir_env_override(tmp_path: Path) -> None:
    retro = tmp_path / "elsewhere"
    r = _run('{"a":1}', retro)
    assert Path(r.stdout.strip()).parent == retro


# requirement: plugin-distribution / Repo data stays in the repo
def test_runs_dir_default_is_cla_io_retro(scratch_repo: Path) -> None:
    # With no override, the dir comes from `git rev-parse --show-toplevel` —
    # hence `cwd`, so the write lands in the scratch repo, not this one.
    r = _run('{"a":1}', None, cwd=scratch_repo)
    assert r.returncode == 0, r.stderr
    written = Path(r.stdout.strip())
    assert written.parent.as_posix().endswith("cla.io/retro")
    assert written.is_relative_to(scratch_repo), f"escaped the scratch repo: {written}"


def test_blank_override_is_treated_as_unset(scratch_repo: Path) -> None:
    r = _run('{"a":1}', Path("   "), cwd=scratch_repo)
    assert r.returncode == 0, r.stderr
    written = Path(r.stdout.strip())
    assert written.parent.as_posix().endswith("cla.io/retro")
    assert written.is_relative_to(scratch_repo), f"escaped the scratch repo: {written}"


def test_relative_override_is_rejected_loudly(tmp_path: Path) -> None:
    # Silently guessing would make logged runs vanish from the retro, which
    # resolves the same path independently.
    r = _run('{"a":1}', Path("relative/retro"))
    assert r.returncode == 1
    assert "absolute path" in r.stderr


# --------------------------------------------------------------------------- #
# Record shapes
# --------------------------------------------------------------------------- #
# Two ledgers have a shape the writer checks. Each refusal case below is one
# edit to a conforming record, and must be refused with one line naming the
# field, leaving the ledger absent. The fleet's real drift is in the list:
# `phases` as an object (the motivating defect), `date` for `ts`, `phase` for
# `name`, `asks` as an object, the legacy severity and model-tier shapes of
# `revise_findings_by_tier`, and a Review `size_gate` contradicting its agents.

SPEC = "spec-to-pr-runs.jsonl"
CODIFY = "codify-runs.jsonl"


def _spec_record() -> dict:
    return {
        "ts": "2026-10-08T09:15:00Z", "change": "add-thing", "mode": "existing-change",
        "args": {"review_rounds": 1, "test_rounds": 3, "pr_rounds": 2, "auto": True},
        "phases": [
            {"name": "Propose", "status": "ok", "report_chars": 120},
            {"name": "Review", "status": "ok", "rounds_used": 1, "rounds_cap": 1,
             "size_gate": "large", "verdict": "FIX FIRST", "verified_claims_count": 9,
             "agents": ["design", "task", "spec"]},
            {"name": "Implement", "status": "ok"},
            {"name": "Test", "status": "warn", "rounds_used": 2, "rounds_cap": 3,
             "reason": "one flaky test re-run"},
            {"name": "Ship", "status": "ok", "version_bumped": False},
            {"name": "Revise", "status": "ok", "rounds_used": 2, "rounds_cap": 2,
             "agents": ["code-reviewer", "silent-failure-hunter"],
             "findings_by_round": [{"round": 1, "found": 3, "sibling_instance": 0},
                                   {"round": 2, "found": 1, "sibling_instance": None}]},
            {"name": "Archive", "status": "ok"},
            {"name": "Handoff", "status": "ok"},
        ],
        "asks": [{"header": "Scope", "choice": "split"}],
        "deferred_to_todo": 0,
        "cost": {"wall_clock_minutes": 42, "model": "opus", "agents_dispatched": 5,
                 "escalations": 0},
        "routing": {"implement_delegated": True, "escalate_up_fired": False,
                    "revise_findings_by_tier": {
                        "code-reviewer": {"found": 2, "phantom": 0},
                        "plugin-dev:skill-reviewer": {"found": 0, "phantom": 0}}},
    }


def _codify_record() -> dict:
    return {
        "ts": "2026-10-08", "scope": "repo-wide",
        "suggestions": {"proposed": 2, "applied": 2, "rejected": 0},
        "memory": {"proposed": 1, "applied": 1},
        "effectiveness": {"prevented": 3, "re_offended": 1, "not_exercised": 9},
        "re_offenses": [{"lesson": "stale-port", "failing_artifact": "CLAUDE.md",
                         "escalated_to": "hook"}],
        "rejected_lessons": [],
        "maintenance": {"failure_modes_bullets": 51, "live_log_entries": 30, "trimmed": False},
        "process_issue": False,
        "output_chars": 900,
    }


def _phase(rec: dict, name: str) -> dict:
    return next(p for p in rec["phases"] if p["name"] == name)


def _set(path: str, value):
    """An edit that sets one dotted path, `phases.Review.size_gate` style."""
    def edit(rec: dict) -> None:
        *parents, last = path.split(".")
        node = rec
        for key in parents:
            node = _phase(rec, key) if node is rec.get("phases") else node[key]
        node[last] = value
    return edit


def _drop(path: str):
    def edit(rec: dict) -> None:
        *parents, last = path.split(".")
        node = rec
        for key in parents:
            node = _phase(rec, key) if node is rec.get("phases") else node[key]
        del node[last]
    return edit


def _review_without_gate_or_agents(rec: dict) -> None:
    review = _phase(rec, "Review")
    del review["size_gate"]
    review["agents"] = []


def _rename_phase_key(rec: dict) -> None:
    rec["phases"] = [{"phase": p.pop("name"), **p} for p in rec["phases"]]


def _date_for_ts(rec: dict) -> None:
    rec["date"] = rec.pop("ts")[:10]


def _phases_as_object(rec: dict) -> None:
    rec["phases"] = {p["name"].lower(): p["status"] for p in rec["phases"]}


SPEC_REFUSALS = [
    # (case id, edit, a fragment the refusal must contain)
    ("phases-object", _phases_as_object, "`phases` must be a list"),
    ("ts-missing", _drop("ts"), "`ts` is required"),
    ("date-instead-of-ts", _date_for_ts, "`ts` is required"),
    ("ts-date-only", _set("ts", "2026-10-08"), "`ts` must be an ISO-8601 date-time"),
    ("ts-no-zone", _set("ts", "2026-10-08T09:15:00"), "`ts` must be"),
    ("ts-not-a-date", _set("ts", "2026-13-40T09:15:00Z"), "`ts` must be"),
    ("ts-number", _set("ts", 1780000000), "`ts` must be"),
    ("change-missing", _drop("change"), "`change` is required"),
    ("mode-unknown", _set("mode", "resume"), "`mode` must be one of"),
    ("phase-key-not-name", _rename_phase_key, "`phases[0].name` is required"),
    ("phase-name-lowercase", _set("phases.Propose.name", "propose"), "`phases[0].name` must be one of"),
    ("status-partial", _set("phases.Implement.status", "partial"), "`phases[2].status` must be one of"),
    ("warn-without-reason", _drop("phases.Test.reason"), "`reason` is required on a warn phase (Test)"),
    ("fail-without-reason", _set("phases.Ship.status", "fail"), "`reason` is required on a fail phase (Ship)"),
    ("empty-reason", _set("phases.Test.reason", " "), "`phases[3].reason` must be a non-empty string"),
    ("rounds-without-cap", _drop("phases.Test.rounds_cap"), "`rounds_used` and `rounds_cap` go together (Test)"),
    ("cap-without-rounds", _drop("phases.Revise.rounds_used"), "`rounds_used` and `rounds_cap` go together (Revise)"),
    ("rounds-as-string", _set("phases.Revise.rounds_used", "2"), "`phases[5].rounds_used` must be a non-negative integer"),
    ("rounds-as-bool", _set("phases.Revise.rounds_used", True), "`phases[5].rounds_used` must be a non-negative integer"),
    ("rounds-negative", _set("phases.Revise.rounds_cap", -1), "`phases[5].rounds_cap` must be a non-negative integer"),
    ("report-chars-float", _set("phases.Propose.report_chars", 1.5), "`phases[0].report_chars`"),
    ("size-gate-unknown", _set("phases.Review.size_gate", "medium"), "`phases[1].size_gate` must be one of"),
    ("verdict-unknown", _set("phases.Review.verdict", "FIX_FIRST"), "`phases[1].verdict` must be one of"),
    ("large-without-agents", _set("phases.Review.agents", []), "`agents` must list the Review agents"),
    ("small-with-agents", _set("phases.Review.size_gate", "small"), "`agents` must list the Review agents"),
    ("agents-not-a-list", _set("phases.Revise.agents", "code-reviewer"), "`phases[5].agents` must be a list"),
    ("agent-not-a-string", _set("phases.Revise.agents", [{"name": "x"}]), "`phases[5].agents[0]` must be a non-empty string"),
    ("version-bumped-string", _set("phases.Ship.version_bumped", "no"), "`phases[4].version_bumped` must be true or false"),
    ("verified-claims-string", _set("phases.Review.verified_claims_count", "9"), "`phases[1].verified_claims_count`"),
    ("findings-by-round-object", _set("phases.Revise.findings_by_round", {"1": 3}), "`phases[5].findings_by_round` must be a list"),
    ("round-missing-sibling", _set("phases.Revise.findings_by_round", [{"round": 1, "found": 3}]),
     "`phases[5].findings_by_round[0].sibling_instance` is required"),
    ("asks-object", _set("asks", {"count": 1, "choices": ["split"]}), "`asks` must be a list"),
    ("ask-missing-choice", _set("asks", [{"header": "Scope"}]), "`asks[0].choice` is required"),
    ("deferred-string", _set("deferred_to_todo", "0"), "`deferred_to_todo` must be a non-negative integer"),
    ("args-string-count", _set("args.review_rounds", "1"), "`args.review_rounds` must be a non-negative integer"),
    ("routing-not-object", _set("routing", ["code-reviewer"]), "`routing` must be an object"),
    ("findings-severity-shape", _set("routing.revise_findings_by_tier", {"critical": 2, "important": 4}),
     "`routing.revise_findings_by_tier.critical` must be an object"),
    ("findings-model-tier-shape", _set("routing.revise_findings_by_tier", {"opus": {"found": 1, "phantom": 0}}),
     "`routing.revise_findings_by_tier` key 'opus' must be one of"),
    ("findings-underscore-key", _set("routing.revise_findings_by_tier", {"code_reviewer": {"found": 1, "phantom": 0}}),
     "key 'code_reviewer'"),
    ("findings-missing-phantom", _set("routing.revise_findings_by_tier", {"code-reviewer": {"found": 1}}),
     "`routing.revise_findings_by_tier.code-reviewer.phantom` is required"),
    ("findings-not-object", _set("routing.revise_findings_by_tier", [1, 2]),
     "`routing.revise_findings_by_tier` must be an object"),
]

CODIFY_REFUSALS = [
    ("ts-missing", _drop("ts"), "`ts` is required"),
    ("ts-not-a-date", _set("ts", "08/10/2026"), "`ts` must be an ISO-8601 date or date-time"),
    ("scope-missing", _drop("scope"), "`scope` is required"),
    ("suggestions-flattened", _drop("suggestions"), "`suggestions` is required"),
    ("suggestions-count-string", _set("suggestions.applied", "2"), "`suggestions.applied` must be a non-negative integer"),
    ("memory-not-object", _set("memory", 1), "`memory` must be an object"),
    ("re-offenses-object", _set("re_offenses", {"lesson": "x"}), "`re_offenses` must be a list"),
    ("rung-unknown", _set("re_offenses", [{"lesson": "x", "escalated_to": "doc"}]),
     "`re_offenses[0].escalated_to` must be one of"),
    ("lesson-missing", _set("re_offenses", [{"escalated_to": "hook"}]), "`re_offenses[0].lesson` is required"),
    ("rejected-lessons-string", _set("rejected_lessons", "stale-port"), "`rejected_lessons` must be a list"),
    ("trimmed-string", _set("maintenance.trimmed", "yes"), "`maintenance.trimmed` must be true or false"),
    ("process-issue-missing", _drop("process_issue"), "`process_issue` is required"),
    ("effectiveness-count-string", _set("effectiveness.prevented", "3"), "`effectiveness.prevented`"),
    ("output-chars-negative", _set("output_chars", -1), "`output_chars` must be a non-negative integer"),
]


def _assert_refused(r: subprocess.CompletedProcess[str], ledger: str, fragment: str,
                    retro: Path) -> None:
    assert r.returncode == 1, f"accepted: {r.stdout}"
    message = r.stderr.strip()
    assert "\n" not in message, f"a refusal is one line, got:\n{message}"
    assert message.startswith(f"log_run: {ledger} record refused: "), message
    assert fragment in message, f"{fragment!r} not in {message!r}"
    assert not (retro / ledger).exists(), "a refused record must leave the ledger unchanged"


# requirement: run-ledgers / Run records are checked when written
@pytest.mark.parametrize("ledger, record", [(SPEC, _spec_record()), (CODIFY, _codify_record())],
                         ids=["spec-to-pr", "codify"])
def test_a_conforming_record_is_appended_unchanged(tmp_path: Path, ledger: str, record: dict) -> None:
    retro = tmp_path / "retro"
    r = _run(json.dumps(record), retro, ledger=ledger)
    assert r.returncode == 0, r.stderr
    assert json.loads((retro / ledger).read_text(encoding="utf-8")) == record


# requirement: run-ledgers / Run records are checked when written
@pytest.mark.parametrize("case, edit, fragment", SPEC_REFUSALS, ids=[c[0] for c in SPEC_REFUSALS])
def test_an_off_shape_spec_to_pr_record_is_refused(tmp_path: Path, case: str, edit, fragment: str) -> None:
    record = _spec_record()
    edit(record)
    _assert_refused(_run(json.dumps(record), tmp_path / "retro", ledger=SPEC), SPEC, fragment,
                    tmp_path / "retro")


# requirement: run-ledgers / Run records are checked when written
@pytest.mark.parametrize("case, edit, fragment", CODIFY_REFUSALS, ids=[c[0] for c in CODIFY_REFUSALS])
def test_an_off_shape_codify_record_is_refused(tmp_path: Path, case: str, edit, fragment: str) -> None:
    record = _codify_record()
    edit(record)
    _assert_refused(_run(json.dumps(record), tmp_path / "retro", ledger=CODIFY), CODIFY, fragment,
                    tmp_path / "retro")


@pytest.mark.parametrize("edit", [
    _drop("args"), _drop("asks"), _drop("routing"), _drop("deferred_to_todo"),
    _drop("phases.Review.size_gate"), _drop("phases.Revise.findings_by_round"),
    _review_without_gate_or_agents, _set("phases.Review.status", "skip"),
    _set("notes", "a key no reader names is kept"),
    _set("ts", "2026-10-08T12:15:00+03:00"),
    _set("routing.revise_findings_by_tier", {}),
], ids=["no-args", "no-asks", "no-routing", "no-deferred", "no-size-gate", "no-findings-by-round",
        "agents-empty-without-gate", "review-skipped", "extra-key", "ts-offset", "findings-empty"])
def test_optional_fields_and_extra_keys_are_accepted(tmp_path: Path, edit) -> None:
    record = _spec_record()
    edit(record)
    r = _run(json.dumps(record), tmp_path / "retro", ledger=SPEC)
    assert r.returncode == 0, r.stderr


# requirement: run-ledgers / Run records are checked when written
def test_a_ledger_with_no_shape_takes_any_object(tmp_path: Path) -> None:
    # The shape check is per ledger. Every other ledger keeps the old contract —
    # one JSON object, under the size ceiling — including a record that would be
    # refused by name as a spec-to-pr record.
    record = _spec_record()
    _phases_as_object(record)
    for ledger in ("lite-pr-runs.jsonl", "spec-to-pr-runs-old.jsonl"):
        r = _run(json.dumps(record), tmp_path / "retro", ledger=ledger)
        assert r.returncode == 0, f"{ledger}: {r.stderr}"
