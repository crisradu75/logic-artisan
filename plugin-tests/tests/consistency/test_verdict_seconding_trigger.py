"""Every place that restates the sub-Opus verdict-seconding rule agrees on one trigger.

`skills/_shared/references/model-routing.md` ("Escalate-up rule") defines it: in a session
below Opus, a Review verdict of RETHINK, or a FIX FIRST verdict carrying a Critical finding,
is seconded by one `opus` Agent. The trigger once depended on the session judging its own
verdict "borderline", which a Sonnet session rarely does. The restating files must not
bring that wording back, and each must name the verdict and the Critical grade.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SKILLS = _ROOT / ".claude" / "plugins" / "cla" / "skills"
_ROUTING = _SKILLS / "_shared" / "references" / "model-routing.md"
# Files that restate the rule, with the text each must carry.
_RESTATING = {
    "model-routing.md": (_ROUTING, r"RETHINK.{0,200}FIX FIRST.{0,200}Critical"),
    "spec-to-pr/SKILL.md (route line)": (_SKILLS / "spec-to-pr" / "SKILL.md", r"Review verdict of RETHINK or of FIX FIRST with a Critical"),
    "spec-to-pr/SKILL.md (review loop)": (_SKILLS / "spec-to-pr" / "SKILL.md", r"`RETHINK` verdict, or a `FIX FIRST` verdict with at least one Critical"),
    "workflow-diagram.md": (_SKILLS / "spec-to-pr" / "references" / "workflow-diagram.md", r"sub-Opus \+ RETHINK or Critical FIX FIRST"),
    "right-model/SKILL.md": (_SKILLS / "right-model" / "SKILL.md", r"RETHINK or Critical-bearing FIX FIRST"),
}
_SELF_JUDGED = re.compile(r"borderline Review verdict|RETHINK-borderline|FIX FIRST / RETHINK boundary|FIX-FIRST/RETHINK\s+boundary", re.I)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_restating_files_name_the_verdict_and_critical_trigger() -> None:
    for name, (path, pattern) in _RESTATING.items():
        assert re.search(pattern, _read(path), re.S), f"{name} does not state the RETHINK / Critical-bearing FIX FIRST trigger"


def test_no_file_keeps_the_self_judged_borderline_trigger() -> None:
    for path in _SKILLS.rglob("*.md"):
        hit = _SELF_JUDGED.search(_read(path))
        assert hit is None, f"{path.relative_to(_ROOT)} still says {hit.group(0)!r}"


def test_the_routing_rule_keeps_its_scope_limits() -> None:
    text = _read(_ROUTING)
    section = text.split("## Escalate-up rule", 1)[1].split("\n## ", 1)[0]
    assert 'model: "opus"' in section.split("Review verdict seconding", 1)[1], "the seconding agent is not pinned to opus"
    assert "Important or Suggestion findings" in section and "READY" in section, "the not-seconded cases are missing"
    assert "Revise triage itself is NOT" in section, "triage-never-escalated line was dropped"
