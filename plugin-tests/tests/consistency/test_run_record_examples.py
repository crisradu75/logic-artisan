"""The example each run-record recipe builds from is a record the writer accepts.

Both producers are told to build their record from an example and, on a refusal,
to rebuild it from that example. That only works if the example itself passes:
an example carrying `"mode": "description|explore-result|existing-change"` is
refused on every copy, and the one retry is spent on the example's own defect.
So each example is extracted from the file the recipe points at and run through
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
    ("codify-runs.jsonl", _SKILLS / "codify-learnings" / "references" / "steps.md",
     re.compile(r"## Step 7 ledger schema\n.*?```json\n(.*?)\n```", re.S)),
]


@pytest.mark.parametrize("ledger, path, fence", EXAMPLES, ids=[e[0] for e in EXAMPLES])
def test_the_example_is_a_record_the_writer_accepts(ledger: str, path: Path, fence) -> None:
    found = fence.findall(path.read_text(encoding="utf-8"))
    assert len(found) == 1, f"{path.name}: expected one example, found {len(found)}"
    record = json.loads(found[0])
    assert log_run.shape_problems(record, log_run.SHAPES[ledger]) == []
