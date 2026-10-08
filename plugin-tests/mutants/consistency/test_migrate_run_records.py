"""Mutation batch for test_migrate_run_records.py.

The migration is run once per repo and its output is committed, so a defect in it
is written into history rather than printed and forgotten. Each mutant below
breaks one mapping the fleet's real records need, or one of the three promises
the script makes about a file: a line already in shape is left byte for byte, a
line it cannot map is left byte for byte, and a dry run writes nothing.

Mutant 3 is the reason the script reads `git log -L` and not `git blame`: taking
the NEWEST commit in a line's history instead of the oldest dates a run by the
last edit to its line, which in one real ledger is a docs commit three weeks
after the run.

**DELIBERATELY NOT MUTANTS:**

  * `_History`'s `timeout=60` — no test makes git hang.
  * `notes` de-duplication (`dict.fromkeys`) — the notes are printed, and no
    assertion reads a note that a duplicate would change.
  * the `os.replace` temp-file write — swapping it for a direct write is
    unobservable in a test that does not crash mid-write.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_migrate_run_records.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
SCRIPT = DEV / "scripts" / "migrate_run_records.py"
TARGETS = [DEV / "tests" / "consistency" / "test_migrate_run_records.py"]

MUTANTS = [
    (
        "a `date` maps to noon rather than the start of its day",
        SCRIPT,
        '        return value + "T00:00:00Z"',
        '        return value + "T12:00:00Z"',
        TARGETS,
    ),
    (
        "a record already in shape is reported as migrated, so a second pass is "
        "never a no-op",
        SCRIPT,
        "        return rec, []",
        '        return rec, ["re-checked"]',
        TARGETS,
    ),
    (
        "an undated record takes the time of the LAST edit to its line — `git blame`'s "
        "answer — instead of the commit that appended it",
        SCRIPT,
        "        when = datetime.fromtimestamp(int(stamps[-1]), tz=timezone.utc)",
        "        when = datetime.fromtimestamp(int(stamps[0]), tz=timezone.utc)",
        TARGETS,
    ),
    (
        "a working copy that differs from HEAD borrows HEAD's line history",
        SCRIPT,
        "                or self.head[line_no - 1].strip() != self.current[line_no - 1].strip()):",
        "                or False):",
        TARGETS,
    ),
    (
        "a warn with no reason is left without one, so the record still fails",
        SCRIPT,
        '            entry["reason"] = NO_REASON',
        "            pass",
        TARGETS,
    ),
    (
        "`partial` is carried through as a status the reader does not count",
        SCRIPT,
        '            entry["status"] = "warn"',
        '            entry["status"] = "partial"',
        TARGETS,
    ),
    (
        "a side block's `rounds` is lifted with no cap to pair it, then parked "
        "beside the phase as if the record had carried it there",
        SCRIPT,
        '                del lifted["rounds_used"]  # still in the side block, where it came from',
        "                pass",
        TARGETS,
    ),
    (
        "round-2 agents are dropped from Revise's dispatch list",
        SCRIPT,
        '        for key in ("agents_round1", "agents_round2", "agents_dispatched"):',
        '        for key in ("agents_round1", "agents_dispatched"):',
        TARGETS,
    ),
    (
        "`rounds` is not read as `rounds_used`, so chain records lose every round count",
        SCRIPT,
        '    if "rounds_used" not in out and "rounds" in side:',
        '    if "rounds_used" not in out and "rounds_x" in side:',
        TARGETS,
    ),
    (
        "a side-block value is lifted without checking it, so `FIX_FIRST` makes the "
        "whole record unmappable",
        SCRIPT,
        "                if key not in entry and _field_ok(key, value):",
        "                if key not in entry:",
        TARGETS,
    ),
    (
        "a Review gate that contradicts its agents is left in place",
        SCRIPT,
        '                or (entry["size_gate"] == "large") != bool(entry.get("agents"))):',
        "                or False):",
        TARGETS,
    ),
    (
        "dict `asks` lose their choices",
        SCRIPT,
        '        asks = [{"header": NOT_RECORDED, "choice": c} for c in choices]',
        "        asks = []",
        TARGETS,
    ),
    (
        "`code_reviewer`-style keys are not re-spelled, so their counts are moved aside",
        SCRIPT,
        '        agent = key.replace("_", "-") if isinstance(key, str) else key',
        "        agent = key",
        TARGETS,
    ),
    (
        "a record it cannot map is rewritten anyway",
        SCRIPT,
        "        if problem:",
        "        if problem and False:",
        TARGETS,
    ),
    (
        "a dry run writes the file",
        SCRIPT,
        "    if migrated and not dry_run:",
        "    if migrated:",
        TARGETS,
    ),
]
