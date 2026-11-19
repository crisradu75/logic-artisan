"""The project-review skill states each outcome the project-review spec requires.

Spec: openspec/specs/project-review. The skill is prose, so these tests pin the text that carries
each outcome, and that its inline verdict table agrees with the rubric reference.
"""

from __future__ import annotations

import re
from pathlib import Path

_PLUGIN = Path(__file__).resolve().parents[4] / ".claude" / "plugins" / "cla"
_DIR = _PLUGIN / "skills" / "project-review"
_SKILL = _DIR / "SKILL.md"
_CRITERIA = _DIR / "references" / "review-criteria.md"
_ROUTING = _PLUGIN / "skills" / "_shared" / "references" / "model-routing.md"

_EXPECTED_ROWS = [
    ("NEEDS WORK", "Two or more D grades, or more than half of the graded dimensions C or D"),
    ("EXEMPLARY", "Every graded dimension A or B"),
    ("STRONG", "No D, at most one C"),
    ("SOLID", "Any other set of grades"),
]


def _flat(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def _rows(path: Path) -> list[tuple[str, str]]:
    return re.findall(r"^\| \*\*([A-Z ]+)\*\* \| (.+?) \|$", path.read_text(encoding="utf-8"), re.M)


# requirement: project-review / Baseline checks run before any reviewer
def test_baseline_checks_finish_before_dispatch_and_reach_every_reviewer():
    text = _flat(_SKILL)
    assert "This step MUST complete before Step 2's dispatch" in text
    assert "every agent receives its output as pre-verified input" in text
    assert "Print any FAIL immediately" in text
    baseline = _flat(_DIR / "references" / "baseline-checks.md")
    assert "recorded as **SKIP**" in baseline
    assert "from `cla.io/project-facts.md`" in baseline


# requirement: project-review / Five dimension reviews run at once
def test_five_reviewers_start_together_with_the_two_premise_dimensions_on_the_strongest_model():
    text = _flat(_SKILL)
    assert "Dispatch all FIVE agents concurrently, in a single message" in text
    assert "Agent 1 (Vision & Clarity) and Agent 4 (Architecture & Design) → `model: \"opus\"`" in text
    assert "Agents 2, 3, 5 (Structure, Requirements & Specs, Validation & QA) → `model: \"sonnet\"`" in text
    routing = _flat(_ROUTING)
    assert "`project-review` Agent 1 (**Vision & Clarity**) + Agent 4 (**Architecture & Design**)" in routing
    assert "| opus | inherited |" in routing


# requirement: project-review / The verdict follows the grades
def test_the_verdict_table_is_the_specified_one_and_the_rubric_reference_agrees():
    assert _rows(_SKILL) == _EXPECTED_ROWS
    assert _rows(_CRITERIA) == _EXPECTED_ROWS
    assert "Leave N/A dimensions out of every count" in _flat(_SKILL)
    assert "Take the first row that matches" in _flat(_SKILL)


# requirement: project-review / A project review changes nothing
def test_the_review_holds_no_editing_tool_and_keeps_no_state():
    tools = []
    for line in _SKILL.read_text(encoding="utf-8").splitlines():
        if line.startswith("allowed-tools:"):
            tools = [tool.strip() for tool in line.split(":", 1)[1].split(",")]
    assert tools, "project-review lost its allowed-tools line"
    for forbidden in ("Write", "Edit", "NotebookEdit"):
        assert forbidden not in tools
    assert "this skill persists no state across runs" in _flat(_SKILL)
    assert "The report is the whole output" in _flat(_SKILL)
