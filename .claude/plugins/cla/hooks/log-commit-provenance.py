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

OFF UNLESS ASKED FOR. The ledger FILE's existence is the opt-in, and this hook
never creates it:

    touch cla.io/retro/commit-provenance.jsonl   # on
    rm    cla.io/retro/commit-provenance.jsonl   # off

Default off is deliberate (issue #219). This is telemetry whose only value is
realised by running a retro command, so a repo that never runs one was paying a
recurring cost — including a mid-merge `git checkout` abort, because this is the
only ledger written by a hook rather than by a skill at a controlled moment — to
produce a number nobody would read. Gating on the ledger DIRECTORY charged that
cost against consent given for the other two ledgers, which live in the same
directory and cost nothing like as much.

AN EXISTING LEDGER STAYS ON, and "default off" applies to repos that do not have
one yet. This matters because the previous version CREATED the file: it opened
`"ab"` unconditionally once the directory existed, so any repo that made one
commit with the directory present now has a ledger and is opted in by this rule.
Measured against a repo scaffolded the way `cla-init` leaves one — the other two
ledgers present, no provenance file:

    old hook -> rc 0, ledger created: True,  rows written: 1
    new hook -> rc 0, ledger created: False, rows written: 0

Staying on is the deliberate choice: an upgrade that silently stopped recording
would be a surprise in the other direction. **To opt out, delete the file.**

FAILURE POSTURE. Best-effort and silent: any parse failure, missing git, absent
ledger, or non-zero git exit ends in exit 0 with nothing written. A telemetry
hook must never disrupt a workflow, and a missing line is infinitely preferable
to a broken commit. The one thing it will not do is write a WRONG line.

A ROW IS BORN UNCOMMITTED, and in a linked worktree that is a leak this hook
cannot close. The row describing commit N cannot be inside commit N, so it waits
in the working tree for a later commit to STAGE the ledger — and this repo's own
Ship rule says never to. `spec-to-pr/references/ship.md` requires path-scoped
staging and "never expand to `-A`", so the ledger is never among the staged
paths and NO row is swept up. Measured, three commits with a hook drive between
each:

    explicit paths (ship.md's rule)  ->  3 of 3 rows left uncommitted
    git add -A                       ->  1 of 3 rows left uncommitted

So `git worktree remove --force` discards every row that worktree wrote, not
just its last. Measured 2026-09-12: nine rows orphaned across five separate
rescues in one session — three from one worktree, two from another — every one
recovered by somebody noticing rather than by anything checking.

An earlier draft of this paragraph said only the LAST row orphans and called it
a bounded one-row-per-session leak. That is true only under `git add -A`, which
the Ship rule forbids, and it understated the problem in the direction that
makes it look smaller — while being offered as input to the #239 decision.

Stated here rather than fixed here because every candidate fix is a decision
this hook does not own. Writing to the primary clone's ledger instead would
dirty a working tree the committer is not in; writing outside git contradicts
`lib/log_run.py`'s stated choice of an in-repo, git-synced ledger over a
machine-local one; and dropping the rows that carry no `Measured-by:` would
delete the denominator the hook exists to supply.

Draining on teardown is the candidate the corrected number argues FOR, and it is
the one to weigh first: recovering every row a worktree wrote is worth more than
recovering its last. Its weakness is coverage rather than principle —
`manual_worktree.py` already refuses to remove a worktree holding uncommitted
work, and `git worktree remove --force` bypasses that refusal — which is an
argument that the refusal is incomplete, not that draining is wrong.

Tracked as issue #239.

That posture has one limit worth naming, because a silent under-count is as
useless as a silent over-count. The commit checks below must never turn "I
cannot tell" into "no". A repo whose reflog is disabled or expired answers
`git reflog` with success and no output, and reading that as a negative would
drop every genuine row for the life of that repo, with the ledger looking
exactly like a repo that simply never commits.
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


# The reasons `git reflog` writes when HEAD moved because a commit was created.
# Every other movement — `checkout:`, `merge`, `rebase`, `pull --ff-only:`,
# `reset:` — means the command that just ran committed nothing, so the HEAD this
# hook is about to read belongs to somebody else's work.
_COMMIT_REFLOG_REASONS = ("commit:", "commit (initial):", "commit (amend):")


def _head_moved_by_commit(cwd: Path) -> bool:
    """True when the last thing to move HEAD was a commit.

    The hook runs on PostToolUse and its payload carries no pre-command state,
    so "did HEAD move?" cannot be answered by comparing before against after.
    The reflog answers the neighbouring question — what moved HEAD last — and
    that is enough to reject the case this exists for: a commit-shaped command
    run when the previous HEAD movement was a checkout, a merge, or a pull.

    Not sufficient on its own, deliberately. A `git commit` that stages nothing
    leaves the reflog untouched, so the top entry is still the PREVIOUS real
    commit and this returns True. `_already_recorded` is what rejects that one.

    "There is no reflog" and "the reflog says this was not a commit" are
    DIFFERENT claims, and collapsing them drops every genuine row in a repo
    whose reflog is off. `core.logAllRefUpdates=false`, an expired reflog, and
    a deleted `.git/logs/HEAD` all leave `rev-parse` and `log -1` working while
    `git reflog -1` succeeds with empty output — so an empty result means this
    check cannot be evaluated, and the hook says so by declining to suppress.
    `_already_recorded` still gates the write; the check degrades rather than
    silently zeroing the denominator the whole hook exists to supply.
    """
    reason = _git("reflog", "-1", "--format=%gs", cwd=cwd)
    if reason is None:
        return False  # git itself failed; nothing here is trustworthy
    if reason == "":
        return True  # no reflog to read — undecidable, not a negative answer
    return reason.startswith(_COMMIT_REFLOG_REASONS)


def _already_recorded(ledger: Path, sha: str) -> bool:
    """True when the ledger's last row already carries this sha.

    Two commits can never share a sha, so a match means this row was written
    already — the shape a failed `git commit` produces when it re-presents the
    HEAD its predecessor legitimately recorded.

    Reads a tail chunk rather than the file: the ledger grows without bound and
    a row is capped at `_MAX_LINE_BYTES`, so 4 KiB always contains a whole last
    line. An unreadable or absent ledger returns False — the hook cannot tell,
    and `_head_moved_by_commit` has already gated this call, so the failure
    posture stays "lose a check, never lose a genuine row".

    That OSError branch covers two cases on purpose and must keep doing so. One
    is a ledger that does not exist yet, where permitting the write is the only
    correct answer — failing closed there would mean no repo ever gets its first
    row. The other is a populated ledger momentarily unreadable, where
    permitting the write can duplicate a row. Anyone tempted to split them and
    fail closed on the second reintroduces the first.

    That first case is no longer reachable from `main()` — the ledger file's
    existence is now the opt-in, so by the time the write path runs the file is
    there. It is stated rather than deleted because this function's contract is
    not "whatever main() happens to need": it is still the right answer for a
    caller that passes a path to a ledger that has yet to be created, and the
    reasoning above is what stops someone re-deriving the wrong fix later.
    `main()` does not use this wrapper any more; see `_already_recorded_fh`.

    Compared as a prefix in either direction, because `rev-parse --short` has no
    fixed width: git recomputes the abbreviation from the object count, so the
    sha stored as `abc1234` can come back as `abc12345` later in the same repo
    and an equality test would silently stop deduplicating.

    Two processes appending to one ledger can still both write: the read and the
    append are not atomic across processes. Worktrees each hold their own
    `cla.io/retro`, so this needs two sessions in one checkout.
    """
    try:
        with ledger.open("rb") as fh:
            return _already_recorded_fh(fh, sha)
    except OSError:
        return False


def _already_recorded_fh(fh, sha: str) -> bool:
    """`_already_recorded`'s body, against a handle the caller already holds.

    Split out so `main()` can read the tail and append through ONE handle, with
    nothing between the two. The path-taking wrapper above keeps its own
    contract — including swallowing OSError — because it is the form the unit
    tests exercise and the form that reads correctly standalone.

    Raises rather than swallows: the caller here is inside the append's own
    `try`, and a read failure there must take the same exit as a write failure
    rather than being silently read as "not recorded" and appending anyway.
    """
    fh.seek(0, os.SEEK_END)
    size = fh.tell()
    fh.seek(max(0, size - 4096))
    chunk = fh.read()
    lines = [line for line in chunk.splitlines() if line.strip()]
    if not lines:
        return False
    try:
        stored = json.loads(lines[-1].decode("utf-8")).get("sha")
    except (UnicodeDecodeError, ValueError, AttributeError):
        return False
    if not isinstance(stored, str) or not stored:
        return False
    return stored.startswith(sha) or sha.startswith(stored)


# A Bash call holds several commands, and every one of these ends one. The
# NEWLINE is the reason this exists as a constant: the earlier character class
# `[^|;&]` separated on the three operators and not on line breaks, so both the
# commit search and the history-reading exclusion ran straight across the lines
# of a multi-line call. A `git commit` on one line and a `git log` on the next
# then read as one command, and the commit went unrecorded — GitHub issue #206.
_SEGMENTS = re.compile(r"[|;&\n\r]+")

# A backslash before a line break is the shell's line continuation: the two
# physical lines are ONE command, and splitting there loses the commit. Joined
# before segmenting, after quoted spans are blanked so a backslash inside a
# quoted message cannot reach this.
_LINE_CONTINUATION = re.compile(r"\\[ \t]*\r?\n")

# A command begins with its program, optionally behind environment assignments
# (`GIT_AUTHOR_DATE=… git commit …`). Requiring that is what keeps PROSE out:
# `strip_quoted_spans` deliberately does not blank heredoc bodies, so a line of
# English mentioning git commit reaches this loop as its own segment. Before the
# split it was suppressed only by accident, because an unrelated `git log` on
# another line matched the whole-string exclusion.
_LEADS_WITH_GIT = re.compile(r"^\s*(?:[A-Za-z_]\w*=\S*\s+)*" + GIT_CMD + r"\b")

# `commit` must be git's SUBCOMMAND, reached only across git's own global options.
# The earlier test was `git.*\bcommit\b`, and `\b` treats a hyphen or a dot as a
# boundary, so any git command whose ARGUMENTS held the word read as a commit:
# `git add cla.io/retro/commit-provenance.jsonl` — the command that stages this
# very ledger — and `git diff -- src/commit.py` both matched. The reflog gate and
# the last-row dedupe usually hid it, until a `git stash push --
# cla.io/retro/commit-provenance.jsonl` removed the last row: the dedupe then had
# nothing to match, and the hook wrote a second row for a commit it had recorded.
#
# The options are the ones that may precede a subcommand (`git --help`): a flag
# taking a separate value (`-C <path>`, `-c <name>=<value>`, and the long forms
# that accept `--opt <value>`), or a self-contained flag. `(?![\w-])` keeps
# `commit-tree` and `commit-graph` out.
#
# A separate value never starts with `-`. Without that, `--git-dir --git-dir …`
# can be split two ways at every word, and a non-matching line of such options
# backtracks exponentially — about 1.6x per word, minutes at forty. A value may
# be a command substitution or carry escaped spaces, because
# `git -C $(git rev-parse --show-toplevel) commit` and `git -C my\ dir commit`
# are real commits the earlier whole-segment search recorded.
_GIT_OPTION_VALUE = r"(?!-)(?:\$\([^)]*\)|(?:\\\s|\S)+)"
_GIT_GLOBAL_OPTION = (
    r"(?:-[Cc]\s+" + _GIT_OPTION_VALUE
    + r"|--(?:git-dir|work-tree|namespace|exec-path|super-prefix|config-env)(?:=\S+|\s+" + _GIT_OPTION_VALUE + r")"
    + r"|--?[A-Za-z][\w-]*(?:=\S+)?)"
)
_COMMIT_SUBCOMMAND = re.compile(
    r"^\s*(?:[A-Za-z_]\w*=\S*\s+)*" + GIT_CMD + r"(?:\s+" + _GIT_GLOBAL_OPTION + r")*\s+commit(?![\w-])"
)


def _is_commit_command(command: str) -> bool:
    """True for a real `git commit`, false for anything that merely mentions it.

    Deliberately narrow. `git log --grep="git commit"`, a `--dry-run`, and any
    prose containing the words must not produce a ledger line; over-recording
    corrupts the very ratio this hook exists to report.

    Judged per segment, and that is the load-bearing part. Every test here is
    about ONE command, so a call holding several must be split before any of
    them is applied — otherwise a neighbouring command's `--dry-run` or `git
    log` suppresses a real commit sitting on another line. Under-recording is
    the mirror of the failure above and costs the same denominator: a commit
    with no row is indistinguishable from a commit that never happened.
    """
    # Blank out quoted spans first, the same way the git guard hooks do: without
    # it `echo 'run git commit later'` reads as a commit and writes a spurious
    # line — precisely the over-recording that corrupts this ledger.
    command = _LINE_CONTINUATION.sub(" ", strip_quoted_spans(command))
    for segment in _SEGMENTS.split(command):
        if not _LEADS_WITH_GIT.match(segment):
            continue
        if not _COMMIT_SUBCOMMAND.match(segment):
            continue
        if "--dry-run" in segment:
            continue
        # No separate history-command exclusion: `git log`, `git show` and
        # `git rev-list` name a different subcommand, so the match above already
        # rejects them. The exclusion that used to sit here searched the whole
        # segment, which dropped a real `git commit -F show.txt`.
        return True
    return False


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

    Scanned from the WHOLE message, not read as a git trailer, and that is the
    fix rather than the shortcut. Git recognises only the LAST contiguous block of
    `Key: value` lines as trailers. Attribution lines (`Co-Authored-By`,
    `Claude-Session`) are appended at the very end, so the moment a blank line
    separates the measurements from them — the natural way to write a long
    message — git's parser sees the attribution block and nothing else, and the
    commit records `measured_by_count: 0`.

    Measured on this repo when this was found: 35 of 184 ledger rows undercounted
    their own commit, and the adoption rate the ledger reported was 0.38 where the
    messages actually gave 0.61. The metric existed to answer whether the
    measurement rule is being followed, and it was answering a question about
    message formatting instead — an absence wearing a measurement's clothes, in
    the one field built to prevent exactly that.

    THE FIX DID NOT REACH THE ROWS ALREADY WRITTEN. A ledger carrying rows from
    before it holds zeros its own commit messages refute, and no later run
    corrects them — so a rate read off an old ledger is a statement about when
    the rows were written as much as about the rule.

    IF A REPO CORRECTS ITS OWN ROWS, apply `main()`'s shaping, not this
    function's return. What a row holds is not what this returns: `main()` caps
    the list at `_MAX_TRAILERS`, truncates each value to `_MAX_TRAILER_CHARS`,
    and then sheds values until the line fits `_MAX_LINE_BYTES`. Skipping that
    writes a row this hook could not have written.

    `_MAX_LINE_BYTES` is the one with a consequence past tidiness, and the
    consequence belongs to the WINDOW rather than to the cap.
    `_already_recorded_fh` reads a fixed tail and parses only the last line, so
    what truncates that line is a row longer than the window, at the end of the
    file — and then `json.loads` fails, the dedupe reads "not recorded", and a
    re-presented HEAD is appended twice. A row past the CAP but inside the window
    still parses. An earlier draft here said otherwise, overstating the failure
    by the factor between the two numbers.

    The relationship that has to hold is one row, not two, and it is about bytes
    ON DISK rather than the bytes the cap counts: `_MAX_LINE_BYTES` budgets
    `json.dumps(record) + "\n"`, one terminator byte, while a CRLF checkout
    stores two. So the window must be at least `_MAX_LINE_BYTES + 1` for a
    maximal row to survive a Windows clone. Today's values clear that by a wide
    margin, and the margin is an observation rather than a contract — nothing
    depends on the cap being half the window, and stating it as a guarantee
    would invite a guard that reds on a legitimate change.

    Record the correction beside the ledger, in the repo's own `cla.io/retro/`.
    A row that no writer could have produced is otherwise indistinguishable from
    one that was written that way, and the ledger is append-only by convention —
    a reader has no reason to suspect an edit unless one is written down.

    Continuations are folded the way `unfold=true` did: a following line that
    starts with whitespace belongs to the value above it, so a wrapped command is
    one value rather than two fragments.

    A commit with no such line yields an empty list, which is the honest reading:
    the rule says a change asserting no measurement writes none. The one thing
    this can over-count is a `Measured-by:` written at column 0 inside a fenced
    block in the body — accepted, because a message that quotes the form is
    vanishingly rarer than one that separates it with a blank line, and
    over-counting a stated measurement is the less damaging error.
    """
    raw = _git("log", "-1", "--format=%B", cwd=cwd)
    if not raw:
        return []
    values: list[str] = []
    # ADJACENCY is the whole of the continuation rule, and leaving it out is a
    # defect this function shipped with. Without it, `values[-1]` stayed the fold
    # target for the rest of the message, so ANY indented line below — a code
    # block, a quoted diff, an example — was welded onto the last measurement,
    # across blank lines and unrelated paragraphs. Measured on this repo: 5 of 56
    # commits carrying a trailer had a value corrupted that way, one by 1296
    # characters. `unfold=true`, which this replaced, folds only the line that
    # immediately continues the trailer.
    folding = False
    for line in raw.splitlines():
        if line.startswith(f"{_TRAILER_KEY}:"):
            value = line[len(_TRAILER_KEY) + 1:].strip()
            values.append(value)
            # A valueless `Measured-by:` starts nothing. Folding onto it
            # resurrected it from the empty-string filter below and recorded a
            # fabricated measurement for a commit that asserted none — inflating
            # the exact numerator `measurement_rate` is built on.
            folding = bool(value)
        elif folding and line[:1].isspace() and line.strip():
            values[-1] = f"{values[-1]} {line.strip()}"
        else:
            folding = False
    return [v for v in values if v]


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
    # rejecting hook) must not be recorded as one. Reading HEAD proves only that
    # a commit exists, never that THIS command made it, so the two checks below
    # carry that claim instead. Together they are the whole defence against
    # over-recording, which the docstring above calls worse than not existing.
    head = _git("rev-parse", "--short", "HEAD", cwd=cwd)
    subject = _git("log", "-1", "--pretty=%s", cwd=cwd)
    if not head or subject is None:
        return 0

    if not _head_moved_by_commit(cwd):
        return 0

    root = _git("rev-parse", "--show-toplevel", cwd=cwd)
    if not root:
        return 0
    ledger_dir = Path(os.environ.get("CLAUDE_RETRO_DIR") or (Path(root) / "cla.io" / "retro"))
    ledger = ledger_dir / _LEDGER_NAME

    # OPT-IN, DEFAULT OFF: the ledger FILE's existence is the consent, and this
    # hook never creates it. `touch cla.io/retro/commit-provenance.jsonl` turns
    # it on; deleting the file turns it off.
    #
    # This used to gate on the ledger DIRECTORY, which is the wrong granularity
    # and was reported as such (issue #219). The other two ledgers are written
    # once per skill run, by the skill, at a controlled moment. This one is
    # written by a PostToolUse hook on every commit, so it is the only one that
    # can land mid-merge and abort a `git checkout` — and a repo that wanted
    # `spec-to-pr-runs.jsonl` had to have `cla.io/retro/`, and therefore got this
    # one too, whether or not it would ever run `codify-retro`. One ledger's cost
    # profile was charged against another ledger's consent.
    #
    # Why file-presence rather than an env flag or a config key: it reuses the
    # convention the directory check already established, at the granularity the
    # report asked for, and it adds no file, no key, and no format. The state IS
    # the file, so "is this on?" is answered by `ls` rather than by knowing where
    # to look. `CLAUDE_RETRO_DIR` was the other candidate and is the wrong lever
    # — it says WHERE a ledger lives, not WHETHER this one is wanted, and
    # overloading it would conflate the two for all three ledgers at once.
    if not ledger.is_file():
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

    # THE DEDUPE READ AND THE APPEND SHARE ONE HANDLE, and the order matters more
    # than the handle does. This check used to sit before `_measured_by`, which
    # put THREE git subprocess calls between deciding "not yet recorded" and
    # acting on it — `log -1 --format=%B`, `log -1 --pretty=%cI`, and
    # `rev-parse --abbrev-ref`. Another process committing in that window wrote a
    # row this one had already decided was absent, and both rows landed.
    #
    # Narrowed, NOT closed. Two processes can still both read a tail that lacks
    # the sha and then both append; nothing here takes a lock, and the remaining
    # window is the handful of instructions between the read and the write rather
    # than three process spawns. A lock would close it and is not worth its price
    # here: it is platform-divergent code in a repo with no CI to exercise both
    # branches, guarding a duplicate row that costs one over-count in a
    # denominator. See `_already_recorded`'s last paragraph, which still stands.
    try:
        with ledger.open("a+b") as fh:
            if _already_recorded_fh(fh, head):
                return 0
            fh.write(line.encode("utf-8"))
    except OSError:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
