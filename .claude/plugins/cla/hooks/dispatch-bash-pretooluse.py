#!/usr/bin/env python3
"""PreToolUse dispatcher for the Bash and PowerShell matchers.

Both shells are wired to this one dispatcher because every hook below reads
`tool_input.command` and matches on the COMMAND SHAPE, not on shell syntax —
`git push --force origin x` is the same text either way. PowerShell is this
harness's primary shell on Windows, and it previously ran exactly one of these
hooks, so a force-push, a push straight to main, or a wrong-identity commit
issued through it bypassed every git guard in the tree.

Runs block-cd-in-bash, block-direct-push-to-main, ask-destructive-git,
ask-git-identity, block-unsafe-recursive-delete, guard-worktree-isolation,
warn-branch-base, warn-stacked-pr-merge, and warn-stray-scratch-artifact in ONE
Python process instead of nine, reading the tool-call JSON from stdin once and
handing it to each in turn via `_dispatch_lib`. Cuts per-Bash-call hook overhead
from 9 interpreter spawns to 1 — commonly cited as ~100-200ms of process-start
cost each on Windows, though not independently benchmarked for this repo.

Each sibling hook file is untouched and still independently runnable/importable
exactly as before (loaded here via the same importlib technique the test suite
uses) — this file only orchestrates them; it holds no hook logic of its own.

Order and semantics preserved exactly:
  - Any hook returning 2 blocks: its stderr message is shown, prefixed with any
    non-blocking warning text already produced by an earlier hook in this same
    run (not silently dropped), then this process exits 2.
  - If none block but one requests an `ask` escalation (ask-destructive-git.py
    or ask-git-identity.py — both return 0 and escalate via stdout), the merged
    decision is re-emitted as this process's own stdout JSON. Only one process's
    stdout is read per call, so a child's decision that isn't re-emitted here is
    silently downgraded to an allow. Precedence is deny > ask > allow, matching
    the documented permission evaluation order.
  - An `ask` forces exit 0 even when a sibling hook errored or advisory hooks
    were skipped, because a permission decision on stdout is only honoured on
    exit 0. Reporting an unrelated hook's failure through the exit code would
    discard the escalation entirely — trading a prompt the user needs for a
    diagnostic they don't. The diagnostic is folded into the prompt text
    instead, so nothing is lost either way.
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
  - If too little handler budget remains for an ADVISORY hook's own worst case,
    it is skipped and the skip is reported. Enforcing hooks are never skipped:
    a late block still blocks, but a block dropped to a handler kill is a silent
    failure. A skip exits 1 rather than 0 so the report actually reaches Claude.
    See `_dispatch_lib.Deadline` and `HOOK_WORST_CASE_SECONDS`.
  - Total stderr is capped to Claude Code's hook output limit, with a blocking
    hook's reason budgeted ahead of any advisory text.
"""

from __future__ import annotations

import json
import sys

from _dispatch_lib import (
    HOOK_WORST_CASE_SECONDS,
    Deadline,
    compose_output,
    fit_json_payload,
    run_hook_file,
)

_HOOK_FILES = [
    "block-cd-in-bash.py",
    "block-direct-push-to-main.py",
    "ask-destructive-git.py",
    "ask-git-identity.py",
    "block-unsafe-recursive-delete.py",
    "guard-worktree-isolation.py",
    "warn-branch-base.py",
    "warn-stacked-pr-merge.py",
    "warn-stray-scratch-artifact.py",
]

# Hooks that can only ever warn, and so may be dropped when too little handler
# budget remains for them. Every hook that changes the OUTCOME of the call — one
# that can return 2, plus `ask-destructive-git.py` and `ask-git-identity.py`,
# which return 0 but escalate to a permission prompt via stdout — is
# deliberately absent from this set AND ordered ahead of these three in
# `_HOOK_FILES`, so budget pressure costs warnings before it can cost
# enforcement. Note the two ask hooks are why the wiring test cannot key on
# `return 2` alone: skipping either would silently downgrade an ask to an allow,
# an enforcement loss no exit code would reveal.
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
        cost = HOOK_WORST_CASE_SECONDS.get(filename, 0.0)
        if filename in _ADVISORY_HOOKS and not deadline.has_room(cost):
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
            "[dispatch] too little handler budget remained for these advisory "
            f"hooks, so they were skipped: {', '.join(skipped)}. Every blocking "
            "guard still ran — only warnings were lost."
        )

    # A skip is a real degradation, not routine: exiting 0 would put the notice
    # on stderr, which the hook contract discards, leaving a run with guards
    # dropped indistinguishable from a clean one.
    degraded = errored or bool(skipped)

    out = compose_output(warnings)
    if out:
        print(out, file=sys.stderr)

    if asks:
        # An `ask` is only honoured on exit 0, so the degradation notice cannot
        # travel as an exit code here without destroying the escalation. It
        # rides along in the prompt text instead, where the user actually sees
        # it — strictly more visible than the hook-error notice it replaces.
        reason = compose_output(asks)
        if degraded:
            reason = compose_output(
                [reason],
                must_keep=(
                    "[dispatch] note: some guards did not complete on this call "
                    "(see the hook output above), so this prompt may not reflect "
                    "every check."
                ),
            )
        # Measured on the SERIALIZED payload, envelope included — clamping only
        # the reason string left the printed total over the cap once JSON
        # escaping expanded it, which sends the whole prompt to a file instead.
        print(fit_json_payload(
            lambda text: {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "ask",
                    "permissionDecisionReason": text,
                }
            },
            reason,
        ))
        return 0

    return 1 if degraded else 0


if __name__ == "__main__":
    sys.exit(main())
