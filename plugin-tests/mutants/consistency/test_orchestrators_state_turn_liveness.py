"""Mutation batch for test_orchestrators_state_turn_liveness.py.

The guard reads prose, so it carries the ordinary risk of a prose-matching check:
it can pass by finding a word while the rule it vouches for has quietly lost the
property that made it work. Each mutant removes ONE property and leaves the
surrounding text intact, which is what a real rewrite would do — none deletes the
rule outright. Mutants 8 and 9 aim at the GUARD rather than a skill, because two
of its properties (the declared-family tripwire, the adjacency requirement) are
its own structure and cannot be exercised from the asset side.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_orchestrators_state_turn_liveness.py

A correction worth keeping, because an earlier revision of this file taught the
wrong model of the tool. It claimed a mutant survived because "the phrase occurs
twice and mutate.py replaces one occurrence". That is not what happened, and
mutate.py does not behave that way: its preflight REFUSES any anchor matching
more than once ("anchor appears {hits}x ... Anchor on something unique"). What
actually happened is subtler. The anchor was unique, but the phrase the guard's
own derivation read at the time — "ready to continue" — occurs a second time
elsewhere in the same file, so removing the anchored bullet left family
membership intact and no assertion moved. That derivation is gone now (the family
is a declared literal), which is the durable fix.
"""

from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
DEV = Path(__file__).resolve().parents[2]
SKILLS = PLUGIN / "skills"
GUARD = DEV / "tests" / "consistency" / "test_orchestrators_state_turn_liveness.py"

# Scoped to the ONE guard under test, never to `tests/consistency/` as a whole.
# `pytest plugin-tests/tests/consistency/` is 1-failed today, so a batch pointed
# at the area would report every mutant "killed" on an unrelated failure and
# prove nothing. That failure is PRE-EXISTING and is itself a bug, not a stable
# fact to design around: `test_overlays_are_reachable.py` imports the staleness
# guard from `.claude/plugins/cla/conformance-checks/tests`, a directory the
# dev-tree extraction deleted. It resolves in a full run only because collecting
# `tests/conformance/` first puts a module of that name on `sys.path` — so the
# guard passes by an ambient import rather than by the path it names. When that
# is fixed, this file-scoping stays correct on its own merits (narrowest target
# that could catch the mutation); only the justification below expires.
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
        # The declared-family tripwire. Dropping a chain skill from _FAMILY must
        # fail via `promising <= set(_FAMILY)`, not pass by quietly checking one
        # skill fewer — that silent-shrink is the failure the literal replaced a
        # derived key to prevent.
        "a chain skill silently drops out of the declared family",
        GUARD,
        '"multi-lite": ("references/candidate-loop.md", "move to the next candidate"),',
        "# dropped",
        TARGETS,
    ),
    (
        # The adjacency property. This single replace BOTH removes the marker
        # from the rule's own bullet AND re-adds it as a separate bullet, so the
        # phrase is still present file-wide while the rule is gutted. A file-wide
        # `in` test passes here; only the block check catches it.
        "a marker survives file-wide but leaves the rule's own block",
        SKILLS / "multi-pr" / "SKILL.md",
        'Nothing else — **announcing the next step is not a mechanism**, and "Is there a tool call in this message?" needs no judgement.',
        'Nothing else, and "Is there a tool call in this message?" needs no judgement.\n- **Aside.** Announcing the next step is not a mechanism.',
        TARGETS,
    ),
]
