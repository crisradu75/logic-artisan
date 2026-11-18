"""The blocking-findings filter is stated once, and no shipped file restates it differently.

`_shared/references/blocking-findings.md` is the one definition of which review findings
are fixed in a change (the blocking ones) and which go to `TODO.md`. A skill that says
"fix every Critical and Important" sends back the old rule: it spends a fix round on a
finding the filter calls non-blocking, and nothing else notices because each file reads
correctly alone.

Two checks. The reference must hold the floor, the default list and the blocking cases.
And no other shipped file may tell its reader to fix, apply or triage *every* Critical
and Important finding without saying "blocking". The rule for the copies of the protected
list is held by `test_cla_setup_rules_match_config.py`; this file holds the filter.
"""

from __future__ import annotations

import re
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
_REFERENCE = _PLUGIN_ROOT / "skills" / "_shared" / "references" / "blocking-findings.md"

# Four forms of "every Critical and Important finding is dealt with", none saying "blocking":
#   active   "fix every Critical and Important", "Apply all Critical/Important findings"
#   split    "fix all Critical and all Important"
#   passive  "Every Critical and Important finding is fixed"
#   verbless "0 Critical+Important after cap"
# A word between the quantifier and "Critical" is allowed unless it is "blocking".
# Severity definitions, ledger notes about old records and "N Critical or Important
# findings that block a merge" do not match: none pairs a quantifier or a count with
# one of these verbs, and the verbless form excludes a trailing "that block".
_SEP = r"\s*(?:/|\+|,|and|or)\s*"
_VERB = r"(?:apply|applies|fix|fixes|triage|triages|address|addresses|resolve|resolves)"
_QUANT = r"(?:every|all|each)"
_PAIR = rf"(?:(?!blocking\b)\w+\s+)?Critical{_SEP}(?:{_QUANT}\s+)?Important"
_RESTATED_FILTER = re.compile(
    rf"\b{_VERB}\s+{_QUANT}\s+{_PAIR}"
    rf"|\b{_QUANT}\s+{_PAIR}(?:\s+\w+){{0,2}}?\s+(?:is|are|was|were|gets|get|must be)\s+"
    r"(?:fixed|applied|triaged|addressed|resolved)\b"
    rf"|\b(?:0|zero)\s+Critical(?:/|\+){{1}}Important\b(?!\s+findings?\s+that\s+block)",
    re.IGNORECASE,
)


def _flat(path: Path) -> str:
    """The file's text on one line, so a wrapped sentence still matches."""
    return " ".join(path.read_text(encoding="utf-8").split())


def restated_filters(text: str) -> list[str]:
    """Each phrase in `text` that says to fix every Critical and Important finding."""
    return [m.group(0) for m in _RESTATED_FILTER.finditer(" ".join(text.split()))]


def test_the_reference_holds_the_floor_the_default_list_and_the_blocking_cases() -> None:
    text = _flat(_REFERENCE)
    # The three conditions under which a finding blocks.
    assert "It touches a protected area." in text
    assert "It is a real correctness bug in what the change ships." in text
    assert "It leaves something unbuildable or unproven." in text
    assert "`openspec validate --strict`" in text
    # A protected-area finding is never filtered out.
    assert "A finding that names a protected area is never non-blocking." in text
    # The default list, used with no Stakes section.
    default = text.split("The default list", 1)[1].split("The floor", 1)[0]
    for area in ("money", "personal data", "accessibility", "the user's own files", "anything shipped to other repos"):
        assert area in default, f"blocking-findings.md default list lacks {area}"
    # The floor, protected whatever the Stakes list says.
    floor = text.split("The floor", 1)[1].split("## What a fix buys", 1)[0]
    for area in ("security", "safety of writes to a user's files", "honesty claims"):
        assert area in floor, f"blocking-findings.md floor lacks {area}"
    # What a fix buys: both triggers stay distinct.
    assert "The by-hand mutation check" in text and "A second review round" in text


def test_the_detector_fires_on_a_restated_filter_and_not_on_the_correct_wording() -> None:
    for bad in (
        "Fix every Critical and Important finding before the PR opens.",
        "Apply every Critical/Important finding as a direct Edit.",
        "triage all Critical+Important findings",
        "Fix every open Critical or Important\nfinding.",
    ):
        assert restated_filters(bad), f"detector missed: {bad!r}"
    for good in (
        "Apply every blocking finding as a direct Edit.",
        "Apply every finding that blocks the merge.",
        "A Critical or Important is Applied only when the defect is shown gone.",
        "every Critical/Important finding triaged Deferred-Known-Issue",
        "0 Critical or Important findings that block a merge",
        "a record from before the filter counted every Critical and Important, and the retro reads both alike",
        "Critical: data loss. Important: a wrong result a user would see.",
        "✓ 0 blocking findings after cap",
    ):
        assert not restated_filters(good), f"detector flagged the correct wording: {good!r}"


def test_no_shipped_file_restates_the_blocking_filter_differently() -> None:
    hits = {}
    for path in sorted(_PLUGIN_ROOT.rglob("*")):
        if path.suffix not in (".md", ".py") or not path.is_file():
            continue
        found = restated_filters(path.read_text(encoding="utf-8"))
        if found:
            hits[str(path.relative_to(_PLUGIN_ROOT))] = found
    assert not hits, (
        f"these files tell the reader to fix every Critical and Important finding; "
        f"the rule is `_shared/references/blocking-findings.md` (fix the blocking ones, "
        f"send the rest to TODO.md): {hits}"
    )
