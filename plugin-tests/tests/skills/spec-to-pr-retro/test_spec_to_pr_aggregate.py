"""Tests for spec_to_pr_aggregate.py — every field it emits, the fleet default and
its fallback, skipped lines, the round-2 yield, and --nudge.

The script runs as a program, the way the retro skill and spec-to-pr's Handoff
invoke it, so every test goes through a subprocess.
"""

from __future__ import annotations

import itertools
import json
import os
import subprocess
import sys
from pathlib import Path

_SKILLS = Path(__file__).resolve().parents[4] / ".claude" / "plugins" / "cla" / "skills"
SCRIPT = _SKILLS / "spec-to-pr-retro" / "scripts" / "spec_to_pr_aggregate.py"
PLACEHOLDER = "reason not recorded (migrated record)"


def _rec(change: str = "c", ts: str = "2026-10-01T10:00:00Z", phases: list | None = None,
         **extra) -> dict:
    return {"ts": ts, "change": change, "mode": "description",
            "phases": phases if phases is not None else [{"name": "Propose", "status": "ok"}],
            **extra}


def _phase(name: str, status: str = "ok", **fields) -> dict:
    return {"name": name, "status": status, **fields}


def _revise(rounds: list[tuple[int, int]], used: int | None = None, cap: int = 2,
            status: str = "ok", **fields) -> dict:
    """A Revise phase whose findings_by_round holds (round, found) pairs."""
    return _phase("Revise", status, rounds_used=used if used is not None else len(rounds),
                  rounds_cap=cap,
                  findings_by_round=[{"round": r, "found": f, "sibling_instance": 0}
                                     for r, f in rounds], **fields)


def _write(path: Path, records: list, raw_lines: list[str] = ()) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(r) for r in records] + list(raw_lines)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _env(retro_dir: Path | None = None) -> dict:
    env = dict(os.environ)
    env.pop("CLAUDE_RETRO_DIR", None)
    if retro_dir is not None:
        env["CLAUDE_RETRO_DIR"] = str(retro_dir)
    return env


def _call(*args: str, env: dict | None = None, cwd: Path | None = None):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", check=False,
                          env=env if env is not None else _env(), cwd=cwd)


def _run(*args: str, env: dict | None = None) -> tuple[dict, str]:
    r = _call(*args, env=env)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout), r.stderr


def _log(*paths: Path, limit: int = 10) -> tuple[dict, str]:
    return _run("--log", *map(str, paths), "--limit", str(limit))


# --- the emitted fields ------------------------------------------------------

def test_emits_exactly_the_kept_fields(tmp_path: Path) -> None:
    out, _ = _log(_write(tmp_path / "l.jsonl", [_rec()]))
    assert set(out) == {
        "source", "ledgers", "runs_analyzed", "window", "skipped_records",
        "warn_reasons", "warn_reasons_unrecorded", "cap_exhaustion",
        "revise_findings", "asks", "round_2_yield",
    }


def test_window_is_chronological_across_ledgers(tmp_path: Path) -> None:
    # Argument order is not time order: the newer ledger is named first.
    newer = _write(tmp_path / "a.jsonl", [_rec(ts="2026-10-05T00:00:00Z")])
    older = _write(tmp_path / "b.jsonl", [_rec(ts="2026-09-01T00:00:00Z")])
    out, _ = _log(newer, older)
    assert out["runs_analyzed"] == 2
    assert out["window"] == {"first_ts": "2026-09-01T00:00:00Z",
                             "last_ts": "2026-10-05T00:00:00Z"}


def test_limit_applies_per_ledger(tmp_path: Path) -> None:
    a = _write(tmp_path / "a.jsonl", [_rec(change=f"a{i}") for i in range(4)])
    b = _write(tmp_path / "b.jsonl", [_rec(change=f"b{i}") for i in range(4)])
    out, _ = _log(a, b, limit=3)
    assert out["runs_analyzed"] == 6
    assert [entry["records"] for entry in out["ledgers"]] == [4, 4]
    out, _ = _log(a, b, limit=0)
    assert out["runs_analyzed"] == 8


def test_warn_reasons_rank_real_reasons_and_count_the_placeholder_apart(tmp_path: Path) -> None:
    log = _write(tmp_path / "l.jsonl", [
        _rec(phases=[_phase("Test", "warn", reason="flaky", rounds_used=1, rounds_cap=3),
                     _phase("Revise", "fail", reason=PLACEHOLDER, rounds_used=1, rounds_cap=2)]),
        _rec(phases=[_phase("Test", "warn", reason="flaky", rounds_used=1, rounds_cap=3)]),
        _rec(phases=[_phase("Ship", "fail", reason="push refused")]),
        # A reason on an ok or skip phase is not a warn reason.
        _rec(phases=[_phase("Archive", "skip", reason="nothing to archive")]),
    ])
    out, _ = _log(log)
    assert out["warn_reasons"] == [{"reason": "flaky", "count": 2},
                                   {"reason": "push refused", "count": 1}]
    assert out["warn_reasons_unrecorded"] == 1


def test_warn_reasons_keep_the_top_ten(tmp_path: Path) -> None:
    log = _write(tmp_path / "l.jsonl", [
        _rec(phases=[_phase("Ship", "warn", reason=f"r{i}")]) for i in range(12)])
    out, _ = _log(log, limit=0)
    assert len(out["warn_reasons"]) == 10


def test_cap_exhaustion_counts_only_phases_with_room_to_loop(tmp_path: Path) -> None:
    log = _write(tmp_path / "l.jsonl", [
        _rec(phases=[_phase("Review", rounds_used=1, rounds_cap=1),   # single pass
                     _phase("Test", rounds_used=3, rounds_cap=3),     # hit
                     _revise([(1, 2), (2, 1)], status="warn", reason="open")]),  # hit
        _rec(phases=[_phase("Review", rounds_used=2, rounds_cap=2),   # hit
                     _phase("Test", rounds_used=1, rounds_cap=3),
                     _revise([(1, 0)])]),
        _rec(phases=[_phase("Test", "skip")]),                        # no pair
    ])
    out, _ = _log(log)
    assert out["cap_exhaustion"] == {
        "review": {"hit": 1, "total": 1},
        "test": {"hit": 1, "total": 2},
        "revise": {"hit": 1, "total": 2},
    }


def test_revise_at_its_cap_counts_only_with_findings_left_open(tmp_path: Path) -> None:
    # Round 2 runs after every fix commit, so a clean Revise at its cap is its
    # normal path; a warn or fail there is the record's spelling for residue.
    log = _write(tmp_path / "l.jsonl", [
        _rec(phases=[_revise([(1, 2), (2, 1)])]),                                 # clean
        _rec(phases=[_revise([(1, 2), (2, 1)], status="warn", reason="open")]),   # hit
        _rec(phases=[_revise([(1, 2), (2, 1)], status="fail", reason="open")]),   # hit
        _rec(phases=[_revise([(1, 2)], status="warn", reason="push failed")]),    # below cap
        # The writer accepts more rounds than the cap; that still reached it.
        _rec(phases=[_revise([(1, 1), (2, 1), (3, 1)], status="warn", reason="open")]),
        # Only Revise needs the warn: Test reaching its cap is exhaustion either way.
        _rec(phases=[_phase("Test", rounds_used=4, rounds_cap=3)]),
    ])
    out, _ = _log(log)
    assert out["cap_exhaustion"]["revise"] == {"hit": 3, "total": 5}
    assert out["cap_exhaustion"]["test"] == {"hit": 1, "total": 1}


def test_revise_findings_sum_per_agent(tmp_path: Path) -> None:
    log = _write(tmp_path / "l.jsonl", [
        _rec(routing={"revise_findings_by_tier": {
            "code-reviewer": {"found": 2, "phantom": 0},
            "comment-analyzer": {"found": 1, "phantom": 1}}}),
        _rec(routing={"revise_findings_by_tier": {
            "code-reviewer": {"found": 3, "phantom": 1},
            "plugin-dev:skill-reviewer": {"found": 1, "phantom": 0}}}),
        _rec(routing={"implement_delegated": True}),  # no findings block
    ])
    out, _ = _log(log)
    assert out["revise_findings"] == {
        "code-reviewer": {"found": 5, "phantom": 1, "runs": 2},
        "comment-analyzer": {"found": 1, "phantom": 1, "runs": 1},
        "plugin-dev:skill-reviewer": {"found": 1, "phantom": 0, "runs": 1},
    }


def test_asks_tally_choices_per_header(tmp_path: Path) -> None:
    log = _write(tmp_path / "l.jsonl", [
        _rec(asks=[{"header": "Tree", "choice": "Commit first"},
                   {"header": "Scope", "choice": "Full"}]),
        _rec(asks=[{"header": "Tree", "choice": "Commit first"}]),
        _rec(asks=[{"header": "Tree", "choice": "Stash — then go"}]),
    ])
    out, _ = _log(log)
    assert {a["header"]: a["choices"] for a in out["asks"]} == {
        "Tree": {"Commit first": 2, "Stash — then go": 1},
        "Scope": {"Full": 1},
    }


# --- skipped lines -----------------------------------------------------------

# requirement: run-ledgers / Summarising recent spec-to-pr runs
def test_unreadable_lines_are_skipped_named_and_counted(tmp_path: Path) -> None:
    log = _write(tmp_path / "l.jsonl", [
        _rec(phases=[_phase("Ship", "warn", reason="kept")]),
        _rec(phases={"review": "ok"}),                              # old dict shape
        _rec(phases=[_revise([(1, 1)], used=True)]),                # bool count
        _rec(routing={"revise_findings_by_tier": {"opus": 3}}),     # not per agent
    ], raw_lines=["{not json", "[1, 2]"])
    out, err = _log(log)
    assert out["runs_analyzed"] == 1
    assert out["warn_reasons"] == [{"reason": "kept", "count": 1}]
    assert out["skipped_records"] == 5
    assert out["ledgers"][0]["skipped"] == 5
    for line, field in [(2, "`phases`"), (3, "`rounds_used`"),
                        (4, "`routing.revise_findings_by_tier`"), (5, "not JSON"),
                        (6, "not a JSON object")]:
        assert f"line {line} skipped: {field}" in err


def test_a_record_without_ts_or_change_is_skipped(tmp_path: Path) -> None:
    no_ts = _rec()
    del no_ts["ts"]
    log = _write(tmp_path / "l.jsonl", [no_ts, _rec(change=None)])
    out, err = _log(log)
    assert out["runs_analyzed"] == 0
    assert out["skipped_records"] == 2
    assert "`ts`" in err and "`change`" in err


# --- which ledgers: --log, the fleet default, the fallback ---------------------

# requirement: run-ledgers / Summarising recent spec-to-pr runs
def test_log_names_every_ledger_and_marks_a_missing_one(tmp_path: Path) -> None:
    real = _write(tmp_path / "a.jsonl", [_rec()])
    out, err = _log(real, tmp_path / "missing.jsonl", real)
    assert out["source"] == "log"
    assert out["ledgers"] == [
        {"path": str(real), "found": True, "records": 1, "skipped": 0},
        {"path": str(tmp_path / "missing.jsonl"), "found": False, "records": 0, "skipped": 0},
    ]
    assert out["runs_analyzed"] == 1  # the repeated path is read once
    assert "no ledger at" in err


def _fleet_repo(tmp_path: Path, bullets: list[str] | None) -> Path:
    """A repo whose ledger dir is `<repo>/cla.io/retro`, with an optional fleet file."""
    retro = tmp_path / "home" / "cla.io" / "retro"
    _write(retro / "spec-to-pr-runs.jsonl", [_rec(change="local")])
    if bullets is not None:
        (retro.parent / "fleet.local.md").write_text(
            "# fleet\n\nprose, not a bullet\n\n" + "".join(f"- {b}\n" for b in bullets),
            encoding="utf-8")
    return retro


# requirement: run-ledgers / Summarising recent spec-to-pr runs
def test_default_reads_every_root_in_the_fleet_file(tmp_path: Path) -> None:
    other = tmp_path / "other"
    _write(other / "cla.io" / "retro" / "spec-to-pr-runs.jsonl",
           [_rec(change="o1"), _rec(change="o2")])
    retro = _fleet_repo(tmp_path, [str(tmp_path / "home"),
                                   f"`{other}`   # a comment",
                                   str(tmp_path / "gone")])
    out, _ = _run("--limit", "0", env=_env(retro))
    assert out["source"] == "fleet"
    assert "fallback" not in out
    assert out["runs_analyzed"] == 3
    assert [(Path(e["path"]).parents[2].name, e["found"]) for e in out["ledgers"]] == [
        ("home", True), ("other", True), ("gone", False)]


def test_no_fleet_file_falls_back_to_the_local_ledger(tmp_path: Path) -> None:
    out, err = _run(env=_env(_fleet_repo(tmp_path, None)))
    assert out["source"] == "local"
    assert "no fleet file" in out["fallback"]
    assert out["runs_analyzed"] == 1
    assert "reading this repo's ledger only" in err


def test_a_fleet_file_with_no_bullets_falls_back(tmp_path: Path) -> None:
    out, _ = _run(env=_env(_fleet_repo(tmp_path, [])))
    assert out["source"] == "local"
    assert "lists no repo root" in out["fallback"]
    assert out["runs_analyzed"] == 1


# requirement: run-ledgers / Summarising recent spec-to-pr runs
def test_a_fleet_file_whose_roots_do_not_exist_here_falls_back(tmp_path: Path) -> None:
    # The fleet file holds per-machine absolute paths: another machine's list
    # resolves to nothing here, and reading nothing would look like a cold start.
    out, _ = _run(env=_env(_fleet_repo(tmp_path, [str(tmp_path / "x"), str(tmp_path / "y")])))
    assert out["source"] == "local"
    assert "exists on this machine" in out["fallback"]
    assert out["runs_analyzed"] == 1


def test_an_unresolvable_repo_root_fails_rather_than_guessing(tmp_path: Path) -> None:
    r = _call(env=_env(), cwd=tmp_path)  # not a git repo, no override
    assert r.returncode == 1
    assert "CLAUDE_RETRO_DIR" in r.stderr


# --- round-2 yield ---------------------------------------------------------

def _yield(tmp_path: Path, records: list, limit: int = 10, name: str = "l.jsonl") -> dict:
    out, _ = _log(_write(tmp_path / name, records), limit=limit)
    return out["round_2_yield"]


def _changes(n: int, surfaced: int, days: list[str]) -> list[dict]:
    """n changes that ran a round 2, `surfaced` of them finding something there,
    dated round-robin over `days`."""
    return [_rec(change=f"c{i}", ts=f"{days[i % len(days)]}T12:00:00Z",
                 phases=[_revise([(1, 3), (2, 1 if i < surfaced else 0)])])
            for i in range(n)]


# requirement: run-ledgers / Summarising recent spec-to-pr runs
def test_round_2_yield_counts_changes_and_the_ones_that_surfaced(tmp_path: Path) -> None:
    out = _yield(tmp_path, _changes(5, 3, ["2026-09-01", "2026-09-02"]))
    assert out["changes_with_round_2"] == 5
    assert out["surfaced_critical_or_important"] == 3
    assert out["chains"] == 2
    assert set(out) == {"changes_with_round_2", "surfaced_critical_or_important",
                        "chains", "chain_proxy"}


# requirement: run-ledgers / Summarising recent spec-to-pr runs
def test_round_2_yield_covers_the_window_like_every_other_metric(tmp_path: Path) -> None:
    # Six older changes that surfaced, then two recent ones that did not.
    records = _changes(6, 6, ["2026-09-01"]) + [
        _rec(change=f"late{i}", ts="2026-09-05T12:00:00Z", phases=[_revise([(1, 3), (2, 0)])])
        for i in range(2)]
    out = _yield(tmp_path, records, limit=3)
    assert (out["changes_with_round_2"], out["surfaced_critical_or_important"]) == (3, 1)
    out = _yield(tmp_path, records, limit=0)
    assert (out["changes_with_round_2"], out["surfaced_critical_or_important"]) == (8, 6)


def test_round_2_yield_counts_only_changes_where_a_round_2_ran(tmp_path: Path) -> None:
    records = _changes(4, 4, ["2026-09-01", "2026-09-02"]) + [
        # Round 1 only, round 2 on another phase, and a rerun of c0: none adds a change.
        _rec(change="single", phases=[_revise([(1, 9)])]),
        _rec(change="elsewhere", phases=[_phase("Test", rounds_used=1, rounds_cap=3),
                                         _phase("Propose")]),
        _rec(change="c0", ts="2026-09-03T00:00:00Z", phases=[_revise([(1, 1), (2, 0)])]),
    ]
    out = _yield(tmp_path, records)
    assert out["changes_with_round_2"] == 4
    assert out["surfaced_critical_or_important"] == 4
    assert out["chains"] == 3  # the rerun ran on a third date


def test_round_2_yield_chain_proxy_is_ledger_and_date(tmp_path: Path) -> None:
    # One date in two repos is two chains; the proxy is stated in the output.
    a = _write(tmp_path / "a" / "l.jsonl", _changes(4, 4, ["2026-09-01"]))
    b = _write(tmp_path / "b" / "l.jsonl", _changes(4, 4, ["2026-09-01"]))
    out, _ = _log(a, b)
    check = out["round_2_yield"]
    assert check["changes_with_round_2"] == 8  # c0..c3 in each repo are different changes
    assert check["chains"] == 2
    assert "ledger" in check["chain_proxy"] and "date" in check["chain_proxy"]


# --- --nudge -----------------------------------------------------------------

def _nudge_call(tmp_path: Path, records: list, raw_lines: list[str] = ()):
    retro = tmp_path / "cla.io" / "retro"
    _write(retro / "spec-to-pr-runs.jsonl", records, raw_lines)
    r = _call("--nudge", env=_env(retro))
    assert r.returncode == 0, r.stderr
    return r


def _nudge(tmp_path: Path, records: list, raw_lines: list[str] = ()) -> str:
    return _nudge_call(tmp_path, records, raw_lines).stdout


_REASONS = itertools.count()


def _capped(name: str, hit: bool) -> dict:
    """A phase at its cap when `hit` — for Revise, also still warning, each with
    its own reason so the repeated-reason trigger stays out of it."""
    if name == "Revise":
        return _phase(name, "warn" if hit else "ok", rounds_used=2, rounds_cap=2,
                      **({"reason": f"open {next(_REASONS)}"} if hit else {}))
    return _phase(name, rounds_used=3 if hit else 1, rounds_cap=3)


# requirement: run-ledgers / Handoff suggests a retro on recurring trouble
def test_nudge_on_three_revise_cap_hits_in_the_last_five(tmp_path: Path) -> None:
    records = [_rec(phases=[_capped("Revise", hit)])
               for hit in (False, False, True, True, False, True, False)]
    out = _nudge(tmp_path, records)
    assert out.count("\n") == 1
    assert "Revise hit its round cap and still warned in 3 of the last 5 runs" in out
    assert "/cla:spec-to-pr-retro" in out


# requirement: run-ledgers / Handoff suggests a retro on recurring trouble
def test_no_nudge_when_revise_reaches_its_cap_cleanly(tmp_path: Path) -> None:
    # Round 2 is routine: five clean Revise phases at the cap are not trouble.
    records = [_rec(phases=[_capped("Revise", False)]) for _ in range(5)]
    assert _nudge(tmp_path, records) == ""
    # A warn below the cap is not a cap hit either.
    below = [_rec(phases=[_phase("Revise", "warn", reason=f"r{i}", rounds_used=1,
                                 rounds_cap=2)]) for i in range(5)]
    assert _nudge(tmp_path, below) == ""


def test_nudge_counts_more_rounds_than_the_cap_as_a_hit(tmp_path: Path) -> None:
    records = [_rec(phases=[_phase("Test", rounds_used=4, rounds_cap=3)]) for _ in range(3)]
    assert "Test hit its round cap in 3 of the last 3 runs" in _nudge(tmp_path, records)


def test_nudge_on_three_test_cap_hits(tmp_path: Path) -> None:
    out = _nudge(tmp_path, [_rec(phases=[_capped("Test", True)]) for _ in range(3)])
    assert "Test hit its round cap in 3 of the last 3 runs" in out


# requirement: run-ledgers / Handoff suggests a retro on recurring trouble
def test_no_nudge_on_two_cap_hits_or_cap_one(tmp_path: Path) -> None:
    records = [_rec(phases=[_capped("Revise", h), _capped("Test", h)])
               for h in (True, True, False, False, False)]
    assert _nudge(tmp_path, records) == ""
    # A cap of 1 used is a single pass, not exhaustion — even on a Revise that warned.
    single = [_rec(phases=[_phase("Test", rounds_used=1, rounds_cap=1),
                           _phase("Revise", "warn", reason=f"r{i}", rounds_used=1, rounds_cap=1)])
              for i in range(5)]
    assert _nudge(tmp_path, single) == ""


def test_old_cap_hits_outside_the_last_five_do_not_nudge(tmp_path: Path) -> None:
    records = [_rec(phases=[_capped("Revise", True)]) for _ in range(3)]
    records += [_rec(phases=[_capped("Revise", False)]) for _ in range(5)]
    assert _nudge(tmp_path, records) == ""


# requirement: run-ledgers / Handoff suggests a retro on recurring trouble
def test_nudge_on_a_warn_reason_repeated_in_two_runs(tmp_path: Path) -> None:
    records = [
        _rec(phases=[_phase("Ship", "warn", reason="push refused")]),
        _rec(),
        _rec(phases=[_phase("Ship", "fail", reason="push refused")]),
    ]
    out = _nudge(tmp_path, records)
    assert 'warn reason "push refused" recurred in 2 of the last 3 runs' in out


def test_no_nudge_on_one_run_repeating_a_reason_or_on_the_placeholder(tmp_path: Path) -> None:
    records = [
        _rec(phases=[_phase("Ship", "warn", reason="same"), _phase("Archive", "warn", reason="same")]),
        _rec(phases=[_phase("Ship", "warn", reason=PLACEHOLDER)]),
        _rec(phases=[_phase("Ship", "warn", reason=PLACEHOLDER)]),
    ]
    assert _nudge(tmp_path, records) == ""


def test_nudge_joins_every_trigger_into_one_line(tmp_path: Path) -> None:
    records = [_rec(phases=[_capped("Revise", True), _phase("Ship", "warn", reason="r")])
               for _ in range(3)]
    out = _nudge(tmp_path, records)
    assert out.count("\n") == 1
    assert "Revise hit" in out and 'warn reason "r"' in out


def test_nudge_skips_unreadable_lines_and_never_fails(tmp_path: Path) -> None:
    assert _nudge(tmp_path, [_rec()], raw_lines=["{broken"]) == ""
    # No ledger at all: nothing printed, exit 0.
    r = _call("--nudge", env=_env(tmp_path / "nowhere"))
    assert (r.returncode, r.stdout) == (0, "")
    # Unresolvable repo root: still exit 0.
    r = _call("--nudge", env=_env(), cwd=tmp_path)
    assert (r.returncode, r.stdout) == (0, "")


def test_nudge_reads_only_this_repos_ledger(tmp_path: Path) -> None:
    r = _call("--nudge", "--log", str(tmp_path / "x.jsonl"))
    assert r.returncode == 2  # argparse: mutually exclusive


# requirement: run-ledgers / Handoff suggests a retro on recurring trouble
def test_handoff_prints_the_nudge_after_appending_the_record() -> None:
    command = "spec-to-pr-retro/scripts/spec_to_pr_aggregate.py --nudge"
    for prose in (_SKILLS / "spec-to-pr" / "references" / "handoff.md",
                  _SKILLS / "spec-to-pr" / "SKILL.md"):
        text = prose.read_text(encoding="utf-8")
        assert command in text, f"{prose.name} no longer runs the nudge"
        # After the append, which is what makes this run one of the last five.
        assert text.index("lib/log_run.py") < text.index(command), prose.name
