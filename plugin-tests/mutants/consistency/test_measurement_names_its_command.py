"""Mutation batch for test_measurement_names_its_command.py.

The guard reads prose, so it carries the ordinary risk of a prose-matching
check: passing because a phrase is still somewhere in the file while the rule it
vouches for has lost the property that made it work. Each asset mutant removes
ONE property and leaves the surrounding text intact, which is what a real rewrite
would do.

Mutants 4-6 aim at the GUARD instead. Its structural constants — the declared
family, the window cap, the trailer token — cannot be exercised from the asset
side at all, and each is exactly the shape that made the sibling turn-liveness
guard vacuous in an earlier revision (an emptied family, an unbounded span).

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_measurement_names_its_command.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
SKILLS = PLUGIN / "skills"
GUARD = DEV / "tests" / "consistency" / "test_measurement_names_its_command.py"

# Scoped to the ONE guard under test, never to `tests/consistency/` as a whole:
# a batch pointed at an area reports every mutant "killed" the moment anything
# else in that area is red, and proves nothing it claims to.
TARGETS = [GUARD]

MUTANTS = [
    (
        "lite-pr's trailer stops requiring a runnable command",
        SKILLS / "lite-pr" / "SKILL.md",
        "Measured-by: <the exact command, runnable as written> — <the claim it produced>",
        "Measured-by: <what was measured> — <the claim it produced>",
        TARGETS,
    ),
    (
        "spec-to-pr's Ship bullet softens the two exits into a note",
        SKILLS / "spec-to-pr" / "SKILL.md",
        "**run the command now, or delete the claim**",
        "**flag the claim as unverified**",
        TARGETS,
    ),
    (
        "ship.md permits the null certification it exists to forbid",
        SKILLS / "spec-to-pr" / "references" / "ship.md",
        "never `Measured-by: none`",
        "otherwise `Measured-by: none`",
        TARGETS,
    ),
    (
        # A call site dropping out of the declared family must fail via the
        # tripwire, not pass by checking one fewer file.
        #
        # Anchored WITHIN one line. A first cut spanned the line ending
        # (`'    "lite-pr/SKILL.md",\n'`) and aborted the whole batch on a CRLF
        # checkout — `mutate.py`'s preflight rejects a bare `\n` in an anchor,
        # and it fails the batch rather than the mutant, so the run reported
        # nothing mutated at all. Leaving the indent behind is harmless: a blank
        # line inside the tuple still drops the entry.
        "a call site silently drops out of the declared family",
        GUARD,
        '"lite-pr/SKILL.md",',
        "",
        TARGETS,
    ),
    (
        # Without the cap, three markers scattered across an unrelated region
        # satisfy "stated together as one rule".
        "the adjacency window widens until any region satisfies it",
        GUARD,
        "_MAX_WINDOW = 1000",
        "_MAX_WINDOW = 100000",
        TARGETS,
    ),
    (
        # The hyphen is load-bearing: bare `Measured:` is already narrative prose
        # in four shipped files, so the tripwire and `git log --grep` both
        # collide with it.
        "the trailer token loses its hyphen and collides with narrative prose",
        GUARD,
        '_TRAILER = "measured-by:"',
        '_TRAILER = "measured:"',
        TARGETS,
    ),
    (
        # Revise's fix-round commit is the highest-frequency chokepoint and was
        # missing from the first cut of this change: the skill ASSERTED the rule
        # covered `fix:` commits while the only binding statement sat ~38k chars
        # away in another file — the loads-early-claim-written-later shape this
        # whole change rejects.
        "Revise's fix-round commit loses the two exits",
        SKILLS / "spec-to-pr" / "references" / "revise.md",
        "**run the command now, or delete the claim**",
        "**note the claim as unverified**",
        TARGETS,
    ),
    (
        # Without a commit action on the far side, a rule block parked after a
        # trailing reference-list mention of the pre-commit check clears both the
        # window cap and the gap bound. A reviewer moved the block to EOF exactly
        # this way and it passed.
        "the far side of the chokepoint sandwich is removed",
        GUARD,
        '_COMMIT_ACTIONS = ("git commit", "commit-push-pr")',
        "_COMMIT_ACTIONS = ()",
        TARGETS,
    ),
    (
        # An unbounded gap accepts any position after the first mention of the
        # check — measured at roughly 40% of `lite-pr/SKILL.md`.
        "the chokepoint gap widens until anything downstream counts as at it",
        GUARD,
        "_MAX_CHOKEPOINT_GAP = 2600",
        "_MAX_CHOKEPOINT_GAP = 1000000",
        TARGETS,
    ),
    (
        # Issue #208's clause, asset side. The softening below is the shape a
        # real rewrite takes: it still mentions one tree, so a grep for
        # "one tree" would pass, but the obligation has become a preference and
        # the pair can ship measured on two trees again.
        "lite-pr's comparison clause softens into a preference",
        SKILLS / "lite-pr" / "SKILL.md",
        "must come from one tree",
        "should ideally be from one tree",
        TARGETS,
    ),
    (
        # ...and guard side, aimed at the way this particular check goes
        # vacuous. `_SAME_TREE` feeds a substring test over prose that discusses
        # trees constantly, so weakening the phrase does not fail — it passes
        # against text stating no such rule. That is why the constant is pinned
        # to its exact value rather than merely asserted non-empty.
        "the comparison clause's phrase weakens until any prose satisfies it",
        GUARD,
        '_SAME_TREE = "must come from one tree"',
        '_SAME_TREE = "tree"',
        TARGETS,
    ),
]

# One property is NOT mutated, deliberately, so that "the batch is all-green"
# does not imply coverage this batch lacks.
#
# **The chokepoint anchor's position test.** Moving the rule ABOVE the
# `git_state.py` mention cannot be expressed as a one-substring swap — it is a
# relocation, not an edit. It is covered structurally instead, by
# `test_the_chokepoint_anchor_is_load_bearing`, which feeds `_why_not` both
# orderings and asserts it separates them. That is the form
# `_shared/references/test-quality.md` prefers anyway, since a tamper test keeps
# holding after a later refactor turns the check into a no-op.
