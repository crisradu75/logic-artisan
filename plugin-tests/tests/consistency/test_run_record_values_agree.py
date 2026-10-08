"""The writer's allowed values and the spec-to-pr retro's agree.

`lib/log_run.py`'s `SHAPES` decides what a spec-to-pr record may hold; the retro's
`spec_to_pr_aggregate.py` reads phases by name and reasons by status. The
aggregator runs as a standalone program and imports nothing from the plugin — the
same reason it carries its own copy of `_runs_dir` — so the names it matches are
copies, and this test keeps them inside what the writer accepts. A phase name the
reader matches and the writer refuses is a metric no record can feed, and it reads
as zero, not as broken.

The aggregator holds the migration's placeholders for the same cause, and the
last test keeps each pair equal too.
"""

from __future__ import annotations

import log_run
import migrate_run_records as mig
import spec_to_pr_aggregate as agg


def test_every_phase_the_aggregator_reads_is_one_the_writer_accepts() -> None:
    named = {*agg.CAPPED_PHASES, *agg.NUDGE_PHASES, *agg.RESIDUE_PHASES, agg.FINDINGS_PHASE}
    assert named <= set(log_run.SPEC_TO_PR_PHASES), named - set(log_run.SPEC_TO_PR_PHASES)


def test_the_phases_that_must_carry_a_rounds_pair_are_all_counted() -> None:
    # The writer requires the pair on these, so the cap metrics must count them;
    # and the nudge reads only phases whose pair is required, since a cap hit on
    # a phase that may omit it would go unseen.
    assert set(log_run.ROUNDS_REQUIRED_ON) <= set(agg.CAPPED_PHASES)
    assert set(agg.NUDGE_PHASES) <= set(log_run.ROUNDS_REQUIRED_ON)
    # A phase whose cap hit needs residue must be one the cap metrics count.
    assert set(agg.RESIDUE_PHASES) <= set(agg.CAPPED_PHASES)


def test_the_statuses_read_for_a_reason_are_the_ones_the_writer_requires_it_on() -> None:
    record = {"name": "Ship", "status": None}
    requiring = []
    for status in log_run.STATUSES:
        record["status"] = status
        if any("`reason` is required" in p for p in log_run._phase_rule(record)):
            requiring.append(status)
    assert list(agg.REASON_STATUSES) == requiring


def test_the_migration_placeholders_are_the_ones_the_aggregator_sets_apart() -> None:
    assert agg.UNRECORDED_REASON == mig.NO_REASON
    assert agg.PARTIAL_REASON == mig.PARTIAL_REASON
    assert set(agg.PLACEHOLDER_REASONS) == {mig.NO_REASON, mig.PARTIAL_REASON}
    assert agg.NOT_RECORDED == mig.NOT_RECORDED
