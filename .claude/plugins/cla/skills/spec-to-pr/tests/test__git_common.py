"""_git_common.py tests.

Every consumer (branch.py, commit.py, check_permissions.py, discover_tests.py,
probe_state.py) monkeypatches its own module-level `REPO_ROOT` directly in
tests, so `repo_root()`'s actual git-invocation and fallback logic was never
exercised by any of those five test files, before or after the extraction
that consolidated five identical copies into this one function. These tests
close that gap.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import _git_common


def test_resolves_the_real_toplevel_from_a_nested_directory(
    monkeypatch, tmp_path: Path
) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    assert _git_common.repo_root().resolve() == tmp_path.resolve()


def test_falls_back_to_cwd_when_git_is_unavailable(monkeypatch, tmp_path: Path) -> None:
    def boom(*_a, **_kw):
        raise FileNotFoundError("git not on PATH")

    monkeypatch.setattr(_git_common.subprocess, "run", boom)
    monkeypatch.chdir(tmp_path)
    assert _git_common.repo_root() == tmp_path


def test_falls_back_to_cwd_on_timeout(monkeypatch, tmp_path: Path) -> None:
    def boom(*_a, **_kw):
        raise subprocess.TimeoutExpired(cmd="git", timeout=10)

    monkeypatch.setattr(_git_common.subprocess, "run", boom)
    monkeypatch.chdir(tmp_path)
    assert _git_common.repo_root() == tmp_path


def test_falls_back_to_cwd_when_git_rejects_the_directory(
    monkeypatch, tmp_path: Path
) -> None:
    # git's own "not a repository" exit: non-zero returncode, no stdout.
    def not_a_repo(*_a, **_kw):
        return subprocess.CompletedProcess(
            args=["git", "rev-parse", "--show-toplevel"],
            returncode=128, stdout="", stderr="fatal: not a git repository",
        )

    monkeypatch.setattr(_git_common.subprocess, "run", not_a_repo)
    monkeypatch.chdir(tmp_path)
    assert _git_common.repo_root() == tmp_path


# --------------------------------------------------------------------------- #
# MD-15 / MD-12 — the branch prefix was hardcoded in the scripts that both
# CREATE the branch and LOOK IT UP, and a miss read as a clean negative.
# --------------------------------------------------------------------------- #


def test_prefix_from_text_takes_the_first_real_line():
    """Split out from file reading so it is testable without a real file at a
    `__file__`-relative path."""
    assert _git_common.prefix_from_text("claude/fix/") == "claude/fix/"
    assert _git_common.prefix_from_text("# a comment\n\nclaude/fix/\n") == "claude/fix/"
    assert _git_common.prefix_from_text("<!-- html comment -->\nwip/\n") == "wip/"


def test_a_missing_trailing_slash_is_added():
    assert _git_common.prefix_from_text("claude/fix") == "claude/fix/"


def test_an_empty_or_comment_only_overlay_yields_none():
    """So `branch_prefix` falls through to the default rather than producing
    `<change-name>` with no prefix at all."""
    assert _git_common.prefix_from_text("") is None
    assert _git_common.prefix_from_text("# only a comment\n\n") is None


def test_the_env_var_overrides_everything(monkeypatch):
    monkeypatch.setenv("CLA_BRANCH_PREFIX", "claude/fix/")
    assert _git_common.branch_name("my-change") == "claude/fix/my-change"


def test_the_env_var_gets_a_trailing_slash_too(monkeypatch):
    monkeypatch.setenv("CLA_BRANCH_PREFIX", "wip")
    assert _git_common.branch_name("x") == "wip/x"


def test_the_default_is_feature_when_nothing_is_configured(monkeypatch):
    """`feature/` stays the default — this is a generalization, not a change of
    behaviour for repos already on that convention."""
    monkeypatch.delenv("CLA_BRANCH_PREFIX", raising=False)
    monkeypatch.setattr(_git_common, "branch_prefix", lambda: _git_common.DEFAULT_BRANCH_PREFIX)
    assert _git_common.branch_name("my-change") == "feature/my-change"
