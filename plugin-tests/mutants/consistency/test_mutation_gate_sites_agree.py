"""Mutation batch for test_mutation_gate_sites_agree.py.

The guard claims that no site stating the mutation gate can drop the
killed-mutant clause without a test going red.

**Provenance.** Mutant 1 is historical in substance: it restores
`lite-pr/SKILL.md` to the state it was actually in before this change — stating
the gate with no killed-mutant clause — which is the exact tree issue #193
described while naming only the other site. Mutant 2 restores the same defect at
the other site. They are two mutants rather than one because that is what shows
the guard is per-file: a draft keyed on "SOME site carries the clause" passes
mutant 1 AND mutant 2, since in each the untouched site still carries it, and
only "EVERY site carries it" kills both. Mutants 3 and 4 target the guard's own
constants, both places a weaker draft was available and tempting.

**Anchors stay inside one line, deliberately.** `.gitattributes` pins no `eol`
for `.md` or `.py`, so with `core.autocrlf=true` these targets are on disk with
CRLF — measured on this tree, `lite-pr/SKILL.md` has CR=194 and LF=194 (`python`
over `read_bytes()`). `mutate.py` matches anchors against the decoded bytes, so a
bare `\\n` in an anchor matches nothing, and its preflight then aborts the WHOLE
batch rather than that one mutant. An earlier draft of this file spanned three
lines that way and cost both gates: the batch mutated nothing and
`test_guards_have_mutant_batches.py::_unresolvable_anchors` failed the
consistency area.

**Why no mutant lowers `_KNOWN_SITE_COUNT`.** It could not be killed. Two sites
really do state the gate, so `2 >= 0` and `2 >= 1` hold exactly as `2 >= 2` does
and the mutant would SURVIVE for a reason no code change fixes — the unkillable
floor `CLAUDE.md` says to record rather than install. What the floor really
defends is reached from the other side by mutant 4: make `_GATE_ANCHOR`
unmatchable and the discovery set empties, at which point the parametrized test
has nothing to run and passes vacuously, and the floor is the only assertion left
that fires.

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
MULTI_LITE_LOOP = PLUGIN / "skills" / "multi-lite" / "references" / "candidate-loop.md"

# Scoped to the ONE guard file: a target red for any other reason reports every
# mutant "killed" and proves nothing.
TARGETS = [GUARD]

# Every site states the clause on one line, so it can be removed without an anchor
# that crosses a line ending. Occurs exactly once in each of the three sites
# (lite-pr, revise.md, multi-lite's candidate-loop.md) and nowhere else in the
# shipped tree: `grep -rn "<this phrase>" .claude/plugins/cla` lists those three.
_CLAUSE_LINE = "read the assertion that killed the mutant and confirm it states the"
_CLAUSE_DROPPED = "confirm the test states the"

MUTANTS = [
    (
        # The tree as it actually stood before this change: the gate stated at
        # both sites, the clause at neither, and issue #193 naming only one.
        "the lite-pr site states the gate without the killed-mutant clause",
        LITE_PR,
        _CLAUSE_LINE,
        _CLAUSE_DROPPED,
        TARGETS,
    ),
    (
        # The same defect at the other site. Separate from mutant 1 on purpose:
        # see "Provenance" above on what the pair shows that either alone cannot.
        "the revise.md site states the gate without the killed-mutant clause",
        REVISE,
        _CLAUSE_LINE,
        _CLAUSE_DROPPED,
        TARGETS,
    ),
    (
        # The third site, added by multi-lite's step 7 enforcement round. It
        # shipped once without the clause, and this guard caught it.
        "the multi-lite site states the gate without the killed-mutant clause",
        MULTI_LITE_LOOP,
        _CLAUSE_LINE,
        _CLAUSE_DROPPED,
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
        # The anchor made unmatchable. Discovery returns nothing, the
        # parametrized test collects no cases and cannot fail, and the floor is
        # the one assertion left to notice — the direction in which the floor IS
        # killable, which is why no mutant here lowers it instead.
        "an unreachable anchor empties the discovery set",
        GUARD,
        '_GATE_ANCHOR = "confirm it FAILS"',
        '_GATE_ANCHOR = "confirm it FAILS SOMEDAY"',
        TARGETS,
    ),
]
