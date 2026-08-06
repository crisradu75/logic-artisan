#!/usr/bin/env python3
r"""PreToolUse hook: escalate history-destroying git commands to a prompt.

Why ASK rather than BLOCK
-------------------------
`.claude/settings.local.json` allows `Bash(git *)` wholesale, and the launcher
runs `--permission-mode auto`. Between them, the two genuinely irreversible git
operations run unattended: a force-push (rewrites a remote branch other people
and other worktrees may have based work on) and `reset --hard` (discards
uncommitted work with no reflog entry for what was in the working tree).

`block-direct-push-to-main.py` covers pushes that TARGET main/master. It does
not cover a force-push to a feature branch, which is the common shape here —
`/cla:spec-to-pr` and `/cla:multi-lite` both work on feature branches and both
run unattended.

A hard block is the wrong instrument. These commands are legitimate often
enough (fixing up a review branch, resetting a botched worktree) that blocking
would train people to set the override env var permanently, which is strictly
worse than a prompt. `permissionDecision: "ask"` escalates to the user's own
permission prompt instead: one keystroke, and — unlike a rule stated in
conversation — it survives compaction, which is exactly the failure mode that
makes conversational guardrails unreliable on a long unattended run.

An `ask` decision also holds in EVERY permission mode, including the `auto`
this harness launches with. A hook can tighten what the permission rules
permit; it cannot loosen it.

Why not a `deny` rule in settings.json instead
----------------------------------------------
Argument-shaped deny rules are fragile: `Bash(git push --force *)` matches
neither `git push -f` nor `git push origin main --force`. Matching the command
SHAPE (via the shared `GIT_GLOBAL_OPTS` blob, after quote-stripping) closes
both, and puts the rule in the same place as every other git guard here.

Detection scope
---------------
- `git push` carrying `--force`, or any bundled short-option cluster
  containing `f` (`-f`, `-uf`, `-fu`). Bundling is the form a hand-typed push
  most often takes, and matching only the standalone `-f` token missed it.
- `git push` with a `+`-prefixed refspec (`git push origin +feat:feat`), which
  is git's other force syntax and carries no flag at all.
- `git reset` carrying `--hard`.
- `gh pr merge` in any form. Not destructive in the same sense, but outward-
  facing and effectively irreversible, and the thing that fails there is
  AUTHORIZATION — which a hook cannot read, so the prompt is unconditional.
  See `_GH_PR_MERGE` for the incident that added it.

`--force-with-lease` and `--force-if-includes` are deliberately NOT matched:
they are the guarded forms that refuse to clobber an unseen remote update, and
prompting on them would make the prompt routine — which is how a checkpoint
stops being read. The `(?:\s|=|$)` boundary excludes them for free, since
`--force` there is followed by `-`.

Deliberately out of scope: `git clean`, `git checkout -- <path>`, `git restore`.
They discard uncommitted work too, but they are frequent enough in ordinary
flow that including them would bury the two operations above in noise. Revisit
only with evidence of a real incident.

Best-effort, not an exhaustive git parser — see `GIT_GLOBAL_OPTS`'s own
docstring for the option shapes it does and does not consume.

Escape hatch: `ALLOW_DESTRUCTIVE_GIT=1` for a deliberate unattended run.

Exit codes:
  0 — always. The decision travels as JSON on stdout, never as an exit code:
      exit 2 would be a hard block, which is the behavior this hook exists to
      avoid. Returning 0 with no output is the "nothing to ask about" case.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# See block-direct-push-to-main.py for why this bootstrap is needed: neither the
# dispatcher's in-process load nor pytest puts the hooks dir at sys.path[0] for
# this file, so the `_dispatch_lib` import below is made explicit rather than
# left to depend on how the process happened to start.
_HOOKS_DIR = str(Path(__file__).resolve().parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from _dispatch_lib import GIT_GLOBAL_OPTS as _G  # noqa: E402
from _dispatch_lib import strip_quoted_spans as _strip_quoted_spans  # noqa: E402

# The trailing `[^&|;\n]*` stops at a shell separator so the flags of a LATER
# command are never attributed to this one. A NEWLINE is a separator too: a
# multi-line Bash command is ordinary here, and without `\n` in this class a
# plain `git push` on one line was flagged because of an `-f` on the next.
_PUSH = re.compile(r"\bgit\s+" + _G + r"push\b([^&|;\n]*)")
_RESET = re.compile(r"\bgit\s+" + _G + r"reset\b([^&|;\n]*)")

# Two shapes force a push. The long flag, where `(?:\s|=|$)` is what spares
# `--force-with-lease` / `--force-if-includes` (both are followed by `-`, which
# the boundary rejects); and a bundled short cluster containing `f`. The
# `-[A-Za-z]*f[A-Za-z]*` arm cannot reach into `--force-with-lease`, because the
# character after the leading `-` there is another `-`, not a letter.
_FORCE_FLAG = re.compile(
    r"(?:^|\s)(?:--force(?:\s|=|$)|-[A-Za-z]*f[A-Za-z]*(?:\s|$))"
)
# `git push origin +feat:feat` — force expressed in the refspec, no flag at all.
_FORCE_REFSPEC = re.compile(r"(?:^|\s)\+\S+")
_HARD_FLAG = re.compile(r"(?:^|\s)--hard(?:\s|=|$)")

# `gh pr merge` — not destructive in the reset/force-push sense, but it is
# outward-facing and effectively irreversible: it publishes to a shared branch,
# can trigger deploys, and `--delete-branch` removes the source.
#
# It is here because AUTHORIZATION is the thing that fails, and a hook cannot
# read authorization. Observed twice in one session: two PRs merged that the
# user had asked to be *built*, not shipped — once by carrying a "merge and
# clean" instruction forward from an earlier, unrelated task. Both had to be
# reverted, one after review found it broken.
#
# So the prompt is unconditional rather than clever. When the merge IS
# authorized it costs a keystroke; when it is not, it is the only thing between
# an assumption and a shared branch. Unlike a rule stated in conversation, it
# survives compaction — which is exactly when the carry-forward mistake happens.
# Tokens between `gh` and `pr merge` are skipped so global options and their
# values match (`gh --repo owner/name pr merge`) — a value can contain `/`, so
# they are matched as generic tokens rather than a `[-\w]` word class, which
# missed exactly that shape. Two guards: the tokens exclude shell separators,
# so a match can never span `&&` into a different command, and the negative
# lookahead stops the skip at the first `pr` rather than running past one.
_GH_PR_MERGE = re.compile(r"\bgh\s+(?:(?!pr\b)[^\s&|;\n]+\s+)*pr\s+merge\b")


def _reasons(command: str) -> list[str]:
    """Every destructive shape present in `command`, as human-readable causes."""
    scanned = _strip_quoted_spans(command)
    found: list[str] = []
    if any(
        _FORCE_FLAG.search(m.group(1)) or _FORCE_REFSPEC.search(m.group(1))
        for m in _PUSH.finditer(scanned)
    ):
        found.append(
            "a force-push, which rewrites a remote branch other worktrees or "
            "collaborators may already have based work on"
        )
    if any(_HARD_FLAG.search(m.group(1)) for m in _RESET.finditer(scanned)):
        found.append(
            "`git reset --hard`, which discards uncommitted working-tree "
            "changes with no reflog entry to recover them from"
        )
    if _GH_PR_MERGE.search(scanned):
        found.append(
            "a PR merge, which publishes to a shared branch and cannot be "
            "cleanly undone — confirm the user actually asked for this MERGE, "
            "not just for the work to be built"
        )
    return found


def main() -> int:
    if os.environ.get("ALLOW_DESTRUCTIVE_GIT") == "1":
        # Only worth saying when there was something to prompt about; otherwise
        # every `ls` in the session would carry the notice. But when a
        # force-push or a `reset --hard` sails through because of a switch
        # somebody exported weeks ago, that has to be visible.
        try:
            payload = json.load(sys.stdin)
        except json.JSONDecodeError:
            return 0
        tool_input = payload.get("tool_input", {}) if isinstance(payload, dict) else {}
        command = tool_input.get("command") if isinstance(tool_input, dict) else None
        if isinstance(command, str) and command and _reasons(command):
            print(
                "[ask-destructive-git] note: this command would normally prompt "
                "for confirmation, but the check is DISABLED by "
                "ALLOW_DESTRUCTIVE_GIT=1. Unset it to re-enable. "
                "(hook: ask-destructive-git.py)",
                file=sys.stderr,
            )
        return 0
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    tool_input = payload.get("tool_input", {}) if isinstance(payload, dict) else {}
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not command:
        return 0

    found = _reasons(command)
    if not found:
        return 0

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": (
                "This command performs "
                + " and ".join(found)
                + ". Confirm it is what you intend. (Set ALLOW_DESTRUCTIVE_GIT=1 "
                "to run a deliberate unattended batch without this prompt; "
                "hook: ask-destructive-git.py)"
            ),
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
