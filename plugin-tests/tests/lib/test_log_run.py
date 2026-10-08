"""Tests for the shared log_run.py — atomic JSONL append into a run ledger.

Ported from the two per-skill copies this replaced (spec-to-pr's and
codify-learnings's `tests/test_log_run.py`, which were themselves near-identical),
plus the cases the new `<ledger>` argument introduces, plus the record-shape check
for the two ledgers it accepts. The plumbing tests write a minimal codify record,
the smallest one the writer takes, so they test the writer and not the shapes. The ledger dir is
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

import log_run as log_run_shapes  # noqa: E402 — the shapes, for the ids a record may use

LEDGER = "codify-runs.jsonl"


def _rec(**extra) -> str:
    """The smallest record the plumbing ledger accepts, plus any extra keys."""
    return json.dumps({"ts": "2026-10-08", "applied": [], "re_offenses": [], **extra},
                      ensure_ascii=False)


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

    r1 = _run(_rec(change="a"), retro)
    r2 = _run(_rec(change="b"), retro)

    assert r1.returncode == 0, r1.stderr
    assert r2.returncode == 0, r2.stderr

    log_path = Path(r1.stdout.strip())
    assert log_path == retro / LEDGER
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["change"] == "a"
    assert json.loads(lines[1])["change"] == "b"


def test_two_ledgers_stay_separate(tmp_path: Path) -> None:
    # The whole point of the `<ledger>` argument: one writer, two ledgers.
    # If the argument were ignored, both records would land in one file.
    retro = tmp_path / "retro"
    assert _run(json.dumps(_spec_record()), retro, ledger=SPEC).returncode == 0
    assert _run(_rec(), retro, ledger=CODIFY).returncode == 0

    assert json.loads((retro / SPEC).read_text(encoding="utf-8")) == _spec_record()
    assert json.loads((retro / CODIFY).read_text(encoding="utf-8")) == json.loads(_rec())


def test_creates_deeply_missing_parent_dirs(tmp_path: Path) -> None:
    retro = tmp_path / "nested" / "deep" / "retro"
    r = _run(_rec(), retro)
    assert r.returncode == 0, r.stderr
    assert Path(r.stdout.strip()).exists()


def test_preserves_unicode(tmp_path: Path) -> None:
    retro = tmp_path / "retro"
    r = _run(_rec(note="café — ✓"), retro)
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
    r = _run(_rec(prose="x" * 5000), tmp_path / "retro")
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
    r = _run(_rec(), tmp_path / "retro", args=[])
    assert r.returncode == 1
    assert "usage" in r.stderr


def test_extra_arguments_are_refused(tmp_path: Path) -> None:
    # A record the ledger accepts, so only the arity rule can refuse it.
    r = _run(_rec(), tmp_path / "retro", args=[LEDGER, "extra.jsonl"])
    assert r.returncode == 1
    assert "usage" in r.stderr
    assert not (tmp_path / "retro").exists()


# requirement: run-ledgers / Only checked run records are written
@pytest.mark.parametrize("bad", [
    "../escape.jsonl",
    "../codify-runs.jsonl",
    "sub/dir.jsonl",
    "sub\\dir.jsonl",
    "runs.txt",
    ".hidden.jsonl",
    "",
    # Retired ledgers, and a near miss of a live one: a typo would start a file
    # nothing reads.
    "lite-pr-runs.jsonl",
    "feedback-runs.jsonl",
    "spec-to-pr-runs-old.jsonl",
    "Codify-runs.jsonl",
])
def test_a_ledger_name_that_is_not_one_of_the_two_is_refused(tmp_path: Path, bad: str) -> None:
    # The caller is a model assembling a command line, so a path-shaped argument
    # writing outside the ledger dir is a real shape, not a hypothetical one.
    retro = tmp_path / "retro"
    r = _run(_rec(), retro, ledger=bad)
    assert r.returncode == 1, f"{bad!r} was accepted"
    assert r.stderr.strip() == (f"log_run: {bad!r} is not a ledger; the ledgers are "
                                "codify-runs.jsonl, spec-to-pr-runs.jsonl")
    assert not retro.exists() and not (tmp_path / "escape.jsonl").exists()


# --------------------------------------------------------------------------- #
# Resolving the ledger dir
# --------------------------------------------------------------------------- #

# requirement: run-ledgers / Ledger files
def test_runs_dir_env_override(tmp_path: Path) -> None:
    retro = tmp_path / "elsewhere"
    r = _run(_rec(), retro)
    assert Path(r.stdout.strip()).parent == retro


# requirement: plugin-distribution / Repo data stays in the repo
def test_runs_dir_default_is_cla_io_retro(scratch_repo: Path) -> None:
    # With no override, the dir comes from `git rev-parse --show-toplevel` —
    # hence `cwd`, so the write lands in the scratch repo, not this one.
    r = _run(_rec(), None, cwd=scratch_repo)
    assert r.returncode == 0, r.stderr
    written = Path(r.stdout.strip())
    assert written.parent.as_posix().endswith("cla.io/retro")
    assert written.is_relative_to(scratch_repo), f"escaped the scratch repo: {written}"


def test_blank_override_is_treated_as_unset(scratch_repo: Path) -> None:
    r = _run(_rec(), Path("   "), cwd=scratch_repo)
    assert r.returncode == 0, r.stderr
    written = Path(r.stdout.strip())
    assert written.parent.as_posix().endswith("cla.io/retro")
    assert written.is_relative_to(scratch_repo), f"escaped the scratch repo: {written}"


def test_relative_override_is_rejected_loudly(tmp_path: Path) -> None:
    # Silently guessing would make logged runs vanish from the retro, which
    # resolves the same path independently.
    r = _run(_rec(), Path("relative/retro"))
    assert r.returncode == 1
    assert "absolute path" in r.stderr


# --------------------------------------------------------------------------- #
# Record shapes
# --------------------------------------------------------------------------- #
# Two ledgers have a shape the writer checks. Each refusal case below is one
# edit to a conforming record, and must be refused with one line naming the
# field, leaving the ledger absent. The fleet's real drift is in the list:
# `phases` as an object (the motivating defect), `date` for `ts`, `phase` for
# `name`, `asks` as an object, and the legacy severity and model-tier shapes of
# `revise_findings_by_tier`.

SPEC = "spec-to-pr-runs.jsonl"
CODIFY = "codify-runs.jsonl"


def _spec_record() -> dict:
    return {
        "ts": "2026-10-08T09:15:00Z", "change": "add-thing", "mode": "existing-change",
        "flags": ["--inherits", "--pr-rounds"],
        "phases": [
            {"name": "Propose", "status": "ok"},
            {"name": "Review", "status": "ok", "rounds_used": 1, "rounds_cap": 1},
            {"name": "Implement", "status": "ok"},
            {"name": "Test", "status": "warn", "rounds_used": 2, "rounds_cap": 3,
             "reason": "one flaky test re-run"},
            {"name": "Ship", "status": "ok"},
            {"name": "Revise", "status": "ok", "rounds_used": 2, "rounds_cap": 2,
             "findings_by_round": [{"round": 1, "found": 3}, {"round": 2, "found": 1}]},
            {"name": "Archive", "status": "ok"},
            {"name": "Handoff", "status": "ok"},
        ],
        "escalated_to_diagnose": 1,
        "asks": [{"header": "Scope", "choice": "split"}],
        "routing": {"revise_findings_by_tier": {
            "code-reviewer": {"found": 2, "phantom": 0},
            "plugin-dev:skill-reviewer": {"found": 0, "phantom": 0}}},
    }


def _codify_record() -> dict:
    return {
        "ts": "2026-10-08",
        "applied": [{"target": "hooks/block-cd-in-bash.py", "rung": "hook"},
                    {"target": "CLAUDE.md", "rung": "doc"}],
        "re_offenses": [{"artifact": "CLAUDE.md", "escalated_to": "hook"}],
    }


def _old_codify_record() -> dict:
    """The shape codify-learnings wrote before slim-codify-learnings: counts and a
    slug per re-offense. Every fleet record has it, and the writer must not take it."""
    return {
        "ts": "2026-10-08", "scope": "repo-wide",
        "suggestions": {"proposed": 2, "applied": 2, "rejected": 0},
        "memory": {"proposed": 1, "applied": 1},
        "re_offenses": [{"lesson": "stale-port", "failing_artifact": "CLAUDE.md",
                         "escalated_to": "hook"}],
        "rejected_lessons": [],
        "maintenance": {"failure_modes_bullets": 51, "live_log_entries": 30, "trimmed": False},
        "process_issue": False,
    }


def _phase(rec: dict, name: str) -> dict:
    return next(p for p in rec["phases"] if p["name"] == name)


def _set(path: str, value):
    """An edit that sets one dotted path, `phases.Test.reason` style."""
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


def _drop_both_rounds(name: str):
    def edit(rec: dict) -> None:
        for key in ("rounds_used", "rounds_cap"):
            del _phase(rec, name)[key]
    return edit


def _chain(*edits):
    def edit(rec: dict) -> None:
        for one in edits:
            one(rec)
    return edit


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
    ("findings-by-round-object", _set("phases.Revise.findings_by_round", {"1": 3}), "`phases[5].findings_by_round` must be a list"),
    ("round-missing-found", _set("phases.Revise.findings_by_round", [{"round": 1}]),
     "`phases[5].findings_by_round[0].found` is required"),
    ("asks-object", _set("asks", {"count": 1, "choices": ["split"]}), "`asks` must be a list"),
    ("ask-missing-choice", _set("asks", [{"header": "Scope"}]), "`asks[0].choice` is required"),
    # Flags by name as typed: one spelling per flag, or the retro counts two.
    ("flags-a-string", _set("flags", "--inherits"), "`flags` must be a list"),
    ("flag-without-dashes", _set("flags", ["inherits"]), "`flags[0]` must be a flag name as typed"),
    ("flag-with-value", _set("flags", ["--pr-rounds 1"]), "`flags[0]` must be a flag name as typed"),
    ("flag-with-equals", _set("flags", ["--pr-rounds=1"]), "`flags[0]` must be a flag name as typed"),
    ("flag-bare-dashes", _set("flags", ["--"]), "`flags[0]` must be a flag name as typed"),
    ("diagnose-string", _set("escalated_to_diagnose", "1"), "`escalated_to_diagnose` must be a non-negative integer"),
    ("diagnose-bool", _set("escalated_to_diagnose", True), "`escalated_to_diagnose` must be a non-negative integer"),
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
    ("findings-two-bad-keys", _set("routing.revise_findings_by_tier", {
        "opus": {"found": 1, "phantom": 0}, "code_reviewer": {"found": 1, "phantom": 0}}),
     "`routing.revise_findings_by_tier` keys 'opus', 'code_reviewer' must each be one of"),
    # The rule reads `name` and `status`; with one missing it must not run, so the
    # refusal names the field instead of crashing on it.
    ("status-missing", _drop("phases.Test.status"), "`phases[3].status` is required"),
    # Findings by canonical id: the prefixed form the dispatch uses is refused by name.
    ("findings-prefixed-key", _set("routing.revise_findings_by_tier",
                                   {"pr-review-toolkit:code-reviewer": {"found": 1, "phantom": 0}}),
     "`routing.revise_findings_by_tier` key 'pr-review-toolkit:code-reviewer' must be one of "
     "code-reviewer, "),
    # The looping phases say how many rounds they used, whenever they ran.
    ("test-without-rounds", _drop_both_rounds("Test"),
     "`rounds_used` and `rounds_cap` are required on a Test phase that was not skipped (warn)"),
    ("revise-without-rounds", _drop_both_rounds("Revise"),
     "`rounds_used` and `rounds_cap` are required on a Revise phase that was not skipped (ok)"),
    ("revise-failed-without-rounds", _chain(_drop_both_rounds("Revise"),
                                            _set("phases.Revise.status", "fail"),
                                            _set("phases.Revise.reason", "gate red")),
     "`rounds_used` and `rounds_cap` are required on a Revise phase that was not skipped (fail)"),
]

CODIFY_REFUSALS = [
    ("ts-missing", _drop("ts"), "`ts` is required"),
    ("ts-not-a-date", _set("ts", "08/10/2026"), "`ts` must be an ISO-8601 date or date-time"),
    ("applied-missing", _drop("applied"), "`applied` is required"),
    ("applied-a-count", _set("applied", 2), "`applied` must be a list"),
    ("applied-target-missing", _set("applied", [{"rung": "doc"}]), "`applied[0].target` is required"),
    ("applied-target-blank", _set("applied", [{"target": " ", "rung": "doc"}]),
     "`applied[0].target` must be a non-empty string"),
    ("applied-rung-missing", _set("applied", [{"target": "CLAUDE.md"}]), "`applied[0].rung` is required"),
    # The old six-value enum named artifact types; a rung is one of four.
    ("applied-rung-artifact-type", _set("applied", [{"target": "CLAUDE.md", "rung": "claude_md"}]),
     '`applied[0].rung` must be one of "checklist", "doc", "hook", "script"'),
    ("re-offenses-missing", _drop("re_offenses"), "`re_offenses` is required"),
    ("re-offenses-object", _set("re_offenses", {"artifact": "x"}), "`re_offenses` must be a list"),
    # Keyed by slug, the old way: 78 distinct slugs over 88 re-offenses never joined.
    ("re-offense-by-slug", _set("re_offenses", [{"lesson": "stale-port", "escalated_to": "hook"}]),
     "`re_offenses[0].artifact` is required"),
    ("escalated-to-missing", _set("re_offenses", [{"artifact": "CLAUDE.md"}]),
     "`re_offenses[0].escalated_to` is required"),
    ("escalated-to-unknown", _set("re_offenses", [{"artifact": "CLAUDE.md", "escalated_to": "memory"}]),
     "`re_offenses[0].escalated_to` must be one of"),
]


def _assert_refused(r: subprocess.CompletedProcess[str], ledger: str, fragment: str,
                    retro: Path) -> None:
    assert r.returncode == 1, f"accepted: {r.stdout}"
    message = r.stderr.strip()
    assert "\n" not in message, f"a refusal is one line, got:\n{message}"
    assert message.startswith(f"log_run: {ledger} record refused: "), message
    assert fragment in message, f"{fragment!r} not in {message!r}"
    assert not (retro / ledger).exists(), "a refused record must leave the ledger unchanged"


# requirement: run-ledgers / Only checked run records are written
@pytest.mark.parametrize("ledger, record", [(SPEC, _spec_record()), (CODIFY, _codify_record())],
                         ids=["spec-to-pr", "codify"])
def test_a_conforming_record_is_appended_unchanged(tmp_path: Path, ledger: str, record: dict) -> None:
    retro = tmp_path / "retro"
    r = _run(json.dumps(record), retro, ledger=ledger)
    assert r.returncode == 0, r.stderr
    assert json.loads((retro / ledger).read_text(encoding="utf-8")) == record


# requirement: run-ledgers / Only checked run records are written
@pytest.mark.parametrize("case, edit, fragment", SPEC_REFUSALS, ids=[c[0] for c in SPEC_REFUSALS])
def test_an_off_shape_spec_to_pr_record_is_refused(tmp_path: Path, case: str, edit, fragment: str) -> None:
    record = _spec_record()
    edit(record)
    _assert_refused(_run(json.dumps(record), tmp_path / "retro", ledger=SPEC), SPEC, fragment,
                    tmp_path / "retro")


# requirement: run-ledgers / Only checked run records are written
@pytest.mark.parametrize("case, edit, fragment", CODIFY_REFUSALS, ids=[c[0] for c in CODIFY_REFUSALS])
def test_an_off_shape_codify_record_is_refused(tmp_path: Path, case: str, edit, fragment: str) -> None:
    record = _codify_record()
    edit(record)
    _assert_refused(_run(json.dumps(record), tmp_path / "retro", ledger=CODIFY), CODIFY, fragment,
                    tmp_path / "retro")


# requirement: run-ledgers / Only checked run records are written
def test_the_old_codify_record_is_refused_naming_each_new_field(tmp_path: Path) -> None:
    r = _run(json.dumps(_old_codify_record()), tmp_path / "retro", ledger=CODIFY)
    for fragment in ("`applied` is required", "`re_offenses[0].artifact` is required"):
        _assert_refused(r, CODIFY, fragment, tmp_path / "retro")


@pytest.mark.parametrize("edit", [
    _set("applied", []), _set("re_offenses", []),
    _set("applied", [{"target": "t", "rung": rung} for rung in log_run_shapes.RUNGS]),
    _set("ts", "2026-10-08T12:15:00Z"), _set("scope", "a key no reader names is kept"),
], ids=["nothing-applied", "no-re-offenses", "every-rung", "ts-date-time", "extra-key"])
def test_a_codify_record_may_be_empty_or_carry_extra_keys(tmp_path: Path, edit) -> None:
    record = _codify_record()
    edit(record)
    r = _run(json.dumps(record), tmp_path / "retro", ledger=CODIFY)
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("edit", [
    _drop("flags"), _set("flags", []), _drop("escalated_to_diagnose"),
    _set("escalated_to_diagnose", 0), _drop("asks"), _drop("routing"),
    _drop("phases.Revise.findings_by_round"), _set("phases.Review.status", "skip"),
    _set("notes", "a key no reader names is kept"),
    _set("ts", "2026-10-08T12:15:00+03:00"),
    _set("routing.revise_findings_by_tier", {}),
    _drop_both_rounds("Review"),
    _chain(_set("phases.Test.status", "skip"), _drop_both_rounds("Test"),
           _drop("phases.Test.reason")),
    _chain(_set("phases.Revise.status", "skip"), _drop_both_rounds("Revise")),
    _set("routing.revise_findings_by_tier",
         {agent: {"found": 0, "phantom": 0} for agent in log_run_shapes.REVISE_AGENTS}),
], ids=["no-flags", "flags-empty", "no-diagnose", "diagnose-zero", "no-asks", "no-routing",
        "no-findings-by-round", "review-skipped", "extra-key", "ts-offset", "findings-empty",
        "review-without-rounds", "test-skipped-without-rounds", "revise-skipped-without-rounds",
        "every-canonical-revise-agent"])
def test_optional_fields_and_extra_keys_are_accepted(tmp_path: Path, edit) -> None:
    record = _spec_record()
    edit(record)
    r = _run(json.dumps(record), tmp_path / "retro", ledger=SPEC)
    assert r.returncode == 0, r.stderr


def test_fields_an_older_record_carries_are_kept_unchecked(tmp_path: Path) -> None:
    # Fields the record dropped, in shapes the writer once refused: a later record
    # carrying them is appended as is, because nothing reads them any more.
    record = _spec_record()
    _phase(record, "Review").update(size_gate="medium", agents=[], verdict="FIX_FIRST")
    _phase(record, "Revise").update(agents=["orchestrator-inline"])
    _phase(record, "Revise")["findings_by_round"][0]["sibling_instance"] = "n/a"
    record.update(args={"auto": "yes"}, cost={"model": 4}, deferred_to_todo="0")
    record["routing"]["escalate_up_fired"] = "no"
    r = _run(json.dumps(record), tmp_path / "retro", ledger=SPEC)
    assert r.returncode == 0, r.stderr
    assert json.loads((tmp_path / "retro" / SPEC).read_text(encoding="utf-8")) == record


# requirement: run-ledgers / Only checked run records are written
def test_every_problem_is_named_on_the_one_refusal_line(tmp_path: Path) -> None:
    # The caller has ONE retry. A refusal naming only the first problem spends it
    # on a record still wrong in a field nobody mentioned.
    record = _spec_record()
    _date_for_ts(record)
    record["mode"] = "resume"
    record["routing"]["revise_findings_by_tier"] = {
        "pr-review-toolkit:code-reviewer": {"found": 1, "phantom": 0},
        "orchestrator-inline": {"found": 1, "phantom": 0}}
    _drop("phases.Test.reason")(record)
    r = _run(json.dumps(record), tmp_path / "retro", ledger=SPEC)
    for fragment in ("`ts` is required", "`mode` must be one of",
                     "`reason` is required on a warn phase (Test)",
                     "`routing.revise_findings_by_tier` keys 'pr-review-toolkit:code-reviewer', "
                     "'orchestrator-inline' must each be one of"):
        _assert_refused(r, SPEC, fragment, tmp_path / "retro")
    assert r.stderr.count("; ") == 3, r.stderr


def test_a_phase_with_an_unknown_status_gets_no_rule_clauses_about_it() -> None:
    # The rules read `status` as a known value. Run on `running`, the rounds rule
    # would add "required on a Test phase that was not skipped (running)" — a
    # clause about a status that does not exist, sending the one retry after the
    # wrong field.
    record = _spec_record()
    test = _phase(record, "Test")
    test["status"] = "running"
    del test["rounds_used"], test["rounds_cap"]
    assert log_run_shapes.shape_problems(record, log_run_shapes.SHAPES[SPEC]) == [
        '`phases[3].status` must be one of "ok", "warn", "skip", "fail", got "running"']
