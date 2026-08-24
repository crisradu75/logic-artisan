#!/usr/bin/env python3
"""PostToolUse (Bash): record whether each commit went through a CLA skill.

WHY THIS EXISTS. Every retro loop in this plugin reads a ledger written *by a
skill that ran*. Nothing anywhere records the work that should have gone through
a skill and did not. So the loops measure their own usage and cannot see their
own adoption: a day of many commits and one logged `spec-to-pr` run reports one
run and reads as quiet.

The ratio that motivated this hook, with the commands that produce it, measured
on the session that wrote it (`6bf0755` is that session's first parent):

    git rev-list --count --no-merges 6bf0755..main   # -> 31
    wc -l < cla.io/retro/spec-to-pr-runs.jsonl       # -> 1

31 to 1. An earlier draft of this docstring said "34" and called it measured; it
was not, and re-deriving it for the PR that shipped this hook is what caught it.
Hence the commands above rather than the number alone.

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

WHAT ELSE IT RECORDS. `measured_by_count` and `measured_by` — the `Measured-by:`
trailers the Ship and Revise commit steps require, one per measurement a change
asserts. Nothing gates a single commit, so a trailer that was never written is
invisible without a ledger; this is the column that makes "is the rule actually
being followed?" a countable question rather than an unfalsifiable one. Same
posture as `skill`: recorded, never adjudicated here.

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

# `Measured-by:` trailers, recorded for the same reason as `skill`: a rule stated
# in a skill has no adoption number until something counts it. The Ship and
# Revise commit steps require one trailer per measurement the change asserts, and
# nothing gates a single commit — so whether the rule is being followed is
# answerable only from a ledger. Same posture as the rest of this hook: it
# records what happened and leaves adjudication to the retro.
#
# `measured_by_count` is exact and always written; `measured_by` holds the values
# and is what gets shortened under the line ceiling, never the count. A trailer
# can be long (a real command plus the claim it produced), and the alternative —
# letting an oversize record drop the whole line — would silently remove the
# commit from the denominator too.
_TRAILER_KEY = "Measured-by"
_MAX_TRAILERS = 10
_MAX_TRAILER_CHARS = 160

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


def _measured_by(cwd: Path) -> list[str]:
    """Every `Measured-by:` trailer value on HEAD, in order.

    `unfold=true` joins a trailer continued across lines, so a wrapped command
    is recorded as the one value it is rather than as two fragments. A commit
    with no such trailer yields an empty list, which is the honest reading: the
    rule says a change asserting no measurement writes none.
    """
    raw = _git(
        "log",
        "-1",
        f"--pretty=%(trailers:key={_TRAILER_KEY},valueonly=true,unfold=true)",
        cwd=cwd,
    )
    if not raw:
        return []
    return [line.strip() for line in raw.splitlines() if line.strip()]


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

    measured = _measured_by(cwd)
    record = {
        "ts": _git("log", "-1", "--pretty=%cI", cwd=cwd) or "",
        "sha": head,
        "subject": subject[:120],
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd) or "",
        "skill": _detect_skill(subject),
        "measured_by_count": len(measured),
        "measured_by": [v[:_MAX_TRAILER_CHARS] for v in measured[:_MAX_TRAILERS]],
    }

    def _line() -> str:
        return json.dumps(record, ensure_ascii=False) + "\n"

    # Shed trailer VALUES until the record fits; `measured_by_count` is never
    # touched, so a shortened list stays distinguishable from an absent one and
    # the adoption number survives intact.
    line = _line()
    while len(line.encode("utf-8")) > _MAX_LINE_BYTES and record["measured_by"]:
        record["measured_by"] = record["measured_by"][:-1]
        line = _line()
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
