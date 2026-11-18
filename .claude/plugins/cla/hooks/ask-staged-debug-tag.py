#!/usr/bin/env python3
"""PreToolUse hook: ask before a commit that would add a `/cla:diagnose` debug tag.

Why
---
`/cla:diagnose` tags every temporary log or probe with its instrumentation tag
(the text `TAG` below, then four hex characters and `]`) so that Phase 6 can
remove them with one grep. A run that is interrupted leaves them in the tree,
and `ship.md` §2a says the same grep "must return nothing; remove any tagged
line before staging". Both are prose a hurried commit skips; this hook is the
mechanical half. The tag also lives in `diagnose/SKILL.md` and `ship.md`; a
rename must touch all three.

Why ASK, not block
------------------
A leaked tag ships noise, which is recoverable, and a line that documents the
tag (this plugin's own diagnose skill does) is legitimate. The user decides.

Detection
---------
For each `git commit` in the command that is not a `--dry-run` (found with
`_dispatch_lib.GitInvocation`, arguments read by `_git_commit_args`), the lines
the commit would add are read from git, in the commit's directory (the payload
`cwd` moved by each `-C`):

- the staged diff, `git diff --cached`;
- with `-a`, or with pathspecs on the commit, or after a `git add` earlier in
  the same command (the hook runs before any of it), the tracked changes those
  name, `git diff` (all of them for `-a`, `-A`, `-u` or `.`-style adds);
- for that `git add`, the untracked files it names
  (`git ls-files --others --exclude-standard`), read whole: every line of a
  new file is an added line.

Every added line holding `TAG` is a hit. One or more: ask, naming up to ten as
`path:line`. Lines a commit only keeps, and the commit message, are not read:
`diagnose`'s own commit message quotes the tag on purpose.

SECURITY: no command text reaches git where git could read it as an option.
Pathspecs go after `--`, the directory is an absolute path, and the diff
options are fixed (`--no-ext-diff`, `--no-textconv`, `--no-color`, explicit
prefixes), so a user's diff configuration cannot run a program or change the
output this hook parses.

Best-effort, like `ask-broad-git-add`. Unparseable input, no git, not a
repository, `--git-dir`/`--work-tree`/`GIT_DIR=` (the repository cannot be
named), a git error or timeout, or any exception: exit 0 silently. All git calls
for one command share `GIT_BUDGET_SECONDS`, and the untracked files read are
capped (`MAX_FILES`, `MAX_FILE_BYTES`, `MAX_TOTAL_BYTES`). The hook never blocks, so the Bash
dispatcher may skip it when the handler budget is spent (`_BEST_EFFORT_HOOKS`).
`ALLOW_DESTRUCTIVE_GIT` does not apply: a commit is not a destructive command.

Exit codes:
  0 -- always. The decision travels as JSON on stdout.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

_HOOKS_DIR = str(Path(__file__).resolve().parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from _dispatch_lib import GitInvocation, strip_quoted_spans  # noqa: E402
from _git_commit_args import COMMIT_OR_ADD, Add, Commit, find_invocations  # noqa: E402

# Built from two halves so that this file's own added lines never hold the tag.
TAG = "[" + "DEBUG-"

# Total wall time for every git call this hook makes on one command, shared.
# `_dispatch_lib.HOOK_WORST_CASE_SECONDS` records the same figure.
GIT_BUDGET_SECONDS = 3.0
MAX_NAMED = 10
MAX_FILES = 200
MAX_FILE_BYTES = 1_000_000
MAX_TOTAL_BYTES = 4_000_000

_MATCHER = GitInvocation(COMMIT_OR_ADD, capture_opts=True)
_HUNK = re.compile(r"@@ -\S+ \+(\d+)")
_DIFF = [
    "diff", "--no-ext-diff", "--no-textconv", "--no-color", "--unified=0",
    "--src-prefix=a/", "--dst-prefix=b/",
]


class _Clock:
    """The shared deadline, and each git answer already had on this command:
    a chain of commits in one directory asks git once, not once per commit."""

    def __init__(self) -> None:
        self.deadline = time.monotonic() + GIT_BUDGET_SECONDS
        self.answers: dict[tuple[str, ...], str | None] = {}

    def left(self) -> float:
        return self.deadline - time.monotonic()


def _git(directory: str, args: list[str], clock: _Clock) -> str | None:
    key = (directory, *args)
    if key not in clock.answers:
        clock.answers[key] = _run_git(directory, args, clock.left())
    return clock.answers[key]


def _run_git(directory: str, args: list[str], timeout: float) -> str | None:
    if timeout <= 0:
        return None
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "-c", "core.quotePath=false", "-C", directory, *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return result.stdout if result.returncode == 0 else None


def _diff_hits(diff: str) -> list[tuple[str, int, str]]:
    """`(path, line, text)` for each added line of a `--unified=0` diff holding the tag."""
    hits: list[tuple[str, int, str]] = []
    path: str | None = None
    line_no = 0
    in_header = False
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            in_header, path = True, None
            continue
        if in_header:
            if line.startswith("+++ "):
                # git ends the line with a tab when the name holds a space.
                target = line[4:].rstrip("\t")
                path = target[2:] if target.startswith("b/") else None
                continue
            if not line.startswith("@@"):
                continue
            in_header = False
        if line.startswith("@@"):
            hunk = _HUNK.match(line)
            line_no = int(hunk.group(1)) if hunk else 0
            continue
        if line.startswith("+"):
            if path is not None and TAG in line:
                hits.append((path, line_no, line[1:]))
            line_no += 1
    return hits


def _file_hits(directory: str, relative: str, budget: list[int]) -> list[tuple[str, int, str]]:
    if budget[0] <= 0:
        return []
    try:
        with open(os.path.join(directory, relative), "rb") as handle:
            data = handle.read(min(MAX_FILE_BYTES, budget[0]))
    except OSError:
        return []
    budget[0] -= len(data)
    text = data.decode("utf-8", errors="replace")
    if TAG not in text:
        return []
    return [
        (relative, number, line)
        for number, line in enumerate(text.splitlines(), 1)
        if TAG in line
    ]


def _commit_hits(commit: Commit, adds: list[Add], clock: _Clock) -> list[tuple[str, int, str]]:
    directory = commit.directory
    if directory is None or not os.path.isdir(directory):
        return []
    hits: list[tuple[str, int, str]] = []
    staged = _git(directory, [*_DIFF, "--cached"], clock)
    hits += _diff_hits(staged or "")

    # Tracked changes the commit takes from the working tree.
    tracked_whole = commit.all_files or any(a.whole_tree for a in adds)
    tracked_specs = list(commit.pathspecs)
    for add in adds:
        tracked_specs += add.pathspecs
    if tracked_whole or tracked_specs:
        args = [*_DIFF] if tracked_whole else [*_DIFF, "--", *tracked_specs]
        hits += _diff_hits(_git(directory, args, clock) or "")

    # Untracked files a `git add` earlier in the command stages.
    new_adds = [a for a in adds if not a.tracked_only]
    if new_adds:
        args = ["ls-files", "-z", "--others", "--exclude-standard"]
        if not any(a.whole_tree for a in new_adds):
            args += ["--", *[spec for a in new_adds for spec in a.pathspecs]]
        listing = _git(directory, args, clock)
        budget = [MAX_TOTAL_BYTES]
        for relative in [p for p in (listing or "").split("\0") if p][:MAX_FILES]:
            hits += _file_hits(directory, relative, budget)
    return hits


def _ask_reason(hits: list[tuple[str, int, str]]) -> str:
    shown = "; ".join(f"`{path[:200]}:{line}` {text.strip()[:80]!r}" for path, line, text in hits[:MAX_NAMED])
    more = f"; and {len(hits) - MAX_NAMED} more" if len(hits) > MAX_NAMED else ""
    return (
        f"this commit would add {len(hits)} line(s) holding `/cla:diagnose`'s `{TAG}xxxx]` "
        f"debug tag: {shown}{more}. Remove each tagged line and re-stage, then commit "
        "(ship.md 2a, diagnose Phase 6); confirm only if the tag is meant to ship, as in a "
        "document about the tag. (hook: ask-staged-debug-tag.py)"
    )


def _decide(stdin_text: str) -> str | None:
    payload = json.loads(stdin_text)
    if not isinstance(payload, dict):
        return None
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or "commit" not in command.lower():
        return None
    cwd = payload.get("cwd")
    cwd = cwd if isinstance(cwd, str) and cwd else os.getcwd()
    invocations = find_invocations(command, strip_quoted_spans(command), _MATCHER, cwd)
    clock = _Clock()
    hits: list[tuple[str, int, str]] = []
    seen: set[tuple[str, int, str]] = set()
    # The adds before each commit, by directory, gathered in one pass.
    adds_in: dict[str | None, list[Add]] = {}
    for inv in invocations:
        if isinstance(inv, Add):
            adds_in.setdefault(inv.directory, []).append(inv)
            continue
        if inv.dry_run:
            continue
        if clock.left() <= 0:
            break  # every later git call would be refused anyway
        for hit in _commit_hits(inv, adds_in.get(inv.directory, []), clock):
            if hit not in seen:
                seen.add(hit)
                hits.append(hit)
    return _ask_reason(hits) if hits else None


def main() -> int:
    try:
        reason = _decide(sys.stdin.read())
    except Exception:  # noqa: BLE001 -- best-effort: a failure to check is silence
        return 0
    if reason:
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": reason,
            }
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
