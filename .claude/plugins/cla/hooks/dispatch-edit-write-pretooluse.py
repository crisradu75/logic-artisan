#!/usr/bin/env python3
"""PreToolUse dispatcher for the Edit|Write matcher.

Runs warn-comment-dates, block-dated-stamps-in-prose, guard-worktree-isolation
(--heartbeat mode), warn-smoke-test-drift, and block-worktree-path-escape in
ONE Python process instead of five. See dispatch-bash-pretooluse.py (the
sibling on the Bash matcher) and the shared `_dispatch_lib` both use.

Two of these hooks (warn-comment-dates, warn-smoke-test-drift) emit a
non-blocking JSON warning on stdout. Only one process's stdout is read per
PreToolUse call, so this dispatcher merges both into the canonical
`hookSpecificOutput.additionalContext` shape (the documented PreToolUse hook
JSON output field) rather than picking one hook's shape over the other.

Order and semantics preserved exactly:
  - Any hook returning 2 blocks: its stderr message is shown, prefixed with any
    non-blocking warning text OR additionalContext already produced by an
    earlier hook in this same run (not silently dropped — a blocking response
    only carries stderr back to Claude, per the documented hook contract, so
    an earlier hook's stdout-JSON warning is folded into stderr as plain text
    here rather than lost), then this process exits 2.
  - If none block, any collected warning messages are merged into one
    hookSpecificOutput.additionalContext JSON object on stdout.
  - If a hook failed to load or crashed, that's isolated to just that hook
    (the rest still run — see `_dispatch_lib.run_hook_file`) but this process
    exits 1 rather than 0 when nothing blocked, so the failure is visible via
    Claude Code's hook-error notice instead of being silently discarded (exit
    0 drops stderr entirely per the documented hook contract).
  - If the handler budget runs out mid-list, the remaining ADVISORY hooks are
    skipped and the skip is reported. Enforcing hooks are never skipped — see
    `_ADVISORY_HOOKS` below and `_dispatch_lib.Deadline`.
  - Both output channels are capped to Claude Code's hook output limit, with a
    blocking hook's reason budgeted ahead of any advisory text.
"""

from __future__ import annotations

import json
import sys

from _dispatch_lib import (
    HOOK_OUTPUT_CHAR_LIMIT,
    Deadline,
    clamp_output,
    compose_output,
    run_hook_file,
)

_HOOK_FILES = [
    "warn-comment-dates.py",
    "block-dated-stamps-in-prose.py",
    "guard-worktree-isolation.py",
    "warn-smoke-test-drift.py",
    "block-worktree-path-escape.py",
]

# Skippable when the handler budget is spent. Note what is NOT here:
# `block-dated-stamps-in-prose.py` and `block-worktree-path-escape.py` can
# return 2, and `guard-worktree-isolation.py` runs in --heartbeat mode, where
# its whole job is the side effect of refreshing this session's presence file —
# skipping it would silently degrade the contention detection every other
# worktree guard depends on. Unlike the Bash dispatcher, a blocking hook sits
# LAST in `_HOOK_FILES` here, so membership of this set is the only thing
# protecting it; order is not a backstop.
_ADVISORY_HOOKS = frozenset({
    "warn-comment-dates.py",
    "warn-smoke-test-drift.py",
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


def _context_json(contexts: list[str]) -> str:
    """Serialize the merged additionalContext, capped as a WHOLE.

    The cap applies to what this process prints, envelope included — and JSON
    escaping can expand the payload past a naive pre-clamp — so the size is
    measured on the serialized string and the context re-clamped by however much
    it overshot. Converges in one or two passes; bounded so it always returns.
    """
    merged = "\n\n".join(contexts)
    out = ""
    for _ in range(4):
        out = json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": merged,
            }
        })
        overflow = len(out) - HOOK_OUTPUT_CHAR_LIMIT
        if overflow <= 0:
            return out
        merged = clamp_output(merged, max(0, len(merged) - overflow))
    return out


def main() -> int:
    stdin_text = sys.stdin.read()
    deadline = Deadline()
    warnings: list[str] = []
    contexts: list[str] = []
    skipped: list[str] = []
    errored = False

    for filename in _HOOK_FILES:
        if filename in _ADVISORY_HOOKS and deadline.expired():
            skipped.append(filename)
            continue

        argv = ["--heartbeat"] if filename == "guard-worktree-isolation.py" else None
        result = run_hook_file(filename, stdin_text, argv=argv)
        errored = errored or result.errored

        if result.code == 2:
            preamble = list(warnings) + [
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

    if skipped:
        warnings.append(
            "[dispatch] handler budget spent before these advisory hooks could "
            f"run, so they were skipped: {', '.join(skipped)}. Every blocking "
            "guard still ran — only warnings were lost."
        )

    err_out = compose_output(warnings)
    if err_out:
        print(err_out, file=sys.stderr)
    if contexts:
        print(_context_json(contexts))
    return 1 if errored else 0


if __name__ == "__main__":
    sys.exit(main())
