"""Mutation batch for test_chain_obligation_carry.py.

The guard reads prose across four files, so it carries the ordinary risk of a
prose-matching check: passing by finding a word while the hand-off it vouches for
has lost the property that made it work. Each mutant removes ONE property and
leaves the surrounding text intact, which is what a real rewrite would do.

Mutants 18-21 aim at the GUARD rather than an asset. Its structural properties —
the flag constant, the region-width cap, the parity floor and the per-file
coverage floor — cannot be exercised from the asset side while the tree is
healthy. The two floors are mutable only because the guard now carries tamper
tests that put the tree INTO the state each floor exists for; an earlier revision
claimed they were "covered structurally" by the gutting cases, and a reviewer
measured that false (each gutting case trips an earlier assertion and never
reaches the floor).

Mutant 11 is the C3 regression: the report template migrating back into the
orchestrator, where the three dispatched review agents never read it. Mutant 13
is the C1 regression: the read scoped to this run's dated notes file, which hides
every obligation an earlier session recorded.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_chain_obligation_carry.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
SKILLS = PLUGIN / "skills"

SPEC_TO_PR = SKILLS / "spec-to-pr" / "SKILL.md"
MULTI_PR = SKILLS / "multi-pr" / "SKILL.md"
CHANGE_LOOP = SKILLS / "multi-pr" / "references" / "change-loop.md"
CHECKLIST = SKILLS / "review-change" / "references" / "checklist.md"
GUARD = DEV / "tests" / "consistency" / "test_chain_obligation_carry.py"

# Scoped to the ONE guard under test, never to `tests/consistency/` as a whole:
# a batch pointed at an area reports every mutant "killed" the moment anything
# else in that area is red, and proves nothing it claims to.
TARGETS = [GUARD]

MUTANTS = [
    # ---- the checklist, which owns review behaviour -----------------------
    (
        "the obligation verdict stops being settled by a command",
        CHECKLIST,
        'grep -rl "<token>" openspec/changes/<name>/',
        "read the artifacts and judge whether the obligation is honoured",
        TARGETS,
    ),
    (
        "settling moves behind the size gate, so the answer depends on the path",
        CHECKLIST,
        "**Settle each entry HERE, in Step 2b, on BOTH size-gate paths.**",
        "**Settle each entry inside whichever review path Step 3 selects.**",
        TARGETS,
    ),
    (
        "a pasted token becomes a valid discharge",
        CHECKLIST,
        "a `tasks.md` subtask naming the field and what reads it, plus the delta spec",
        "a sentence in `proposal.md` naming the field, plus the delta spec",
        TARGETS,
    ),
    (
        "the countability rule goes, so a missing verdict line reads as a pass",
        CHECKLIST,
        "Fewer lines than entries means the round did not complete — a missing line is a failed round, not a pass.",
        "Cover the entries that look relevant to this change.",
        TARGETS,
    ),
    (
        "the verdict stops moving — READY can sit beside NOT ADDRESSED",
        CHECKLIST,
        "**and every Step 2b inherited obligation `HONOURED`.**",
        "and nothing else outstanding.",
        TARGETS,
    ),
    (
        "the omit-empty exemption goes, so an all-honoured section is dropped",
        CHECKLIST,
        "**except `### Inherited obligations`, which is omitted only when the caller supplied no entries.**",
        "This applies to every section without exception.",
        TARGETS,
    ),
    (
        "the dispatched agents stop being told what an obligation row means",
        CHECKLIST,
        "not a mention pasted into prose",
        "however the artifacts prefer to phrase it",
        TARGETS,
    ),
    # ---- spec-to-pr, which delivers ---------------------------------------
    (
        "the flag stops outliving the phase probe",
        SPEC_TO_PR,
        "**The flag is not resumable-past**",
        "**The flag is handled once, in Review**",
        TARGETS,
    ),
    (
        "the resume rule loses the reason it exists",
        SPEC_TO_PR,
        "The JSON above has **no `review` field**:",
        "The JSON above lists the phases it knows about:",
        TARGETS,
    ),
    (
        "the hand-off stops naming the step it hands to",
        SPEC_TO_PR,
        "pass the entries into the checklist's **Step 2b**,",
        "pass the entries into the review below,",
        TARGETS,
    ),
    (
        # C3, exactly: review logic migrating back into the orchestrator.
        "the report template migrates back into the orchestrator",
        SPEC_TO_PR,
        "do not restate its rules here.**",
        "the template is `HONOURED | VIOLATED | NOT ADDRESSED`.**",
        TARGETS,
    ),
    (
        "the argument contract stops deriving the carry from the prerequisite's actual state",
        SPEC_TO_PR,
        "which by definition post-date this change's authoring — not from the batch as proposed",
        "which the chain plan already described up front",
        TARGETS,
    ),
    # ---- multi-pr, which records and reads back ----------------------------
    (
        # C1, exactly: the notes file is dated, so a later-date resume sees none.
        "the read is scoped to this run's notes file only",
        CHANGE_LOOP,
        "**Read EVERY running-notes file, not just this run's**",
        "**Read this run's running-notes file**",
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
        "an empty carry reverts to a word anyone can type",
        CHANGE_LOOP,
        "**Zero obligations is a real answer, and it is written as the DERIVATION, never the bare word.**",
        "**Zero obligations is written as `none`.**",
        TARGETS,
    ),
    (
        "the third derivation source goes — the finding that names its consumer outright",
        CHANGE_LOOP,
        "genuinely out of scope for this change — belongs to a different change entirely",
        "genuinely large in scope",
        TARGETS,
    ),
    (
        "multi-pr's hoisted invariant loses the reason the record alone is not enough",
        MULTI_PR,
        "**A carry list written and then not fed into the dependent's own Review is indistinguishable from never having written it**",
        "**A carry list should be fed into the dependent's own Review**",
        TARGETS,
    ),
    # ---- the guard's own structure ----------------------------------------
    (
        "the guard's carry-flag constant drifts from the files it guards",
        GUARD,
        '_CARRY_FLAG = "--inherits"',
        '_CARRY_FLAG = "--carries"',
        TARGETS,
    ),
    (
        "the region cap widens until any slice satisfies it",
        GUARD,
        "_MAX_REGION = 5000",
        "_MAX_REGION = 1000000",
        TARGETS,
    ),
    (
        # Reachable only because `test_the_parity_floor_is_reachable` puts the
        # tree into the state the floor exists for.
        "the parity floor is relaxed to nothing",
        GUARD,
        "    assert len(flags) >= 5, (",
        "    assert len(flags) >= 0, (",
        TARGETS,
    ),
    (
        # Likewise `test_the_coverage_floor_is_reachable`.
        "the per-file coverage floor is relaxed to nothing",
        GUARD,
        "        assert covered.count(path) >= sides, (",
        "        assert covered.count(path) >= 0, (",
        TARGETS,
    ),
]

# One property is NOT mutated, deliberately, so "the batch is all-green" does not
# imply coverage this batch lacks.
#
# **Deleting a whole region entry.** `mutate.py` anchors on a single line and a
# region entry spans several, so the drop cannot be expressed as a one-line
# substitution. Renaming its key — the one-line approximation — was tried and
# SURVIVED, correctly: a rename changes no file, no anchor and no marker, so
# nothing should notice. The real drop is exercised by
# `test_the_coverage_floor_is_reachable`, and the floor it trips is itself
# mutated above.
