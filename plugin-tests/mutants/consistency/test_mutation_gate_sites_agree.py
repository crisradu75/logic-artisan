"""Mutation batch for test_mutation_gate_sites_agree.py.

The guard claims that no site stating the mutation gate can drop the
killed-mutant clause without a test going red.

**Provenance.** Mutant 1 is historical in substance: it restores
`lite-pr/SKILL.md` to the state it was actually in before this change — stating
the gate with no killed-mutant clause — which is the exact tree issue #193
described while naming only the other site. Mutants 2 and 3 restore the same
defect at the other site and at both at once, because a guard that only ever
sees one file drift is not shown to be per-file. Mutants 4 and 5 target the
guard's own constants, both places a weaker draft was available and tempting.

**Why a mutant on the floor is here and the usual objection does not apply.**
`CLAUDE.md` warns that a floor constant is commonly unkillable — it only binds
when something is missing, so mutating it on a correct tree is a no-op. That is
true of a floor *raised* above its population, which is why mutant 5 LOWERS it
to zero and pairs the lowering with the deletion that makes it bite. Zero alone
survives; zero plus an emptied discovery set is what the non-vacuity test exists
to catch, and it dies.

**One weakness is deliberately NOT a mutant, with the reason.** Replacing
`_REQUIRED_CLAUSE` with a bare `"killed"` is the weaker presence check the guard's
docstring argues against. It cannot be shown to fail here: every site currently
carries the full clause, so the loose pattern and the strict one agree on this
tree, and expressing the difference needs a site rewritten to mention killing
without instructing the read — two coordinated edits, which this batch format
does not carry. Recorded rather than installed, because a survivor nobody can act
on trains the next reader to skip the list.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_mutation_gate_sites_agree.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"

GUARD = DEV / "tests" / "consistency" / "test_mutation_gate_sites_agree.py"
LITE_PR = PLUGIN / "skills" / "lite-pr" / "SKILL.md"
REVISE = PLUGIN / "skills" / "spec-to-pr" / "references" / "revise.md"

# Scoped to the ONE guard file: a target red for any other reason reports every
# mutant "killed" and proves nothing.
TARGETS = [GUARD]

_CLAUSE = (
    "**A test that DOES fail is\n"
    "   not thereby correct: read the assertion that killed the mutant and confirm it states the\n"
    "   behaviour you want.** "
)

MUTANTS = [
    (
        # The tree as it actually stood before this change: the gate stated at
        # both sites, the clause at neither, and issue #193 naming only one.
        "the lite-pr site states the gate without the killed-mutant clause",
        LITE_PR,
        _CLAUSE,
        "",
        TARGETS,
    ),
    (
        "the revise.md site states the gate without the killed-mutant clause",
        REVISE,
        _CLAUSE,
        "",
        TARGETS,
    ),
    (
        # Both at once. A guard keyed on "any site carries it" rather than
        # "every site carries it" passes mutants 1 and 2 and fails only here.
        "the clause is dropped from every site at once",
        LITE_PR,
        "read the assertion that killed the mutant",
        "read the assertion that killed it",
        TARGETS,
    ),
    (
        # The presence-check draft, in the direction that CAN be shown: matching
        # a phrase that no site carries proves the assertion is really read
        # rather than trivially satisfied.
        "the required clause is matched by a phrase no site states",
        GUARD,
        '_REQUIRED_CLAUSE = "read the assertion that killed the mutant"',
        '_REQUIRED_CLAUSE = "read the assertion that slew the mutant"',
        TARGETS,
    ),
    (
        # The floor lowered to zero AND the discovery set emptied. Either alone
        # is a no-op on a correct tree; together they are the vacuous-guard
        # shape the non-vacuity test exists to catch.
        "an unreachable anchor empties the discovery set",
        GUARD,
        '_GATE_ANCHOR = "confirm it FAILS"',
        '_GATE_ANCHOR = "confirm it FAILS SOMEDAY"',
        TARGETS,
    ),
]
