"""Mutation batch for the release-precondition guard — break each guarantee, confirm a test fails.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/release/test_release_preconditions.py

This guard has no code of its own to mutate: it reads two DOCUMENTS —
`CLAUDE.md`'s "Before opening a PR" row and `.claude/skills/release/SKILL.md`'s
Step 1 block — and asserts they agree. So the mutants break the documents, which
is the real failure this guard exists to catch: the two drifting apart.

It was itself shipped without a batch by the very review round that added it, and
the meta-guard could not see that: `_guard_files()` was still globbing
`tests/<area>` while this guard lives at `tests/skills/release/`. Both halves are
fixed; this batch is the evidence that the guard can fail.

ANCHORING NOTES, both learned by the preflight refusing.

1. The two gate commands appear THREE times each in `SKILL.md` — the precondition
   table, Step 1's runnable block, and Step 3's re-run block — so a bare command
   anchor is ambiguous and `mutate.py` refuses it. That ambiguity is not
   incidental: it is the same repetition that let the guard be satisfied by the
   table describing the gate rather than by the gate itself. Mutant 1 therefore
   carries the preceding `git status -sb` line, which occurs only in Step 1.
2. `mutate.py` reads `read_bytes().decode()`, so line endings survive verbatim
   and a hardcoded `\\n` will not match this repo's CRLF checkout. The separator
   is read off the file rather than assumed, so the batch works on either — and
   a wrong guess would fail the preflight loudly rather than silently checking
   nothing, which is the failure mode this whole file exists to prevent.
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
REPO = DEV.parent
SKILL = REPO / ".claude" / "skills" / "release" / "SKILL.md"
CLAUDE_MD = REPO / "CLAUDE.md"

TARGETS = [DEV / "tests" / "skills" / "release" / "test_release_preconditions.py"]

_NL = "\r\n" if b"\r\n" in SKILL.read_bytes() else "\n"

MUTANTS = [
    (
        # The exact drop round 1 found: the release gate stopped covering the
        # Node suite when `run_tests.py` was deleted, so a shipped `.mjs` could
        # ship broken behind a fully green precondition list.
        "the Node suite is dropped from Step 1's runnable preconditions",
        SKILL,
        _NL.join(
            [
                "git status -sb",
                "pytest plugin-tests -q -n auto --dist loadfile",
                "node --test plugin-tests/node/mechanical-checks.test.mjs",
            ]
        ),
        _NL.join(["git status -sb", "pytest plugin-tests -q -n auto --dist loadfile"]),
        TARGETS,
    ),
    (
        # The guard derives the gate from CLAUDE.md rather than hardcoding it.
        # If the row stops yielding commands the derivation is empty, and every
        # later assertion is then trivially satisfied — the guard passes having
        # checked nothing, the shape this repo keeps shipping.
        "CLAUDE.md's gate row can no longer be found, so nothing is derived",
        CLAUDE_MD,
        "| Before opening a PR |",
        "| Before opening a PR (see above) |",
        TARGETS,
    ),
    (
        # The Step 1 slice is bounded by the `## Step 2` heading. Rename it and
        # the slice runs to end of file, swallowing Step 3's re-run block, which
        # repeats these same commands — so Step 1 could lose one entirely and
        # the guard would still find both strings somewhere in the slice.
        "the Step 2 heading is renamed, so the Step 1 slice runs to end of file",
        SKILL,
        "## Step 2 — Choose the version",
        "## Stage 2 — Choose the version",
        TARGETS,
    ),
    (
        # The one rule in this skill whose breach cannot be undone: a published
        # tag consumers have already fetched.
        "the never-move-a-published-tag invariant is dropped from the skill",
        SKILL,
        "**A published tag is never moved.**",
        "**A published tag may be moved when convenient.**",
        TARGETS,
    ),
]
