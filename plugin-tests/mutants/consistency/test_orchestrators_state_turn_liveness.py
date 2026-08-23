"""Mutation batch for test_orchestrators_state_turn_liveness.py.

The guard reads prose, so it carries the ordinary risk of a prose-matching
check: passing by finding a word while the rule it vouches for has lost the
property that made it work. Each mutant removes ONE property and leaves the
surrounding text intact, which is what a real rewrite would do.

Mutants 9-12 aim at the GUARD rather than a skill. Its structural properties —
the declared family, the seam exemption, the span cap — cannot be exercised from
the asset side, and every one of them was a live defect in an earlier revision:
a review proved that emptying `_FAMILY` or `_MARKERS` left tests passing while
reading nothing, that an unconstrained `None` silenced two of three seams, and
that markers scattered through one large block satisfied a plain "same block"
test. A batch that only mutates the assets would have caught none of those.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_orchestrators_state_turn_liveness.py
"""

from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
DEV = Path(__file__).resolve().parents[2]
SKILLS = PLUGIN / "skills"
GUARD = DEV / "tests" / "consistency" / "test_orchestrators_state_turn_liveness.py"

# Scoped to the ONE guard under test, never to `tests/consistency/` as a whole:
# a batch pointed at an area reports every mutant "killed" the moment anything
# else in that area is red, and proves nothing it claims to.
#
# That was not hypothetical here. `pytest plugin-tests/tests/consistency/` was
# 1-failed for exactly this reason until `fix/consistency-scope-import`:
# `test_overlays_are_reachable.py` imported the staleness guard from
# `.claude/plugins/cla/conformance-checks/tests`, a directory the dev-tree
# extraction deleted, and it resolved in a FULL run only because collecting
# `tests/conformance/` first put a module of that name in `sys.modules`. The
# guard is fixed and the area is green now; the file-scoping stays on its own
# merits.
TARGETS = [GUARD]

MUTANTS = [
    (
        "multi-pr's rule loses the mechanical same-message form",
        SKILLS / "multi-pr" / "SKILL.md",
        "status text and the next tool call go in the SAME message",
        "a closing status report should not read as an ending",
        TARGETS,
    ),
    (
        "multi-lite's rule reverts to the asked-a-question discriminator",
        SKILLS / "multi-lite" / "SKILL.md",
        "is there a pending event that will re-invoke this session?",
        "did you ask the user a question?",
        TARGETS,
    ),
    (
        "multi-spec's rule drops announcing-is-not-doing",
        SKILLS / "multi-spec" / "SKILL.md",
        "**announcing the next step is not a mechanism**",
        "**announcing the next step is good practice**",
        TARGETS,
    ),
    (
        "spec-to-pr, the rule's origin, loses the discriminator",
        SKILLS / "spec-to-pr" / "SKILL.md",
        "whether a **pending event** will re-invoke this session",
        "whether you have said what happens next",
        TARGETS,
    ),
    (
        "multi-pr's seam stops stating the mechanical form",
        SKILLS / "multi-pr" / "references" / "change-loop.md",
        "step-1 resume check go **in the same message**",
        "step-1 resume check follow promptly",
        TARGETS,
    ),
    (
        "multi-lite's seam drops announcing-is-not-doing",
        SKILLS / "multi-lite" / "references" / "candidate-loop.md",
        "announcing the next candidate **is not a mechanism**",
        "announcing the next candidate is courteous",
        TARGETS,
    ),
    (
        "multi-spec's seam loses the discriminator",
        SKILLS / "multi-spec" / "references" / "authoring-brief.md",
        "**pending event** will re-invoke this session, not whether you asked",
        "the previous change went well, not whether you asked",
        TARGETS,
    ),
    (
        "a skill drifts back to a third legitimate exit case",
        SKILLS / "multi-pr" / "SKILL.md",
        "legitimate in exactly two cases",
        "legitimate in exactly three cases",
        TARGETS,
    ),
    (
        # The declared-family tripwire. Dropping a chain skill must fail via
        # `promising <= set(_FAMILY)` and the floor, not pass by checking one
        # fewer — that silent shrink is why the literal replaced a derived key.
        "a chain skill silently drops out of the declared family",
        GUARD,
        '"multi-lite": ("references/candidate-loop.md", "move to the next candidate"),',
        "# dropped",
        TARGETS,
    ),
    (
        # An unconstrained None was a silent opt-out from the seam requirement.
        "the seam exemption stops being pinned to spec-to-pr alone",
        GUARD,
        '_SEAMLESS = {"spec-to-pr"}',
        '_SEAMLESS = {"spec-to-pr", "multi-pr", "multi-lite", "multi-spec"}',
        TARGETS,
    ),
    (
        # Without the cap, markers scattered through a large unrelated block
        # satisfy "same block". A reviewer defeated the guard exactly this way.
        "the adjacency cap widens until any block satisfies it",
        GUARD,
        "_MAX_SPAN = 1200",
        "_MAX_SPAN = 100000",
        TARGETS,
    ),
]

# Two properties are NOT mutated, deliberately. Recorded here rather than left as
# a silent gap, because "the batch is all-green" would otherwise imply a coverage
# this batch does not have.
#
# **The `_MARKERS` floor.** Replacing `assert len(_MARKERS) == 3 and all(_MARKERS)`
# with `assert True` survives, and correctly. In an earlier revision empty markers
# made every check vacuously pass, which is why the floor exists — but the rewrite
# made `_span_of_best_block` compute `max()` over an empty sequence, so empty
# markers now RAISE rather than pass. The floor buys a legible message instead of
# a `ValueError`; it is no longer what stops the vacuity.
#
# **The line/paragraph granularity split.** Switching SKILL.md to
# `paragraphs=True` also survives, because `_blocks` is a strict superset of
# `_lines` and the span function takes the TIGHTEST span — so adding paragraph
# blocks can only lower it, never raise it. The split still matters (it rejects
# markers spread across two adjacent bullets that happen to fall inside the span
# cap), but that is unreachable by mutating source against a healthy tree.
#
# Both are the same class: a floor is unexercised while the thing it floors is
# healthy. They are covered structurally instead, by
# `test_the_guard_notices_when_its_own_state_is_gutted`,
# `test_the_adjacency_cap_is_load_bearing` and
# `test_line_granularity_rejects_markers_split_across_bullets` — which is the
# form `_shared/references/test-quality.md` prefers anyway, since a tamper test
# keeps holding after a later refactor turns the check into a no-op.
