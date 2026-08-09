#!/usr/bin/env python3
"""PreToolUse dispatcher for the Edit|Write matcher.

Runs warn-comment-dates and block-worktree-path-escape in ONE Python process
instead of two. See dispatch-bash-pretooluse.py (the sibling on the Bash
matcher) and the shared `_dispatch_lib` both use.

One of these hooks (warn-comment-dates) emits a non-blocking JSON warning on
stdout. Only one process's stdout is read per PreToolUse call, so this
dispatcher normalizes it into the canonical
`hookSpecificOutput.additionalContext` shape (the documented PreToolUse hook
JSON output field) — the merge still matters because a future second advisory
hook must not have its shape picked over this one's.

Order and semantics preserved exactly:
  - Any hook returning 2 blocks: its stderr message is shown, prefixed with any
    non-blocking warning text OR additionalContext already produced by an
    earlier hook in this same run (not silently dropped — a blocking response
    only carries stderr back to Claude, per the documented hook contract, so
    an earlier hook's stdout-JSON warning is folded into stderr as plain text
    here rather than lost), then this process exits 2.
  - If none block, every collected warning is merged into one
    hookSpecificOutput.additionalContext JSON object on stdout at exit 0. That
    is the only channel Claude reads: stderr from a hook exiting 0 goes to the
    debug log only, and a non-zero exit discards stdout while surfacing just the
    first line of stderr. So this dispatcher never exits non-zero unless a hook
    actually blocked.
  - If a hook failed to load or crashed, that's isolated to just that hook
    (the rest still run — see `_dispatch_lib.run_hook_file`) and the failure is
    reported as additionalContext, where it arrives whole.
  - If too little handler budget remains for an ADVISORY hook's worst case, it
    is skipped and named in the DEBUG LOG — not in context, since that skip is
    designed degradation rather than a defect. Enforcing hooks are never skipped
    — see `_ADVISORY_HOOKS` below and `_dispatch_lib.Deadline`.
  - Both output channels are capped to Claude Code's hook output limit, with a
    blocking hook's reason budgeted ahead of any advisory text.
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
    "warn-comment-dates.py",
    "block-worktree-path-escape.py",
]

# Skippable when the handler budget is spent. Note what is NOT here:
# `block-worktree-path-escape.py` can return 2. Unlike the Bash dispatcher, the
# blocking hook sits LAST in `_HOOK_FILES` here, so membership of this set is the
# only thing protecting it; order is not a backstop.
_ADVISORY_HOOKS = frozenset({
    "warn-comment-dates.py",
})


def _extract_context(stdout_text: str) -> str | None:
    """Pull the additionalContext message out of a hook's stdout JSON."""
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
    if isinstance(nested, dict) and nested.get("additionalContext"):
        return str(nested["additionalContext"])
    return None


def _ask_json(reason: str, contexts: list[str]) -> str:
    """Serialize an `ask` decision, carrying any advisory context alongside.

    This dispatcher previously had NO ask channel — only `additionalContext` —
    so an escalation had nowhere to go even once the variable existed. The ask
    reason is held whole and the advisory context is what shrinks under the cap,
    matching the Bash dispatcher.
    """
    return fit_json_payload(
        lambda text: {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": reason,
                **({"additionalContext": text} if text else {}),
            }
        },
        "\n\n".join(contexts),
    )


def _context_json(contexts: list[str]) -> str:
    """Serialize the merged additionalContext, capped as a WHOLE.

    The cap applies to what this process prints, envelope included — and JSON
    escaping can expand the payload past a naive pre-clamp — so the size is
    measured on the serialized string and the context re-clamped by however much
    it overshot. Converges in one or two passes; bounded so it always returns.
    """
    return fit_json_payload(
        lambda text: {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": text,
            }
        },
        "\n\n".join(contexts),
    )


def _skip_notice(skipped: list[str]) -> str:
    if not skipped:
        return ""
    return (
        "[dispatch] too little handler budget remained for these advisory "
        f"hooks, so they were skipped: {', '.join(skipped)}. Every blocking "
        "guard still ran — only warnings were lost."
    )


def main() -> int:
    stdin_text = sys.stdin.read()
    deadline = Deadline()
    warnings: list[str] = []
    contexts: list[str] = []
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

        if result.code == 2:
            # The skip notice DOES belong here, and only here. On exit 2 stderr is
            # shown to Claude, and a block is the one moment where knowing some
            # advisory checks were dropped changes how much the message is worth
            # trusting. On the allow path it stays out of context (see below) —
            # the asymmetry is deliberate, not an oversight.
            preamble = [n for n in (_skip_notice(skipped),) if n] + list(warnings) + [
                f"[non-blocking warning from an earlier hook this same call]\n{c}"
                for c in contexts
            ]
            sys.stderr.write(compose_output(preamble, must_keep=result.stderr))
            return 2

        if result.stderr.strip():
            warnings.append(result.stderr.rstrip("\n"))
        context = _extract_context(result.stdout)
        if context:
            contexts.append(context)

    # Debug log only, not context — see the Bash dispatcher for the reasoning:
    # an advisory hook stepping aside under load is designed degradation, and
    # putting it in Claude's context on every Edit is noise on the hottest path
    # in the session. A crashed hook is a defect and does go to context, below.
    notice = _skip_notice(skipped)
    if notice:
        print(notice, file=sys.stderr)
    if errored:
        warnings.append(
            "[dispatch] one or more hooks failed to load or crashed on this "
            "call, so their checks did not run. Re-run with `claude --debug` "
            "for the traceback."
        )
    ask_reason = ""
    if errored_enforcing:
        # Escalated to `ask`, not left as a warning. `_dispatch_lib`'s docstring
        # records why exiting non-zero here would be wrong — it USED to ask for
        # it, and was corrected to match what both dispatchers actually do, so
        # this comment cited a requirement the same release had deleted and
        # pointed at a contract whose text now says the reverse. The reasoning
        # is unchanged: a non-zero exit makes Claude Code discard stdout — which
        # would downgrade this very ask to an allow and surface only the first
        # line of merged stderr. `ask` is the one channel that reaches the user
        # and cannot be ignored, and it costs nothing when the edit was fine.
        #
        # Advisory hooks are deliberately excluded: losing a warning is the
        # acceptable half of the trade this dispatcher already makes for budget.
        ask_reason = (
            "an ENFORCING guard could not run on this call — "
            + ", ".join(sorted(errored_enforcing))
            + ". Its check did NOT happen, so this write is unguarded rather "
            "than approved. Confirm only if you know the change is safe; re-run "
            "with `claude --debug` for the traceback."
        )

    # a hook that exits 0 is never shown in the transcript and Claude never sees
    # it. This write exists for `claude --debug`; everything Claude must act on
    # goes out as stdout JSON below.
    err_out = compose_output(warnings)
    if err_out:
        print(err_out, file=sys.stderr)

    # A warning is only delivered if it travels as additionalContext. Exiting
    # non-zero to signal a problem would discard stdout altogether and surface
    # just the FIRST LINE of stderr, so it reports less, not more — the same
    # reasoning as the Bash dispatcher.
    merged = contexts + warnings
    if ask_reason:
        print(_ask_json(ask_reason, merged))
    elif merged:
        print(_context_json(merged))
    return 0


if __name__ == "__main__":
    sys.exit(main())
