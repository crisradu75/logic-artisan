"""Mutation batch for test_spec_to_pr_aggregate.py.

The aggregator's output is what a retro proposes orchestrator changes FROM, and
its `--nudge` line is what sends a user to the retro at all. So the mutants are
the edits that would change a number a reader acts on without anything looking
wrong: a threshold off by one, a window that silently widens, a placeholder
counted as a real reason, a reversal check that reads only the recent window.

**NONE OF THE SHARED-COPY FUNCTIONS IS MUTATED HERE.** `_git_toplevel`,
`_runs_dir` and `_fleet_roots` are copies of `lib/` code; the directory resolver
is mutated in `mutants/consistency/test_ledger_dir_agrees.py`, and the phase and
status constants in `mutants/consistency/test_run_record_values_agree.py`.

**DELIBERATELY NOT A MUTANT:** `used == cap` -> `used >= cap` in `_cap_hit`. The
writer does not refuse `rounds_used > rounds_cap`, but no real run can use more
rounds than its cap, so the two expressions agree on every record a correct
producer writes. A fixture with `used > cap` would pin behaviour for an input that
cannot occur — mutating the input, not the guard, has nothing honest to mutate.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/spec-to-pr-retro/test_spec_to_pr_aggregate.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"

SCRIPT = PLUGIN / "skills" / "spec-to-pr-retro" / "scripts" / "spec_to_pr_aggregate.py"

TARGETS = [
    DEV / "tests" / "skills" / "spec-to-pr-retro" / "test_spec_to_pr_aggregate.py"
]

MUTANTS = [
    # --- reading ------------------------------------------------------------
    (
        "a bool passes as a count, so `true` reads as one round",
        SCRIPT,
        "    return type(value) is int  # bool is an int subclass and is not a count",
        "    return isinstance(value, int)",
        TARGETS,
    ),
    (
        "an unreadable line is dropped without being counted",
        SCRIPT,
        "                skipped += 1",
        "                pass",
        TARGETS,
    ),
    (
        "a ledger named twice is read twice, doubling every count",
        SCRIPT,
        "        if key in seen:  # one ledger named twice would double every count",
        "        if False:",
        TARGETS,
    ),
    (
        "a fleet file listing only another machine's paths is read as the fleet, "
        "reporting nothing — which reads as a cold start",
        SCRIPT,
        "    if not any(root.is_dir() for root in roots):",
        "    if False:",
        TARGETS,
    ),
    (
        "--limit stops applying, so the window is the whole history",
        SCRIPT,
        "        window += records[-args.limit:] if args.limit > 0 else records",
        "        window += records",
        TARGETS,
    ),
    # --- window metrics -----------------------------------------------------
    (
        "the migration's placeholder is ranked with the real reasons",
        SCRIPT,
        "            if reason == UNRECORDED_REASON:",
        "            if False:",
        TARGETS,
    ),
    (
        "warn_reasons stops keeping only the top ten",
        SCRIPT,
        "warn_reasons.most_common(10)]",
        "warn_reasons.most_common()]",
        TARGETS,
    ),
    (
        "a single-pass phase joins the exhaustion denominator and depresses the rate",
        SCRIPT,
        '            if phase["name"] in caps and phase.get("rounds_cap", 0) > 1:',
        '            if phase["name"] in caps and phase.get("rounds_cap", 0) > 0:',
        TARGETS,
    ),
    (
        "a cap of 1 reached counts as exhaustion",
        SCRIPT,
        '    return cap > 1 and phase.get("rounds_used") == cap',
        '    return cap > 0 and phase.get("rounds_used") == cap',
        TARGETS,
    ),
    (
        "an agent's runs stop being counted, so found/runs has no denominator",
        SCRIPT,
        '            findings[agent]["runs"] += 1',
        '            findings[agent]["runs"] += 0',
        TARGETS,
    ),
    # --- the reversal check -------------------------------------------------
    (
        "the reversal check reads only the --limit window, not every record",
        SCRIPT,
        "        everything += [(str(path), rec) for rec in records]",
        "        everything += [(str(path), rec) for rec in records[-args.limit:]]",
        TARGETS,
    ),
    (
        "a round-1-only change counts as one where a round 2 ran",
        SCRIPT,
        '                 for r in p.get("findings_by_round", []) if r["round"] >= 2]',
        '                 for r in p.get("findings_by_round", []) if r["round"] >= 1]',
        TARGETS,
    ),
    (
        "a re-run change counts twice",
        SCRIPT,
        '        key = (ledger, rec["change"])',
        '        key = (ledger, rec["change"], rec["ts"])',
        TARGETS,
    ),
    (
        "a round 2 that found nothing counts as surfacing a finding",
        SCRIPT,
        '        if any(r["found"] >= 1 for r in later):',
        '        if any(r["found"] >= 0 for r in later):',
        TARGETS,
    ),
    (
        "the chain proxy drops the ledger, so two repos on one date are one chain",
        SCRIPT,
        '        chains.add((ledger, rec["ts"][:10]))',
        '        chains.add(rec["ts"][:10])',
        TARGETS,
    ),
    (
        "a tie counts as a majority",
        SCRIPT,
        "                          and 2 * len(surfaced) > len(changes)),",
        "                          and 2 * len(surfaced) >= len(changes)),",
        TARGETS,
    ),
    (
        "seven changes satisfy the eight-change floor",
        SCRIPT,
        "REVERSAL_MIN_CHANGES = 8",
        "REVERSAL_MIN_CHANGES = 7",
        TARGETS,
    ),
    (
        "one chain satisfies the two-chain floor",
        SCRIPT,
        "REVERSAL_MIN_CHAINS = 2",
        "REVERSAL_MIN_CHAINS = 1",
        TARGETS,
    ),
    # --- the nudge ----------------------------------------------------------
    (
        "the nudge reads the whole ledger, so old cap hits keep nudging",
        SCRIPT,
        "    recent = records[-NUDGE_RUNS:]",
        "    recent = records",
        TARGETS,
    ),
    (
        "two cap hits nudge",
        SCRIPT,
        "NUDGE_CAP_HITS = 3",
        "NUDGE_CAP_HITS = 2",
        TARGETS,
    ),
    (
        "a reason must recur three times to nudge",
        SCRIPT,
        "NUDGE_SAME_REASON = 2",
        "NUDGE_SAME_REASON = 3",
        TARGETS,
    ),
    (
        "one run warning twice with one reason counts as the reason recurring",
        SCRIPT,
        "    seen = Counter(r for rec in recent for r in set(_reasons(rec)) if r != UNRECORDED_REASON)",
        "    seen = Counter(r for rec in recent for r in _reasons(rec) if r != UNRECORDED_REASON)",
        TARGETS,
    ),
    (
        "the migration placeholder recurring nudges",
        SCRIPT,
        "    seen = Counter(r for rec in recent for r in set(_reasons(rec)) if r != UNRECORDED_REASON)",
        "    seen = Counter(r for rec in recent for r in set(_reasons(rec)))",
        TARGETS,
    ),
]
