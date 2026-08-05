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
  - If the handler budget runs out mid-list, the remaining ADVISORY hooks are
    skipped and the skip is reported on stderr. Enforcing hooks are never
    skipped: a late block still blocks, but a block dropped to a handler kill
    is a silent failure. See `_dispatch_lib.Deadline`.
  - Total stderr is capped to Claude Code's hook output limit, with a blocking
    hook's reason budgeted ahead of any advisory text.
"""

from __future__ import annotations

import sys

from _dispatch_lib import Deadline, compose_output, run_hook_file

_HOOK_FILES = [
    "block-cd-in-bash.py",
    "block-direct-push-to-main.py",
    "block-unsafe-recursive-delete.py",
    "guard-worktree-isolation.py",
    "warn-branch-base.py",
    "warn-stacked-pr-merge.py",
    "warn-stray-scratch-artifact.py",
]

# Hooks that can only ever warn, and so may be dropped when the handler budget
# is spent. Every hook capable of returning 2 is deliberately absent from this
# set AND ordered ahead of these three in `_HOOK_FILES`, so budget pressure
# costs warnings before it can cost enforcement. Keep both properties together:
# a new blocking hook appended to the end of the list would still run, but only
# because it is not named here — the wiring test pins the invariant.
_ADVISORY_HOOKS = frozenset({
    "warn-branch-base.py",
    "warn-stacked-pr-merge.py",
    "warn-stray-scratch-artifact.py",
})


def main() -> int:
    stdin_text = sys.stdin.read()
    deadline = Deadline()
    warnings: list[str] = []
    skipped: list[str] = []
    errored = False

    for filename in _HOOK_FILES:
        if filename in _ADVISORY_HOOKS and deadline.expired():
            skipped.append(filename)
            continue

        argv = [] if filename == "guard-worktree-isolation.py" else None
        result = run_hook_file(filename, stdin_text, argv=argv)
        errored = errored or result.errored

        if result.code == 2:
            sys.stderr.write(compose_output(warnings, must_keep=result.stderr))
            return 2

        if result.stderr.strip():
            warnings.append(result.stderr.rstrip("\n"))

    if skipped:
        warnings.append(
            "[dispatch] handler budget spent before these advisory hooks could "
            f"run, so they were skipped: {', '.join(skipped)}. Every blocking "
            "guard still ran — only warnings were lost."
        )

    out = compose_output(warnings)
    if out:
        print(out, file=sys.stderr)
    return 1 if errored else 0


if __name__ == "__main__":
    sys.exit(main())
