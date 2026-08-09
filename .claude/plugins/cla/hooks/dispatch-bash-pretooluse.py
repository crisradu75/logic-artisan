#!/usr/bin/env python3
"""PreToolUse dispatcher for the Bash and PowerShell matchers.

Both shells are wired to this one dispatcher because every hook below reads
`tool_input.command` and matches on the COMMAND SHAPE, not on shell syntax —
`git push --force origin x` is the same text either way. PowerShell is this
harness's primary shell on Windows, and it previously ran exactly one of these
hooks, so a force-push, a push straight to main, or a wrong-identity commit
issued through it bypassed every git guard in the tree.

Runs block-cd-in-bash, ask-destructive-git, block-unsafe-recursive-delete,
warn-stacked-pr-merge, and warn-stray-scratch-artifact in ONE Python process
instead of five, reading the tool-call JSON from stdin once and handing it to
each in turn via `_dispatch_lib`. Cuts per-Bash-call hook overhead from 5
interpreter spawns to 1 — commonly cited as ~100-200ms of process-start cost
each on Windows, though not independently benchmarked for this repo.

Pushes to main/master are NOT guarded here. That check moved to `git/pre-push`,
which git hands the resolved refspec — no command string to parse, so none of
the `git.exe` / `-C` / quoting spellings that defeated the old hook can reach
it differently. See that file's header.

Each sibling hook file is untouched and still independently runnable/importable
exactly as before (loaded here via the same importlib technique the test suite
uses) — this file only orchestrates them; it holds no hook logic of its own.

Order and semantics preserved exactly:
  - Any hook returning 2 blocks: its stderr message is shown, prefixed with any
    non-blocking warning text already produced by an earlier hook in this same
    run (not silently dropped), then this process exits 2.
  - If none block but one requests an `ask` escalation (ask-destructive-git.py
    returns 0 and escalates via stdout), the merged decision is re-emitted as
    this process's own stdout JSON. Only one process's stdout is read per call,
    so a child's decision that isn't re-emitted here is silently downgraded to
    an allow. Precedence is deny > ask > allow, matching the documented
    permission evaluation order.
  - If none block, EVERYTHING non-blocking leaves as one stdout JSON object at
    exit 0: `permissionDecision` for an ask, `additionalContext` for advisory
    text — e.g. from warn-stacked-pr-merge.py / warn-stray-scratch-artifact.py.

    This is the only channel that works. Per the documented contract, stderr
    from a hook exiting 0 goes to the debug log and Claude never sees it, so
    writing a warning there delivers it to nobody; and a non-zero exit discards
    stdout entirely while surfacing only the FIRST LINE of stderr, which for
    merged multi-hook output is rarely the useful one. The dispatcher therefore
    never exits non-zero on the non-blocking path — doing so would report LESS.
  - If a hook failed to load or crashed, that's isolated to just that hook
    (the rest still run — see `_dispatch_lib.run_hook_file`) and the failure is
    reported as additionalContext, where it arrives whole.
  - If too little handler budget remains for an ADVISORY hook's own worst case,
    it is skipped and named in the DEBUG LOG — not in context. That skip is the
    mechanism working as designed (advisory means the loss is acceptable), and
    routine notices on the session's hottest path train the channel to be
    ignored. Enforcing hooks are never skipped at all: a late block still
    blocks, but a block dropped to a handler kill is a silent failure. See
    `_dispatch_lib.Deadline` and `HOOK_WORST_CASE_SECONDS`.
  - Both channels are capped to Claude Code's hook output limit, with a blocking
    hook's reason (or an ask's) budgeted ahead of any advisory text.
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
    "ask-destructive-git.py",
    "block-unsafe-recursive-delete.py",
    "warn-stacked-pr-merge.py",
    "warn-stray-scratch-artifact.py",
]

# Hooks that can only ever warn, and so may be dropped when too little handler
# budget remains for them. Every hook that changes the OUTCOME of the call — one
# that can return 2, plus `ask-destructive-git.py`, which returns 0 but escalates
# to a permission prompt via stdout — is deliberately absent from this set AND
# ordered ahead of these two in `_HOOK_FILES`, so budget pressure costs warnings
# before it can cost enforcement. Note the ask hook is why the wiring test cannot
# key on `return 2` alone: skipping it would silently downgrade an ask to an
# allow, an enforcement loss no exit code would reveal.
_ADVISORY_HOOKS = frozenset({
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
    errored_enforcing: list[str] = []

    for filename in _HOOK_FILES:
        cost = HOOK_WORST_CASE_SECONDS.get(filename, 0.0)
        if filename in _ADVISORY_HOOKS and not deadline.has_room(cost):
            skipped.append(filename)
            continue

        result = run_hook_file(filename, stdin_text)
        errored = errored or result.errored
        # An ENFORCING hook that failed to load did not run its check, and from
        # the outside that is indistinguishable from one that ran and allowed.
        # Tracked separately from `errored` so the escalation below fires only
        # for guards whose absence actually matters.
        if result.errored and filename not in _ADVISORY_HOOKS:
            errored_enforcing.append(filename)

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

    # Skips go to stderr (the debug log) ONLY, deliberately, and are not added
    # to `warnings` — which is what becomes additionalContext below.
    #
    # An advisory hook stepping aside under load is this mechanism working as
    # designed: `_ADVISORY_HOOKS` membership is precisely the statement that
    # losing this hook is acceptable. Announcing it in Claude's context on every
    # busy call is noise on the hottest path in the session, and a channel that
    # carries routine noise stops being read — the same reasoning that keeps the
    # env-override notices off unrelated commands.
    #
    # A hook that CRASHED is the opposite: not designed degradation but a defect,
    # and it does go to context, below. Enforcement is never skipped at all, so
    # nothing load-bearing is being quietly dropped here.
    if skipped:
        print(
            "[dispatch] too little handler budget remained for these advisory "
            f"hooks, so they were skipped: {', '.join(skipped)}. Every blocking "
            "guard still ran — only warnings were lost.",
            file=sys.stderr,
        )
    if errored:
        warnings.append(
            "[dispatch] one or more hooks failed to load or crashed on this "
            "call, so their checks did not run. Re-run with `claude --debug` "
            "for the traceback."
        )
    if errored_enforcing:
        # Escalated to `ask`, not left as a warning. `_dispatch_lib`'s docstring
        # records why exiting non-zero here would be wrong — it USED to ask for
        # it, and was corrected to match what both dispatchers actually do, so
        # this comment cited a requirement the same release had deleted and
        # pointed at a contract whose text now says the reverse. The reasoning
        # is unchanged: a non-zero exit makes Claude Code discard stdout — which
        # would downgrade a pending `ask` to an allow and surface only the first
        # line of merged stderr. `ask` is the one channel that reaches the user,
        # cannot be ignored, and costs nothing when the call was legitimate.
        #
        # Advisory hooks are deliberately excluded: losing a warning is the
        # acceptable half of the trade this dispatcher already makes for budget.
        asks.append(
            "an ENFORCING guard could not run on this call — "
            + ", ".join(sorted(errored_enforcing))
            + ". Its check did NOT happen, so this call is unguarded rather than "
            "approved. Confirm only if you know the action is safe; re-run with "
            "`claude --debug` for the traceback."
        )

    # stderr here reaches the DEBUG LOG ONLY. Per the hook contract, stderr from
    # a hook that exits 0 is never shown in the transcript and Claude never sees
    # it — so everything Claude must act on travels as stdout JSON below, and
    # this write exists purely for `claude --debug`.
    if warnings:
        print(compose_output(warnings), file=sys.stderr)

    # Everything non-blocking leaves through ONE stdout JSON object at exit 0 —
    # the only channel a PreToolUse hook has that Claude actually reads. An
    # `ask` and advisory text coexist in it: `permissionDecision` carries the
    # escalation, `additionalContext` the warnings.
    #
    # A non-zero exit is never used here, and that is deliberate. It discards
    # stdout entirely (so the ask would be downgraded to an allow) and surfaces
    # only the FIRST LINE of stderr, which for merged multi-hook output is
    # almost never the useful one. Exiting 1 to "report" a failed hook would
    # therefore cost more information than it conveys; the failure is reported
    # as context instead, where it arrives whole.
    reason = compose_output(asks) if asks else ""
    context = compose_output(warnings) if warnings else ""
    if not reason and not context:
        return 0

    def _payload(context_text: str) -> dict:
        nested: dict = {"hookEventName": "PreToolUse"}
        if reason:
            nested["permissionDecision"] = "ask"
            nested["permissionDecisionReason"] = reason
        if context_text:
            nested["additionalContext"] = context_text
        return {"hookSpecificOutput": nested}

    # Measured on the SERIALIZED payload, envelope included — clamping only the
    # inner strings left the printed total over the cap once JSON escaping
    # expanded it, which sends the whole thing to a file instead. The advisory
    # context is the part that shrinks; the ask reason is held whole.
    print(fit_json_payload(_payload, context))
    return 0


if __name__ == "__main__":
    sys.exit(main())
