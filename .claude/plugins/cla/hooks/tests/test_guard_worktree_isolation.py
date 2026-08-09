"""Tests for the guard-worktree-isolation PreToolUse hook.

Unit-tests the pure decision logic, and end-to-end-tests `main()` via subprocess
against a throwaway git repo (solo allowed, contended blocked, worktree allowed).
"""

import importlib.util
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

_HOOK = Path(__file__).resolve().parent.parent / "guard-worktree-isolation.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("guard_worktree_isolation", _HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


guard = _load_module()


# --------------------------------------------------------------------------- #
# Pure decision logic
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("cmd", [
    "git checkout -b feature/x",
    "git checkout -B feature/x",
    "git switch -c feature/x",
    "git switch --create feature/x",
    "git switch main",
    "git switch -",              # toggle to previous branch — a real HEAD move
    "git commit -m 'msg'",
    "git commit",
    "git -c core.hooksPath=x commit -m y",   # global-option prefix must not bypass
    "git -C /some/path commit -m y",
    "git --no-pager switch main",
    "git --work-tree /some/path commit -m y",   # regression: space-separated long opt
    "git --git-dir /some/path/.git commit -m y",   # regression: space-separated long opt
    'git -C "/some/checkout path/with a space" commit -m y',  # regression: quoted value with a space
    # Executable spellings at the ENFORCING layer. The constant test proves the
    # regex; this proves the guard. `GIT commit` runs on a case-insensitive
    # filesystem and used to move HEAD with the isolation guard blind to it.
    "git.exe commit -m y",
    "GIT commit -m y",
    "GIT.EXE checkout -b feature/x",
    "Git.Cmd switch -c feature/x",
])
def test_mutating_commands_detected(cmd):
    # cwd is irrelevant for these shapes (no ref resolution needed).
    assert guard._mutates_shared_head(cmd, os.getcwd()) is not None


@pytest.mark.parametrize("cmd", [
    "git status",
    "git log --oneline",
    "git diff main...HEAD",
    "git fetch origin",
    "git worktree add ../wt -b feature/x",
    "git commit --dry-run",
    "git commit-tree abc123 -m x",   # plumbing — moves no branch
    "git switch --help",             # help form, not a switch
    "git push -u origin feature/x",
    "ls -la",
    # `\b` must still hold once the command name is case-folded.
    "digit commit -m y",
    "DIGIT commit -m y",
])
def test_nonmutating_commands_ignored(cmd):
    assert guard._mutates_shared_head(cmd, os.getcwd()) is None


def test_commit_inside_quotes_not_detected():
    # A `git commit` mentioned inside a quoted string must not trip the matcher.
    cmd = "echo 'run git commit to save' > notes.txt"
    assert guard._mutates_shared_head(cmd, os.getcwd()) is None


def test_checkout_of_a_quoted_branch_name_resolves_the_real_target(repo):
    # `_CHECKOUT_ARG`'s group 2 is re-sliced from the ORIGINAL command (not
    # `scanned`) specifically so a quoted checkout target still resolves
    # against the real ref via `git rev-parse` — a naive collapse-to-`''`
    # would have handed `_is_checkout_switch` the placeholder text instead,
    # silently misclassifying every quoted-target checkout as a file restore.
    cmd = "git checkout 'main'"
    assert guard._mutates_shared_head(cmd, str(repo)) == "switch branches"


@pytest.mark.parametrize("cmd", [
    "git --work-tree /some/path checkout main",
    "git --git-dir /some/path/.git checkout main",
    "git --no-pager checkout main",
    "git --bare checkout main",
])
def test_checkout_switch_detected_behind_a_long_global_option(repo, cmd):
    # The branch-SWITCH path (as opposed to create/commit) used to bail on a
    # bare `"--" in scanned`, which is true of ANY long option — so every one
    # of these silently skipped the check and allowed a HEAD move on the shared
    # primary clone. Only a STANDALONE `--` (end-of-options) should skip it.
    assert guard._mutates_shared_head(cmd, str(repo)) == "switch branches"


@pytest.mark.parametrize("cmd", [
    "git checkout -- somefile.py",
    "git checkout -- README.md",
])
def test_end_of_options_marker_still_means_file_restore(repo, cmd):
    # The complement of the test above: a standalone `--` marks the args after
    # it as PATHS, so this is a file restore and must stay unguarded.
    assert guard._mutates_shared_head(cmd, str(repo)) is None


# --------------------------------------------------------------------------- #
# session-id handling -- an anonymous caller must not pollute real guard state
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("raw", [None, "", "   ", "___"])
def test_unidentifiable_session_id_resolves_to_none(raw):
    # The old placeholder ("unknown-session") made every anonymous invocation
    # share ONE heartbeat filename that nothing ever cleaned up, leaving a
    # permanent phantom peer that blocked real commits in the primary clone.
    assert guard._sanitize_session_id(raw) is None


def test_real_session_id_is_still_sanitized_not_dropped():
    assert guard._sanitize_session_id("abc/../def 123") == "abc_.._def_123"


@pytest.mark.parametrize("mode", ["--heartbeat", "--cleanup"])
def test_presence_modes_write_nothing_without_a_session_id(tmp_path, monkeypatch, mode):
    # A test run, or an agent reproducing a sample payload, must leave no trace
    # in the guard dir — this is exactly how a stray heartbeat got created.
    guard_dir = tmp_path / "guard"
    guard_dir.mkdir()
    monkeypatch.setattr(guard, "_primary_guard_dir", lambda cwd: guard_dir)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(tmp_path)})))
    assert guard.main([mode]) == 0
    assert list(guard_dir.iterdir()) == [], "an anonymous session must not register presence"


def test_presence_mode_writes_a_heartbeat_when_the_session_is_identified(tmp_path, monkeypatch):
    guard_dir = tmp_path / "guard"
    guard_dir.mkdir()
    monkeypatch.setattr(guard, "_primary_guard_dir", lambda cwd: guard_dir)
    payload = json.dumps({"cwd": str(tmp_path), "session_id": "sess-1"})
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    assert guard.main(["--heartbeat"]) == 0
    assert [p.name for p in guard_dir.iterdir()] == ["sess-1"]


def test_guard_mode_fails_open_and_warns_without_a_session_id(tmp_path, monkeypatch, capsys):
    # Without an id the hook cannot tell its own heartbeat from a peer's, so
    # every live session would count as "other" and a SOLO session would be
    # blocked. Fail open, but say so.
    guard_dir = tmp_path / "guard"
    guard_dir.mkdir()
    (guard_dir / "someone-else").touch()
    monkeypatch.setattr(guard, "_primary_guard_dir", lambda cwd: guard_dir)
    payload = json.dumps({"cwd": str(tmp_path), "tool_input": {"command": "git commit -m x"}})
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    assert guard.main([]) == 0
    assert "session_id" in capsys.readouterr().err


def test_other_live_sessions_counts_and_prunes(tmp_path):
    gdir = tmp_path / "guard"
    gdir.mkdir()
    now = time.time()
    # A fresh other session, a fresh self, and a stale other.
    (gdir / "other-fresh").touch()
    (gdir / "me").touch()
    stale = gdir / "other-stale"
    stale.touch()
    os.utime(stale, (now - 10_000, now - 10_000))  # older than the 15-min TTL

    others = guard._other_live_sessions(gdir, "me", now)
    assert others == 1                      # only the fresh OTHER counts
    assert not stale.exists()               # stale beat pruned
    assert (gdir / "other-fresh").exists()  # fresh beat kept


# --------------------------------------------------------------------------- #
# End-to-end via subprocess against a real temp git repo
# --------------------------------------------------------------------------- #

def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True,
                   capture_output=True, text=True, encoding="utf-8", errors="replace")


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "clone"
    r.mkdir()
    _git(r, "init", "-b", "main")
    _git(r, "config", "user.email", "t@t.t")
    _git(r, "config", "user.name", "t")
    (r / "f.txt").write_text("x", encoding="utf-8")
    _git(r, "add", "-A")
    _git(r, "commit", "-m", "init")
    return r


def _invoke(cwd, command, session_id="s1", env_extra=None, args=None):
    payload = json.dumps({
        "tool_input": {"command": command},
        "session_id": session_id,
        "cwd": str(cwd),
    })
    env = {**os.environ, "ALLOW_SHARED_CLONE_MUTATION": ""}
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(_HOOK), *(args or [])],
        input=payload, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )


def _guard_dir_path(repo):
    common = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--git-common-dir"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=True).stdout.strip()
    common = Path(repo) / common if not os.path.isabs(common) else Path(common)
    return common / ".claude-worktree-guard"


def _plant_other_session(repo, name="other"):
    common = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--git-common-dir"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=True).stdout.strip()
    common = Path(repo) / common if not os.path.isabs(common) else Path(common)
    gdir = common / ".claude-worktree-guard"
    gdir.mkdir(parents=True, exist_ok=True)
    (gdir / name).touch()
    return gdir


def test_solo_primary_clone_allows_commit(repo):
    # No other session present → even a mutating op is allowed (backward compatible).
    r = _invoke(repo, "git commit -m x")
    assert r.returncode == 0, r.stderr


def test_contended_primary_clone_blocks_branch_create(repo):
    _plant_other_session(repo)
    r = _invoke(repo, "git checkout -b feature/x")
    assert r.returncode == 2
    assert "worktree" in r.stderr.lower()


def test_contended_primary_clone_blocks_commit(repo):
    _plant_other_session(repo)
    r = _invoke(repo, "git commit -m x")
    assert r.returncode == 2


def test_contended_primary_clone_allows_readonly(repo):
    _plant_other_session(repo)
    r = _invoke(repo, "git status")
    assert r.returncode == 0, r.stderr


def test_contended_blocks_switch_to_existing_branch(repo):
    _git(repo, "branch", "feature/existing")
    _plant_other_session(repo)
    r = _invoke(repo, "git checkout feature/existing")
    assert r.returncode == 2


def test_escape_hatch_allows(repo):
    _plant_other_session(repo)
    r = _invoke(repo, "git commit -m x", env_extra={"ALLOW_SHARED_CLONE_MUTATION": "1"})
    assert r.returncode == 0, r.stderr


def test_linked_worktree_always_allowed(repo, tmp_path):
    # A session in a linked worktree is isolated → allowed even when contended.
    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", str(wt), "-b", "feature/wt")
    _plant_other_session(repo)
    r = _invoke(wt, "git commit -m x", session_id="s2")
    assert r.returncode == 0, r.stderr


def test_own_heartbeat_does_not_self_block(repo):
    # Two calls from the SAME session must not count as contention with itself.
    _invoke(repo, "git status", session_id="solo")
    r = _invoke(repo, "git commit -m x", session_id="solo")
    assert r.returncode == 0, r.stderr


def test_non_git_command_ignored(repo):
    _plant_other_session(repo)
    r = _invoke(repo, "ls -la")
    assert r.returncode == 0, r.stderr


def test_contended_blocks_switch_dash(repo):
    # `git switch -` toggles to the previous branch — a real shared-HEAD move.
    _plant_other_session(repo)
    r = _invoke(repo, "git switch -")
    assert r.returncode == 2


def test_contended_blocks_checkout_sha(repo):
    # Detached-HEAD checkout of a commit-ish moves the shared working tree.
    sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace", check=True).stdout.strip()
    _plant_other_session(repo)
    r = _invoke(repo, f"git checkout {sha}")
    assert r.returncode == 2


def test_contended_allows_checkout_file_restore(repo):
    # `git checkout <existing-file>` is a file restore, NOT a branch switch (false-
    # positive boundary) — must stay allowed even under contention.
    _plant_other_session(repo)
    assert _invoke(repo, "git checkout f.txt").returncode == 0
    # The explicit-path form (`--`) is likewise a restore.
    assert _invoke(repo, "git checkout -- f.txt").returncode == 0


def test_stale_beat_is_not_contention_e2e(repo):
    # A dead peer (heartbeat older than the TTL) must NOT count as contention —
    # exercised end-to-end through main(), not just the pruning helper.
    gdir = _plant_other_session(repo, name="dead-peer")
    old = time.time() - (guard._TTL_SECONDS + 1000)
    os.utime(gdir / "dead-peer", (old, old))
    r = _invoke(repo, "git commit -m x")
    assert r.returncode == 0, r.stderr
    assert not (gdir / "dead-peer").exists()  # stale beat pruned


def test_malformed_stdin_fails_open(repo):
    # The documented fail-open safety property: unparseable input never blocks.
    r = subprocess.run(
        [sys.executable, str(_HOOK)],
        input="not json", capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "ALLOW_SHARED_CLONE_MUTATION": ""},
    )
    assert r.returncode == 0


# --------------------------------------------------------------------------- #
# Presence modes: --heartbeat (SessionStart / Edit|Write) and --cleanup (SessionEnd)
# --------------------------------------------------------------------------- #

def test_heartbeat_mode_registers_presence(repo):
    # SessionStart / non-Bash tool use keeps a session live even without a git command.
    r = _invoke(repo, "", session_id="beater", args=["--heartbeat"])
    assert r.returncode == 0, r.stderr
    assert (_guard_dir_path(repo) / "beater").exists()


def test_heartbeat_from_worktree_registers_nothing(repo, tmp_path):
    # A worktree session is isolated — it must not register in the primary clone's dir.
    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", str(wt), "-b", "feature/wt")
    r = _invoke(wt, "", session_id="wtbeater", args=["--heartbeat"])
    assert r.returncode == 0, r.stderr
    gdir = _guard_dir_path(repo)
    assert not (gdir.exists() and (gdir / "wtbeater").exists())


def test_cleanup_mode_removes_own_beat(repo):
    # SessionEnd removes this session's heartbeat immediately (no waiting for TTL),
    # so a closed session stops contending at once.
    _invoke(repo, "", session_id="leaver", args=["--heartbeat"])
    assert (_guard_dir_path(repo) / "leaver").exists()
    r = _invoke(repo, "", session_id="leaver", args=["--cleanup"])
    assert r.returncode == 0, r.stderr
    assert not (_guard_dir_path(repo) / "leaver").exists()


def test_cleanup_leaves_other_beats(repo):
    _plant_other_session(repo, name="peer")
    _invoke(repo, "", session_id="leaver", args=["--heartbeat"])
    _invoke(repo, "", session_id="leaver", args=["--cleanup"])
    assert (_guard_dir_path(repo) / "peer").exists()      # peer untouched
    assert not (_guard_dir_path(repo) / "leaver").exists()
