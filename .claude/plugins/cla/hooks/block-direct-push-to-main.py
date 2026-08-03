#!/usr/bin/env python3
"""PreToolUse hook: block direct `git push` to main/master.

Convention: no direct commits to the default branch — use feature branches.
A retroactive paperwork-PR after the fact is structurally impossible (GitHub
refuses no-diff PRs), so the only fix is
to prevent the push at the moment it would happen.

Detection: locate EVERY `git push` in the Bash command — including a `push`
reached via a git GLOBAL option between `git` and the subcommand (`-c`/`-C`/
`--work-tree`/etc., see `_dispatch_lib.GIT_GLOBAL_OPTS`) — and read each one's
own positional arguments, stopping at the shell separator that ends that
push's argument list. Scanning every match matters: `git push origin
feature/x && git push origin main` is exactly what a drifted session runs, and
inspecting only the first match let the second reach the remote unblocked. For
each push, the first positional is the remote and the rest are refspecs, each
normalized (surrounding quotes stripped, a leading `+` force-marker dropped, a
`refs/heads/` prefix removed) before EITHER side of a `src:dst` pair is
compared against main/master. Blocked shapes therefore include:
  - `git push <remote> main` / `git push <remote> master`
  - `git push <remote> HEAD:main` / `git push <remote> <branch>:main`
  - `git push <remote> main:<branch>` (pushing the main branch's content out)
  - `git push <remote> refs/heads/main` (fully-qualified destination)
  - `git push <remote> +main` (force refspec) and `git push <remote> :main`
    (deleting the remote default branch)
  - `git push <remote> "main"` / `'main'` (quoted destination)
  - Same with `--force` / `-f` / `--force-with-lease`
  - `git push` / `git push <remote>` with NO refspec, when HEAD is main/master
  - `git push <remote> HEAD` / `@` (or either side of a `HEAD:<dst>` pair) when
    HEAD is main/master. `HEAD` is a positional refspec, so the bare-push
    current-branch check never ran for it, and as a literal ref name it matches
    nothing protected — yet `git push origin HEAD` is what a script emits when
    it does not want to hardcode a branch name, and from main it pushes main.
  - Any of the above after a `&&`, `;`, or `|` earlier in the same command

Which branch counts as "current" is resolved in the command's OWN directory:
`payload["cwd"]`, overridden by a `-C` / `--work-tree` value when the
invocation carries one (the same shape `guard-worktree-isolation.py` uses).
Resolving it in the hook process's cwd instead fails BOTH ways — a session in a
worktree while the primary clone sits on main allows a real direct push, and
the inverse blocks a legitimate one.

Resolution stays lazy: a literal refspec (`git push origin main`) is decided
with NO subprocess call at all, so the guard does not become dependent on git
being usable to catch its most common offense. Only a `HEAD`/`@` refspec or a
refspec-less push shells out.

Allow:
  - `git push -u origin feature/...` (any non-main destination)
  - Branch names that merely START with main/master — `main-refactor`,
    `master-list`, `main.old`, `maintenance` — are compared as whole refs, so
    they are NOT blocked. (A substring/word-boundary match got this wrong.)
  - `git push` with no refspec when the current branch is NOT main
  - Any push when the env var `ALLOW_PUSH_TO_MAIN=1` is set (escape hatch for
    the rare legitimate case — e.g. an admin restoring after force-push).

Exit codes:
  0 — allow
  2 — block with stderr explaining the rule

Best-effort, with the gaps named rather than implied: a `git push` invoked via
an alias, or one built by string interpolation, slips past; so does a global
option shape outside `GIT_GLOBAL_OPTS`'s named, closed set (see that helper's
docstring). A `git push origin main` sitting in a HEREDOC BODY is matched and
blocked even though it is being written to a file rather than run — accepted,
per `strip_quoted_spans`'s stated scope. The common offense (`git push origin
main` from a session that drifted onto main, with or without a `-C`/
`--work-tree`/`-c` prefix) is caught.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# The `_dispatch_lib` import below resolves through `sys.path`. Running
# standalone (`python3 <hooks-dir>/<this>.py`, the shape `hooks.json` uses)
# normally puts the hooks dir at `sys.path[0]`, but that is suppressed under
# `PYTHONSAFEPATH=1` / `python -I` / `python -P`. Insert it explicitly so an
# import failure can never silently disable this guard.
_HOOKS_DIR = str(Path(__file__).resolve().parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from _dispatch_lib import GIT_GLOBAL_OPTS as _G  # noqa: E402
from _dispatch_lib import strip_quoted_spans as _strip_quoted_spans  # noqa: E402

# Group 1 captures the global-option blob between `git` and `push`, so a
# `-C`/`--work-tree` belonging to THIS invocation can be recovered per match
# rather than scanned for anywhere in the command line.
_GIT_PUSH = re.compile(r"\bgit\s+(" + _G + r")push\b")

# Where the `git push` argument list ends: a shell separator starts a new
# command, so tokens past it are not this push's refspecs.
_SHELL_SEPARATOR = re.compile(r"[;&|)\n]")

# A directory-changing global option's value, read out of one invocation's
# option blob. Best-effort and first-match-wins: git applies repeated `-C`
# cumulatively, which this does not model — the shape worth resolving is the
# single `git -C <path> push …` a script emits.
_GIT_DIR_OPT = re.compile(r"(?:^|\s)(?:-C\s+(\S+)|--work-tree(?:=|\s+)(\S+))")

_PROTECTED = ("main", "master")

# Positional refspecs that MEAN the current branch rather than naming a ref.
_HEAD_ALIASES = ("HEAD", "@")


def _normalize_ref(ref: str) -> str:
    """Reduce one side of a refspec to a bare branch name for comparison."""
    ref = ref.strip("'\"").lstrip("+")
    if ref.startswith("refs/heads/"):
        ref = ref[len("refs/heads/") :]
    return ref


def _refspec_touches_main(refspec: str, cwd: str | None = None) -> bool:
    """True iff either side of `[+][src]:[dst]` (or a bare ref) is main/master.

    Both sides count: `<branch>:main` pushes TO the default branch, and
    `main:<branch>` pushes the default branch's content OUT — the convention
    this hook enforces treats both as a direct-to-main operation.

    `HEAD`/`@` on either side is not a ref NAME but a reference to whatever
    branch is checked out, so it is resolved through `_current_branch`. That
    resolution is deliberately reached only AFTER the literal comparison fails:
    the common offense (`git push origin main`) must stay decidable without
    git being usable at all.
    """
    ref = refspec.strip("'\"").lstrip("+")
    sides = ref.split(":") if ":" in ref else [ref]
    normalized = [_normalize_ref(side) for side in sides]
    if any(side in _PROTECTED for side in normalized):
        return True
    if any(side in _HEAD_ALIASES for side in normalized):
        return _current_branch(cwd) in _PROTECTED
    return False


def _push_argument_lists(scanned: str, command: str) -> list[tuple[str | None, list[str]]]:
    """Return one window per `git push` in the command: its own `-C` /
    `--work-tree` override (or None) paired with the whitespace-delimited
    tokens following it, re-sliced from the ORIGINAL command so a quoted
    refspec keeps its real text.

    One window per match, not just the first: truncating at the first shell
    separator correctly ends ONE push's argument list, but a `.search()` then
    made every later push invisible, so `git push origin feature/x && git push
    origin main` reached the remote unblocked.

    `strip_quoted_spans` is length-preserving precisely so these offsets stay
    valid against `command`; matching on `scanned` is what keeps a `git push`
    inside an echoed string from being seen at all.
    """
    windows: list[tuple[str | None, list[str]]] = []
    for m in _GIT_PUSH.finditer(scanned):
        rest = scanned[m.end() :]
        stop = _SHELL_SEPARATOR.search(rest)
        if stop:
            rest = rest[: stop.start()]
        base = m.end()
        work_tree = _command_work_tree(m.group(1), command[m.start(1) : m.end(1)])
        windows.append((
            work_tree,
            [command[base + t.start() : base + t.end()] for t in re.finditer(r"\S+", rest)],
        ))
    return windows


def _command_work_tree(scanned_options: str, raw_options: str) -> str | None:
    """The `-C` / `--work-tree` path from ONE invocation's global-option blob,
    or None.

    Matched against the SCANNED text (so a quoted path containing a space is
    one `\\S+` token) and re-sliced from the RAW text at the same offsets (so
    the returned value is the real path, not the placeholder fill) — the same
    length-preserving contract `_push_argument_lists` relies on."""
    m = _GIT_DIR_OPT.search(scanned_options)
    if not m:
        return None
    idx = 1 if m.group(1) is not None else 2
    return raw_options[m.start(idx) : m.end(idx)].strip("'\"") or None


def _current_branch(cwd: str | None = None) -> str | None:
    """The checked-out branch in `cwd` (the session's own directory), NOT in
    whatever directory this hook process happens to be running from — those
    differ whenever the session works in a linked worktree, and getting it
    wrong fails open there."""
    try:
        result = subprocess.run(
            ["git", *(["-C", cwd] if cwd else []), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        # `SubprocessError` covers `TimeoutExpired`. Without the timeout a hung
        # `git rev-parse` (stale index.lock, network FS, credential prompt)
        # would burn the dispatcher's whole 10s budget and take every other
        # guard down with it. Surface the degradation rather than allowing
        # silently — this is the one branch where the hook cannot tell whether
        # a bare push is safe.
        print(
            "[block-direct-push-to-main] warn: could not resolve HEAD (git "
            "unavailable or timed out) — bare-push detection is off for this call.",
            file=sys.stderr,
        )
        return None
    if result.returncode != 0:
        return None
    return (result.stdout or "").strip() or None


def _is_direct_push_to_main(command: str, cwd: str | None = None) -> bool:
    """Return True iff ANY `git push` in the command pushes to main/master
    directly. `cwd` is the session's own directory (the hook payload's), used
    for branch resolution unless a push carries its own `-C`/`--work-tree`."""
    scanned = _strip_quoted_spans(command)
    for work_tree, tokens in _push_argument_lists(scanned, command):
        target_dir = work_tree or cwd

        # First positional is the remote; anything after it is a refspec. Flags
        # are dropped — including `--force-with-lease=origin/main`, whose value
        # is not a push destination.
        positionals = [t for t in tokens if not t.startswith("-")]
        refspecs = positionals[1:]

        if refspecs:
            if any(_refspec_touches_main(r, target_dir) for r in refspecs):
                return True
            continue

        # No refspec (`git push`, `git push --force`, `git push origin`) → the
        # destination is the current branch's upstream.
        if _current_branch(target_dir) in _PROTECTED:
            return True
    return False


def main() -> int:
    if os.environ.get("ALLOW_PUSH_TO_MAIN") == "1":
        return 0
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        # ValueError also catches a UnicodeDecodeError on stdin. Matches the
        # sibling hooks, which already caught both.
        return 0
    tool_input = payload.get("tool_input", {}) if isinstance(payload, dict) else {}
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str):
        return 0
    cwd = payload.get("cwd") if isinstance(payload, dict) else None
    if not isinstance(cwd, str) or not cwd:
        cwd = None
    if not _is_direct_push_to_main(command, cwd):
        return 0
    print(
        "blocked: `git push` targets main/master directly. No direct commits to "
        "the default branch — create a feature branch first: "
        "`git checkout -b feature/<name>` -> commit -> push -> "
        "open a PR via `gh pr create`. Override for a genuine emergency by "
        "setting `ALLOW_PUSH_TO_MAIN=1` in the environment. "
        "(hook: block-direct-push-to-main.py)",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
