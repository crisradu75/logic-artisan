#!/usr/bin/env python3
"""PreToolUse hook: WARN (never block) before a `git add`/`git commit` that
might sweep up a stray scratch artifact left in the repo root.

A background Implement delegate on Windows can mangle a scratchpad-temp path
(e.g. `C:\\Users\\...\\AppData\\Local\\Temp\\...\\scratchpad\\diff.txt`) when a
Bash redirect target's backslashes get stripped — the path collapses into one
long, extension-bearing, separator-free filename that lands in the repo root
as an untracked file (a `git diff` dump or similar), not real project content.
This recurred twice in one /multi-pr session (2026-07-16), once per delegated
Implement run, and was only caught by an observant `git status --porcelain`
read before each Ship-phase commit — this hook makes that check automatic.

Detection: the Bash command runs `git add` or `git commit`, optionally behind
git global options, with quoted spans collapsed first so `echo 'git commit'`
no longer triggers it. That collapse cuts both ways and the trade is accepted
for a warn-only hook: a git command wrapped in a quoted sub-shell string
(`bash -c 'git add .'`) is now INVISIBLE to this hook and will not warn, where
previously it did. Then `git status
--porcelain` is scanned for an UNTRACKED (`??`) entry whose path has no path
separator (`/` or `\\`) — sits at repo root, not inside any real source/doc
directory — AND whose name contains `AppData`, `LocalTemp`, or `scratchpad`
(case-insensitive).

This hook only WARNS (exit 0) — a legitimate root-level file could coincidentally
match, so a hard block would over-fire; the warning just prompts a look before
staging.

Best-effort: any parse/git failure exits 0 silently — a warning hook must never
disrupt the workflow.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys

from pathlib import Path

# The `_dispatch_lib` import below resolves through `sys.path`; running
# standalone normally puts the hooks dir at `sys.path[0]`, but that is
# suppressed under `PYTHONSAFEPATH=1` / `python -I` / `python -P`. Insert it
# explicitly so an import failure can't silently disable this hook.
_HOOKS_DIR = str(Path(__file__).resolve().parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from _dispatch_lib import GIT_GLOBAL_OPTS as _G  # noqa: E402
from _dispatch_lib import strip_quoted_spans  # noqa: E402

_GIT_ADD_OR_COMMIT = re.compile(r"\bgit\s+" + _G + r"(?:add|commit)\b")
_SUSPICIOUS_NAME = re.compile(r"AppData|LocalTemp|scratchpad", re.IGNORECASE)


def _porcelain_lines() -> list[str] | None:
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            # 4s, not 2s like the `rev-parse` hooks: `status` walks the working
            # tree, so it is genuinely slower on a large repo. Still charged
            # against the shared budget — see
            # `_dispatch_lib.HOOK_WORST_CASE_SECONDS`.
            capture_output=True, text=True, timeout=4,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return r.stdout.splitlines()


def _stray_untracked_paths(lines: list[str]) -> list[str]:
    stray = []
    for line in lines:
        if not line.startswith("??"):
            continue
        path = line[3:].strip().strip('"')
        if "/" in path or "\\" in path:
            continue  # lives inside a real directory, not a bare repo-root drop
        if _SUSPICIOUS_NAME.search(path):
            stray.append(path)
    return stray


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    tool_input = payload.get("tool_input")
    cmd = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    if not isinstance(cmd, str) or not cmd:
        return 0

    if not _GIT_ADD_OR_COMMIT.search(strip_quoted_spans(cmd)):
        return 0

    lines = _porcelain_lines()
    if lines is None:
        return 0

    stray = _stray_untracked_paths(lines)
    if not stray:
        return 0

    names = ", ".join(f'"{p}"' for p in stray)
    print(
        f"[warn-stray-scratch-artifact] untracked file(s) at repo root look like a "
        f"mangled scratchpad-temp path, not real project content: {names}. "
        f"Read the first few lines to confirm, then `rm` before staging if it's "
        f"tool-generated garbage rather than your own work.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
