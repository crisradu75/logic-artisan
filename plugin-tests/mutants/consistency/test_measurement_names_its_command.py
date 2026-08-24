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
        "a call site silently drops out of the declared family",
        GUARD,
        '    "lite-pr/SKILL.md",\n',
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
