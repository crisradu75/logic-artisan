"""_git_common.py tests.

`probe_state.py`, the one surviving consumer, monkeypatches its own
module-level `REPO_ROOT` directly in tests, so `repo_root()`'s actual
git-invocation and fallback logic is never exercised there. These tests close
that gap. (The function was extracted when five scripts each carried a
byte-identical copy; four of those five were deleted in the script audit.)
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


def test_prefix_from_text_reads_the_flat_frontmatter_key():
    """Flat `key: value` between `---` fences — the format every other overlay
    in the plugin used, back when there were others. This one
    originally read "the first non-comment line", a third syntax for the third
    overlay, which gave the value no name at the point of use."""
    assert _git_common.prefix_from_text("---\nbranch_prefix: claude/fix/\n---\n") == "claude/fix/"
    assert _git_common.prefix_from_text(
        "---\nother_key: x\nbranch_prefix: wip/\n---\nbody text\n"
    ) == "wip/"


def test_the_prefix_is_used_verbatim_with_no_trailing_slash_forced(capsys):
    """Forcing a trailing `/` ruled out a flat prefix like `wip-`, which a repo
    may legitimately want. The default carries its own slash, so nothing is lost
    by leaving the choice to whoever writes the overlay."""
    assert _git_common.prefix_from_text("---\nbranch_prefix: wip-\n---\n") == "wip-"
    assert capsys.readouterr().err == ""


# --- the diagnostics, and the split that makes them meaningful --------------- #
#
# These four are the entire argument for this implementation over the silent
# one, and they are the part a suite most easily fails to hold: measured before
# they existed, neutering every `_warn` call left the whole scope green. A
# diagnostic nobody asserts on can be deleted by a refactor, a mutation, or a
# sync — which returns you to the silent fallback, with the code still looking
# correct.


def test_an_unusable_key_warns_and_falls_back(capsys):
    assert _git_common.prefix_from_text("---\nbranch_prefix:\n---\n") is None
    assert "no usable" in capsys.readouterr().err


def test_a_missing_frontmatter_fence_warns(capsys):
    assert _git_common.prefix_from_text("claude/fix/\n") is None
    err = capsys.readouterr().err
    # "does not start with", not merely "---": a mutation disabling this check
    # falls through to the UNCLOSED-fence branch, whose message also contains
    # `---` and the overlay name, so the looser assertion passed on the wrong
    # branch. The two degradations have different causes and must stay
    # distinguishable to whoever has to fix the overlay.
    assert "does not start with" in err
    assert _git_common._BRANCH_PREFIX_OVERLAY in err


def test_an_unclosed_frontmatter_fence_warns(capsys):
    assert _git_common.prefix_from_text("---\nbranch_prefix: wip/\n") is None
    assert "closing" in capsys.readouterr().err


def test_an_absent_overlay_is_silent(monkeypatch, capsys, tmp_path):
    """The non-vacuity partner, and the one case that must stay quiet: not
    configured is the ORDINARY state, so a warning here would fire in every repo
    carrying no overlay — which is most of them, including this one.

    The overlay path is repo-root-relative, so `is_file` is intercepted for
    that one leaf name and delegated for everything else, rather than writing
    into the live `cla.io/overlays/` directory.
    """
    real_is_file = _git_common.Path.is_file

    def _fake_is_file(self):
        if self.name == _git_common._BRANCH_PREFIX_OVERLAY:
            return False
        return real_is_file(self)

    monkeypatch.delenv("CLA_BRANCH_PREFIX", raising=False)
    monkeypatch.setattr(_git_common.Path, "is_file", _fake_is_file)
    assert _git_common.branch_prefix() == _git_common.DEFAULT_BRANCH_PREFIX
    assert capsys.readouterr().err == "", "an un-configured repo must not be warned at"


def test_a_present_overlay_is_actually_read_end_to_end(monkeypatch, tmp_path, capsys):
    """The join between `overlay_path()` and `prefix_from_text()` — the ONE path
    that matters in a configured repo, and the one nothing covered.

    Measured: mutating `branch_prefix`'s final line to `return
    DEFAULT_BRANCH_PREFIX` survived both this scope and `consistency-checks`.
    Every other test here either exercises `prefix_from_text` as a pure function,
    forces the overlay absent, or sets `CLA_BRANCH_PREFIX` — which short-circuits
    before the file is ever opened. The scope's own `conftest` pins that env var
    for every test, so it must be deleted here.

    What the gap costs, in this module's own words: a configured repo silently
    gets `feature/`, and `probe_state` then reports finished work as not started
    — which the orchestrator answers by redoing it and opening a duplicate PR.
    """
    monkeypatch.delenv("CLA_BRANCH_PREFIX", raising=False)
    overlay = tmp_path / "cla.io" / "overlays" / _git_common._BRANCH_PREFIX_OVERLAY
    overlay.parent.mkdir(parents=True)
    overlay.write_text("---\nbranch_prefix: claude/feature/\n---\n", encoding="utf-8")
    monkeypatch.setattr(_git_common, "repo_root", lambda: tmp_path)

    assert _git_common.overlay_path() == overlay, "the reader is looking elsewhere"
    assert _git_common.branch_prefix() == "claude/feature/"
    assert _git_common.branch_name("add-thing") == "claude/feature/add-thing"
    assert capsys.readouterr().err == "", "a valid overlay must not warn"


def test_the_env_var_overrides_everything(monkeypatch):
    monkeypatch.setenv("CLA_BRANCH_PREFIX", "claude/fix/")
    assert _git_common.branch_name("my-change") == "claude/fix/my-change"


def test_the_env_var_is_also_used_verbatim(monkeypatch):
    """Was `test_the_env_var_gets_a_trailing_slash_too`. The env var and the
    overlay must agree about this, or the same string means two branches
    depending on where it was configured."""
    monkeypatch.setenv("CLA_BRANCH_PREFIX", "wip-")
    assert _git_common.branch_name("x") == "wip-x"


def test_the_default_is_feature_when_nothing_is_configured(monkeypatch):
    """`feature/` stays the default — this is a generalization, not a change of
    behaviour for repos already on that convention."""
    monkeypatch.delenv("CLA_BRANCH_PREFIX", raising=False)
    monkeypatch.setattr(_git_common, "branch_prefix", lambda: _git_common.DEFAULT_BRANCH_PREFIX)
    assert _git_common.branch_name("my-change") == "feature/my-change"
