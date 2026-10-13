"""lite-pr's SKILL.md keeps a trigger for each rule moved into a reference.

The Measured-by rules, the mutation gate and the /cla:diagnose escalation live in
`lite-pr/references/`, read only when SKILL.md's one-line trigger says to. Deleting
a trigger leaves the reference in place and every other guard green (the
mutation-gate guard finds its site by walking the tree), while the rule silently
stops being read. This names each trigger path and requires the file behind it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_LITE_PR = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "skills" / "lite-pr"
_PREFIX = "${CLAUDE_PLUGIN_ROOT}/skills/lite-pr/references/"


@pytest.mark.parametrize("name", ["measured-by.md", "mutation-gate.md", "diagnose-escalation.md"])
def test_skill_md_names_each_moved_reference_by_full_path(name: str) -> None:
    skill = (_LITE_PR / "SKILL.md").read_text(encoding="utf-8")
    assert _PREFIX + name in skill, f"lite-pr/SKILL.md lost its trigger to read references/{name}"
    assert (_LITE_PR / "references" / name).is_file(), f"references/{name} is missing"


def test_subagent_brief_is_never_named_by_a_bare_filename() -> None:
    """A bare `subagent-brief.md` opens nothing from lite-pr's directory: the file lives
    under spec-to-pr. The reference lint only catches bare `references/<file>` paths, so
    a bare filename inside the moved gate text went unnoticed."""
    full = "${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/references/subagent-brief.md"
    for path in [_LITE_PR / "SKILL.md", *sorted((_LITE_PR / "references").glob("*.md"))]:
        text = path.read_text(encoding="utf-8")
        assert text.count("subagent-brief.md") == text.count(full), (
            f"{path.name} names subagent-brief.md without the full {full} path"
        )


def test_test_phase_has_one_retry_budget_and_halt_follows_diagnose() -> None:
    """Step 3 once said "two rounds" before escalating while step 4 halted after one
    retry, so the escalation could never fire before the halt. One budget: one fix, one
    retry, then /cla:diagnose; step 4's HALT comes after that path."""
    skill = (_LITE_PR / "SKILL.md").read_text(encoding="utf-8")
    ref = (_LITE_PR / "references" / "diagnose-escalation.md").read_text(encoding="utf-8")
    for name, text in [("SKILL.md", skill), ("diagnose-escalation.md", ref)]:
        assert "two rounds on the same" not in text.lower(), f"{name} states a two-round budget again"
    step3 = next(line for line in skill.splitlines() if line.startswith("3. Any failure"))
    step4 = next(line for line in skill.splitlines() if line.startswith("4. Still failing"))
    assert "one fix, one retry" in step3, "SKILL.md step 3 lost the one-fix-one-retry budget"
    assert "/cla:diagnose" in step3, "SKILL.md step 3 lost the escalation trigger"
    assert "after the `/cla:diagnose` path" in step4, "step 4 HALTs without the diagnose path before it"
    assert "after that one retry →" not in step4, "step 4 HALTs straight after the retry again"
    assert "UNCOMMITTED in the working tree" in ref and "Ship commits them on the feature branch" in ref, (
        "the reference lost the rule that a Test-phase diagnose leaves its fix uncommitted for Ship"
    )
    assert "leaves its fix uncommitted; Ship commits it" in step3, "step 3 lost the uncommitted-fix short form"
    assert "third edit" not in ref,"the reference still counts a third edit under the one budget"
    assert "One fix and one retry with the gate still red, on the same stated cause or a new one" in ref, (
        "diagnose-escalation.md does not name the same one-fix-one-retry trigger as step 3"
    )


def test_a_retry_failing_on_a_new_cause_reaches_diagnose_before_the_halt() -> None:
    """#350: a retry that failed on a DIFFERENT cause used to HALT with no diagnose step,
    though a failure that appears right after a fix is most often the fix itself. Both
    causes now take the same path: diagnose first, then step 4's HALT if still red."""
    skill = (_LITE_PR / "SKILL.md").read_text(encoding="utf-8")
    step3 = next(line for line in skill.splitlines() if line.startswith("3. Any failure"))
    step4 = next(line for line in skill.splitlines() if line.startswith("4. Still failing"))
    assert "on the same stated cause or a new one → stop editing and escalate to `/cla:diagnose`" in step3, (
        "step 3 no longer sends a new-cause failure to diagnose"
    )
    assert step4.startswith("4. Still failing after the `/cla:diagnose` path in step 3"), (
        "step 4 HALTs on something other than the diagnose path again"
    )
    assert "cause" not in step4.split("(")[0], "step 4 HALTs a failure by its cause again, skipping diagnose"
    ref = (_LITE_PR / "references" / "diagnose-escalation.md").read_text(encoding="utf-8")
    assert "Hand `diagnose` the retry's failure output, not the original one" in ref, (
        "on a new cause, diagnose may be handed the original failure and stop without a root cause"
    )
