"""Mutation batch for test_orchestrators_state_turn_liveness.py — break each
property the guard pins and confirm a test fails.

The guard reads prose, so the risk it carries is the ordinary one for a
prose-matching check: it can pass by finding a word while the rule it vouches for
has quietly lost the property that made it work. Each mutant below removes ONE
such property and leaves the surrounding paragraph intact, which is what a real
rewrite would do — none of them delete the rule outright.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_orchestrators_state_turn_liveness.py
"""

from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
DEV = Path(__file__).resolve().parents[2]
SKILLS = PLUGIN / "skills"
# Scoped to the ONE guard under test, never to `tests/consistency/` as a whole.
# `python -m pytest plugin-tests/tests/consistency/` is unconditionally 1-failed:
# `test_overlays_are_reachable.py` imports the staleness guard by bare module
# name, which resolves only once the conformance area has been collected. A batch
# pointed at the whole area would report every mutant "killed" on that unrelated
# failure, having proven nothing about this guard at all.
TARGETS = [DEV / "tests" / "consistency" / "test_orchestrators_state_turn_liveness.py"]

MUTANTS = [
    (
        "the rule keeps its prose but loses the mechanical same-message form",
        SKILLS / "multi-lite" / "SKILL.md",
        "status text and the next tool call go in the SAME message",
        "a closing status report should not read as an ending",
        TARGETS,
    ),
    (
        "the discriminator reverts to the asked-a-question one",
        SKILLS / "multi-pr" / "SKILL.md",
        "is there a pending event that will re-invoke this session?",
        "did you ask the user a question?",
        TARGETS,
    ),
    (
        "announcing-is-not-doing drops out of the hoisted rule",
        SKILLS / "multi-pr" / "SKILL.md",
        "the next step is not a mechanism",
        "the next step is good practice",
        TARGETS,
    ),
    (
        "the between-changes seam stops restating the rule",
        SKILLS / "multi-pr" / "references" / "change-loop.md",
        "Announcing the next change is not a mechanism",
        "Announcing the next change is courteous",
        TARGETS,
    ),
    (
        # Aimed at the GUARD, not at a skill. The obvious version — delete the
        # promise from `multi-pr/SKILL.md` — is a false mutant: the phrase occurs
        # twice in that file and `mutate.py` replaces one occurrence, so the
        # derivation still matches and nothing changes. It reported SURVIVED, and
        # it was right to. Breaking the derivation itself is the real test of
        # whether the non-vacuity partner can fire.
        "the guard's family derivation silently stops matching anything",
        DEV / "tests" / "consistency" / "test_orchestrators_state_turn_liveness.py",
        'if "ready to continue" in text.lower():',
        'if "ready to proceed" in text.lower():',
        TARGETS,
    ),
]
