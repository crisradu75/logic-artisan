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
        ["python", str(_HOOK)],
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
        ["python", str(_HOOK)],
        input="not json",
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    assert r.returncode == 0
