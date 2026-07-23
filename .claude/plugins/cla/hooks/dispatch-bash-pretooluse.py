#!/usr/bin/env python3
"""PreToolUse dispatcher for the Bash matcher.

Runs block-cd-in-bash, block-direct-push-to-main, block-unsafe-recursive-delete,
guard-worktree-isolation, warn-branch-base, warn-stacked-pr-merge, and
warn-stray-scratch-artifact in ONE Python process instead of seven, reading
the tool-call JSON from stdin once and handing it to each in turn via
`_dispatch_lib`. Cuts per-Bash-call hook overhead from 7 interpreter spawns
to 1 — commonly cited as ~100-200ms of process-start cost each on Windows,
though not independently benchmarked for this repo.

Each sibling hook file is untouched and still independently runnable/importable
exactly as before (loaded here via the same importlib technique the test suite
uses) — this file only orchestrates them; it holds no hook logic of its own.

Order and semantics preserved exactly:
  - Any hook returning 2 blocks: its stderr message is shown, prefixed with any
    non-blocking warning text already produced by an earlier hook in this same
    run (not silently dropped), then this process exits 2.
  - If none block, any non-blocking warning stderr text is passed through —
    e.g. from warn-branch-base.py / warn-stacked-pr-merge.py /
    warn-stray-scratch-artifact.py, or guard-worktree-isolation.py's
    degraded-mode warnings (it fails open with a warning rather than
    blocking when it can't resolve a checkout target or its heartbeat dir).
  - If a hook failed to load or crashed, that's isolated to just that hook
    (the rest still run — see `_dispatch_lib.run_hook_file`) but this process
    exits 1 rather than 0 even when nothing blocked, so the failure is
    visible via Claude Code's hook-error notice instead of being silently
    discarded (exit 0 drops stderr entirely per the documented hook contract).
"""

from __future__ import annotations

import sys

from _dispatch_lib import run_hook_file

_HOOK_FILES = [
    "block-cd-in-bash.py",
    "block-direct-push-to-main.py",
    "block-unsafe-recursive-delete.py",
    "guard-worktree-isolation.py",
    "warn-branch-base.py",
    "warn-stacked-pr-merge.py",
    "warn-stray-scratch-artifact.py",
]


def main() -> int:
    stdin_text = sys.stdin.read()
    warnings: list[str] = []
    errored = False

    for filename in _HOOK_FILES:
        argv = [] if filename == "guard-worktree-isolation.py" else None
        result = run_hook_file(filename, stdin_text, argv=argv)
        errored = errored or result.errored

        if result.code == 2:
            for w in warnings:
                print(w, file=sys.stderr)
            sys.stderr.write(result.stderr)
            return 2

        if result.stderr.strip():
            warnings.append(result.stderr.rstrip("\n"))

    for w in warnings:
        print(w, file=sys.stderr)
    return 1 if errored else 0


if __name__ == "__main__":
    sys.exit(main())
