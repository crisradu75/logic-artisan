"""Mutation batch for test_check_labels_agree.py.

The guard claims that no enumeration of `checklist.md`'s high-yield checks can go
stale without a test going red. Each mutant below restores an enumeration to the
exact defective text the repo actually carried before this session, so the batch
measures the guard against history rather than against invented shapes.

Two mutants target the guard's own regexes rather than the prose, because both
were places its first draft was wrong.

**One weakness is deliberately NOT a mutant here, and the reason is worth
stating.** The guard's first draft used a presence check — "the newest label
appears somewhere in the file" — which is satisfied by a file naming `0l` in one
sentence while still enumerating the old set in another. That is exactly the
shape `review-gate.md` shipped in, so the draft passed on a corrected tree and
missed the real defect. Re-installing that weaker rule as a mutant SURVIVES, and
correctly so: a guard weakening cannot be detected on a tree with nothing stale
to catch, and expressing the pair needs two files mutated at once, which this
batch format does not carry. The same is true of narrowing `_DEFINITION` back to the
checklist's single heading spelling: with the `0j` collision already resolved there
is nothing for the narrow pattern to miss.

An earlier version of this paragraph claimed "mutant 3 is what holds the broad
pattern in place — narrow the regex and mutant 3 stops dying". **A reviewer
measured that and it is false.** Narrowing `_DEFINITION` leaves `pytest` green and
makes `mutate.py` abort in *preflight* — mutant 5's `old` string is the whole
`_DEFINITION` line, so any edit to that regex trips its anchor before mutant 3
ever runs. The protection is real but it comes from mutant 5's anchor, not from
mutant 3, and the claim as written was reasoning presented as measurement. Stated
correctly: **any edit to `_DEFINITION` fails this batch at preflight**, which is
coarser than a kill but is what actually holds it. `_RANGE` has the same coupling
through mutant 4, and `claims_residence` has no mutant at all — its non-vacuity is
asserted by a test instead.

The presence-check weakness was measured directly, by
replaying the four historical defects against both drafts: the presence-check
draft caught 3 of 4, the coverage rule catches 4 of 4. Mutant 1 is what holds the
coverage rule in place from here.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_check_labels_agree.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"

GUARD = DEV / "tests" / "consistency" / "test_check_labels_agree.py"
CHECKLIST = PLUGIN / "skills" / "review-change" / "references" / "checklist.md"
REVIEW_GATE = PLUGIN / "skills" / "multi-spec" / "references" / "review-gate.md"
RC_SKILL = PLUGIN / "skills" / "review-change" / "SKILL.md"

# Scoped to the ONE guard file: a target red for any other reason reports every
# mutant "killed" and proves nothing.
TARGETS = [GUARD]

MUTANTS = [
    (
        # The defect that actually shipped, in PR #158's feature commit. Its own
        # Measured-by grep was scoped to checklist.md, so this line in another
        # file was never looked at.
        "review-gate claims only 0a-0e live in the checklist, omitting 0j-0l",
        REVIEW_GATE,
        "note that `0a`–`0e` and `0j`–`0l` live in `checklist.md` itself; only the domain-specific checks (`0f`–`0i`)",
        "note that only 0a–0e live in `checklist.md` itself; the domain-specific checks (0f–0i)",
        TARGETS,
    ),
    (
        "an entry point advertises the old check count",
        RC_SKILL,
        "the 12 high-yield verification checks (`0a`–`0l`)",
        "the 10 high-yield verification checks",
        TARGETS,
    ),
    (
        # A batch orchestrator that had already run checklist 0j reads
        # "add check 0j" as work already done, and the check this gate exists
        # for is skipped with the report identical either way.
        "a skill defines its own check under a label the checklist owns",
        REVIEW_GATE,
        "**0m — Cross-change cross-reference check",
        "**0j — Cross-change cross-reference check",
        TARGETS,
    ),
    (
        # Without backtick tolerance the pattern misses `0a`–`0e`, which is how
        # the prose is actually written in the file the stale line lives in.
        "the range pattern stops tolerating backticked labels",
        GUARD,
        r'_RANGE = re.compile(r"`?\b(0[a-z])\b`?\s*[–—-]\s*`?\b(0[a-z])\b`?")',
        r'_RANGE = re.compile(r"\b(0[a-z])\s*[–—-]\s*(0[a-z])\b")',
        TARGETS,
    ),
    (
        # Non-vacuity partner: proves the definition scan is actually read,
        # rather than the guard passing on an empty `defined` set.
        "the definition scan stops matching the checklist's own check headings",
        GUARD,
        '_DEFINITION = re.compile(r"^(?:\\*\\*)?(0[a-z])(?:\\.|\\s*[–—-])\\s", re.MULTILINE)',
        '_DEFINITION = re.compile(r"^(?:\\*\\*)?(9[a-z])(?:\\.|\\s*[–—-])\\s", re.MULTILINE)',
        TARGETS,
    ),
    # ----------------------------------------------------------------------- #
    # Rule 5 — the marked enumerations. These re-break the defect the marker
    # mechanism was added to close: a restatement inside the checklist going
    # short while the suite stays green.
    # ----------------------------------------------------------------------- #
    (
        # The literal defect two reviewers reproduced: the orchestrator-runs-these
        # line names a set that stops short of what the checklist defines, so an
        # orchestrator reading it runs the old set.
        "a marked enumeration goes short by one check",
        CHECKLIST,
        "All checks above (generic 0a–0e and 0j–0l here, plus the overlay's 0f–0i and 1–9)",
        "All checks above (generic 0a–0e and 0j–0k here, plus the overlay's 0f–0i and 1–9)",
        TARGETS,
    ),
    (
        # Rewording a marked line without carrying its marker leaves the prose
        # unwatched. The floor is what turns that into a failure rather than a
        # silently smaller rule.
        "a marked line loses its marker in a reword",
        CHECKLIST,
        "not on the change's self-description. <!-- enumerates-checks -->",
        "not on the change's self-description.",
        TARGETS,
    ),
    (
        # Discriminates the no-subtraction choice in the rule. Dropping a
        # DELEGATED label (`0i`) from a marked line must fail: the rule compares
        # against `defined`, so a marked line claiming the whole set has to name
        # the overlay's checks too. Under the residence rule's `owned` set — with
        # the delegated labels subtracted — this edit would pass, which is why
        # the two rules deliberately do not share that subtraction.
        #
        # This replaced a direct mutation of `defined - covered` to
        # `defined - _delegated_labels() - covered`, which SURVIVED. It had to:
        # every marked line in the correct tree covers the delegated labels
        # anyway, so the two expressions agree everywhere the real file reaches.
        # Mutating the guard could not distinguish them; mutating the prose can.
        "a marked enumeration drops a check the overlay owns",
        CHECKLIST,
        "plus the overlay's 0f–0i and 1–9)",
        "plus the overlay's 0f–0h and 1–9)",
        TARGETS,
    ),
]

# DELIBERATELY NOT A MUTANT: `_MIN_MARKED_LINES = 3` → `0`.
#
# It was written, it survived, and it cannot do otherwise. The floor only binds
# when markers are missing, and in the correct tree all three are present — so
# lowering it changes no outcome any test can observe. Killing it would mean
# asserting the constant's value against the live count, which turns the floor
# into a population and deletes the protection it exists to give.
#
# The floor's real non-vacuity is the "a marked line loses its marker in a
# reword" mutant above, which removes a marker and IS killed. Keeping an
# unkillable mutant in the batch would report a survivor on every clean run,
# and a survivor nobody acts on trains the next reader to skip the whole list.
