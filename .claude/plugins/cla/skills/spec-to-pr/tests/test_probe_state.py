"""probe_state.py tests.

Patches REPO_ROOT to the tmp repo so subprocess invocations of `git`/`openspec`/`gh`
operate against the test fixture. `gh` is mocked via monkeypatched _run.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import probe_state
from conftest import commit_on_branch, make_change


REPO_VIEW_KEY = ("gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner")
REPO_VIEW_OK = subprocess.CompletedProcess([], 0, "owner/agentic-air\n", "")
REPO_VIEW_FAIL = subprocess.CompletedProcess([], 1, "", "not authenticated")


@pytest.fixture(autouse=True)
def _repo_root(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(probe_state, "REPO_ROOT", tmp_repo)


def _stub_run(returns: dict[tuple[str, ...], subprocess.CompletedProcess[str]]):
    def fake(cmd, cwd=None, check=False):
        key = tuple(cmd)
        if key in returns:
            return returns[key]
        # Default to subprocess.run for git commands
        return subprocess.run(cmd, cwd=cwd, check=check, capture_output=True, text=True)
    return fake


def _gh_closed_stubs(branch: str) -> dict:
    """Stubs that make _pr_state return {open: False, url: None} via repo-view failure."""
    return {REPO_VIEW_KEY: REPO_VIEW_FAIL}


def test_no_artifacts(tmp_repo: Path, monkeypatch):
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "missing", "--json"):
            subprocess.CompletedProcess([], 1, "", "no such change"),
        REPO_VIEW_KEY: REPO_VIEW_FAIL,
    }))
    result = probe_state.probe("missing")
    assert result["propose"] is False
    assert result["implement"] is False
    assert result["branch"] is False
    assert result["pr"] == {"open": False, "url": None}
    assert result["fix_rounds_applied"] == 0
    assert result["archived"] is False


def test_archived_detection(tmp_repo: Path, monkeypatch):
    archive_dir = tmp_repo / "openspec" / "changes" / "archive" / "2026-05-03-demo"
    archive_dir.mkdir(parents=True)
    (archive_dir / "proposal.md").write_text("## Why\n", encoding="utf-8")
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "demo", "--json"):
            subprocess.CompletedProcess([], 1, "", ""),
        REPO_VIEW_KEY: REPO_VIEW_FAIL,
    }))
    result = probe_state.probe("demo")
    assert result["archived"] is True
    assert result["propose"] is False


def test_archived_no_suffix_collision(tmp_repo: Path, monkeypatch):
    """Change `bar` must NOT match archive dir `2026-05-03-add-foo-bar`."""
    archive_dir = tmp_repo / "openspec" / "changes" / "archive" / "2026-05-03-add-foo-bar"
    archive_dir.mkdir(parents=True)
    (archive_dir / "proposal.md").write_text("## Why\n", encoding="utf-8")
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "bar", "--json"):
            subprocess.CompletedProcess([], 1, "", ""),
        REPO_VIEW_KEY: REPO_VIEW_FAIL,
    }))
    result = probe_state.probe("bar")
    assert result["archived"] is False, "suffix collision: 'bar' wrongly matched 'add-foo-bar'"


def test_archived_no_match_when_archive_dir_present_but_different_name(tmp_repo: Path, monkeypatch):
    archive_dir = tmp_repo / "openspec" / "changes" / "archive" / "2026-05-03-other-change"
    archive_dir.mkdir(parents=True)
    (archive_dir / "proposal.md").write_text("## Why\n", encoding="utf-8")
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "demo", "--json"):
            subprocess.CompletedProcess([], 1, "", ""),
        REPO_VIEW_KEY: REPO_VIEW_FAIL,
    }))
    result = probe_state.probe("demo")
    assert result["archived"] is False


def test_archived_ignores_non_date_prefixed_dirs(tmp_repo: Path, monkeypatch):
    bad = tmp_repo / "openspec" / "changes" / "archive" / "demo"
    bad.mkdir(parents=True)
    (bad / "proposal.md").write_text("## Why\n", encoding="utf-8")
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "demo", "--json"):
            subprocess.CompletedProcess([], 1, "", ""),
        REPO_VIEW_KEY: REPO_VIEW_FAIL,
    }))
    result = probe_state.probe("demo")
    assert result["archived"] is False


def test_proposal_exists(tmp_repo: Path, monkeypatch):
    make_change(tmp_repo, "demo")
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "demo", "--json"):
            subprocess.CompletedProcess([], 1, "", ""),
        REPO_VIEW_KEY: REPO_VIEW_FAIL,
    }))
    result = probe_state.probe("demo")
    assert result["propose"] is True
    assert result["implement"] is False


def test_implement_complete(tmp_repo: Path, monkeypatch):
    make_change(tmp_repo, "demo")
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "demo", "--json"):
            subprocess.CompletedProcess([], 0, json.dumps({"isComplete": True}), ""),
        REPO_VIEW_KEY: REPO_VIEW_FAIL,
    }))
    result = probe_state.probe("demo")
    assert result["implement"] is True


def test_branch_present_and_ahead(tmp_repo: Path, monkeypatch):
    commit_on_branch(tmp_repo, "feature/demo", "first feature commit")
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "demo", "--json"):
            subprocess.CompletedProcess([], 1, "", ""),
        REPO_VIEW_KEY: REPO_VIEW_FAIL,
    }))
    result = probe_state.probe("demo")
    assert result["branch"] is True


def test_pr_open(tmp_repo: Path, monkeypatch):
    make_change(tmp_repo, "demo")
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "demo", "--json"):
            subprocess.CompletedProcess([], 1, "", ""),
        REPO_VIEW_KEY: REPO_VIEW_OK,
        ("gh", "pr", "view", "feature/demo", "--repo", "owner/agentic-air", "--json", "url,state"):
            subprocess.CompletedProcess([], 0,
                json.dumps({"url": "https://example.com/pr/42", "state": "OPEN"}), ""),
    }))
    result = probe_state.probe("demo")
    assert result["pr"] == {"open": True, "url": "https://example.com/pr/42"}


def test_pr_probe_scoped_to_current_repo(tmp_repo: Path, monkeypatch):
    """Regression: _pr_state must scope `gh pr view` by --repo so a fork or
    multiple-PR-on-same-branch context cannot resolve to the wrong PR.

    Mocks: `gh repo view` returns `owner/agentic-air`. The unscoped form
    (`gh pr view feature/demo --json url,state`) is intentionally NOT in the
    stub map — if _pr_state ever reverts to that shape, the test fixture's
    fallback subprocess will run real `gh` and the assertion still fails (no
    matching open PR for this tmp repo).
    """
    make_change(tmp_repo, "demo")
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "demo", "--json"):
            subprocess.CompletedProcess([], 1, "", ""),
        REPO_VIEW_KEY: REPO_VIEW_OK,
        # Only the SCOPED form is wired to a successful response. Unscoped form
        # would 404 / hit the wrong repo.
        ("gh", "pr", "view", "feature/demo", "--repo", "owner/agentic-air", "--json", "url,state"):
            subprocess.CompletedProcess([], 0,
                json.dumps({"url": "https://example.com/owner/agentic-air/pr/7", "state": "OPEN"}), ""),
    }))
    result = probe_state.probe("demo")
    assert result["pr"]["open"] is True
    assert result["pr"]["url"] == "https://example.com/owner/agentic-air/pr/7"


def test_pr_state_degrades_when_repo_view_returns_empty_stdout(tmp_repo: Path, monkeypatch):
    """`gh repo view` exits 0 but emits nothing (or whitespace only). _pr_state
    must NOT then call `gh pr view --repo "" ...` — it must short-circuit to
    closed/None."""
    make_change(tmp_repo, "demo")
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "demo", "--json"):
            subprocess.CompletedProcess([], 1, "", ""),
        REPO_VIEW_KEY: subprocess.CompletedProcess([], 0, "\n", ""),
    }))
    result = probe_state.probe("demo")
    assert result["pr"] == {"open": False, "url": None}


def test_pr_state_strips_repo_view_trailing_newline(tmp_repo: Path, monkeypatch):
    """Real `gh repo view` returns stdout with a trailing newline; the helper
    must strip it before forming the --repo argument."""
    make_change(tmp_repo, "demo")
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "demo", "--json"):
            subprocess.CompletedProcess([], 1, "", ""),
        REPO_VIEW_KEY: subprocess.CompletedProcess([], 0, "owner/agentic-air\n", ""),
        # If strip is dropped, the lookup key would carry the newline and miss this stub.
        ("gh", "pr", "view", "feature/demo", "--repo", "owner/agentic-air", "--json", "url,state"):
            subprocess.CompletedProcess([], 0,
                json.dumps({"url": "https://example.com/pr/9", "state": "OPEN"}), ""),
    }))
    result = probe_state.probe("demo")
    assert result["pr"]["open"] is True


def test_pr_state_degrades_when_repo_view_fails(tmp_repo: Path, monkeypatch):
    """If `gh repo view` itself fails (unauthenticated, no remote), _pr_state
    must degrade to {open: False, url: None} rather than raise."""
    make_change(tmp_repo, "demo")
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "demo", "--json"):
            subprocess.CompletedProcess([], 1, "", ""),
        REPO_VIEW_KEY: REPO_VIEW_FAIL,
    }))
    result = probe_state.probe("demo")
    assert result["pr"] == {"open": False, "url": None}


def test_fix_rounds_counted(tmp_repo: Path, monkeypatch):
    commit_on_branch(tmp_repo, "feature/demo", "feat: demo")
    commit_on_branch(tmp_repo, "feature/demo", "fix: review round 1")
    commit_on_branch(tmp_repo, "feature/demo", "fix: review round 2")
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "demo", "--json"):
            subprocess.CompletedProcess([], 1, "", ""),
        REPO_VIEW_KEY: REPO_VIEW_FAIL,
    }))
    result = probe_state.probe("demo")
    assert result["fix_rounds_applied"] == 2


def test_fix_rounds_uses_distinct_count_not_max(tmp_repo: Path, monkeypatch):
    """Regression: _fix_rounds_applied counts DISTINCT round numbers, not max(N).

    A manual squash that drops round 2 but keeps rounds 1 and 3 must report 2
    (distinct rounds present), not 3 (max number). The round counter is
    consumed downstream as 'next round to apply' and a wrong count silently
    breaks Revise's diff-scoping.
    """
    commit_on_branch(tmp_repo, "feature/demo", "feat: demo")
    commit_on_branch(tmp_repo, "feature/demo", "fix: review round 1")
    commit_on_branch(tmp_repo, "feature/demo", "fix: review round 3")
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "demo", "--json"):
            subprocess.CompletedProcess([], 1, "", ""),
        REPO_VIEW_KEY: REPO_VIEW_FAIL,
    }))
    result = probe_state.probe("demo")
    assert result["fix_rounds_applied"] == 2, (
        "must count distinct round numbers (1 and 3 present, round 2 squashed) "
        "and not max(N)"
    )


def test_fix_rounds_dedupes_repeated_round_numbers(tmp_repo: Path, monkeypatch):
    """Two commits both labeled `fix: review round 1` (e.g. round 1 was squashed
    and re-applied) must collapse to 1, not 2. Pins the dedup behavior so a
    refactor from `set` to `list` would be caught."""
    commit_on_branch(tmp_repo, "feature/demo", "feat: demo")
    commit_on_branch(tmp_repo, "feature/demo", "fix: review round 1")
    commit_on_branch(tmp_repo, "feature/demo", "fix: review round 1")
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "demo", "--json"):
            subprocess.CompletedProcess([], 1, "", ""),
        REPO_VIEW_KEY: REPO_VIEW_FAIL,
    }))
    result = probe_state.probe("demo")
    assert result["fix_rounds_applied"] == 1, (
        "duplicate round numbers must dedupe — len(set(rounds)), not len(rounds)"
    )


def test_tools_missing_surfaces_in_result(tmp_repo: Path, monkeypatch):
    """Regression: when openspec.cmd or gh is not on PATH, _run catches the
    FileNotFoundError and records the tool as missing. probe() must surface
    `tools_missing` in the JSON so the orchestrator distinguishes "phase
    not done" from "tool unavailable" — the documented Windows-degradation
    contract. Without this, missing tools look identical to incomplete
    workflows and resume picks the wrong phase."""
    def fake_run(cmd, cwd=None, check=False):
        # Simulate openspec.cmd missing on PATH (the typical Windows path).
        if cmd and cmd[0] == "openspec":
            if cmd[0] not in probe_state._missing_tools:
                probe_state._missing_tools.append(cmd[0])
            return subprocess.CompletedProcess(
                cmd, returncode=probe_state._TOOL_MISSING_RC, stdout="",
                stderr=f"executable not found: {cmd[0]}")
        # Other commands fall through to a generic non-zero so the rest of
        # probe() can complete without exploding.
        return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="")

    monkeypatch.setattr(probe_state, "_run", fake_run)
    result = probe_state.probe("demo")
    assert "tools_missing" in result, (
        "tools_missing must appear in result whenever any required tool is unavailable"
    )
    assert "openspec" in result["tools_missing"]
    assert result["implement"] is False  # not "complete" — we couldn't tell
