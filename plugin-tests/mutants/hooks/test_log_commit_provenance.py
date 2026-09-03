"""Mutant batch for `tests/hooks/test_log_commit_provenance.py`.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/hooks/test_log_commit_provenance.py

The hook exists to supply a denominator the retro loops have never had, and its
whole value is in NOT lying about that denominator: no row for a command that
did not commit, no split row for one that did, no fragment where a trailer was
one value. Two of the entries below re-create real regressions this hook has
already shipped and had fixed by hand, with no mutant proving the fix stays
fixed:

  * `05355ff` — main() wrote a provenance row for ANY commit-shaped Bash call,
    regardless of whether that call was what moved HEAD. A `git commit` run
    right after a `git checkout` re-recorded the checked-out commit under the
    wrong provenance. `_head_moved_by_commit` is the gate that rejects it.
  * `e805870` — `_is_commit_command` judged a whole multi-line Bash call as one
    string, so a `git commit` on one line beside a `git log` on the next read
    as a single command the history-reading exclusion then suppressed, and the
    commit went unrecorded (issue #206). `_SEGMENTS` including `\\n`/`\\r` is
    what splits the call before judging it.

The rest cover capabilities beyond those two fixes: how a `Measured-by:`
trailer is parsed off HEAD, the shape of the row written under the line-size
ceiling, a negative case that must never produce a row, the dedupe's tolerance
for a re-abbreviated sha, and the line-continuation join `e805870`'s second
round added alongside the newline split.

Every anchor here is a single physical line — this repo's checkout is CRLF and
the hook is not one of the `eol=lf` launchers, so a bare `\\n` inside an anchor
would match nothing (see `mutate.py`'s own docstring, "KEEP \\n OUT OF AN
ANCHOR"). Paths resolve from this file's own location: an absolute developer
path would work on one machine and leak a repo name into synced core.
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
HOOK = PLUGIN / "hooks" / "log-commit-provenance.py"
TARGETS = [DEV / "tests" / "hooks" / "test_log_commit_provenance.py"]

MUTANTS = [
    (
        # Gate from 05355ff (#204): a provenance row must land only when THIS
        # command is what moved HEAD, not whenever HEAD happens to name a real
        # commit. Neutering the call site — rather than the function body —
        # reproduces exactly the regression that shipped: a `git commit` run
        # right after a checkout/merge/reset re-records the commit that was
        # already there under the wrong provenance.
        "the head-moved-by-commit gate stops being consulted in main(), so a "
        "commit-shaped command re-records whatever HEAD already points at "
        "after a checkout, merge, or reset",
        HOOK,
        "if not _head_moved_by_commit(cwd):",
        "if False and not _head_moved_by_commit(cwd):",
        TARGETS,
    ),
    (
        # Gate from e805870 (#206), round 1: without the newline/CR in the
        # separator class, a multi-line Bash call is judged as ONE string, so a
        # `git commit` on one line beside a `git log` on the next reads as a
        # single command the history-reading exclusion then suppresses — the
        # exact defect issue #206 reported.
        "the segment splitter stops treating a line break as ending a "
        "command, so a git commit sharing a Bash call with a git log/show/"
        "rev-list on another line is dropped again",
        HOOK,
        '_SEGMENTS = re.compile(r"[|;&\\n\\r]+")',
        '_SEGMENTS = re.compile(r"[|;&]+")',
        TARGETS,
    ),
    (
        # Gate from e805870 (#206), round 2: a backslash before a line break is
        # the shell's line continuation, so `git \` / `commit -m 'x'` is ONE
        # command. Without joining it first, the segmenter cuts it into two
        # halves that neither look like a full commit, silently dropping the
        # row exactly as the pre-round-2 code did.
        "the line-continuation join is skipped, so a backslash-continued "
        "git commit is split into two non-commit segments and produces no row",
        HOOK,
        'command = _LINE_CONTINUATION.sub(" ", strip_quoted_spans(command))',
        "command = strip_quoted_spans(command)",
        TARGETS,
    ),
    (
        # `Measured-by:` trailer parsing. `unfold=true` joins a trailer that
        # git wrapped across lines back into the one value it is; dropping it
        # makes a single wrapped claim come back as two separate lines, which
        # both mis-reports the value and inflates measured_by_count.
        "the Measured-by trailer format drops unfold=true, so a wrapped "
        "trailer is read back as two fragments instead of the one value it is",
        HOOK,
        'f"--pretty=%(trailers:key={_TRAILER_KEY},valueonly=true,unfold=true)",',
        'f"--pretty=%(trailers:key={_TRAILER_KEY},valueonly=true)",',
        TARGETS,
    ),
    # DROPPED, not forgotten: "the trailer-shedding loop rewrites
    # measured_by_count to match the shortened list". It targeted a real
    # invariant — the ceiling must cost DETAIL, never the adoption number — and
    # it SURVIVED, because the loop it mutates cannot execute under the current
    # caps. Every contributing field is bounded (`subject[:120]`, 10 values of
    # 160 chars), leaving only the branch name, and reaching the 2048 ceiling
    # needs ~250 characters of branch, which git refuses to create.
    #
    # Measured: a realistic record is 1801 bytes. Monkeypatching the ceiling does
    # not help — the hook runs as a separate process and reads the shipped
    # constant.
    #
    # An unkillable mutant is worse than a missing one: a survivor nobody can act
    # on trains the next reader to skip the whole list. Same disposition as the
    # `_MIN_MARKED_LINES` floor constant CLAUDE.md records. The gap it found is
    # kept as `test_the_shedding_loop_is_unreachable_under_the_current_caps`,
    # which fails if the caps ever rise far enough to make the loop live.
    (
        # Negative case: a command that must NEVER produce a row. Disabling the
        # --dry-run exclusion makes `git commit --dry-run` (which commits
        # nothing) register as a real commit, over-recording exactly the way
        # the hook's own docstring calls worse than under-recording.
        "the --dry-run exclusion is disabled, so `git commit --dry-run` is "
        "recorded as though it were a real commit",
        HOOK,
        'if "--dry-run" in segment:',
        'if False and "--dry-run" in segment:',
        TARGETS,
    ),
    (
        # The dedupe's sha-width tolerance. `rev-parse --short` has no fixed
        # width, so a sha stored at one abbreviation can come back wider later
        # in the same repo; comparing for exact equality stops matching at
        # exactly that point and lets a repeated command duplicate a row.
        "the dedupe compares stored and current sha for exact equality, so a "
        "re-abbreviated sha no longer matches its own earlier prefix and the "
        "same commit is recorded twice",
        HOOK,
        "return stored.startswith(sha) or sha.startswith(stored)",
        "return stored == sha",
        TARGETS,
    ),
]
