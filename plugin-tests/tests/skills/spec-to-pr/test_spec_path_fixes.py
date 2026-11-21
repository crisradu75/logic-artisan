"""spec-to-pr and review-change: design alternatives, spec kept true, current PR body, wording fixes.

Prose a model reads, so each test pins what text can show: the sentence is in the place the run reads
it, and the wording defect it replaced is gone.
"""
from __future__ import annotations

import re
from pathlib import Path

_SKILLS = Path(__file__).resolve().parents[4] / ".claude" / "plugins" / "cla" / "skills"
_SKILL = _SKILLS / "spec-to-pr" / "SKILL.md"
_HANDOFF = _SKILLS / "spec-to-pr" / "references" / "handoff.md"
_CHECKLIST = _SKILLS / "review-change" / "references" / "checklist.md"
_REVIEW_SKILL = _SKILLS / "review-change" / "SKILL.md"


def _flat(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def _section(text: str, heading: str) -> str:
    match = re.search(rf"^### {re.escape(heading)}\n(.*?)(?=^#{{2,3}} )", text, re.S | re.M)
    assert match, f"no '### {heading}' section"
    return match.group(1)


# requirement: change-workflow / A protected change records its rejected alternatives
def test_propose_asks_a_protected_change_to_list_its_rejected_alternatives() -> None:
    propose = " ".join(_section(_SKILL.read_text(encoding="utf-8"), "Propose").split())
    for wanted in ("touches a protected area", "lists its rejected alternatives in `design.md`",
                   "one line each", "`none considered` is a valid entry"):
        assert wanted in propose, f"Propose lost {wanted!r}"


# requirement: change-workflow / A build that departs from the spec updates the spec
def test_implement_edits_the_delta_spec_when_the_build_departs_on_purpose() -> None:
    implement = " ".join(_section(_SKILL.read_text(encoding="utf-8"), "Implement").split())
    assert "departs from a requirement on purpose" in implement
    assert "edit the change's delta spec in the same commit" in implement
    assert "re-run `openspec validate <change-name> --strict`" in implement


# requirement: change-workflow / The pull request body is current after the review rounds
def test_handoff_refreshes_the_risk_and_checks_lines_and_keeps_the_rest() -> None:
    text = _flat(_HANDOFF)
    for wanted in ("check that the PR body still describes the branch as it is now",
                   "its `Risk:` and `Checks:` clauses are current",
                   "Update only those two clauses within the one-liner",
                   "Keep the rest of the one-liner", "\"Stacked on #N.\"", "\"Closes openspec/changes/<name>/.\"",
                   "add no log of the review",
                   "`Risk: <level> — <reason>; reviewers: <list>.`"):
        assert wanted in text, f"handoff.md lost {wanted!r}"


def test_the_high_yield_check_count_leaves_out_the_overlay_labels() -> None:
    for path in (_SKILL, _REVIEW_SKILL):
        text = _flat(path)
        assert "12 high-yield" not in text, f"{path.parent.name} still advertises 12 checks"
        assert "the 8 high-yield checks (`0a`–`0e`, `0j`–`0l`; a repo overlay may add `0f`–`0i`)" in text


def test_generic_checks_0a_to_0c_name_no_one_stack() -> None:
    text = _CHECKLIST.read_text(encoding="utf-8")
    start = text.index("0a. **Symbol reality check**")
    end = text.index("0d. **Idempotency")
    block = text[start:end]
    for stack_word in ("TypeScript", "React", "i18n", "dashboard.example.label", "JSON"):
        assert stack_word not in block, f"checks 0a-0c still name {stack_word!r}"
    assert "translation files" not in text.split("Source files are authoritative", 1)[1].split("\n", 1)[0]


def test_review_change_says_it_only_reports_and_names_what_spec_to_pr_reads() -> None:
    text = _REVIEW_SKILL.read_text(encoding="utf-8")
    description = re.search(r'^description: "(.*)"$', text, re.M).group(1)
    assert "Reports only and edits nothing" in description
    body = " ".join(text.split())
    assert "reads `checklist.md` directly, and `dispatch.md` only for a large change" in body
    assert "also read directly by" not in body


def test_the_references_list_files_each_shared_file_under_one_read_condition() -> None:
    refs = _SKILL.read_text(encoding="utf-8").split("## References", 1)[1]
    trigger, revising = refs.split("Only when revising the skill:", 1)
    revising = revising.split("Shared, under", 1)[0]
    assert "`past-offenses.md`" in revising and "`past-offenses.md`" not in trigger
    for cited in ("blocking-findings.md", "test-quality.md", "orchestration-economy.md"):
        assert f"`{cited}`" in trigger, f"{cited} is cited in the body but not listed"
    assert "`implement-checks.md`" in trigger
    assert (_SKILLS / "spec-to-pr" / "references" / "implement-checks.md").is_file()


# requirement: change-workflow / The pull request body is current after the review rounds
def test_the_output_table_does_not_limit_the_body_update_to_issues() -> None:
    row = next(line for line in _SKILL.read_text(encoding="utf-8").splitlines() if line.startswith("| PR body refresh"))
    assert "only when issues exist" not in row
    assert "after any Revise fix round" in row and "`Risk:` and `Checks:` clauses" in row
    assert "when issues exist" in row
