#!/usr/bin/env python3
r"""PreToolUse hook: escalate history-destroying git commands to a prompt.

Why ASK rather than BLOCK
-------------------------
`.claude/settings.local.json` allows `Bash(git *)` wholesale, and the launcher
runs `--permission-mode auto`. Between them, the two genuinely irreversible git
operations run unattended: a force-push (rewrites a remote branch other people
and other worktrees may have based work on) and `reset --hard` (discards
uncommitted work with no reflog entry for what was in the working tree).

The `git/pre-push` hook covers pushes that TARGET main/master. It does not
cover a force-push to a feature branch, which is the common shape here —
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
- `gh pr merge`, including behind global options and as `gh.exe`/`gh.cmd`. Not
  destructive in the same sense, but outward-facing and effectively
  irreversible, and the thing that fails there is AUTHORIZATION — which a hook
  cannot read, so the prompt is unconditional. NOT matched (regex cannot reach
  them, and they are named rather than implied): a shell alias, a case variant
  like `GH pr merge`, and the REST form `gh api -X PUT .../pulls/N/merge`.
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

Escape hatches:
  - `ALLOW_PR_MERGE=1` — drops ONLY the PR-merge confirmation. This is the one
    to use for a skill that merges as an ordinary step of a long unattended run
    (`multi-pr`, `multi-lite`); force-push and `reset --hard` stay checked.
    Prefer it per-command over exporting it.
  - `ALLOW_DESTRUCTIVE_GIT=1` — drops every check below, for a deliberate
    unattended batch.

`ALLOW_DESTRUCTIVE_GIT`'s scope widened when `gh pr merge` was added, and the
name stopped describing it — it now also silences an AUTHORIZATION checkpoint,
so a value exported weeks ago for a force-push batch would wave through every
PR merge too. `ALLOW_PR_MERGE` exists so that trade never has to be made: an
unattended run that merges declares exactly that, and keeps its force-push and
reset guards. Prefer either per-command over exporting it for a session; the
stderr `DISABLED` notice fires on every command they suppress.

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

# Why this bootstrap is needed: neither the
# dispatcher's in-process load nor pytest puts the hooks dir at sys.path[0] for
# this file, so the `_dispatch_lib` import below is made explicit rather than
# left to depend on how the process happened to start.
_HOOKS_DIR = str(Path(__file__).resolve().parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from _dispatch_lib import GIT_CMD as _GIT_CMD  # noqa: E402
from _dispatch_lib import GIT_GLOBAL_OPTS as _G  # noqa: E402
from _dispatch_lib import strip_quoted_spans as _strip_quoted_spans  # noqa: E402

# Horizontal whitespace, or a backslash line continuation. A continuation is a
# JOINED line, not a new command, so it separates tokens; a bare newline ends
# the command and must not. Both rules below and `_GH_PR_MERGE` share this —
# four review rounds each found the same bug one construct over, every time
# because one position used a plain `\s` or excluded the newline outright.
_SEP = r"(?:[ \t]|\\\r?\n)+"

# The trailing tail stops at a shell separator so the flags of a LATER command
# are never attributed to this one. A NEWLINE is such a separator: a multi-line
# Bash command is ordinary here, and without `\n` excluded, a plain `git push`
# on one line was flagged because of an `-f` on the next.
#
# But a CONTINUED newline is not a command boundary, and excluding `\n` flatly
# made `git push \`+newline+`--force origin feat` — an ordinary multi-line
# invocation — a silent bypass of the force-push guard. The tail therefore
# admits a continuation while still stopping at a bare newline, and the
# `git`→subcommand gap uses `_SEP` for the same reason.
_TAIL = r"((?:\\\r?\n|[^&|;\n])*)"
_PUSH = re.compile(_GIT_CMD + _SEP + _G + r"push\b" + _TAIL)
_RESET = re.compile(_GIT_CMD + _SEP + _G + r"reset\b" + _TAIL)

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
# missed exactly that shape.
#
# Separators are `_SEP` — horizontal whitespace, or a backslash line
# continuation — never a bare `\s`. `\s` matches a newline, so the skip walked
# across line breaks into an unrelated command and `gh auth status` + newline +
# `echo pr merge` fired. `_PUSH`/`_RESET` already exclude `\n` for this exact
# reason (see their comment above).
#
# But excluding the newline outright was ALSO wrong, and briefly shipped that
# way: `gh \`+newline+`pr merge` is an ordinary multi-line invocation and became
# a silent bypass. A continuation is a joined line, not a new command, so it is
# a separator; a bare newline is not.
#
# `_SEP` must be used at EVERY separator position, including between `pr` and
# `merge`. A first pass applied it to the `gh`→token and token→token positions
# and left the subcommand pair as `[ \t]`, which moved the identical bypass one
# token to the right — `gh pr \`+newline+`merge` was still silent. Same bug,
# different position, caught only by a review pass that re-probed the fix.
#
# The skip is LAZY with no lookahead. An earlier `(?!pr…)` guard was there to
# stop the skip running past the first `pr`, but laziness does that for free and
# the guard had its own bug: it could not skip a token that merely began with
# `pr`, so `gh --repo pr-tools/x pr merge` — and, after that was narrowed,
# `gh --repo pr pr merge` — were misses. Shortest-match-first handles both.
#
# The optional extension matches `gh.exe` / `gh.cmd`, ordinary spellings on
# this repo's primary platform, which bare `\bgh\s` missed entirely.
#
# `merge(?![\w-])` rather than `merge\b`: `\b` ends at a hyphen, so
# `gh pr merge-queue status` — a real, read-only subcommand — was prompting.
#
# Known misses, stated rather than implied: a shell alias, a case variant
# (`GH pr merge` — PowerShell resolves commands case-insensitively), and the
# REST equivalent `gh api -X PUT repos/o/n/pulls/N/merge`. A regex cannot
# resolve an alias, and the `gh api` surface is too broad to match without
# false-firing on every read-only API call. Named here so the gap is a known
# limitation rather than a surprise.
# `_SEP` is defined once, above, and shared with `_PUSH`/`_RESET`. The
# extension group is case-folded: it exists because Windows is the primary
# platform, and that shell resolves `gh.EXE` as readily as `gh.exe`, so a
# case-sensitive group would have been the same inconsistency one more time.
#
# The escaped dot sits OUTSIDE the case-folding group deliberately. With it
# inside, the source text would contain a letter-colon-backslash run, which the
# conformance guard's Windows-drive-path scanner flags as a hardcoded developer
# path. Same match either way; this spelling avoids the false alarm.
_GH_PR_MERGE = re.compile(
    r"\bgh(?:\.(?i:exe|cmd|bat|com|ps1))?" + _SEP
    + r"(?:[^\s&|;\n]+" + _SEP + r")*?pr" + _SEP + r"merge(?![\w-])"
)


# Named so `main()` can suppress THIS reason alone under `ALLOW_PR_MERGE=1`,
# without touching the force-push and reset checks. The narrow variable exists
# because `multi-pr` and `multi-lite` merge as an ordinary loop step of a long
# unattended run — an audit of every mutating command those skills emit found
# the merge prompt was the only NEW thing standing in their way. Silencing it
# with the broad `ALLOW_DESTRUCTIVE_GIT` would have disarmed force-push and
# `reset --hard` for the same commands, which is a strictly worse trade.
# An inline `ALLOW_PR_MERGE=1` env-assignment prefix, at the start of the whole
# command or of a segment after a shell separator. Anchored so it cannot be
# satisfied by the string appearing mid-command (inside an echoed message, say)
# — it has to sit where a shell would actually treat it as an assignment.
_ALLOW_MERGE_PREFIX = re.compile(r"(?:^|[&|;]\s*)ALLOW_PR_MERGE=1[ \t]")

MERGE_REASON = (
    "a PR merge, which publishes to a shared branch and cannot be cleanly "
    "undone — confirm the user actually asked for this MERGE, not just for "
    "the work to be built"
)


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
        found.append(MERGE_REASON)
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

    # `ALLOW_PR_MERGE=1` drops ONLY the merge reason. A command that also
    # force-pushes still prompts, on the force-push — which is the whole point
    # of a narrow variable over the broad one. Announced on stderr for the same
    # reason the broad hatch is: a merge sailing through because of a switch set
    # earlier in the run must not look like one the guard deliberately allowed.
    #
    # Honoured from the COMMAND TEXT as well as the environment, and the command
    # text is the form to prefer. A PreToolUse hook runs BEFORE the command is
    # executed, so an inline `ALLOW_PR_MERGE=1 gh pr merge …` prefix never
    # reaches this process's `os.environ` — reading only the environment would
    # mean the per-command form silently did nothing, which is exactly how it
    # was first written. Matching the prefix here is what makes "authorize this
    # one command" expressible at all; the environment form remains for a
    # caller that genuinely wants it set for a whole run.
    # Scanned on the QUOTE-STRIPPED text, like every other matcher in this file.
    # Scanning the raw command made the escape hatch satisfiable by prose: the
    # anchor `(?:^|[&|;]\s*)` accepts a separator that sits INSIDE a quoted span,
    # which the shell treats as one literal and never evaluates as an assignment.
    # Both of these silenced the prompt entirely:
    #
    #   gh pr merge 27 && echo "; ALLOW_PR_MERGE=1 done"
    #   git commit -m "fix hook; ALLOW_PR_MERGE=1 now bypasses it" && gh pr merge 27
    #
    # The second is the shape a session working on THIS hook writes. The guard
    # exists because authorization is the one thing a hook cannot read, so a
    # bypass firing on unrelated text removes exactly the protection it adds --
    # and the stderr note below then announced a disabling nobody requested.
    #
    # A genuine inline `ALLOW_PR_MERGE=1 gh pr merge …` prefix is unquoted, so it
    # survives stripping intact and the per-command form still works.
    if found and (
        os.environ.get("ALLOW_PR_MERGE") == "1"
        or _ALLOW_MERGE_PREFIX.search(_strip_quoted_spans(command))
    ):
        kept = [r for r in found if r != MERGE_REASON]
        if len(kept) != len(found):
            print(
                "[ask-destructive-git] note: the PR-merge confirmation is "
                "DISABLED by ALLOW_PR_MERGE=1 for this command. Force-push and "
                "reset --hard are still checked. (hook: ask-destructive-git.py)",
                file=sys.stderr,
            )
        found = kept
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
