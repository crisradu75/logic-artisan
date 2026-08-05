"""Tests for block-worktree-path-escape.py.

This hook had no test file of its own for most of its life — it was reached only
indirectly, through the Edit/Write dispatcher's tests. That is a thin place for a
BLOCKING hook that runs on every single Edit and Write, and it let two changes
land unexercised: the switch from the process cwd to the payload cwd, and the
collapse of two `rev-parse` calls into one.

The payload-cwd case is the one worth stating plainly. Every earlier test set the
PROCESS cwd, so they exercised only the fallback — reverting the hook to
`os.getcwd()` would have left them all green while re-opening the bug.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).resolve().parent.parent


def _load_module():
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    spec = importlib.util.spec_from_file_location(
        "block_worktree_path_escape", _HOOKS_DIR / "block-worktree-path-escape.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hook = _load_module()


def _git(cwd, *args):
    subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True
    )


@pytest.fixture
def worktree_pair(tmp_path):
    """A primary clone with one linked worktree, both real.

    `git worktree` is the whole subject here, so these are genuine git
    invocations rather than a faked `.git` layout — the hook distinguishes the
    two by `--absolute-git-dir` vs `--git-common-dir`, which only real plumbing
    produces correctly.
    """
    primary = tmp_path / "primary"
    primary.mkdir()
    _git(primary, "init", "-q")
    _git(primary, "config", "user.email", "a@b.c")
    _git(primary, "config", "user.name", "a")
    (primary / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(primary, "add", "-A")
    _git(primary, "commit", "-q", "-m", "seed")

    linked = tmp_path / "linked"
    _git(primary, "worktree", "add", "-q", str(linked), "-b", "feature")
    return primary, linked


def _run(mod, file_path, cwd_payload=None, process_cwd=None, monkeypatch=None):
    payload = {"tool_input": {"file_path": str(file_path)}}
    if cwd_payload is not None:
        payload["cwd"] = str(cwd_payload)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    if process_cwd is not None:
        monkeypatch.chdir(process_cwd)
    return mod.main()


# --------------------------------------------------------------------------- #
# The payload cwd is what the hook must reason about
# --------------------------------------------------------------------------- #


def test_blocks_an_escape_using_the_payload_cwd_not_the_process_cwd(
    worktree_pair, monkeypatch, capsys
):
    """The case that distinguishes the fix from the bug.

    The session is in the linked worktree (payload cwd) while the hook process
    sits in the primary clone — the normal state for the worktree sessions this
    hook protects. Reading the process cwd would resolve the primary clone,
    conclude "not in a worktree", and allow the escape.
    """
    primary, linked = worktree_pair
    monkeypatch.delenv("ALLOW_WORKTREE_PATH_ESCAPE", raising=False)

    rc = _run(
        hook,
        primary / "seed.txt",          # a write back into the primary clone
        cwd_payload=linked,            # ...from a session inside the worktree
        process_cwd=primary,           # ...with the process elsewhere
        monkeypatch=monkeypatch,
    )
    assert rc == 2, "an escape from the payload cwd's worktree must block"
    # stderr, not stdout: exit 2 is the one path where stderr is fed to Claude.
    assert "resolves outside it" in capsys.readouterr().err


def test_allows_a_write_inside_the_payload_cwd_worktree(worktree_pair, monkeypatch):
    primary, linked = worktree_pair
    monkeypatch.delenv("ALLOW_WORKTREE_PATH_ESCAPE", raising=False)
    rc = _run(
        hook, linked / "seed.txt", cwd_payload=linked, process_cwd=primary,
        monkeypatch=monkeypatch,
    )
    assert rc == 0


def test_a_relative_path_resolves_against_the_payload_cwd(worktree_pair, monkeypatch):
    """A relative `file_path` joined to the wrong cwd silently checks the wrong
    file. Pinned separately because it is a different code path from the
    absolute case above."""
    primary, linked = worktree_pair
    monkeypatch.delenv("ALLOW_WORKTREE_PATH_ESCAPE", raising=False)
    rc = _run(
        hook, "seed.txt", cwd_payload=linked, process_cwd=primary, monkeypatch=monkeypatch
    )
    assert rc == 0, "seed.txt relative to the worktree is inside it"


def test_falls_back_to_the_process_cwd_when_the_payload_omits_it(
    worktree_pair, monkeypatch, capsys
):
    primary, linked = worktree_pair
    monkeypatch.delenv("ALLOW_WORKTREE_PATH_ESCAPE", raising=False)
    rc = _run(
        hook, primary / "seed.txt", cwd_payload=None, process_cwd=linked,
        monkeypatch=monkeypatch,
    )
    assert rc == 2, "with no payload cwd the process cwd must still be honoured"


# --------------------------------------------------------------------------- #
# Scope: what is deliberately NOT this hook's problem
# --------------------------------------------------------------------------- #


def test_a_session_in_the_primary_clone_is_not_restricted(worktree_pair, monkeypatch):
    primary, _linked = worktree_pair
    monkeypatch.delenv("ALLOW_WORKTREE_PATH_ESCAPE", raising=False)
    rc = _run(
        hook, primary / "seed.txt", cwd_payload=primary, process_cwd=primary,
        monkeypatch=monkeypatch,
    )
    assert rc == 0, "the primary clone has no worktree boundary to escape"


def test_a_target_outside_the_repo_family_is_allowed(worktree_pair, tmp_path, monkeypatch):
    # A memory dir or an unrelated repo is a different, legitimate pattern.
    _primary, linked = worktree_pair
    monkeypatch.delenv("ALLOW_WORKTREE_PATH_ESCAPE", raising=False)
    outside = tmp_path / "somewhere-else" / "notes.md"
    outside.parent.mkdir(parents=True)
    rc = _run(hook, outside, cwd_payload=linked, process_cwd=linked, monkeypatch=monkeypatch)
    assert rc == 0


def test_not_a_repo_at_all_fails_open(tmp_path, monkeypatch):
    monkeypatch.delenv("ALLOW_WORKTREE_PATH_ESCAPE", raising=False)
    rc = _run(
        hook, tmp_path / "x.txt", cwd_payload=tmp_path, process_cwd=tmp_path,
        monkeypatch=monkeypatch,
    )
    assert rc == 0


def test_override_env_var_allows_a_deliberate_escape(worktree_pair, monkeypatch):
    primary, linked = worktree_pair
    monkeypatch.setenv("ALLOW_WORKTREE_PATH_ESCAPE", "1")
    rc = _run(
        hook, primary / "seed.txt", cwd_payload=linked, process_cwd=primary,
        monkeypatch=monkeypatch,
    )
    assert rc == 0


def test_a_payload_without_a_file_path_is_ignored(monkeypatch):
    monkeypatch.delenv("ALLOW_WORKTREE_PATH_ESCAPE", raising=False)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"tool_input": {}})))
    assert hook.main() == 0


def test_malformed_payload_fails_open(monkeypatch):
    monkeypatch.delenv("ALLOW_WORKTREE_PATH_ESCAPE", raising=False)
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json"))
    assert hook.main() == 0


# --------------------------------------------------------------------------- #
# Subprocess discipline
# --------------------------------------------------------------------------- #


def test_clone_paths_uses_one_git_call_for_both_answers(worktree_pair, monkeypatch):
    """Two `rev-parse` calls became one, which is what let the Edit/Write
    dispatcher's enforcing hooks fit inside the handler budget. If a future edit
    splits them again the budget test would eventually catch it, but only after
    the table was updated to match — this pins the call count directly."""
    _primary, linked = worktree_pair
    calls = []
    real = hook.subprocess.run

    def counting(argv, **kw):
        calls.append(argv)
        return real(argv, **kw)

    monkeypatch.setattr(hook.subprocess, "run", counting)
    hook._clone_paths(str(linked))
    assert len(calls) == 1, f"expected one rev-parse, got {len(calls)}: {calls}"


def test_every_git_call_is_bounded_by_a_timeout(worktree_pair, monkeypatch):
    # An unbounded git here is a hook that can hang forever, and the likeliest
    # cause is the index-lock contention this hook family exists to detect.
    _primary, linked = worktree_pair
    seen = []
    real = hook.subprocess.run

    def recording(argv, **kw):
        seen.append(kw.get("timeout"))
        return real(argv, **kw)

    monkeypatch.setattr(hook.subprocess, "run", recording)
    hook._clone_paths(str(linked))
    hook._worktree_root(str(linked))
    assert seen and all(t is not None for t in seen), seen


def test_a_timed_out_git_fails_open(monkeypatch, tmp_path):
    def boom(*_a, **_kw):
        raise subprocess.TimeoutExpired(cmd="git", timeout=1)

    monkeypatch.setattr(hook.subprocess, "run", boom)
    assert hook._clone_paths(str(tmp_path)) is None


# --------------------------------------------------------------------------- #
# Path casing — why these guards survive what EnterWorktree does not
# --------------------------------------------------------------------------- #


def test_path_comparison_survives_a_case_only_spelling_difference(worktree_pair, monkeypatch):
    """The bug that breaks `EnterWorktree` must not reach this hook.

    On a case-insensitive filesystem the same directory has two working
    spellings: git reports the true on-disk casing while a session's cwd can
    carry whatever was typed at launch. `EnterWorktree` compares those as
    literal strings and refuses. This hook is immune ONLY because every path
    goes through `os.path.realpath` first, which canonicalises to the
    filesystem's real casing before anything is compared.

    That is a load-bearing implementation detail with no other visible effect,
    which makes it exactly the kind of call a later cleanup drops as redundant.
    Pinned here so that removal fails a test instead of silently turning the
    guard into a no-op on Windows.
    """
    primary, linked = worktree_pair
    swapped = str(linked).swapcase()
    if not os.path.isdir(swapped) or swapped == str(linked):
        pytest.skip("filesystem is case-sensitive; this divergence cannot occur here")

    monkeypatch.delenv("ALLOW_WORKTREE_PATH_ESCAPE", raising=False)
    rc = _run(
        hook,
        primary / "seed.txt",     # escape target, primary-clone casing
        cwd_payload=swapped,      # session cwd, opposite casing — same directory
        process_cwd=primary,
        monkeypatch=monkeypatch,
    )
    assert rc == 2, (
        "a case-only difference in the session cwd must not disable the guard; "
        "check that _clone_paths/_worktree_root/target still realpath their inputs"
    )


def test_is_inside_is_not_a_raw_string_comparison(worktree_pair):
    """Directly pins the comparison helper against the mixed-case pair, so a
    failure points at `_is_inside` rather than at the whole hook."""
    _primary, linked = worktree_pair
    root = os.path.realpath(str(linked))
    target = os.path.realpath(os.path.join(str(linked).swapcase(), "seed.txt"))
    if not os.path.exists(target):
        pytest.skip("filesystem is case-sensitive; this divergence cannot occur here")
    assert hook._is_inside(target, root)
