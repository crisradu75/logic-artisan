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
"""

from __future__ import annotations

import json
import sys

from _dispatch_lib import run_hook_file

_HOOK_FILES = [
    "warn-comment-dates.py",
    "block-dated-stamps-in-prose.py",
    "guard-worktree-isolation.py",
    "warn-smoke-test-drift.py",
    "block-worktree-path-escape.py",
]


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


def main() -> int:
    stdin_text = sys.stdin.read()
    warnings: list[str] = []
    contexts: list[str] = []
    errored = False

    for filename in _HOOK_FILES:
        argv = ["--heartbeat"] if filename == "guard-worktree-isolation.py" else None
        result = run_hook_file(filename, stdin_text, argv=argv)
        errored = errored or result.errored

        if result.code == 2:
            for w in warnings:
                print(w, file=sys.stderr)
            for c in contexts:
                print(f"[non-blocking warning from an earlier hook this same call]\n{c}", file=sys.stderr)
            sys.stderr.write(result.stderr)
            return 2

        if result.stderr.strip():
            warnings.append(result.stderr.rstrip("\n"))
        context = _extract_context(result.stdout)
        if context:
            contexts.append(context)

    for w in warnings:
        print(w, file=sys.stderr)
    if contexts:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": "\n\n".join(contexts),
            }
        }))
    return 1 if errored else 0


if __name__ == "__main__":
    sys.exit(main())
