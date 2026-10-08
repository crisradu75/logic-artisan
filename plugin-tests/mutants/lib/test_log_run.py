"""Mutation batch for test_log_run.py.

CLAUDE.md's script table justifies `log_run.py` as "the one ledger writer:
validates the record, enforces the 4 KiB atomic-append ceiling, refuses every
ledger name but `spec-to-pr-runs.jsonl`". Those are three separable claims and this batch
breaks each of them, because each fails silently in a different way: an
off-shape record is one the retro skips, an oversize record interleaves bytes
inside one line under concurrency, and any other name starts a file nothing
reads, or writes outside the ledger directory entirely.

**Mutant 4 is inside `_runs_dir`**, whose logic has a copy in the aggregator.
It edits only an error message, which the writer/reader agreement test
(`tests/consistency/test_ledger_dir_agrees.py`) does not read, and `TARGETS` is
the single guard file, so the kill attributes to this guard.

**One candidate was rejected for a SIDE EFFECT rather than for being unkillable.**
Defeating `if not path.is_absolute():` makes the child write
`relative/retro/spec-to-pr-runs.jsonl` relative to the pytest process cwd — i.e.
into the working tree. `mutate.py` restores the mutated SOURCE but does not
remove a file the mutant's run created, so the batch would litter the repo. The
message mutant (mutant 4) pins the same test without writing anything.

**DELIBERATELY NOT MUTANTS, each unkillable in a correct tree:**

  * `>= 4096` -> `> 4096`. Nothing in the suite sits at exactly 4096 bytes, so the
    two comparisons agree on every input. Mutant 1 changes the MAGNITUDE instead,
    which the ~5 KB record does discriminate.
  * `timeout=10` in `_git_toplevel` -> any other value. No test makes git hang.
  * `_runs_dir() / ledger` -> `_runs_dir() / "spec-to-pr-runs.jsonl"`. With one
    accepted name the two are the same path; it was a mutant while there were two.
  * `_pin_streams_utf8`'s body -> `pass`. Every message the tests read back is
    ASCII, and the ledger write goes through `sys.stdin.buffer` and an explicit
    `encode("utf-8")`, never the reconfigured streams.

**Mutants 7 onward are the record-shape check.** Mutant 8 is the dropped
2026-09-05 proposal's own failure, restored on purpose: a check that sees the
`phases` KEY and not its VALUE accepts `phases` written as an object, which is the
drift that motivated the check. The rest each loosen one rule the fleet's real
records broke — a date where a date-time belongs, `true` where a count belongs, a
warn with no reason, half a rounds pair — or one of the four places the walker
descends (list items, map values, optional keys, an object's rule).

**DELIBERATELY NOT A MUTANT, for the shapes:** `_shown`'s 40-character cut. No
test reads back a value that long, and the refusal names the field either way.

**The mutants after the C1 marker are its review findings:** every problem on the
one line (S1) — at the join, in the object walk, and in the findings key rule —
the rule gated on conforming required keys, and the rounds pair required on a
Test or Revise that ran (Choice 1). The object-walk mutant writes a newline into
the source through `\n` in its REPLACEMENT, never its anchor, so it holds on
either checkout. (The Review-pair and Revise-agents mutants went with those
fields, in retire-unread-ledgers.)

**The last four are the fields retire-unread-ledgers added:** a flag spelled two ways, or with its value, would
split one flag's count, and a diagnose count that is not a count reads as zero.

And one honest limit, recorded rather than chased:
`test_nothing_is_written_when_the_record_is_rejected` is a real test but is not
independently pinnable — no single-token edit makes a rejected record write
without also reddening `test_rejects_malformed_json`.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/lib/test_log_run.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"

SCRIPT = PLUGIN / "lib" / "log_run.py"

TARGETS = [DEV / "tests" / "lib" / "test_log_run.py"]

MUTANTS = [
    (
        # The ceiling is about ATOMICITY, not disk: POSIX guarantees an append
        # under PIPE_BUF lands whole. Above it two parallel sessions can
        # interleave bytes inside a single line, which corrupts the row rather
        # than losing it.
        "the atomic-append ceiling is raised past the record that tests it, so a "
        "prose-carrying record big enough to interleave under concurrency is accepted",
        SCRIPT,
        "    if len(encoded) >= 4096:",
        "    if len(encoded) >= 8192:",
        TARGETS,
    ),
    (
        # Loosening `!=` to `<` keeps the missing-argument refusal working, which
        # is what makes this a probe of the arity rule rather than of the check's
        # existence.
        "extra arguments stop being refused, so a mis-assembled command line "
        "writes to the first thing it named and silently drops the rest",
        SCRIPT,
        "    if len(args) != 1:",
        "    if len(args) < 1:",
        TARGETS,
    ),
    (
        # The old contract: any `.jsonl` name passes the name check. The record
        # then has no shape to check against, so the run dies on a traceback
        # instead of the one line naming the ledgers it may use.
        "any `.jsonl` name passes the ledger check, so a retired or misspelled "
        "ledger gets past the refusal",
        SCRIPT,
        "    if ledger not in SHAPES:",
        '    if ledger not in SHAPES and not ledger.endswith(".jsonl"):',
        TARGETS,
    ),
    (
        # The no-side-effect stand-in for the absolute-path mutant. It pins the
        # same test through its stderr assertion without letting the child write
        # anywhere.
        "the absolute-path refusal stops saying `absolute path`, so the one "
        "diagnostic telling a caller what is wrong with its override goes missing",
        SCRIPT,
        "must be an absolute path",
        "must be an abs path",
        TARGETS,
    ),
    (
        # The quietest of the lot: nothing errors, the file exists, the last run
        # is in it. A retro then reports one run and calls it the history.
        'append becomes overwrite ("ab" -> "wb"), so every run truncates the '
        "ledger and the retro reads the last run as the whole history",
        SCRIPT,
        '        with log_path.open("ab") as fh:',
        '        with log_path.open("wb") as fh:',
        TARGETS,
    ),
    (
        "unicode is escaped on the way in, so a ledger row stops being the text "
        "the session actually produced",
        SCRIPT,
        "ensure_ascii=False",
        "ensure_ascii=True",
        TARGETS,
    ),
    (
        "the shape check is computed and ignored, so every off-shape record is "
        "appended as before",
        SCRIPT,
        "    problem = shape_problem(record, SHAPES[ledger])",
        "    problem = None",
        TARGETS,
    ),
    (
        # The 2026-09-05 proposal's defect: key presence, not value shape.
        "`phases` is checked for presence only, so a dict-shaped `phases` passes",
        SCRIPT,
        '         "phases": ("list", _PHASE)},',
        '         "phases": _leaf(lambda v: v is not None, "present")},',
        TARGETS,
    ),
    (
        "a spec-to-pr `ts` may be a bare date, the shape chain runs wrote as `date`",
        SCRIPT,
        "TS = _leaf(lambda v: _iso(v, date_ok=False),",
        "TS = _leaf(lambda v: _iso(v, date_ok=True),",
        TARGETS,
    ),
    (
        "a date-time without a zone passes, so the window sorts local times as UTC",
        SCRIPT,
        r'(Z|[+-]\d{2}:\d{2})$")',
        r'(Z|[+-]\d{2}:\d{2})?$")',
        TARGETS,
    ),
    (
        "the pattern alone decides a `ts`, so month 13 day 40 is a valid time",
        SCRIPT,
        '        datetime.fromisoformat(value.replace("Z", "+00:00"))',
        "        pass",
        TARGETS,
    ),
    (
        "`true` passes as a count — Python's bool is an int",
        SCRIPT,
        'COUNT = _leaf(lambda v: type(v) is int and v >= 0, "a non-negative integer")',
        'COUNT = _leaf(lambda v: isinstance(v, int) and v >= 0, "a non-negative integer")',
        TARGETS,
    ),
    (
        "a negative count passes",
        SCRIPT,
        'COUNT = _leaf(lambda v: type(v) is int and v >= 0, "a non-negative integer")',
        'COUNT = _leaf(lambda v: type(v) is int, "a non-negative integer")',
        TARGETS,
    ),
    (
        "a warn or fail phase may omit its reason, the one field the retro groups by",
        SCRIPT,
        '    if status in ("warn", "fail") and "reason" not in phase:',
        '    if status in ("warn",) and "reason" not in phase:',
        TARGETS,
    ),
    (
        "only `rounds_used` without `rounds_cap` is caught; the other half slips",
        SCRIPT,
        '    if ("rounds_used" in phase) != ("rounds_cap" in phase):',
        '    if "rounds_used" in phase and "rounds_cap" not in phase:',
        TARGETS,
    ),
    (
        "list items are never checked, so a phase entry may be anything",
        SCRIPT,
        "        return [problem for i, item in enumerate(value)",
        "        return [problem for i, item in enumerate(value[:0])",
        TARGETS,
    ),
    (
        "a map's key rule is skipped, so legacy `opus` / `code_reviewer` keys pass",
        SCRIPT,
        "        return problems + shape[2](value)",
        "        return problems",
        TARGETS,
    ),
    (
        "optional keys are never checked once present",
        SCRIPT,
        "    for key, sub in {**required, **optional}.items():",
        "    for key, sub in required.items():",
        TARGETS,
    ),
    (
        "an object's rule is skipped, so every cross-field check goes quiet",
        SCRIPT,
        "        problems += rule(value)",
        "        pass",
        TARGETS,
    ),
    (
        "the agent list loses an id it must accept, refusing a real record",
        SCRIPT,
        '                 "comment-analyzer", "type-design-analyzer", "plugin-dev:skill-reviewer")',
        '                 "comment-analyzer", "type-design-analyzer")',
        TARGETS,
    ),
    # --- review findings on C1 ------------------------------------------------
    (
        # S1. The refusal names the first problem only; the one retry fixes it
        # and is refused again on the next.
        "the refusal line names only the first problem",
        SCRIPT,
        '    return "; ".join(shape_problems(value, shape)) or None',
        "    return (shape_problems(value, shape) or [None])[0]",
        TARGETS,
    ),
    (
        "the object walk stops at the first field with a problem",
        SCRIPT,
        "            problems += found",
        "            if found:\n                return problems + found",
        TARGETS,
    ),
    (
        # The rule reads `status` as a known value; ungated it crashes on a
        # missing one and adds clauses about a status that does not exist.
        "an object's rule runs even when its required keys are missing or off-list",
        SCRIPT,
        "    if rule and required_ok:",
        "    if rule:",
        TARGETS,
    ),
    (
        "only a missing required key gates the rule; an off-list one does not",
        SCRIPT,
        "            if found and key in required:",
        "            if found and key in optional:",
        TARGETS,
    ),
    (
        "a findings refusal names only the first bad key",
        SCRIPT,
        "    bad = [agent for agent in by_agent if agent not in REVISE_AGENTS]",
        "    bad = [agent for agent in by_agent if agent not in REVISE_AGENTS][:1]",
        TARGETS,
    ),
    (
        # Choice 1, both halves.
        "Revise may omit its rounds pair; only Test is held to it",
        SCRIPT,
        'ROUNDS_REQUIRED_ON = ("Test", "Revise")',
        'ROUNDS_REQUIRED_ON = ("Test",)',
        TARGETS,
    ),
    (
        "a skipped Test or Revise must carry a rounds pair it never had",
        SCRIPT,
        '    elif "rounds_used" not in phase and name in ROUNDS_REQUIRED_ON and status != "skip":',
        '    elif "rounds_used" not in phase and name in ROUNDS_REQUIRED_ON:',
        TARGETS,
    ),
    # --- the fields retire-unread-ledgers added -------------------------------
    (
        "a flag without its leading dashes passes, counted apart from the same flag",
        SCRIPT,
        'FLAG = _leaf(lambda v: isinstance(v, str) and len(v) > 2 and v.startswith("--")',
        'FLAG = _leaf(lambda v: isinstance(v, str) and len(v) > 2',
        TARGETS,
    ),
    (
        "a flag may carry its value after `=`, one flag per value",
        SCRIPT,
        '             and "=" not in v and not any(c.isspace() for c in v),',
        "             and not any(c.isspace() for c in v),",
        TARGETS,
    ),
    (
        "a flag may carry its value after a space, one flag per value",
        SCRIPT,
        '             and "=" not in v and not any(c.isspace() for c in v),',
        '             and "=" not in v,',
        TARGETS,
    ),
    (
        "the diagnose count may be anything, and a string reads as no escalation",
        SCRIPT,
        '         "escalated_to_diagnose": COUNT,',
        '         "escalated_to_diagnose": TEXT,',
        TARGETS,
    ),
]
