#!/usr/bin/env python3
"""PreToolUse dispatcher for the Bash matcher.

Runs block-cd-in-bash, block-direct-push-to-main, ask-destructive-git,
block-unsafe-recursive-delete, guard-worktree-isolation, warn-branch-base,
warn-stacked-pr-merge, and warn-stray-scratch-artifact in ONE Python process
instead of eight, reading the tool-call JSON from stdin once and handing it to
each in turn via `_dispatch_lib`. Cuts per-Bash-call hook overhead from 8
interpreter spawns to 1 — commonly cited as ~100-200ms of process-start cost
each on Windows, though not independently benchmarked for this repo.

Each sibling hook file is untouched and still independently runnable/importable
exactly as before (loaded here via the same importlib technique the test suite
uses) — this file only orchestrates them; it holds no hook logic of its own.

Order and semantics preserved exactly:
  - Any hook returning 2 blocks: its stderr message is shown, prefixed with any
    non-blocking warning text already produced by an earlier hook in this same
    run (not silently dropped), then this process exits 2.
  - If none block but one requests an `ask` escalation (ask-destructive-git.py),
    the merged decision is re-emitted as this process's own stdout JSON. Only
    one process's stdout is read per call, so a child's decision that isn't
    re-emitted here is silently downgraded to an allow. Precedence is
    deny > ask > allow, matching the documented permission evaluation order.
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

import json
import sys

from _dispatch_lib import Deadline, compose_output, run_hook_file

_HOOK_FILES = [
    "block-cd-in-bash.py",
    "block-direct-push-to-main.py",
    "ask-destructive-git.py",
    "block-unsafe-recursive-delete.py",
    "guard-worktree-isolation.py",
    "warn-branch-base.py",
    "warn-stacked-pr-merge.py",
    "warn-stray-scratch-artifact.py",
]

# Hooks that can only ever warn, and so may be dropped when the handler budget
# is spent. Every hook that changes the OUTCOME of the call — one that can
# return 2, and `ask-destructive-git.py`, which returns 0 but escalates to a
# permission prompt — is deliberately absent from this set AND ordered ahead of
# these three in `_HOOK_FILES`, so budget pressure costs warnings before it can
# cost enforcement. Note the ask hook is the reason the wiring test cannot key
# on `return 2` alone: skipping it would silently downgrade an ask to an allow,
# which is an enforcement loss that no exit code would reveal.
_ADVISORY_HOOKS = frozenset({
    "warn-branch-base.py",
    "warn-stacked-pr-merge.py",
    "warn-stray-scratch-artifact.py",
})


def _extract_ask(stdout_text: str) -> str | None:
    """Pull an `ask` escalation's reason out of a hook's stdout JSON.

    A hook that wants the user prompted (rather than blocked outright) exits 0
    and emits `permissionDecision: "ask"`. Only this process's stdout is read
    per PreToolUse call, so the decision has to be re-emitted here or it is
    silently downgraded to an allow.
    """
    stdout_text = stdout_text.strip()
    if not stdout_text:
        return None
    try:
        payload = json.loads(stdout_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    nested = payload.get("hookSpecificOutput")
    if not isinstance(nested, dict) or nested.get("permissionDecision") != "ask":
        return None
    return str(nested.get("permissionDecisionReason") or "A guard requested confirmation.")


def main() -> int:
    stdin_text = sys.stdin.read()
    deadline = Deadline()
    warnings: list[str] = []
    asks: list[str] = []
    skipped: list[str] = []
    errored = False

    for filename in _HOOK_FILES:
        if filename in _ADVISORY_HOOKS and deadline.expired():
            skipped.append(filename)
            continue

        argv = [] if filename == "guard-worktree-isolation.py" else None
        result = run_hook_file(filename, stdin_text, argv=argv)
        errored = errored or result.errored

        # Precedence is deny > ask > allow, matching the documented permission
        # evaluation order: a block short-circuits, and any pending `ask` is
        # moot once the call is refused outright.
        if result.code == 2:
            sys.stderr.write(compose_output(warnings, must_keep=result.stderr))
            return 2

        if result.stderr.strip():
            warnings.append(result.stderr.rstrip("\n"))
        ask = _extract_ask(result.stdout)
        if ask:
            asks.append(ask)

    if skipped:
        warnings.append(
            "[dispatch] handler budget spent before these advisory hooks could "
            f"run, so they were skipped: {', '.join(skipped)}. Every blocking "
            "guard still ran — only warnings were lost."
        )

    out = compose_output(warnings)
    if out:
        print(out, file=sys.stderr)
    if asks:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": compose_output(asks),
            }
        }))
    return 1 if errored else 0


if __name__ == "__main__":
    sys.exit(main())
