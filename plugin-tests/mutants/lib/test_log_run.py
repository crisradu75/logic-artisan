"""Mutation batch for test_log_run.py.

CLAUDE.md's script table justifies `log_run.py` as "the one ledger writer:
validates the record, enforces the 4 KiB atomic-append ceiling, refuses a
path-shaped ledger argument". Those are three separable claims and this batch
breaks each of them, because each fails silently in a different way: a wrong
ledger name splits a history nobody reads back, an oversize record interleaves
bytes inside one line under concurrency, and a path-shaped argument writes
outside the ledger directory entirely.

**Mutant 5 is inside `_runs_dir`**, whose logic has copies in three other files.
It edits only an error message, which the writer/reader agreement test
(`tests/consistency/test_ledger_dir_agrees.py`) does not read, and `TARGETS` is
the single guard file, so the kill attributes to this guard.

**One candidate was rejected for a SIDE EFFECT rather than for being unkillable.**
Defeating `if not path.is_absolute():` makes the child write
`relative/retro/spec-to-pr-runs.jsonl` relative to the pytest process cwd — i.e.
into the working tree. `mutate.py` restores the mutated SOURCE but does not
remove a file the mutant's run created, so the batch would litter the repo. The
message mutant (mutant 5) pins the same test without writing anything.

**DELIBERATELY NOT MUTANTS, each unkillable in a correct tree:**

  * `>= 4096` -> `> 4096`. Nothing in the suite sits at exactly 4096 bytes, so the
    two comparisons agree on every input. Mutant 2 changes the MAGNITUDE instead,
    which the ~5 KB record does discriminate.
  * `timeout=10` in `_git_toplevel` -> any other value. No test makes git hang.
  * `_pin_streams_utf8`'s body -> `pass`. Every message the tests read back is
    ASCII, and the ledger write goes through `sys.stdin.buffer` and an explicit
    `encode("utf-8")`, never the reconfigured streams.

**Mutants 8 onward are the record-shape check.** Mutant 9 is the dropped
2026-09-05 proposal's own failure, restored on purpose: a check that sees the
`phases` KEY and not its VALUE accepts `phases` written as an object, which is the
drift that motivated the check. The rest each loosen one rule the fleet's real
records broke — a date where a date-time belongs, `true` where a count belongs, a
warn with no reason, half a rounds pair, a large Review with no agents — or one of
the four places the walker descends (list items, map values, optional keys, an
object's rule).

**DELIBERATELY NOT A MUTANT, for the shapes:** `_shown`'s 40-character cut. No
test reads back a value that long, and the refusal names the field either way.

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
        # One writer, one file again. Every skill's record lands in the
        # orchestrator's ledger whatever ledger it named, and each retro then
        # reads a history that is partly someone else's.
        "the ledger argument is ignored and every record lands in one file",
        SCRIPT,
        "        log_path = _runs_dir() / ledger",
        '        log_path = _runs_dir() / "spec-to-pr-runs.jsonl"',
        TARGETS,
    ),
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
        # The traversal the constant exists to stop. Narrow on purpose:
        # `../escape.jsonl` and `.hidden.jsonl` are still refused by the FIRST
        # character class, so the kill names the separator case specifically.
        "the ledger-name pattern admits path separators, so a model-assembled "
        "argument writes outside the ledger directory",
        SCRIPT,
        r"[A-Za-z0-9][A-Za-z0-9._-]*\.jsonl$",
        r"[A-Za-z0-9][A-Za-z0-9._\-/\\]*\.jsonl$",
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
        "        problem = shape_problem(record, SHAPES[ledger])",
        "        problem = None",
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
        '    if phase["status"] in ("warn", "fail") and "reason" not in phase:',
        '    if phase["status"] in ("warn",) and "reason" not in phase:',
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
        "only `large` with no agents is caught; `small` listing agents slips",
        SCRIPT,
        '        if (phase["size_gate"] == "large") != bool(phase.get("agents")):',
        '        if phase["size_gate"] == "large" and not phase.get("agents"):',
        TARGETS,
    ),
    (
        "list items are never checked, so a phase entry may be anything",
        SCRIPT,
        "        for i, item in enumerate(value):",
        "        for i, item in enumerate(value[:0]):",
        TARGETS,
    ),
    (
        "a map's key rule is skipped, so legacy `opus` / `code_reviewer` keys pass",
        SCRIPT,
        "        return shape[2](value)",
        "        return None",
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
        "    return rule(value) if rule else None",
        "    return None",
        TARGETS,
    ),
    (
        "the agent list loses an id it must accept, refusing a real record",
        SCRIPT,
        '                 "comment-analyzer", "type-design-analyzer", "plugin-dev:skill-reviewer")',
        '                 "comment-analyzer", "type-design-analyzer")',
        TARGETS,
    ),
]
