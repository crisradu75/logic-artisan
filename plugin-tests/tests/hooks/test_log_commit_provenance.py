"""The commit-provenance hook records what happened and never guesses.

This ledger exists to supply a denominator the retro loops have never had: how
many commits went through a skill versus around one. Two failure shapes would
destroy that number, and both are worse than the hook not existing:

  - OVER-recording. A line written for something that was not a commit (a
    `--dry-run`, a `git log --grep="git commit"`, a failed commit) inflates the
    total and makes bypass look better than it is.
  - WRONG attribution. Guessing a skill from an unrecognised subject inflates
    the numerator, which is the exact figure the loops would act on.

So the tests below are mostly about what it declines to write.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_HOOK = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "hooks" / "log-commit-provenance.py"


def _load():
    spec = importlib.util.spec_from_file_location("_log_commit_provenance", _HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load()


# ---------- command recognition ----------


@pytest.mark.parametrize(
    "command",
    [
        "git commit -m 'x'",
        'git commit -m "feat: y"',
        "git -C /some/path commit -m 'x'",
        "git.exe commit -m 'x'",
        "GIT commit -m 'x'",
    ],
)
def test_a_real_commit_is_recognised(command):
    assert mod._is_commit_command(command) is True


@pytest.mark.parametrize(
    "command",
    [
        'git log --grep="git commit"',
        "git commit --dry-run",
        "git show HEAD --format='git commit'",
        "echo 'run git commit later'",
        "git rev-list --all",
        "git status",
    ],
)
def test_a_non_commit_is_not_recognised(command):
    """Over-recording corrupts the ratio this hook exists to report."""
    assert mod._is_commit_command(command) is False


# ---------- skill attribution ----------


@pytest.mark.parametrize(
    "subject,expected",
    [
        ("fix: review round 2", "spec-to-pr"),
        ("chore: archive add-thing", "spec-to-pr"),
        ("chore: spec-to-pr run log", "spec-to-pr"),
        ("fix: address review findings", "lite-pr"),
    ],
)
def test_a_known_skill_subject_is_attributed(subject, expected, monkeypatch):
    monkeypatch.delenv("CLAUDE_SKILL", raising=False)
    monkeypatch.delenv("CLA_ACTIVE_SKILL", raising=False)
    assert mod._detect_skill(subject) == expected


@pytest.mark.parametrize(
    "subject",
    [
        "docs: tidy the readme",
        "feat: something a human typed",
        "Merge pull request #12 from x",
        "release: 1.2.3",
    ],
)
def test_an_unrecognised_subject_is_null_not_guessed(subject, monkeypatch):
    """`null` is the honest answer. A guess here inflates the numerator, which is
    the one number a retro would act on."""
    monkeypatch.delenv("CLAUDE_SKILL", raising=False)
    monkeypatch.delenv("CLA_ACTIVE_SKILL", raising=False)
    assert mod._detect_skill(subject) is None


def test_an_explicit_env_skill_wins_over_subject_inference(monkeypatch):
    monkeypatch.setenv("CLAUDE_SKILL", "multi-pr")
    assert mod._detect_skill("fix: review round 1") == "multi-pr"


# ---------- end to end, against a real repo ----------


def _repo(tmp_path: Path) -> Path:
    def git(*a):
        subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    (tmp_path / "f.txt").write_text("x\n", encoding="utf-8")
    git("add", "f.txt")
    git("commit", "-q", "-m", "fix: review round 1")
    (tmp_path / "cla.io" / "retro").mkdir(parents=True)
    return tmp_path


def _run(repo: Path, command: str, env_extra=None):
    import os

    env = {**os.environ, **(env_extra or {})}
    env.pop("CLAUDE_SKILL", None)
    env.pop("CLA_ACTIVE_SKILL", None)
    env.pop("CLAUDE_RETRO_DIR", None)
    payload = json.dumps({"tool_input": {"command": command}, "cwd": str(repo)})
    return subprocess.run(
        [sys.executable, str(_HOOK)],
        input=payload,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )


def _ledger(repo: Path):
    f = repo / "cla.io" / "retro" / "commit-provenance.jsonl"
    if not f.is_file():
        return []
    return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_it_writes_one_line_for_a_real_commit(tmp_path):
    repo = _repo(tmp_path)
    r = _run(repo, "git commit -m 'fix: review round 1'")
    assert r.returncode == 0, r.stderr
    rows = _ledger(repo)
    assert len(rows) == 1
    assert rows[0]["subject"] == "fix: review round 1"
    assert rows[0]["skill"] == "spec-to-pr"
    assert rows[0]["branch"] == "main"
    assert rows[0]["sha"]


def test_it_writes_nothing_for_a_non_commit(tmp_path):
    repo = _repo(tmp_path)
    assert _run(repo, "git status").returncode == 0
    assert _ledger(repo) == []


def test_it_writes_nothing_when_the_retro_dir_does_not_exist(tmp_path):
    """A repo that never ran `cla-init` has not opted into per-repo state; the
    hook must not create the tree to satisfy itself."""
    repo = _repo(tmp_path)
    (repo / "cla.io" / "retro").rmdir()
    assert _run(repo, "git commit -m 'fix: review round 1'").returncode == 0
    assert not (repo / "cla.io" / "retro").exists()


def test_it_is_silent_and_exits_zero_outside_a_git_repo(tmp_path):
    """Best-effort: a telemetry hook must never disrupt a workflow."""
    (tmp_path / "cla.io" / "retro").mkdir(parents=True)
    r = _run(tmp_path, "git commit -m 'x'")
    assert r.returncode == 0
    assert _ledger(tmp_path) == []


def test_malformed_stdin_exits_zero(tmp_path):
    r = subprocess.run(
        [sys.executable, str(_HOOK)],
        input="not json",
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    assert r.returncode == 0


# ---------- the Measured-by column ----------
#
# The Ship and Revise commit steps require one `Measured-by:` trailer per
# measurement a change asserts, and nothing gates a single commit. Whether that
# rule is followed is therefore answerable only from this ledger, which makes
# these columns the evidence — so they are tested for the two ways a count goes
# wrong: reading nothing when trailers exist, and reporting a shortened list as
# though it were the whole one.


def _commit_with(repo: Path, subject: str, trailer_block: str | None) -> None:
    (repo / "f.txt").write_text(subject + "\n", encoding="utf-8")
    args = ["git", "commit", "-q", "-a", "-m", subject]
    if trailer_block is not None:
        args += ["-m", trailer_block]
    subprocess.run(args, cwd=repo, check=True, capture_output=True)


def test_trailers_are_recorded_with_an_exact_count(tmp_path):
    repo = _repo(tmp_path)
    _commit_with(
        repo,
        "fix: review round 2",
        "Measured-by: pytest plugin-tests -q — 1237 passed\n"
        "Measured-by: node --test x.mjs — 70 pass",
    )
    assert _run(repo, "git commit -m 'fix: review round 2'").returncode == 0
    row = _ledger(repo)[-1]
    assert row["measured_by_count"] == 2
    assert row["measured_by"] == [
        "pytest plugin-tests -q — 1237 passed",
        "node --test x.mjs — 70 pass",
    ]


def test_a_commit_asserting_nothing_records_an_empty_list_not_a_missing_key(tmp_path):
    """The rule says a change asserting no measurement writes no trailer, so
    zero is a real reading rather than an absence. A missing key would be
    indistinguishable from a hook that could not parse the commit."""
    repo = _repo(tmp_path)
    _commit_with(repo, "chore: no claims here", None)
    assert _run(repo, "git commit -m 'chore: no claims here'").returncode == 0
    row = _ledger(repo)[-1]
    assert row["measured_by_count"] == 0
    assert row["measured_by"] == []


def test_a_wrapped_trailer_is_one_value_not_two_fragments(tmp_path):
    """`unfold=true`. A long command wrapped across lines is still one claim;
    recorded as fragments it would inflate the count it exists to report."""
    repo = _repo(tmp_path)
    _commit_with(
        repo,
        "feat: wrapped",
        "Measured-by: git log -8 -p --format= --unified=0\n"
        "  | grep -cE '^[+]' — 7280 added lines",
    )
    assert _run(repo, "git commit -m 'feat: wrapped'").returncode == 0
    row = _ledger(repo)[-1]
    assert row["measured_by_count"] == 1
    assert "7280 added lines" in row["measured_by"][0]


def test_an_oversize_record_sheds_values_but_never_the_count(tmp_path):
    """The ceiling must cost detail, not the commit. Dropping the whole line
    would remove the commit from the denominator too — the number this hook was
    built to supply."""
    repo = _repo(tmp_path)
    trailers = "\n".join(
        f"Measured-by: {'c' * 300} — claim {i}" for i in range(12)
    )
    _commit_with(repo, "feat: many claims", trailers)
    assert _run(repo, "git commit -m 'feat: many claims'").returncode == 0
    rows = _ledger(repo)
    # One hook invocation, one line. The fixture's own commit predates the hook
    # and writes nothing, so a dropped line would leave the ledger empty.
    assert len(rows) == 1, "the line must still be written, not dropped"
    row = rows[-1]
    assert row["measured_by_count"] == 12, "the count is exact regardless of shedding"
    assert len(row["measured_by"]) < 12, "values must have been shed to fit"
    assert all(len(v) <= mod._MAX_TRAILER_CHARS for v in row["measured_by"])
    line_bytes = len(json.dumps(row, ensure_ascii=False).encode("utf-8")) + 1
    assert line_bytes <= mod._MAX_LINE_BYTES


def test_the_shedding_loop_terminates_on_a_record_that_can_never_fit(monkeypatch):
    """A subject alone over the ceiling exhausts the list and must then return
    without writing, rather than looping. Reached by shrinking the ceiling,
    since no real subject is 2 KiB."""
    monkeypatch.setattr(mod, "_MAX_LINE_BYTES", 10)
    record = {"subject": "x" * 50, "measured_by_count": 3, "measured_by": ["a", "b", "c"]}
    while (
        len(json.dumps(record, ensure_ascii=False).encode("utf-8")) > mod._MAX_LINE_BYTES
        and record["measured_by"]
    ):
        record["measured_by"] = record["measured_by"][:-1]
    assert record["measured_by"] == []
    assert record["measured_by_count"] == 3
