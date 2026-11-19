"""Mutant batch for `tests/hooks/test_pre_push.py`.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/hooks/test_pre_push.py

`hooks/git/pre-push` is the ONLY thing enforcing "no direct push to main/master"
in this repo (CLAUDE.md: "Merging is unguarded. Your local run before opening a
PR is the only gate." — pre-push is the analogous statement for
pushing). It replaced a 491-line PreToolUse hook that parsed the `git push`
command string and lost to every spelling variant; the whole point of the
replacement is that git hands it the RESOLVED refspec, so there is no command
shape left to get wrong — only the ref-matching logic inside the hook itself.
These mutants re-break that logic, one capability at a time: which branches are
protected, how the refspec fields are parsed, the escape hatch, and the
negative case (an ordinary feature-branch push must still go through).

The hook is a POSIX `sh` script pinned to `eol=lf` by `.gitattributes` (checked
directly: `b"\\r\\n" not in pre-push.read_bytes()`), unlike the CRLF `.py` files
elsewhere in this repo. Every anchor below is confined to a single line, so the
line-ending question never bites regardless.

Paths resolve from this file's own location, never an absolute developer path.

TAG MUTANTS (the last eleven). The hook also refuses a push that deletes a tag on
the remote or moves one the remote has, under its own `ALLOW_TAG_REWRITE=1`
override. Each mutant below breaks one input of that decision: which refs count
as tags, the zero test, the delete and move conditions, the no-change branch,
and the separation of the two overrides.

COUNT NOTE (first seven mutants): 7 MUTANTS ARE NOT 7 INDEPENDENT PIECES OF EVIDENCE. Review measured
that mutant 3 (refspec field scramble) dies on the same single assertion as
mutant 2 (drop `main` from the case arm), because scrambling the fields breaks
main and master together — its effect is the union of 1 and 2, and nothing in the
guard separates "field order wrong" from "both branch names dropped". Mutants 1,
5 and 6 (master-only, catch-all, substring) ARE distinguishable. Read a clean run
as 6 distinct capabilities.

PLATFORM NOTE, because a skip reads as a SURVIVED verdict. This guard carries
`pytestmark = pytest.mark.skipif(_SH is None, ...)`: with no POSIX `sh` on PATH
the whole module skips, pytest exits 0, and `mutate.py` reports every mutant
here as SURVIVED. That is a report about the machine, not about the batch --
check for an `s` in the pytest line before treating a survivor as a finding.
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]  # <repo>/plugin-tests
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
HOOK = PLUGIN / "hooks" / "git" / "pre-push"
TARGETS = [DEV / "tests" / "hooks" / "test_pre_push.py"]

MUTANTS = [
    (
        # Capability: "master" is one of the two protected branch names. If the
        # case arm loses it, a direct push to master — a real default-branch
        # name on plenty of repos — goes straight through, silently defeating
        # half the guard's stated job.
        "the protected-branch match drops 'master', letting a direct push to it through",
        HOOK,
        'refs/heads/main|refs/heads/master)',
        'refs/heads/main)',
        TARGETS,
    ),
    (
        # Capability: same as above for "main" — the repo's actual default
        # branch (see git status: "Main branch ... main"). Losing this arm
        # would let the exact push this hook exists to stop go straight to
        # origin/main.
        "the protected-branch match drops 'main', letting a direct push to it through",
        HOOK,
        'refs/heads/main|refs/heads/master)',
        'refs/heads/master)',
        TARGETS,
    ),
    (
        # Capability: the refspec parsing git hands the hook on stdin
        # (`<local ref> <local sha> <remote ref> <remote sha>`). Swapping which
        # field lands in `remote_ref` (here: field 2, the local sha, instead of
        # field 3, the actual remote ref) means the case statement is now
        # matching a SHA against `refs/heads/main`, which never matches — so
        # nothing is ever refused, on any ref, including main itself. This is
        # exactly the class of bug a `pre-push` hook is supposed to make
        # impossible by construction; getting the field order wrong reopens it.
        "the refspec field order is scrambled, so remote_ref never holds the actual ref",
        HOOK,
        'while read -r _local_ref local_sha remote_ref remote_sha; do',
        'while read -r _local_ref remote_ref local_sha remote_sha; do',
        TARGETS,
    ),
    (
        # Capability: the escape hatch (`ALLOW_PUSH_TO_MAIN=1`) must require
        # the exact value "1", not merely a non-empty value. The hook's own
        # comment spells the override as "=1"; a looser check means an
        # accidental `ALLOW_PUSH_TO_MAIN=0` (e.g. a stray env var left set to
        # "false" as 0) silently disarms the one guard standing between a
        # session and a push to main.
        "the escape hatch disarms on ANY non-empty value, not just '1'",
        HOOK,
        '[ "${ALLOW_PUSH_TO_MAIN:-}" = "1" ] && continue',
        '[ -n "${ALLOW_PUSH_TO_MAIN:-}" ] && continue',
        TARGETS,
    ),
    (
        # Negative case: an ordinary feature-branch push must be allowed
        # through untouched — that is the hook's other half, not just refusing
        # main. Widening the case pattern to a catch-all re-creates the failure
        # mode of an overzealous rewrite that blocks every push, which would
        # make the hook useless (and would be noticed immediately, but the
        # guard should be the thing that notices it, not a human hitting it).
        "the case pattern is widened to match every ref, blocking feature pushes too",
        HOOK,
        'refs/heads/main|refs/heads/master)',
        '*)',
        TARGETS,
    ),
    (
        # Capability: the match must be an EXACT ref comparison, not a
        # substring/prefix one. `refs/heads/maintenance` legitimately contains
        # "refs/heads/main" as a prefix; a sloppy case pattern
        # (`*refs/heads/main*`) would wrongly refuse that unrelated branch.
        # This is the real-world shape of bug the hook's own case syntax is
        # supposed to avoid by matching the whole ref, not a fragment of it.
        "the exact-ref match becomes a substring match, catching unrelated branches",
        HOOK,
        'refs/heads/main|refs/heads/master)',
        '*refs/heads/main*|*refs/heads/master*)',
        TARGETS,
    ),
    (
        # Capability: a branch DELETION (all-zero local sha, same remote ref)
        # must be refused exactly like an update — the hook's own comment says
        # so explicitly ("so deleting the default branch is refused by the
        # same case below"). A plausible "fix" that skips processing when
        # nothing is really being pushed (local sha is all zero) would silently
        # let `git push origin :main` through and delete the default branch.
        "lines with an all-zero local sha (a branch deletion) are skipped entirely",
        HOOK,
        '[ -n "$remote_ref" ] || continue',
        '[ -n "$remote_ref" ] && ! is_zero "$local_sha" || continue',
        TARGETS,
    ),
    # ---------------------------------------------------------------- tags
    (
        # A delete arrives with an all-zero local sha. Without this condition
        # a delete still trips the move test below (remote sha set, differs),
        # so the refusal survives but names the wrong act; the tests pin the
        # message, which is what the user reads to know what was refused.
        "the delete test is dropped, so a tag delete is reported as a move",
        HOOK,
        'if is_zero "$local_sha"; then',
        'if false; then',
        TARGETS,
    ),
    (
        # Dropping the remote-is-zero condition refuses every NEW tag: the
        # release flow's own tag push would be refused.
        "the move test forgets that an all-zero remote sha is a new tag",
        HOOK,
        'elif ! is_zero "$remote_sha" && [ "$remote_sha" != "$local_sha" ]; then',
        'elif [ "$remote_sha" != "$local_sha" ]; then',
        TARGETS,
    ),
    (
        # Dropping the inequality refuses a push of a tag the remote already
        # holds at the same object, which is not a move.
        "the move test forgets to compare the two shas",
        HOOK,
        'elif ! is_zero "$remote_sha" && [ "$remote_sha" != "$local_sha" ]; then',
        'elif ! is_zero "$remote_sha"; then',
        TARGETS,
    ),
    (
        "the move test is dropped, so a forced tag move goes through",
        HOOK,
        'elif ! is_zero "$remote_sha" && [ "$remote_sha" != "$local_sha" ]; then',
        'elif false; then',
        TARGETS,
    ),
    (
        # The no-change branch skips the refusal. Turned into a branch that is
        # never taken, every tag push (creation included) falls into it.
        "the no-change branch falls through to the refusal",
        HOOK,
        '            else',
        '            elif false; then',
        TARGETS,
    ),
    (
        "the tag override disarms on ANY non-empty value, not just '1'",
        HOOK,
        '[ "${ALLOW_TAG_REWRITE:-}" = "1" ] && continue',
        '[ -n "${ALLOW_TAG_REWRITE:-}" ] && continue',
        TARGETS,
    ),
    (
        # Each override lifts only its own refusal: the default-branch hatch
        # must not also let a tag be deleted.
        "the tag arm honours the default-branch override instead of its own",
        HOOK,
        '[ "${ALLOW_TAG_REWRITE:-}" = "1" ] && continue',
        '[ "${ALLOW_PUSH_TO_MAIN:-}" = "1" ] && continue',
        TARGETS,
    ),
    (
        # The old shape: `ALLOW_PUSH_TO_MAIN=1` exited before reading any line,
        # which would lift the tag refusal too.
        "the default-branch override exits before any ref is read",
        HOOK,
        'status=0',
        '[ "${ALLOW_PUSH_TO_MAIN:-}" = "1" ] && exit 0; status=0',
        TARGETS,
    ),
    (
        # The hook ships to every consuming repo, so it covers any tag name, not
        # only this repo's release-tag shape.
        "the tag arm narrows to tags starting with 'v'",
        HOOK,
        'refs/tags/*)',
        'refs/tags/v*)',
        TARGETS,
    ),
    (
        # Only `refs/tags/*` is a tag; a branch named `tags/x` stays a branch.
        "the tag arm widens to any ref with a 'tags' segment",
        HOOK,
        'refs/tags/*)',
        '*/tags/*)',
        TARGETS,
    ),
    (
        # A SHA-256 repository writes 64 zeros for "no object".
        "the zero test reads a 64-digit all-zero sha as an object",
        HOOK,
        '*[!0]*) return 1 ;;',
        '*[!0]*|????????????????????????????????????????????????????????????????) return 1 ;;',
        TARGETS,
    ),
]
