#!/usr/bin/env python3
"""PreToolUse hook: refuse a commit that certifies a check nobody ran.

Why
---
Two shipped rules keep a commit's record honest, and both lived in prose only:

- `ship.md` §2b and `lite-pr/references/measured-by.md`: a change that asserts
  no measurement carries no `Measured-by:` trailer, "never `Measured-by: none`",
  which certifies a check nobody ran while reading as evidence that one did.
- `spec-to-pr/references/revise.md` step 3: a review round whose findings were
  all rejected leaves no `fix: review round <N>` commit, and "Never manufacture
  an empty commit for the counter". `probe_state.py` counts rounds by those
  subjects, so an empty one tells the next run a fix landed that did not.

Decision
--------
On each `git commit` in the command (found with `_shell_text.GitInvocation`
behind any global options, in any `&&` / `;` / `|` / newline / subshell
segment; arguments read by `_git_commit_args`):

- BLOCK when a message line (from each `-m`/`--message`, a `-F`/`--file`
  message file, or a stdin heredoc after `-F -`) is a `Measured-by: none`
  trailer, or a `--trailer` value is one. The key is matched as git matches
  trailer keys, ignoring case; the value is `none` alone or followed by a
  remark (`none (docs only)`). A line that only mentions it ("never
  `Measured-by: none`") is not a trailer and passes.
- BLOCK `--allow-empty` when the subject is a review-round subject, matched
  with `probe_state.py`'s own pattern: that commit exists only to move the
  counter.
- WARN on any other `--allow-empty`. An empty commit is sometimes deliberate
  (a repository's first commit), so the warning states the rule and the call
  runs.

Silent for `--dry-run` (no commit is made), for a message this hook cannot see
(the editor, `-C`, a message piped in), and for a command git would refuse.
`ALLOW_DESTRUCTIVE_GIT` does not apply: it silences prompts before a
destructive git command, and these blocks guard a record, not a working tree.
There is no override; the fix is always to the message.

Enforcing, at no cost to the handler budget: it runs no subprocess. Its only
I/O is reading a `-F` message file, capped at
`_git_commit_args.MAX_MESSAGE_FILE_BYTES`. Linear time on any input (see
`_git_commit_args`). Bad input fails open: unparseable JSON, a missing command
or unreadable command text exits 0 with no output. If the file itself fails to
load, the Bash dispatcher counts it as an enforcing guard that did not run and
asks.

Exit codes:
  0 -- allow (a warning, if any, on stderr, which the dispatcher forwards).
  2 -- block; the reason is on stderr.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

_HOOKS_DIR = str(Path(__file__).resolve().parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from _shell_text import GitInvocation, strip_quoted_spans  # noqa: E402
from _git_commit_args import COMMIT_OR_ADD, Commit, find_invocations  # noqa: E402

_MATCHER = GitInvocation(COMMIT_OR_ADD, capture_opts=True)

# A message line that is a `Measured-by: none` trailer. Git reads a trailer
# key without regard to case; the value is `none`, alone or before a remark
# (`none (docs)`, `none - docs`, `none` and a dash), never a longer word.
_NONE_VALUE = r"none(?=[ \t]*$|[ \t]*[(\[.,;:\u2013\u2014]|[ \t]+-)"
_NONE_LINE = re.compile(r"^measured-by[ \t]*:[ \t]*" + _NONE_VALUE, re.I | re.M)
# A `--trailer` value also takes `=` as its separator.
_NONE_TRAILER = re.compile(r"^[ \t]*measured-by[ \t]*[:=][ \t]*" + _NONE_VALUE, re.I)
# Kept identical to `skills/spec-to-pr/scripts/probe_state.py`'s round counter;
# `test_block_dishonest_commit.py` fails when the two differ.
_ROUND_SUBJECT = re.compile(r"^fix: review round (\d+)\b")


def _measured_by_none(commit: Commit) -> bool:
    # Only the trailer block counts, as git parses it: the last paragraph of
    # the message, a line starting at column 0. A body line that mentions it,
    # or an indented example, is prose.
    last = re.split(r"\n[ \t]*\n", "\n\n".join(commit.messages).strip("\r\n \t"))[-1]
    lines = [ln for ln in last.splitlines() if ln.strip()]
    block = all(re.match(r"[A-Za-z0-9-]+[ \t]*:|[ \t]", ln) for ln in lines)
    return (block and _NONE_LINE.search(last) is not None) or any(
        _NONE_TRAILER.match(t) for t in commit.trailers
    )


def _review_round(commit: Commit) -> bool:
    subject = commit.subject
    return subject is not None and _ROUND_SUBJECT.match(subject) is not None


_BLOCK_NONE = (
    "blocked: this commit carries a `Measured-by: none` trailer. A change that asserts no "
    "measurement carries no `Measured-by:` line at all; `none` certifies a check nobody ran. "
    "Delete the line, or run the measurement and name its command "
    "(`Measured-by: <command> — <claim>`). (hook: block-dishonest-commit.py)"
)
_BLOCK_ROUND = (
    "blocked: an empty commit with a review-round subject (`fix: review round <N>`) moves "
    "`probe_state.py`'s round counter without a fix. A round whose findings were all rejected "
    "leaves no commit: record it in the Handoff report (\"round N: all findings "
    "remedy-rejected, no commit\") instead. (hook: block-dishonest-commit.py)"
)
_WARN_EMPTY = (
    "[block-dishonest-commit] `git commit --allow-empty` records a commit that changes "
    "nothing. If it stands for work (a review round, a fix, a measurement), drop it and "
    "report the outcome instead; if it is deliberate, such as a repository's first commit, "
    "carry on."
)


def _decide(stdin_text: str) -> tuple[int, str]:
    payload = json.loads(stdin_text)
    if not isinstance(payload, dict):
        return 0, ""
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or "commit" not in command.lower():
        return 0, ""
    cwd = payload.get("cwd")
    cwd = cwd if isinstance(cwd, str) and cwd else os.getcwd()
    commits = [
        inv for inv in find_invocations(command, strip_quoted_spans(command), _MATCHER, cwd)
        if isinstance(inv, Commit) and not inv.dry_run
    ]
    warn = False
    for commit in commits:
        if _measured_by_none(commit):
            return 2, _BLOCK_NONE
        if commit.allow_empty:
            if _review_round(commit):
                return 2, _BLOCK_ROUND
            warn = True
    return 0, _WARN_EMPTY if warn else ""


def main() -> int:
    try:
        code, message = _decide(sys.stdin.read())
    except Exception:  # noqa: BLE001 -- bad input fails open
        return 0
    if message:
        print(message, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
