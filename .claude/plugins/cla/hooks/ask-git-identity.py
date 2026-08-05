#!/usr/bin/env python3
"""PreToolUse hook: catch a wrong or missing git identity before it is baked in.

Why this ranks above the SSH-key case
-------------------------------------
The two identity failures fail very differently. A wrong SSH *key* is rejected
loudly by the remote at push time — you find out immediately and fix it. A wrong
`user.email` is ACCEPTED silently, lands in the commit, and surfaces later in the
log, by which point fixing it means rewriting history. The quiet one is the
expensive one, so it is the one worth a checkpoint.

Nothing in this harness checked either. `git_state.py` and `--expect-branch`
verify branch and working-tree state; neither says anything about *who* is
committing.

Two modes
---------
- **Configured (strict).** Set `CLA_EXPECTED_GIT_EMAIL` to the address this repo
  should commit as. A mismatch escalates to a permission prompt
  (`permissionDecision: "ask"`), because at that point the expectation is
  explicit and the mismatch is the bug. Opt-in by construction: a harness cannot
  know your identity, and guessing one would be worse than not checking.
- **Zero-config.** With no expectation set, the hook still warns when the repo
  has NO `user.email` at all — that commit is either about to fail or about to
  be attributed to whatever global default happens to be present, and neither is
  what anyone wants.

Silent otherwise. An identity that exists and matches (or exists with no stated
expectation) produces no output.

Why `ssh -T` is deliberately NOT run here
-----------------------------------------
Verifying the key would mean a network round-trip on a hook that fires on every
commit and every push — exactly the per-tool-call cadence that produced the
handler-timeout defects this hook layer was just fixed for. `git config` reads a
local file and costs nothing.

If you do add an SSH check somewhere slower-cadence: read the GREETING line, not
the exit code. `ssh -T git@github.com` prints `Hi <user>!` and then exits **1**,
because GitHub closes the connection without granting a shell. A check keyed on
the exit code reports failure on a perfectly good setup, which trains people to
ignore it.

Fires on commit AND push. Commit is where the email is actually baked in, so it
is the preventive moment; push is the last checkpoint before it becomes someone
else's problem.

Escape hatch: `ALLOW_GIT_IDENTITY_MISMATCH=1`.

Exit codes:
  0 — always. A mismatch escalates via JSON on stdout; a missing identity warns
      on stderr. Neither blocks: the hook cannot tell a deliberate identity from
      a mistaken one, and refusing the commit outright would be wrong.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# See block-direct-push-to-main.py for why this bootstrap is needed.
_HOOKS_DIR = str(Path(__file__).resolve().parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from _dispatch_lib import GIT_GLOBAL_OPTS as _G  # noqa: E402
from _dispatch_lib import strip_quoted_spans as _strip_quoted_spans  # noqa: E402

# Local file read, no network — but bounded anyway, because every subprocess on a
# per-tool-call path is bounded in this tree (see the handler-budget notes in
# _dispatch_lib).
_GIT_TIMEOUT_SECONDS = 3

_IDENTITY_BAKING = re.compile(r"\bgit\s+" + _G + r"(?:commit|push)\b")


def _git_email(cwd: str) -> str | None:
    """The email git would actually use in `cwd`, or None if it cannot be read.

    Resolved in the SESSION's directory rather than wherever this hook process
    happens to be running: the two differ whenever the session works in a linked
    worktree, and a repo-local `user.email` is exactly the kind of config that
    differs between them.
    """
    try:
        r = subprocess.run(
            ["git", "-C", cwd, "config", "user.email"],
            capture_output=True, text=True, timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    # rc 1 with empty output is git's "not set" answer, distinct from a failure
    # to run git at all — but both leave us with nothing to compare, so the
    # caller treats an empty string as "unset" and None as "could not tell".
    if r.returncode not in (0, 1):
        return None
    return (r.stdout or "").strip()


def main() -> int:
    if os.environ.get("ALLOW_GIT_IDENTITY_MISMATCH") == "1":
        return 0
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    if not isinstance(payload, dict):
        return 0
    tool_input = payload.get("tool_input", {})
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not command:
        return 0
    if not _IDENTITY_BAKING.search(_strip_quoted_spans(command)):
        return 0

    cwd = payload.get("cwd") or os.getcwd()
    if not isinstance(cwd, str):
        cwd = os.getcwd()

    actual = _git_email(cwd)
    if actual is None:
        # Could not read git at all. Fail open and silent: this hook is an
        # identity check, not a git-health monitor, and the sibling hooks
        # already report a broken git loudly.
        return 0

    expected = (os.environ.get("CLA_EXPECTED_GIT_EMAIL") or "").strip()

    if not actual:
        print(
            "[ask-git-identity] warn: this repo has no `user.email` configured, so "
            "the commit will either fail or be attributed to a global default. "
            "Set it with `git config user.email '<you@example.com>'` before "
            "committing. (hook: ask-git-identity.py)",
            file=sys.stderr,
        )
        return 0

    if expected and actual != expected:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": (
                    f"Git identity mismatch: this repo is configured to commit as "
                    f"'{actual}', but CLA_EXPECTED_GIT_EMAIL says '{expected}'. A "
                    "wrong email is accepted silently and only shows up later in the "
                    "log, where fixing it means rewriting history. Fix with "
                    f"`git config user.email '{expected}'`, or confirm to proceed as "
                    f"'{actual}'. (Set ALLOW_GIT_IDENTITY_MISMATCH=1 to silence; "
                    "hook: ask-git-identity.py)"
                ),
            }
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
