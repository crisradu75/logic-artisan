"""Mutation batch for test_spec_to_pr_aggregate.py.

The aggregator's output is what a retro proposes orchestrator changes FROM, and
its `--nudge` line is what sends a user to the retro at all. So the mutants are
the edits that would change a number a reader acts on without anything looking
wrong: a threshold off by one, a window that silently widens, a placeholder
counted as a real reason, a routine Revise round 2 counted as cap exhaustion.

**NEITHER SHARED-COPY FUNCTION IS MUTATED HERE.** `_git_toplevel` and
`_runs_dir` are copies of `lib/log_run.py`'s; the directory resolver is mutated
in `mutants/consistency/test_ledger_dir_agrees.py`, and the phase and status
constants in `mutants/consistency/test_run_record_values_agree.py`. `_fleet_roots`
is no copy any more — its twin went with the generic ledger reader — so its two
parsing rules are mutated below.

`_cap_hit` uses `>=` because the writer accepts `rounds_used > rounds_cap`; the
tests write such a record, so `==` is a killable mutant here.

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
        "a line that is not UTF-8 ends the whole run again",
        SCRIPT,
        "            except UnicodeDecodeError:",
        "            except KeyError:",
        TARGETS,
    ),
    (
        "a skipped line is no longer named on stderr",
        SCRIPT,
        "                if not quiet:",
        "                if False:",
        TARGETS,
    ),
    (
        "--nudge names every unreadable line of the whole ledger again",
        SCRIPT,
        "            line = nudge(_load(path, quiet=True)[0]) if path.exists() else None",
        "            line = nudge(_load(path)[0]) if path.exists() else None",
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
        "        kept = records[-args.limit:] if args.limit > 0 else records",
        "        kept = records",
        TARGETS,
    ),
    # --- window metrics -----------------------------------------------------
    (
        "the migration's placeholder is ranked with the real reasons",
        SCRIPT,
        "            if reason in PLACEHOLDER_REASONS:",
        "            if False:",
        TARGETS,
    ),
    (
        "the migration's `partial` placeholder is ranked, and can nudge, as a real reason",
        SCRIPT,
        "PLACEHOLDER_REASONS = (UNRECORDED_REASON, PARTIAL_REASON)",
        "PLACEHOLDER_REASONS = (UNRECORDED_REASON,)",
        TARGETS,
    ),
    (
        "asks under the migration's placeholder header are tallied as one question",
        SCRIPT,
        "            if ask[\"header\"] == NOT_RECORDED:  # one header for every question",
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
        '    if not (cap > 1 and phase.get("rounds_used", 0) >= cap):',
        '    if not (cap > 0 and phase.get("rounds_used", 0) >= cap):',
        TARGETS,
    ),
    (
        "more rounds than the cap, which the writer accepts, stops counting as a hit",
        SCRIPT,
        '    if not (cap > 1 and phase.get("rounds_used", 0) >= cap):',
        '    if not (cap > 1 and phase.get("rounds_used", 0) == cap):',
        TARGETS,
    ),
    (
        "Revise's routine round 2 counts as exhaustion",
        SCRIPT,
        '    return phase["name"] not in RESIDUE_PHASES or phase["status"] in REASON_STATUSES',
        "    return True",
        TARGETS,
    ),
    (
        "Test needs a warn too, so a clean Test that used every round stops counting",
        SCRIPT,
        '    return phase["name"] not in RESIDUE_PHASES or phase["status"] in REASON_STATUSES',
        '    return phase["status"] in REASON_STATUSES',
        TARGETS,
    ),
    (
        "a Revise that failed at its cap is not counted as leaving findings open",
        SCRIPT,
        '    return phase["name"] not in RESIDUE_PHASES or phase["status"] in REASON_STATUSES',
        '    return phase["name"] not in RESIDUE_PHASES or phase["status"] == "warn"',
        TARGETS,
    ),
    (
        "an agent's runs stop being counted, so found/runs has no denominator",
        SCRIPT,
        '            findings[agent]["runs"] += 1',
        '            findings[agent]["runs"] += 0',
        TARGETS,
    ),
    # --- round-2 yield -----------------------------------------------------
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
    # --- the nudge ----------------------------------------------------------
    (
        "the nudge reads the whole ledger, so old cap hits keep nudging",
        SCRIPT,
        "    recent = records[-NUDGE_RUNS:]",
        "    recent = records",
        TARGETS,
    ),
    (
        "the nudge line names only warn, though a Revise that failed at its cap counts too",
        SCRIPT,
        '            still = " and still warned or failed" if name in RESIDUE_PHASES else ""',
        '            still = " and still warned" if name in RESIDUE_PHASES else ""',
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
        "    seen = Counter(r for rec in recent for r in set(_reasons(rec)) if r not in PLACEHOLDER_REASONS)",
        "    seen = Counter(r for rec in recent for r in _reasons(rec) if r not in PLACEHOLDER_REASONS)",
        TARGETS,
    ),
    (
        "the migration placeholder recurring nudges",
        SCRIPT,
        "    seen = Counter(r for rec in recent for r in set(_reasons(rec)) if r not in PLACEHOLDER_REASONS)",
        "    seen = Counter(r for rec in recent for r in set(_reasons(rec)))",
        TARGETS,
    ),
    # --- the fleet file, now read here only -----------------------------------
    (
        "an inline `#` comment is read as part of the repo root",
        SCRIPT,
        '        item = line[2:].split("#", 1)[0].strip().strip("`").strip()',
        '        item = line[2:].strip().strip("`").strip()',
        TARGETS,
    ),
    (
        "a root in backticks is read with its backticks",
        SCRIPT,
        '        item = line[2:].split("#", 1)[0].strip().strip("`").strip()',
        '        item = line[2:].split("#", 1)[0].strip()',
        TARGETS,
    ),
    # --- flags and diagnose escalations ------------------------------------
    (
        "a run naming one flag twice counts as two runs using it",
        SCRIPT,
        '            flags.update(set(rec["flags"]))',
        '            flags.update(rec["flags"])',
        TARGETS,
    ),
    (
        "a record written before `flags` existed counts as a run with no flags",
        SCRIPT,
        '        if "flags" in rec:  # absent on records written before the field existed',
        "        if True:",
        TARGETS,
    ),
    (
        "flags tied on count come out in file order, not by name",
        SCRIPT,
        "                  \"runs\": dict(sorted(flags.items(), key=lambda kv: (-kv[1], kv[0])))},",
        "                  \"runs\": dict(flags.most_common())},",
        TARGETS,
    ),
    (
        "a run with zero escalations counts as a run that escalated",
        SCRIPT,
        '            diagnose["runs"] += rec["escalated_to_diagnose"] > 0',
        '            diagnose["runs"] += 1',
        TARGETS,
    ),
    (
        "a diagnose count that is not a count is read rather than skipped",
        SCRIPT,
        '    if "escalated_to_diagnose" in rec and not _is_int(rec["escalated_to_diagnose"]):',
        "    if False:",
        TARGETS,
    ),
    (
        "a flag that is not a string is read rather than skipped",
        SCRIPT,
        "    if not (isinstance(flags, list) and all(isinstance(f, str) for f in flags)):",
        "    if not isinstance(flags, list):",
        TARGETS,
    ),
]
