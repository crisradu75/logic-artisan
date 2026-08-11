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



def make_dir_alias(link: Path, real: Path) -> None:
    """Create `link` -> `real` as a directory alias, or skip if neither works.

    A real symlink where permitted, else an NTFS junction (`mklink /J`), which
    needs no elevated privileges on Windows -- unlike a symlink, which raises
    WinError 1314 for every unprivileged account. Without the fallback these
    tests skipped on the ONE platform whose path handling they exist to check,
    while the suite still reported green.

    `os.path.realpath` resolves a junction exactly like a symlink, and every
    caller here goes through `realpath`, so the substitution is exact.
    (`os.path.islink()` is False for a junction -- irrelevant here, and exactly
    why `block-unsafe-recursive-delete` does its own reparse-point check rather
    than trusting `islink`.)
    """
    try:
        link.symlink_to(real, target_is_directory=True)
        return
    except (OSError, NotImplementedError, AttributeError):
        pass
    if os.name != "nt":
        # The junction fallback is Windows-only. Without this gate, ANY
        # non-privilege symlink failure on Linux/macOS -- FileExistsError, an
        # overlayfs or SMB mount that disallows symlinks -- spawned `cmd`, which
        # does not exist there, and `FileNotFoundError` propagated: the test
        # ERRORED where it previously skipped. These files are synced core, so
        # every POSIX consumer would have inherited that.
        pytest.skip("symlink creation not permitted, and junctions are Windows-only")
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(real)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        pytest.skip(f"neither symlink nor junction creation permitted here: {result.stderr}")
    if not link.exists():
        # `mklink /J` reports success against a MISSING target: rc 0, "Junction
        # created for ...", and the link resolves nowhere. Without this the
        # helper returns normally having created nothing usable, and the caller
        # asserts against an alias that does not resolve -- a test that passes
        # for the wrong reason, which is the failure shape this helper was
        # written to remove.
        pytest.skip("directory alias created but does not resolve")

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
import _dispatch_lib  # noqa: E402 - needs _load_module()'s sys.path insert first


def _git(cwd, *args):
    subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True, encoding="utf-8", errors="replace"
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
    the table was updated to match — this pins the call count directly.

    Patches `_dispatch_lib.subprocess.run`, not `hook.subprocess.run`: `_clone_paths`
    is imported from `_dispatch_lib` (shared with guard-worktree-isolation.py), so
    its `subprocess` calls resolve through THAT module's globals, not this hook's.
    """
    _primary, linked = worktree_pair
    calls = []
    real = _dispatch_lib.subprocess.run

    def counting(argv, **kw):
        calls.append(argv)
        return real(argv, **kw)

    monkeypatch.setattr(_dispatch_lib.subprocess, "run", counting)
    hook._clone_paths(str(linked))
    assert len(calls) == 1, f"expected one rev-parse, got {len(calls)}: {calls}"


def test_every_git_call_is_bounded_by_a_timeout(worktree_pair, monkeypatch):
    # An unbounded git here is a hook that can hang forever, and the likeliest
    # cause is the index-lock contention this hook family exists to detect.
    _primary, linked = worktree_pair
    seen = []
    real = _dispatch_lib.subprocess.run

    def recording(argv, **kw):
        seen.append(kw.get("timeout"))
        return real(argv, **kw)

    monkeypatch.setattr(_dispatch_lib.subprocess, "run", recording)
    hook._clone_paths(str(linked))
    hook._worktree_root(str(linked))
    assert seen and all(t is not None for t in seen), seen


def test_a_timed_out_git_fails_open(monkeypatch, tmp_path):
    def boom(*_a, **_kw):
        raise subprocess.TimeoutExpired(cmd="git", timeout=1)

    monkeypatch.setattr(_dispatch_lib.subprocess, "run", boom)
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


def test_is_inside_tolerates_a_differently_spelled_but_identical_path(worktree_pair):
    """Pins `_is_inside` against a spelling divergence the CALLER did not fold.

    The earlier version of this test realpathed BOTH arguments before calling,
    so both arrived already canonical and the assertion held for any
    string-equality implementation — it proved nothing about `_is_inside` and
    would have passed against the raw `commonpath ==` that used to be there.
    This passes the un-normalised spelling, which is the only version that can
    fail.
    """
    _primary, linked = worktree_pair
    root = os.path.realpath(str(linked))
    odd = str(linked).swapcase()
    if not os.path.isdir(odd) or odd == str(linked):
        pytest.skip("filesystem is case-sensitive; this divergence cannot occur here")
    assert hook._is_inside(os.path.join(odd, "seed.txt"), root)


def test_is_inside_survives_a_symlinked_spelling_on_every_platform(worktree_pair, tmp_path):
    """The case-insensitivity tests skip on Linux — where CI runs.

    That left the whole invariant unexercised precisely where an agent tidying
    up a `realpath`/`normcase` call would be working. A symlink produces the
    same shape (two spellings, one directory) on every platform, so this runs
    everywhere and pins the same behaviour.
    """
    _primary, linked = worktree_pair
    alias = tmp_path / "alias"
    make_dir_alias(alias, Path(linked))

    root = os.path.realpath(str(linked))
    assert hook._is_inside(str(alias / "seed.txt"), root), (
        "a path reaching the worktree by another spelling is still inside it"
    )


def test_is_inside_still_says_no_for_a_genuinely_outside_path(worktree_pair, tmp_path):
    """Non-vacuity: a containment test that answers True for everything would
    pass every case above while disabling the guard completely."""
    _primary, linked = worktree_pair
    assert not hook._is_inside(str(tmp_path / "elsewhere" / "x.txt"), os.path.realpath(str(linked)))


def test_is_inside_rejects_a_sibling_whose_name_starts_with_the_root(tmp_path):
    """The case that separates `commonpath` from the obvious `startswith`.

    `_is_inside` is component-aware today, so a sibling directory whose name
    merely BEGINS with the root's name is outside. Rewrite the body as
    `normcase(path).startswith(normcase(root))` — which looks equivalent and
    reads simpler — and every other test in this file stays green while a live
    bypass opens: a session in `.claude/worktrees/foo` could write into
    `.claude/worktrees/foo-backup/`. Those are ordinary sibling names under this
    plugin's own `DEFAULT_WORKTREE_DIR`, not contrived ones.
    """
    root = tmp_path / "worktrees" / "foo"
    sibling = tmp_path / "worktrees" / "foo-backup"
    sibling.mkdir(parents=True)
    root.mkdir(parents=True)

    assert not hook._is_inside(
        str(sibling / "escaped.txt"), os.path.realpath(str(root))
    ), "a sibling sharing the root's name as a prefix is NOT inside the root"
    assert hook._is_inside(str(root / "ok.txt"), os.path.realpath(str(root))), (
        "non-vacuity: the same-shaped path that really is inside must still pass"
    )


# --------------------------------------------------------------------------- #
# Degraded-git diagnostics (MD-7, reported by a consuming repo)
#
# Every fail-open path returned 0 in silence, so an enforcing guard that had
# stopped enforcing looked identical to one that ran and allowed. A wedged git
# or a held `index.lock` is the concurrent-session scenario this hook exists for.
# --------------------------------------------------------------------------- #


def test_degraded_git_in_a_real_work_tree_is_announced(monkeypatch, capsys, tmp_path):
    """`_clone_paths` returning None inside an actual repo means git could not
    answer — the case where silence lets a write escape the worktree."""
    monkeypatch.setattr(hook, "_clone_paths", lambda cwd: None)
    monkeypatch.setattr(hook, "_is_work_tree", lambda cwd: True)
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(json.dumps({
            "tool_name": "Write",
            "tool_input": {"file_path": str(tmp_path / "x.md")},
            "cwd": str(tmp_path),
        })),
    )
    assert hook.main() == 0  # still fails OPEN
    assert "could not resolve git dirs" in capsys.readouterr().err


def test_a_non_repo_directory_is_not_announced(monkeypatch, capsys, tmp_path):
    """Non-vacuity partner, and the reason the warning is conditional at all:
    `_clone_paths` also returns None for the commonest benign case — no repo
    here. Warning on that fires on every write in a scratch directory, and a
    diagnostic that cries wolf takes the real one down with it."""
    monkeypatch.setattr(hook, "_clone_paths", lambda cwd: None)
    monkeypatch.setattr(hook, "_is_work_tree", lambda cwd: False)
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(json.dumps({
            "tool_name": "Write",
            "tool_input": {"file_path": str(tmp_path / "x.md")},
            "cwd": str(tmp_path),
        })),
    )
    assert hook.main() == 0
    captured = capsys.readouterr()
    assert captured.err == "", f"noisy outside a repo: {captured.err!r}"
