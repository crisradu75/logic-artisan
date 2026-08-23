"""A chain skill that promises no inter-unit pauses must also say how a turn ends.

The two rules look like one rule and are not. "Run start-to-finish with no
'ready to continue?' pauses" forbids *asking permission*. The failure that
actually stops a chain asks nothing: the orchestrator announces the next unit,
ends the turn believing it is continuing, and nothing ever re-invokes the
session. Measured in a consuming repo on 2026-08-23 — a six-change chain lost
~4.5 hours with 4 of 6 changes unstarted, on a closing line of "Starting change
3: ...". Neither skill's no-pause rule covered it, because nothing had been
asked.

So this scope pins that every skill making the no-pause promise ALSO carries the
turn-liveness rule, and that the rule keeps the two properties that make it more
than a restatement of the prohibition it sits next to:

- a *mechanical* form (is there a tool call in this message?) rather than only a
  judgement about whether the prose reads as an ending — the judgement form is
  the one that lost in practice;
- the *pending-event* discriminator rather than the asked-a-question one.

Why key the family on the literal phrase "ready to continue": it was measured,
not guessed. The obvious key, the word "unattended", hits four `SKILL.md` files,
two of them incidental mentions with no autonomy contract at all
(`multi-spec`'s comparison of run shapes, `right-model`'s advice about effort
settings) — a drift guard built on it would have shipped two false failures on
its first run. "ready to continue" hits exactly the chain skills.

Spec: `openspec/specs/cla-plugin/spec.md`, "Unattended-run turn liveness".
"""

from __future__ import annotations

from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
_SKILLS = _PLUGIN_ROOT / "skills"

# The mechanical form, the discriminator, and the announcing-is-not-doing rule.
# All three are what separate this rule from the no-pause rule beside it.
_MECHANICAL = "in the same message"
_DISCRIMINATOR = "pending event"
_NOT_A_MECHANISM = "is not a mechanism"


def _no_pause_chain_skills() -> dict[str, str]:
    """Every SKILL.md promising no pauses between units, by skill name."""
    found = {}
    for skill_md in sorted(_SKILLS.glob("*/SKILL.md")):
        text = skill_md.read_text(encoding="utf-8")
        if "ready to continue" in text.lower():
            found[skill_md.parent.name] = text
    return found


def test_the_no_pause_chain_skills_are_actually_found():
    """Non-vacuity partner. Every assertion below iterates this set, so a
    derivation that silently stopped matching would pass them all while checking
    nothing."""
    found = _no_pause_chain_skills()
    assert found, (
        "no SKILL.md promises 'ready to continue' pauses any more — the "
        "derivation below now matches nothing and the checks are vacuous"
    )
    assert set(found) >= {"multi-pr", "multi-lite"}, (
        f"expected the chain skills among the no-pause set, got {sorted(found)}"
    )


def test_every_no_pause_chain_skill_states_the_turn_liveness_rule():
    for name, text in _no_pause_chain_skills().items():
        low = text.lower()
        assert _MECHANICAL in low, (
            f"{name}/SKILL.md promises no inter-unit pauses but never states the "
            f"mechanical form of the turn-liveness rule ({_MECHANICAL!r}). "
            "Without it the rule is a judgement about how prose reads, which is "
            "the form that has already failed."
        )
        assert _DISCRIMINATOR in low, (
            f"{name}/SKILL.md states the turn-liveness rule without the "
            f"{_DISCRIMINATOR!r} discriminator. Whether a question was asked is "
            "the wrong test — the stall asks nothing."
        )
        assert _NOT_A_MECHANISM in low, (
            f"{name}/SKILL.md omits that announcing the next step "
            f"{_NOT_A_MECHANISM}. That sentence is the one the measured failure "
            "walked straight through."
        )


def test_the_change_loop_seam_restates_the_rule():
    """The gap opens BETWEEN units, which is exactly where the reference file
    carrying the loop has been read and closed and the orchestrator is running on
    the SKILL.md summary. The hoisted copy is not enough on its own."""
    seam = _SKILLS / "multi-pr" / "references" / "change-loop.md"
    assert seam.is_file(), f"{seam} is missing"
    low = seam.read_text(encoding="utf-8").lower()

    assert "move to the next change" in low, (
        "change-loop.md no longer has the between-changes seam this check is "
        "anchored to; re-point the check rather than deleting it"
    )
    assert _DISCRIMINATOR in low and _NOT_A_MECHANISM in low, (
        "change-loop.md's seam does not restate the turn-liveness rule. The "
        "hoisted rule in SKILL.md binds, but this is the point at which that "
        "file is no longer in front of the reader."
    )
