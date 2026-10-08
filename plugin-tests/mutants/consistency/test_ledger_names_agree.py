"""Mutation batch for test_ledger_names_agree.py.

The guard claims the ledger filename a skill WRITES cannot drift from the one its
retro skill READS without a test going red. The failure it exists for is silent
in a way worth restating: `log_run.py` validates only the SHAPE of the argument,
so a misspelled name is written happily to a brand-new file, the reader then finds
nothing, and the retro skill instructs the model to read `runs_analyzed: 0` as
"the loop has not run yet". Three silences in a row and the history is gone.

**Both halves of the one remaining contract.** The contract spans two languages —
prose on the writer side, a Python constant on the reader side — so one mutant
breaks the spec-to-pr writer and one its reader. Two more break the guard's own
extraction, because a guard that cannot read either side reports agreement
between two things it never found. The codify ledger lost its retro reader with
`codify-retro`; its writer's spelling is still pinned, by the cla-init scan's
non-vacuity set, and the first mutant proves that.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_ledger_names_agree.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"

GUARD = DEV / "tests" / "consistency" / "test_ledger_names_agree.py"
CODIFY_SKILL = PLUGIN / "skills" / "codify-learnings" / "SKILL.md"
SCHEMA = PLUGIN / "skills" / "_shared" / "references" / "run-log-schema.md"
S2P_READER = PLUGIN / "skills" / "spec-to-pr-retro" / "scripts" / "spec_to_pr_aggregate.py"
CLA_INIT = PLUGIN / "skills" / "cla-init" / "SKILL.md"

# Scoped to the ONE guard file: a target red for any other reason reports every
# mutant "killed" and proves nothing.
TARGETS = [GUARD]

MUTANTS = [
    (
        # A singular/plural slip in prose is exactly the typo `log_run.py`'s
        # shape validation accepts: it matches the filename pattern, so the write
        # succeeds into a new file and nothing anywhere reports a problem. With
        # no codify reader left, the cla-init scan's non-vacuity set is what
        # names the ledger codify-learnings must write.
        "the codify writer's prose names a ledger cla-init does not seed",
        CODIFY_SKILL,
        "log_run.py codify-runs.jsonl",
        "log_run.py codify-run.jsonl",
        TARGETS,
    ),
    (
        # THE DEFECT THE GUARD EXISTS FOR, writer side. The invocation lives in
        # a SHARED reference rather than in a skill's own SKILL.md.
        "the spec-to-pr writer's prose names a ledger its retro does not read",
        SCHEMA,
        "log_run.py spec-to-pr-runs.jsonl",
        "log_run.py spec-to-pr-run.jsonl",
        TARGETS,
    ),
    (
        # Reader side: the write succeeds to the right file and the READ goes to
        # a name nobody writes.
        "the spec-to-pr reader opens a ledger its writer never writes",
        S2P_READER,
        'return _runs_dir() / "spec-to-pr-runs.jsonl"',
        'return _runs_dir() / "spec-to-pr-run.jsonl"',
        TARGETS,
    ),
    (
        # NON-VACUITY, writer side. If `_WRITER_RE` stops matching the real
        # invocation spelling, `written` is empty and the comparison below it
        # never runs. The guard already asserts `written` is non-empty for
        # exactly this reason; this proves that assertion fires rather than
        # decorating the function. The edit performed is to the command NAME —
        # `log_run\.py` -> `log_run\.pyx` — which is what makes the pattern
        # match nothing.
        #
        # WHAT THIS DOES NOT COVER, measured rather than assumed. An earlier
        # version of this comment claimed the mutant narrowed `\s+` to a single
        # literal space and called that "the realistic shape of the slip". It
        # did not perform that edit, and when a reviewer ran the edit it
        # described, it SURVIVED — every `log_run.py <ledger>` invocation in the
        # prose sits on one line with exactly one space
        # (`codify-learnings/SKILL.md`), so `\s+` and `" "` agree on every
        # input the real files supply. That is this batch's own unkillable class
        # again, and here the input side cannot rescue it either: wrapping an
        # invocation across a line is tolerated by `\s+`, so the guard still
        # passes and there is no kill in either direction. `\s+` is therefore
        # NOT load-bearing on today's prose. Recorded rather than papered over —
        # the defect was a coverage claim asserted without running it.
        "the writer pattern stops matching the invocation as it is actually written",
        GUARD,
        r'_WRITER_RE = re.compile(r"log_run\.py\s+([A-Za-z0-9][A-Za-z0-9._-]*\.jsonl)")',
        r'_WRITER_RE = re.compile(r"log_run\.pyx\s+([A-Za-z0-9][A-Za-z0-9._-]*\.jsonl)")',
        TARGETS,
    ),
    (
        # NON-VACUITY, reader side. The AST walk finds the constant by locating
        # `_default_log_path` by name; point it at a function that does not exist
        # and the loop falls through to the `raise AssertionError` at the bottom.
        # Worth a mutant because that raise is the only thing standing between a
        # renamed reader function and a guard that silently compares nothing.
        "the reader scan looks for a function name that does not exist",
        GUARD,
        'if isinstance(node, ast.FunctionDef) and node.name == "_default_log_path":',
        'if isinstance(node, ast.FunctionDef) and node.name == "_default_log_pathx":',
        TARGETS,
    ),
    (
        # Mutates the INPUT, not the guard: drop one ledger from cla-init's list
        # and the scan must name it as missing.
        "cla-init's ledger list drops a ledger a skill still writes",
        CLA_INIT,
        "#   lite-pr-runs, shape-decision-runs, feedback-runs\n",
        "#   shape-decision-runs, feedback-runs\n",
        TARGETS,
    ),
    (
        # NON-VACUITY of the scan: a pattern that finds nothing would pass the
        # missing-ledger check on an empty set.
        "the cross-skill scan reads no files",
        GUARD,
        'for md in sorted(_PLUGIN_ROOT.glob("skills/**/*.md")):',
        'for md in sorted(_PLUGIN_ROOT.glob("skills/**/*.mdx")):',
        TARGETS,
    ),
]
