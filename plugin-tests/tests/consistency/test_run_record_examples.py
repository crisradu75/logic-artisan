"""The example each run-record recipe builds from is a record the writer accepts.

The producer is told to build its record from an example and, on a refusal,
to rebuild it from that example. That only works if the example itself passes:
an example carrying `"mode": "description|explore-result|existing-change"` is
refused on every copy, and the one retry is spent on the example's own defect.
So the example is extracted from the file the recipe points at and run through
`SHAPES` exactly as written.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import log_run

_SKILLS = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "skills"

# (ledger, file the recipe points at, how the example is fenced there)
EXAMPLES = [
    ("spec-to-pr-runs.jsonl", _SKILLS / "_shared" / "references" / "run-log-schema.md",
     re.compile(r"spec-to-pr-runs\.jsonl <<'JSON'\n(.*?)\nJSON\n", re.S)),
]


# requirement: run-ledgers / The spec-to-pr run record
@pytest.mark.parametrize("ledger, path, fence", EXAMPLES, ids=[e[0] for e in EXAMPLES])
def test_the_example_is_a_record_the_writer_accepts(ledger: str, path: Path, fence) -> None:
    found = fence.findall(path.read_text(encoding="utf-8"))
    assert len(found) == 1, f"{path.name}: expected one example, found {len(found)}"
    record = json.loads(found[0])
    assert log_run.shape_problems(record, log_run.SHAPES[ledger]) == []
    # The example carries every field the record defines, so a model copying it
    # leaves none out: an optional field missing from the example is one no run writes.
    shape = log_run.SHAPES[ledger]
    assert set(record) == set(shape[1]) | set(shape[2])


# requirement: run-ledgers / The spec-to-pr run record
def test_the_diagnose_escalation_is_counted_where_it_happens() -> None:
    # Handoff writes the count at the end of a long run; counted only then, it
    # is rebuilt from memory of the Test loop.
    text = (_SKILLS / "spec-to-pr" / "SKILL.md").read_text(encoding="utf-8")
    site = text.index("escalate to `/cla:diagnose` via `Skill(cla:diagnose)`")
    assert "add one to the run's `escalated_to_diagnose` count now" in text[site:site + 300]
