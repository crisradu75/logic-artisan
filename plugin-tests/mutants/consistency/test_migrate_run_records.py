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

**The mutants after the marker are the review findings on C1:** a findings map
emptied by the move dropped rather than left `{}`, and per-agent severity counts
mapped to `found` only where the record leaves no doubt (S4), the one history gap
excused and nothing wider (Choice 1), and a junk `ts` giving way to `started` (d).
The Review-gate and Revise-agents mappings went when the record dropped those
fields.

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
LOG_RUN = DEV.parent / ".claude" / "plugins" / "cla" / "lib" / "log_run.py"
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
        "`rounds` is not read as `rounds_used`, so chain records lose every round count",
        SCRIPT,
        '    if "rounds_used" not in out and "rounds" in side:',
        '    if "rounds_used" not in out and "rounds_x" in side:',
        TARGETS,
    ),
    (
        "a side-block value is lifted without checking it, so a count where a list "
        "belongs makes the whole record unmappable",
        SCRIPT,
        "                if key not in entry and _field_ok(key, value):",
        "                if key not in entry:",
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
        "        if problems:",
        "        if problems and False:",
        TARGETS,
    ),
    (
        "a dry run writes the file",
        SCRIPT,
        "    if migrated and not dry_run:",
        "    if migrated:",
        TARGETS,
    ),
    # --- review findings on C1 ------------------------------------------------
    (
        # S4. `{}` left behind reads as "Revise found nothing".
        "a findings map emptied by the move is left as `{}` instead of dropped",
        SCRIPT,
        "        elif kept:",
        "        else:",
        TARGETS,
    ),
    (
        "per-agent severity counts are moved aside instead of mapped",
        SCRIPT,
        "            counts = _severity_counts(value)",
        "            counts = None",
        TARGETS,
    ),
    (
        "`found` counts suggestions too",
        SCRIPT,
        '    return {"found": value.get("critical", 0) + value.get("important", 0), "phantom": 0}',
        '    return {"found": sum(value.values()), "phantom": 0}',
        TARGETS,
    ),
    (
        # The ambiguous one: are the phantoms within critical+important or beside?
        "a severity map carrying `phantom` is mapped as if its meaning were known",
        SCRIPT,
        "    if not isinstance(value, dict) or not set(value) <= _SEVERITY_ONLY:",
        '    if not isinstance(value, dict) or not set(value) <= _SEVERITY_ONLY | {"phantom"}:',
        TARGETS,
    ),
    (
        # Choice 1. History without a rounds pair is reported unmappable and left
        # in its old shape — or, the other way, any refusal is excused.
        "the rounds-pair gap is not excused, so a record that never had the pair "
        "cannot be migrated at all",
        SCRIPT,
        "    return [p for p in log_run.shape_problems(rec, SHAPE) if not _HISTORY_GAP.match(p)]",
        "    return log_run.shape_problems(rec, SHAPE)",
        TARGETS,
    ),
    (
        # `(Test|Revise)` and `(\w+)` agree on every clause the writer emits today,
        # so this survived until a test stated the pattern's scope directly. The
        # INPUT mutant below covers what the scope is for.
        "the gap pattern excuses the clause on any phase, not only Test and Revise",
        SCRIPT,
        '_HISTORY_GAP = re.compile(r"^`rounds_used` and `rounds_cap` are required on a (Test|Revise) "',
        '_HISTORY_GAP = re.compile(r"^`rounds_used` and `rounds_cap` are required on a (\\w+) "',
        TARGETS,
    ),
    (
        # Mutating the INPUT: when the writer starts requiring the pair on another
        # phase, history missing it there must be reported, not silently excused.
        "the writer starts requiring the rounds pair on Review, and Review history "
        "missing it goes unreported",
        LOG_RUN,
        'ROUNDS_REQUIRED_ON = ("Test", "Revise")',
        'ROUNDS_REQUIRED_ON = ("Test", "Revise", "Review")',
        TARGETS,
    ),
    (
        "the gap excuses every refusal",
        SCRIPT,
        "    return [p for p in log_run.shape_problems(rec, SHAPE) if not _HISTORY_GAP.match(p)]",
        "    return []",
        TARGETS,
    ),
    (
        # nit (d). A junk `ts` overwrote the date derived from `started`.
        "a junk `ts` survives over the date the record's own `started` gives",
        SCRIPT,
        "        if key == \"ts\" and ts:",
        "        if key == \"ts\" and ts_from == \"ts\":",
        TARGETS,
    ),
    (
        "the junk `ts` is lost rather than kept beside",
        SCRIPT,
        '                out["ts_unmapped"] = value',
        "                pass",
        TARGETS,
    ),
]
