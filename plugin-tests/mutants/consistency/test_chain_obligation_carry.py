"""Mutation batch for test_chain_obligation_carry.py.

The guard reads prose across three files, so it carries the ordinary risk of a
prose-matching check: passing by finding a word while the hand-off it vouches for
has lost the property that made it work. Each mutant removes ONE property and
leaves the surrounding text intact, which is what a real rewrite would do.

Mutants 9-10 aim at the GUARD rather than an asset. Its structural properties —
the declared region set and the region-width cap — cannot be exercised from the
asset side while the tree is healthy, and both were live defects in the first
revision: a file-wide marker test passed with the whole Review block deleted, and
an unbounded region passed with its end anchor removed.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_chain_obligation_carry.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
SKILLS = PLUGIN / "skills"

SPEC_TO_PR = SKILLS / "spec-to-pr" / "SKILL.md"
MULTI_PR = SKILLS / "multi-pr" / "SKILL.md"
CHANGE_LOOP = SKILLS / "multi-pr" / "references" / "change-loop.md"
GUARD = DEV / "tests" / "consistency" / "test_chain_obligation_carry.py"

# Scoped to the ONE guard under test, never to `tests/consistency/` as a whole:
# a batch pointed at an area reports every mutant "killed" the moment anything
# else in that area is red, and proves nothing it claims to.
TARGETS = [GUARD]

MUTANTS = [
    (
        "the review verdict stops being settled by a command",
        SPEC_TO_PR,
        'Settle each verdict with one command rather than by reading: `grep -rl "<token>" openspec/changes/<change-name>/`.',
        "Settle each verdict by reading the change's artifacts and judging.",
        TARGETS,
    ),
    (
        "the required field stops being required — a missing line reads as a pass",
        SPEC_TO_PR,
        "**done is countable — one verdict line per `;`-separated entry, and a missing line is a failed round, not a pass.**",
        "cover the entries that seem relevant to this change.",
        TARGETS,
    ),
    (
        "a dropped obligation stops being a Critical finding",
        SPEC_TO_PR,
        "**`VIOLATED` and `NOT ADDRESSED` are each a Critical finding**",
        "`VIOLATED` and `NOT ADDRESSED` are each worth a note",
        TARGETS,
    ),
    (
        "the argument contract stops deriving the carry from the prerequisite's actual state",
        SPEC_TO_PR,
        "which by definition post-date this change's authoring — not from the batch as proposed",
        "which the chain plan already described up front",
        TARGETS,
    ),
    (
        "the flag is renamed on the producer side only",
        CHANGE_LOOP,
        '`Skill(cla:spec-to-pr, args="<name> --inherits \'<entry>; <entry>\'',
        '`Skill(cla:spec-to-pr, args="<name> --carries \'<entry>; <entry>\'',
        TARGETS,
    ),
    (
        "the read step stops naming the step that writes the rows",
        CHANGE_LOOP,
        "**This is the only place anything reads those rows back, and reading them back is the entire mechanism** — step 4a writes them,",
        "**This is where the rows are read back** — they are written earlier in the loop,",
        TARGETS,
    ),
    (
        "an empty carry stops being written down, so a resume cannot tell it from nobody looking",
        CHANGE_LOOP,
        "   - **Zero obligations is a real answer and is written down as `none`** beside this change's name, under the same heading.",
        "   - Zero obligations needs no entry; simply move on.",
        TARGETS,
    ),
    (
        "multi-pr's hoisted invariant loses the reason the record alone is not enough",
        MULTI_PR,
        "**A carry list written and then not fed into the dependent's own Review is indistinguishable from never having written it**",
        "**A carry list should be fed into the dependent's own Review**",
        TARGETS,
    ),
    (
        # The guard's own notion of the flag drifting away from both files it
        # checks — the parity assertion then vouches for a flag nobody passes.
        "the guard's carry-flag constant drifts from the files it guards",
        GUARD,
        '_CARRY_FLAG = "--inherits"',
        '_CARRY_FLAG = "--carries"',
        TARGETS,
    ),
    (
        # Without the cap, a region whose end anchor was deleted runs on into
        # neighbouring prose where the markers may live by coincidence.
        "the region cap widens until any slice satisfies it",
        GUARD,
        "_MAX_REGION = 4000",
        "_MAX_REGION = 1000000",
        TARGETS,
    ),
]

# Two properties are NOT mutated, deliberately, so "the batch is all-green" does
# not imply coverage this batch lacks.
#
# **The parity floor** (`len(flags) >= 5`) and **the per-file region-coverage
# floor**. Both defend against a state the tree is not in, so a mutation over
# healthy files cannot reach them. Measured: a throwaway batch relaxing
# `len(flags) >= 5` and `covered.count(path) >= sides` to `>= 0` and run through
# `python3 plugin-tests/mutate.py` reported 2 of 2 SURVIVED. They are
# covered structurally instead, by the `_INVOCATION`-stops-matching and
# one-region-dropped cases in `test_the_guard_notices_when_its_own_state_is_
# gutted` — the form `_shared/references/test-quality.md` prefers anyway, since a
# tamper test keeps holding after a later refactor turns the check into a no-op.
#
# **Deleting a whole region entry** is likewise not mutated: `mutate.py` anchors
# on a single line and a region entry spans several, so the drop cannot be
# expressed as a one-line substitution. Renaming its key — the one-line
# approximation — was tried and SURVIVED, correctly: a rename changes no file,
# no anchor and no marker, so nothing should notice. The real drop is exercised
# by the tamper case above.
