#!/usr/bin/env python3
"""PreToolUse hook: block direct `git push` to main/master.

Convention: no direct commits to the default branch — use feature branches.
A retroactive paperwork-PR after the fact is structurally impossible (GitHub
refuses no-diff PRs), so the only fix is
to prevent the push at the moment it would happen.

Detection: locate a `git push` in the Bash command — including a `push` reached
via a git GLOBAL option between `git` and the subcommand (`-c`/`-C`/
`--work-tree`/etc., see `_dispatch_lib.GIT_GLOBAL_OPTS`) — then read the
positional arguments after it. The first is the remote; the rest are refspecs,
each normalized (surrounding quotes stripped, a leading `+` force-marker
dropped, a `refs/heads/` prefix removed) before EITHER side of a `src:dst` pair
is compared against main/master. Blocked shapes therefore include:
  - `git push <remote> main` / `git push <remote> master`
  - `git push <remote> HEAD:main` / `git push <remote> <branch>:main`
  - `git push <remote> main:<branch>` (pushing the main branch's content out)
  - `git push <remote> refs/heads/main` (fully-qualified destination)
  - `git push <remote> +main` (force refspec) and `git push <remote> :main`
    (deleting the remote default branch)
  - `git push <remote> "main"` / `'main'` (quoted destination)
  - Same with `--force` / `-f` / `--force-with-lease`
  - `git push` / `git push <remote>` with NO refspec, when HEAD is main/master

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

_GIT_PUSH = re.compile(r"\bgit\s+" + _G + r"push\b")

# Where the `git push` argument list ends: a shell separator starts a new
# command, so tokens past it are not this push's refspecs.
_SHELL_SEPARATOR = re.compile(r"[;&|)\n]")

_PROTECTED = ("main", "master")


def _normalize_ref(ref: str) -> str:
    """Reduce one side of a refspec to a bare branch name for comparison."""
    ref = ref.strip("'\"").lstrip("+")
    if ref.startswith("refs/heads/"):
        ref = ref[len("refs/heads/") :]
    return ref


def _refspec_touches_main(refspec: str) -> bool:
    """True iff either side of `[+][src]:[dst]` (or a bare ref) is main/master.

    Both sides count: `<branch>:main` pushes TO the default branch, and
    `main:<branch>` pushes the default branch's content OUT — the convention
    this hook enforces treats both as a direct-to-main operation.
    """
    ref = refspec.strip("'\"").lstrip("+")
    sides = ref.split(":") if ":" in ref else [ref]
    return any(_normalize_ref(side) in _PROTECTED for side in sides)


def _push_arguments(scanned: str, command: str) -> list[str] | None:
    """Return the whitespace-delimited tokens following `git push`, re-sliced
    from the ORIGINAL command so a quoted refspec keeps its real text.

    `strip_quoted_spans` is length-preserving precisely so these offsets stay
    valid against `command`; matching on `scanned` is what keeps a `git push`
    inside an echoed string from being seen at all.
    """
    m = _GIT_PUSH.search(scanned)
    if not m:
        return None
    rest = scanned[m.end() :]
    stop = _SHELL_SEPARATOR.search(rest)
    if stop:
        rest = rest[: stop.start()]
    base = m.end()
    return [command[base + t.start() : base + t.end()] for t in re.finditer(r"\S+", rest)]


def _current_branch() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
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


def _is_direct_push_to_main(command: str) -> bool:
    """Return True iff the command shape pushes to main/master directly."""
    scanned = _strip_quoted_spans(command)
    tokens = _push_arguments(scanned, command)
    if tokens is None:
        return False

    # First positional is the remote; anything after it is a refspec. Flags are
    # dropped — including `--force-with-lease=origin/main`, whose value is not a
    # push destination.
    positionals = [t for t in tokens if not t.startswith("-")]
    refspecs = positionals[1:]

    if refspecs:
        return any(_refspec_touches_main(r) for r in refspecs)

    # No refspec (`git push`, `git push --force`, `git push origin`) → the
    # destination is the current branch's upstream.
    return _current_branch() in _PROTECTED


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
    if not _is_direct_push_to_main(command):
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
