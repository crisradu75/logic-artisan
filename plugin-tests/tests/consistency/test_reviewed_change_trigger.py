"""spec-to-pr skips its checklist pass only on a qualifying multi-spec review record.

multi-spec's review gate writes `openspec/changes/<name>/review.json` for every
change it reviews (`review-gate.md`, Step 7). spec-to-pr's Review reads it and
skips the checklist pass only when the record says READY, or FIX FIRST with
every Critical and Important finding applied and none deferred
(`spec-to-pr/SKILL.md`, Review). If either side renames the file or a field,
the other still reads fine and the skip silently stops firing, or fires on a
record that no longer says what the reader thinks it says.

Scope, stated narrowly: this pins that the writer and the reader agree, and
that the reader's rule is the fail-closed one. It does not exercise the skip,
which is prose the orchestrator runs.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_SKILLS = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "skills"
_SPEC_TO_PR = _SKILLS / "spec-to-pr" / "SKILL.md"
_REVIEW_GATE = _SKILLS / "multi-spec" / "references" / "review-gate.md"
_RUN_LOG_SCHEMA = _SKILLS / "_shared" / "references" / "run-log-schema.md"
_CHECKLIST = _SKILLS / "review-change" / "references" / "checklist.md"

_RECORD = "openspec/changes/<name>/review.json"
_FIELDS = {"verdict", "all_applied", "deferred", "artifacts", "date"}
# The digest both sides compute, with the change name spelled as each side spells it.
_DIGEST = (
    "`git ls-files -s -- openspec/changes/{n}/ ':(exclude)openspec/changes/{n}/review.json' "
    "| git hash-object --stdin`"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _example_record() -> dict:
    blocks = re.findall(r"```json\n(.*?)\n\s*```", _read(_REVIEW_GATE), re.S)
    assert len(blocks) == 1, "review-gate.md should show exactly one example record"
    return json.loads(blocks[0])


# scenario: cla-plugin / A READY change gets a review record
def test_multi_spec_writes_a_record_for_every_change_whatever_its_verdict():
    text = _read(_REVIEW_GATE)
    assert f"**Write a review record into every reviewed change, whatever its verdict**, as `{_RECORD}`." in text
    # The record must reach the commit, so the add must cover the change directories.
    assert "git add -- openspec/changes/" in text


# scenario: cla-plugin / A finding deferred out of scope
def test_the_example_record_has_exactly_the_documented_fields():
    record = _example_record()
    assert set(record) == _FIELDS
    text = _read(_REVIEW_GATE)
    for field in _FIELDS:
        assert f"   - `{field}` — " in text, f"review-gate.md does not define `{field}`"


def test_a_batch_of_one_still_reaches_the_record():
    # Step 1 hands a one-change batch to the single-change checklist; without
    # this sentence that change never gets a record and is always reviewed twice.
    assert "Then go to Step 7 with that change's verdict, so it still gets its fixes applied and its review record written." in _read(_REVIEW_GATE)


def test_the_verdict_values_match_the_rubric():
    assert "`READY`, `FIX FIRST` or `RETHINK`" in _read(_REVIEW_GATE)
    assert "**Verdict: READY / FIX FIRST / RETHINK**" in _read(_CHECKLIST)


# scenario: cla-plugin / A change edited after multi-spec's review
# scenario: cla-plugin / An edit squashed in after multi-spec's review
def test_both_sides_compute_the_same_artifact_digest():
    assert _DIGEST.format(n="<name>") in _read(_REVIEW_GATE)
    assert _DIGEST.format(n="<change-name>") + " equals the record's `artifacts`" in _read(_SPEC_TO_PR)


def test_the_digest_is_taken_from_the_staged_fixes():
    # `git ls-files -s` reads the index, so unstaged fixes would be digested as
    # their pre-fix content and the record would never match the merged change.
    assert "Stage the fixes first, `git add -- openspec/changes/`, because `artifacts` digests the staged files." in _read(_REVIEW_GATE)


def test_spec_to_pr_reads_the_record_multi_spec_writes():
    assert "`openspec/changes/<change-name>/review.json`" in _read(_SPEC_TO_PR)


# scenario: cla-plugin / A change multi-spec passed
# scenario: cla-plugin / A change multi-spec did not pass
def test_spec_to_pr_skips_only_on_a_qualifying_record():
    text = _read(_SPEC_TO_PR)
    # One sentence, so RETHINK, a partial apply or a deferral cannot slip in.
    assert (
        "The record parses as JSON, its `verdict` is `READY` or `FIX FIRST`, "
        "`all_applied` is `true`, and `deferred` is empty."
    ) in text


# scenario: cla-plugin / A change with no usable review record
def test_spec_to_pr_fails_closed_on_a_missing_or_unreadable_record():
    assert (
        "Skip only when all of these hold; anything else, including a missing or "
        "unreadable record, runs the full checklist:"
    ) in _read(_SPEC_TO_PR)


def test_spec_to_pr_carries_deferred_findings_into_a_full_review():
    assert (
        "When a readable record lists `deferred` findings, the full checklist takes "
        "each one as a known issue"
    ) in _read(_SPEC_TO_PR)


def test_the_skip_logs_the_verdict_it_trusted():
    reason = '`reason: "reviewed by multi-spec: <verdict>"`'
    assert reason in _read(_SPEC_TO_PR)
    assert reason in _read(_RUN_LOG_SCHEMA)
