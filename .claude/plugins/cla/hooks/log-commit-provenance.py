#!/usr/bin/env python3
"""PostToolUse (Bash): record whether each commit went through a CLA skill.

WHY THIS EXISTS. Every retro loop in this plugin reads a ledger written *by a
skill that ran*. Nothing anywhere records the work that should have gone through
a skill and did not. So the loops measure their own usage and cannot see their
own adoption: a day with 34 commits and one logged `spec-to-pr` run reports one
run and reads as quiet. That exact ratio was measured in this repo, which is why
this hook exists.

`codify-retro`'s premise is "is the loop working?", and that question has no
answer while the denominator is missing. This supplies the denominator: one line
per commit, with the skill that produced it or `null`.

WHAT IT IS NOT. It is not a guard — it never blocks, never warns, never prints
on the happy path. It is not a judgement about whether a bypass was wrong: plenty
of commits legitimately skip the skills (a merge, a release bump, a one-line typo
fix). It records what happened and leaves adjudication to the retro that reads it.

HOW THE SKILL IS DETECTED. `CLAUDE_SKILL` if the harness exports it; otherwise
the commit subject's conventional prefix maps to the skill that writes it
(`feat: <change>` / `fix: review round N` / `chore: archive` are spec-to-pr's own
message shapes, pinned in its message-style table). A subject matching none of
them is recorded as `null` rather than guessed at — a wrong attribution is worse
than an honest unknown, because it inflates exactly the number this exists to
measure.

FAILURE POSTURE. Best-effort and silent: any parse failure, missing git, absent
ledger dir, or non-zero git exit ends in exit 0 with nothing written. A telemetry
hook must never disrupt a workflow, and a missing line is infinitely preferable
to a broken commit. The one thing it will not do is write a WRONG line.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Same resolution the sibling git hooks use: the import goes through `sys.path`,
# which a standalone run populates only via `sys.path[0]`.
_HOOKS_DIR = str(Path(__file__).resolve().parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from _dispatch_lib import GIT_CMD, strip_quoted_spans  # noqa: E402

# Matches the plugin's other git-touching hooks rather than inventing a budget.
_GIT_TIMEOUT_SECONDS = 3

# Conventional subjects the ship skills emit, per spec-to-pr's message-style
# table and lite-pr's Ship step. Order matters only for readability; the patterns
# are mutually exclusive.
_SUBJECT_TO_SKILL = (
    (re.compile(r"^fix: review round \d+$"), "spec-to-pr"),
    (re.compile(r"^chore: archive "), "spec-to-pr"),
    (re.compile(r"^chore: spec-to-pr run log$"), "spec-to-pr"),
    (re.compile(r"^fix: address review findings$"), "lite-pr"),
)

_LEDGER_NAME = "commit-provenance.jsonl"

# One line must stay well under the atomic-append ceiling `lib/log_run.py`
# enforces for the same reason: a single small write cannot interleave with a
# concurrent one.
_MAX_LINE_BYTES = 2048


def _git(*args: str, cwd: Path) -> str | None:
    try:
        r = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _is_commit_command(command: str) -> bool:
    """True for a real `git commit`, false for anything that merely mentions it.

    Deliberately narrow. `git log --grep="git commit"`, a `--dry-run`, and any
    prose containing the words must not produce a ledger line; over-recording
    corrupts the very ratio this hook exists to report.
    """
    # Blank out quoted spans first, the same way the git guard hooks do: without
    # it `echo 'run git commit later'` reads as a commit and writes a spurious
    # line — precisely the over-recording that corrupts this ledger.
    command = strip_quoted_spans(command)
    if not re.search(GIT_CMD + r"[^|;&]*\bcommit\b", command):
        return False
    if "--dry-run" in command:
        return False
    # A commit inside a pipeline reading history (`git log … | …`) is not a commit.
    return not re.search(GIT_CMD + r"[^|;&]*\b(log|show|rev-list)\b", command)


def _detect_skill(subject: str) -> str | None:
    env_skill = os.environ.get("CLAUDE_SKILL") or os.environ.get("CLA_ACTIVE_SKILL")
    if env_skill:
        return env_skill.strip() or None
    for pattern, skill in _SUBJECT_TO_SKILL:
        if pattern.search(subject):
            return skill
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    command = ((payload.get("tool_input") or {}).get("command")) or ""
    if not _is_commit_command(command):
        return 0

    cwd = Path(payload.get("cwd") or os.getcwd())

    # The commit must actually exist — a failed `git commit` (nothing staged, a
    # rejecting hook) must not be recorded as one.
    head = _git("rev-parse", "--short", "HEAD", cwd=cwd)
    subject = _git("log", "-1", "--pretty=%s", cwd=cwd)
    if not head or subject is None:
        return 0

    root = _git("rev-parse", "--show-toplevel", cwd=cwd)
    if not root:
        return 0
    ledger_dir = Path(os.environ.get("CLAUDE_RETRO_DIR") or (Path(root) / "cla.io" / "retro"))
    if not ledger_dir.is_dir():
        # Never create the tree: a repo that has not run `cla-init` has not opted
        # into per-repo state, and this hook is not the place to decide it should.
        return 0

    record = {
        "ts": _git("log", "-1", "--pretty=%cI", cwd=cwd) or "",
        "sha": head,
        "subject": subject[:120],
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd) or "",
        "skill": _detect_skill(subject),
    }
    line = json.dumps(record, ensure_ascii=False) + "\n"
    if len(line.encode("utf-8")) > _MAX_LINE_BYTES:
        return 0

    try:
        with (ledger_dir / _LEDGER_NAME).open("ab") as fh:
            fh.write(line.encode("utf-8"))
    except OSError:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
