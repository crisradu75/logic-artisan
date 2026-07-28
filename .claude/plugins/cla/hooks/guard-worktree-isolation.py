#!/usr/bin/env python3
"""PreToolUse hook: enforce worktree isolation for concurrent sessions.

Problem this solves
-------------------
git's HEAD and working tree are per-CLONE, not per-session. Two Claude sessions
pointed at the same folder share ONE HEAD. So when session A runs
`git checkout -b feature/x`, session B — sitting in the same directory — is
dragged onto `feature/x` too, and its next commit lands there. Result: two
sessions' unrelated changes mix on one branch / one PR (observed repeatedly).

The proper fix is ISOLATION: each concurrent session works in its own
`git worktree` (own directory, own HEAD, shared object store), and the primary
clone stays on `main`. This hook enforces that repo-wide, for EVERY session and
workflow (not just /spec-to-pr), because it is wired in `.claude/settings.json`.

Design — contention-based (isolation-first, zero disruption to solo work)
-------------------------------------------------------------------------
- A session working in a LINKED WORKTREE is already isolated → always allowed.
- A SOLO session in the primary clone is unaffected → always allowed (so this
  does not change day-to-day single-session behavior, incl. /spec-to-pr).
- Only when ANOTHER live session is present in the primary clone does the hook
  block the HEAD-mutating ops most likely to collide there — branch create,
  branch switch (`git switch` any form, `git checkout <commit-ish>`), and
  `git commit` — and direct the actor to a worktree, the exact moment the
  shared-HEAD collision would otherwise happen. `git merge`/`rebase`/`reset` and
  common global-option prefixes are handled (`git -c … commit`, `git -C path
  checkout`), but `git merge`/`rebase`/`reset` and exotic/quoted shapes are
  intentionally NOT guarded (same best-effort posture as the sibling git hooks).

Presence is tracked by per-session heartbeat files under
`<git-common-dir>/.claude-worktree-guard/<session_id>` (mtime = last-seen). The
same script runs in three modes so presence stays accurate across a whole
session, not only when it happens to run a Bash command:
  - default (PreToolUse Bash)               refresh presence AND run block logic
  - --heartbeat (SessionStart, Edit|Write)  refresh presence only (register at
                                             start; stay live during non-Bash work)
  - --cleanup (SessionEnd)                   remove this session's beat at once, so
                                             a closed session stops contending now
A beat older than TTL is a crash backstop (reaps a session that died without a
SessionEnd).

Escape hatch: set `ALLOW_SHARED_CLONE_MUTATION=1` to bypass the block (e.g. a
deliberate solo main-branch fix while another session is parked).

Exit codes:
  0 — allow (worktree, solo, non-mutating command, escape hatch, or a presence mode)
  2 — block with stderr explaining how to use a worktree

Best-effort: any parse/git/FS error exits 0 (fail-open) — a guard must never
wedge the workflow.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from _dispatch_lib import GIT_GLOBAL_OPTS as _G
from _dispatch_lib import strip_quoted_spans as _strip_quoted_spans

# A heartbeat older than this = the session is gone. Set as a CRASH backstop, not
# the primary liveness signal: presence is refreshed on SessionStart + every
# Bash/Edit/Write and REMOVED on SessionEnd, so a cleanly-closed session disappears
# at once and this TTL only reaps sessions that crashed without a SessionEnd. Kept
# generous so a long non-tool turn (big LLM/web step, user away) doesn't prune a
# still-open peer and let the other session mutate believing it's solo.
_TTL_SECONDS = 60 * 60
_GUARD_DIRNAME = ".claude-worktree-guard"


# --- HEAD-mutating command detection ----------------------------------------

_GIT = r"\bgit\s+" + _G

# branch create-and-switch: `git checkout -b|-B|--orphan NAME`, `git switch -c|-C|--create NAME`
_BRANCH_CREATE = re.compile(
    _GIT + r"(?:checkout\s+(?:-b|-B|--orphan)|switch\s+(?:-c|-C|--create))\b"
)
# `git switch ...` — switching is git-switch's ONLY job, so any invocation (incl.
# `git switch -` toggle, `git switch --detach X`) moves the shared HEAD. Only the
# help forms are exempt.
_SWITCH = re.compile(_GIT + r"switch\b")
_SWITCH_HELP = re.compile(_GIT + r"switch\s+(?:-h|--help)\b")
# `git commit ...` — `commit(?=\s|$)` so `git commit-tree` (plumbing, moves no branch)
# is NOT matched.
_COMMIT = re.compile(_GIT + r"commit(?=\s|$)")
# `git checkout ARG` where ARG might be a branch/commit-ish (resolved below).
_CHECKOUT_ARG = re.compile(_GIT + r"checkout\s+((?:(?:-[a-zA-Z]+|--\S+)\s+)*)(\S+)")


def _warn(msg: str) -> None:
    """Surface a guard-disabling/degraded condition (repo policy: recoverable ->
    Warning on stderr). The hook still fails OPEN — it prints, then returns 0."""
    print(f"[guard-worktree-isolation] warn: {msg}", file=sys.stderr)


def _run_git(cwd: str, args: list[str]) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(
            ["git", "-C", cwd, *args],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _is_checkout_switch(cwd: str, arg: str) -> bool:
    """Return True iff `git checkout <arg>` would move HEAD (branch/tag/sha/DWIM
    remote branch) rather than restore a file. Covers the cases `_is_local_branch`
    missed: a DWIM remote-only branch and a detached-HEAD sha both move the shared
    working tree, so both are treated as switches."""
    arg = arg.strip("'\"")
    if arg in ("-", "--detach"):  # toggle to previous branch / explicit detach
        return True
    # An existing path in the working tree → file restore, not a HEAD move.
    if os.path.exists(os.path.join(cwd, arg)):
        return False
    r = _run_git(cwd, ["rev-parse", "--verify", "--quiet", f"{arg}^{{commit}}"])
    if r is None:
        # git errored/timed out — cannot classify. Fail OPEN (allow) but surface it,
        # since under active contention this is exactly when the guard should fire.
        _warn(f"could not resolve `git checkout {arg}` target — guard fell open for it")
        return False
    return r.returncode == 0


def _mutates_shared_head(command: str, cwd: str) -> str | None:
    """Return a short label of the HEAD-mutating op, or None if the command does
    not move the shared branch/HEAD. Covers branch create, branch switch (`git
    switch` any form, `git checkout <commit-ish>`), and `git commit`. Intentionally
    NOT covered (accepted, same best-effort posture as the sibling git hooks):
    `git merge`/`git rebase`/`git reset`, and shapes hidden behind global options
    (`git -c ... commit`)."""
    scanned = _strip_quoted_spans(command)

    if _BRANCH_CREATE.search(scanned):
        return "create a branch"

    if _SWITCH.search(scanned) and not _SWITCH_HELP.search(scanned):
        return "switch branches"

    if _COMMIT.search(scanned) and "--dry-run" not in scanned:
        return "commit"

    # `git checkout <commit-ish>` (not a file restore). Skip when `--` present
    # (explicit paths) or a create form (already handled above).
    m = _CHECKOUT_ARG.search(scanned)
    if m and "--" not in scanned:
        flags = m.group(1)
        if "-b" not in flags and "-B" not in flags and "--orphan" not in flags:
            # Re-slice group 2 from the ORIGINAL command, not `scanned`: a
            # quoted checkout target (`git checkout "some-branch"`) would
            # otherwise hand `_is_checkout_switch` the scan-time placeholder
            # text instead of the real ref name, breaking its `git rev-parse`
            # classification — `strip_quoted_spans` is length-preserving
            # specifically so this offset is still valid against `command`.
            target = command[m.start(2) : m.end(2)]
            if _is_checkout_switch(cwd, target):
                return "switch branches"
    return None


# --- primary-clone vs worktree + presence -----------------------------------


def _clone_paths(cwd: str) -> tuple[str, str] | None:
    """Return (git_dir, git_common_dir) as realpaths, or None on failure."""
    gd = _run_git(cwd, ["rev-parse", "--absolute-git-dir"])
    gc = _run_git(cwd, ["rev-parse", "--git-common-dir"])
    if not gd or gd.returncode != 0 or not gc or gc.returncode != 0:
        return None
    git_dir = os.path.realpath(gd.stdout.strip())
    common = gc.stdout.strip()
    if not os.path.isabs(common):
        common = os.path.join(cwd, common)
    return git_dir, os.path.realpath(common)


def _other_live_sessions(guard_dir: Path, my_id: str, now: float) -> int:
    """Prune stale beats and count OTHER sessions whose heartbeat is still fresh."""
    others = 0
    try:
        for beat in guard_dir.iterdir():
            try:
                age = now - beat.stat().st_mtime
            except OSError:
                continue
            if age > _TTL_SECONDS:
                try:
                    beat.unlink()
                except OSError:
                    pass
                continue
            if beat.name != my_id:
                others += 1
    except OSError as e:
        # Can't read the heartbeat dir → we cannot see peer sessions, so the guard
        # is effectively OFF for this call. Fail open, but make the blind spot visible.
        _warn(f"cannot read heartbeat dir ({e}); contention detection is off for this call")
        return 0
    return others


def _touch(guard_dir: Path, my_id: str) -> None:
    try:
        guard_dir.mkdir(parents=True, exist_ok=True)
        (guard_dir / my_id).touch()
    except OSError as e:
        # Can't register our heartbeat → peers can't see us; two sessions could each
        # believe they're solo. Fail open, but surface that protection is degraded.
        _warn(f"cannot write heartbeat ({e}); other sessions may not detect this one")


def _remove(guard_dir: Path, my_id: str) -> None:
    try:
        (guard_dir / my_id).unlink()
    except OSError:
        pass  # already gone / unreadable — nothing to clean up


def _sanitize_session_id(raw: object) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", str(raw or "unknown-session"))[:128] or "unknown-session"


def _read_payload() -> dict | None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _primary_guard_dir(cwd: str) -> Path | None:
    """Guard dir for a PRIMARY-clone session, or None when in a linked worktree
    (isolated), not a repo, or git is unavailable."""
    paths = _clone_paths(cwd)
    if paths is None:
        return None
    git_dir, common_dir = paths
    if git_dir != common_dir:
        return None  # linked worktree — isolated, nothing to track/guard
    return Path(common_dir) / _GUARD_DIRNAME


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    payload = _read_payload()
    if payload is None:
        return 0

    session_id = _sanitize_session_id(payload.get("session_id"))
    cwd = payload.get("cwd") or os.getcwd()
    guard_dir = _primary_guard_dir(cwd)

    # --- presence modes (wired to SessionStart / SessionEnd / Edit|Write) --------
    if "--cleanup" in argv:  # SessionEnd: remove our heartbeat immediately
        if guard_dir is not None:
            _remove(guard_dir, session_id)
        return 0
    if "--heartbeat" in argv:  # SessionStart / non-Bash tool use: refresh presence
        if guard_dir is not None:
            _touch(guard_dir, session_id)
        return 0

    # --- guard mode (Bash PreToolUse) --------------------------------------------
    if os.environ.get("ALLOW_SHARED_CLONE_MUTATION") == "1":
        return 0
    if guard_dir is None:
        return 0  # worktree / not a repo — allow

    tool_input = payload.get("tool_input") or {}
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not command:
        return 0

    now = time.time()
    others = _other_live_sessions(guard_dir, session_id, now)
    _touch(guard_dir, session_id)  # register/refresh our presence

    if others == 0:
        return 0  # solo in the primary clone — unaffected (backward compatible)

    op = _mutates_shared_head(command, cwd)
    if op is None:
        return 0  # read-only / non-HEAD-moving command — fine even when contended

    print(
        f"blocked: another Claude session is live in this shared clone, and this "
        f"command would {op} on the primary clone's HEAD — which git shares across "
        f"every session in this directory, so it would drag the other session onto "
        f"your branch and mix unrelated changes.\n"
        f"Do feature work in an isolated worktree instead (own directory + own HEAD, "
        f"shared object store):\n"
        f"    git worktree add .claude/worktrees/<task> -b feature/<task>\n"
        f"then relaunch this session in .claude/worktrees/<task>. The primary clone "
        f"stays on master.\n"
        f"(Escape hatch for a deliberate solo action: ALLOW_SHARED_CLONE_MUTATION=1. "
        f"Hook: guard-worktree-isolation.py)",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
