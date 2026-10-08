"""The writer's allowed values and the spec-to-pr retro's agree.

`lib/log_run.py`'s `SHAPES` decides what a spec-to-pr record may hold; the retro's
`spec_to_pr_aggregate.py` decides what it counts as signal and what as drift. The
aggregator runs as a standalone program and imports nothing from the plugin — the
same reason it carries its own copy of `_runs_dir` — so its lists are copies, and
this test is what keeps the copies equal. A value the writer accepts and the reader
does not know reads as producer drift on a record that is correct; a value the
reader knows and the writer refuses is a branch no record can reach.

The aggregator holds the migration's placeholder reason for the same cause, and
the last test keeps that pair equal too.
"""

from __future__ import annotations

import re
from pathlib import Path

import log_run
import migrate_run_records as mig
import spec_to_pr_aggregate as agg

_SOURCE = Path(agg.__file__).read_text(encoding="utf-8")


def test_size_gates_agree() -> None:
    assert agg.VALID_SIZE_GATES == set(log_run.SIZE_GATES)


def test_verdicts_agree() -> None:
    assert agg.VALID_VERDICTS == set(log_run.VERDICTS)


def test_revise_agent_ids_agree() -> None:
    # The aggregator keys agents after `_normalize_agent` (`plugin-dev:` -> `plugin-dev-`),
    # so it is the writer's list through that same function that must match.
    assert agg.REVISE_AGENT_NAMES == {agg._normalize_agent(a) for a in log_run.REVISE_AGENTS}


def test_every_phase_the_aggregator_names_is_one_the_writer_accepts() -> None:
    named = set(re.findall(r'\bname == "(\w+)"', _SOURCE))
    assert named, "the aggregator names no phase — the pattern no longer reads it"
    assert named <= set(log_run.SPEC_TO_PR_PHASES), named - set(log_run.SPEC_TO_PR_PHASES)
    # The looping phases: the ones the cap metrics count are the ones that carry a
    # rounds pair, and the two the writer requires it on are among them.
    caps = re.search(r"cap_hit = \{([^}]*)\}", _SOURCE)
    assert caps, "cap_hit is no longer a literal the test can read"
    capped = set(re.findall(r'"(\w+)"', caps.group(1)))
    assert capped <= {p.lower() for p in log_run.SPEC_TO_PR_PHASES}
    assert {p.lower() for p in log_run.ROUNDS_REQUIRED_ON} <= capped


def test_statuses_agree() -> None:
    # The output schema in the docstring lists the statuses the tally reports...
    outcomes = re.search(r'"phase_outcomes": \{<phase>: \{([^}]*)\}\}', agg.__doc__)
    assert outcomes, "the docstring's phase_outcomes line is no longer readable"
    assert re.findall(r'"(\w+)": n', outcomes.group(1)) == list(log_run.STATUSES)
    # ...and the statuses that carry a reason are the ones the writer requires it on.
    read = re.findall(r'status in \(("\w+"(?:, "\w+")*)\) and phase\.get\("reason"\)', _SOURCE)
    assert read == ['"warn", "fail"']
    record = {"name": "Ship", "status": None}
    requiring = []
    for status in log_run.STATUSES:
        record["status"] = status
        if any("`reason` is required" in p for p in log_run._phase_rule(record)):
            requiring.append(status)
    assert requiring == ["warn", "fail"]


def test_the_migration_placeholder_is_the_one_the_aggregator_sets_apart() -> None:
    assert agg.UNRECORDED_REASON == mig.NO_REASON
