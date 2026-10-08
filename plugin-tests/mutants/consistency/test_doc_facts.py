"""Mutation batch for test_doc_facts.py — break each doc claim it pins and
confirm a test fails.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_doc_facts.py
"""

from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
DEV = Path(__file__).resolve().parents[2]
REPO = PLUGIN.parents[2]
# Scoped to the ONE guard file rather than to `tests/consistency/`. An area
# target reports every mutant "killed" whenever anything else in the area is red
# — which this area demonstrably can be: `test_overlays_are_reachable.py` was
# 1-failed here from the dev-tree extraction until the commit that added this
# comment, so every run of this batch in between proved nothing it claimed to.
TARGETS = [DEV / "tests" / "consistency" / "test_doc_facts.py"]

MUTANTS = [
    (
        # Anchored on the PREFIX, not on a version. Pinning the literal
        # `cla--v0.10.0` meant every release broke this batch in preflight — and
        # mutate.py aborts the whole batch on one bad anchor, so a stale anchor
        # here silently disarmed the other mutants too. Caught by
        # a batch-loadability check (since deleted) while cutting
        # 1.0.0. Injecting a digit after the `v` drifts the line from plugin.json
        # whatever the current version is.
        "CLAUDE.md's release line drifts from plugin.json",
        REPO / "CLAUDE.md",
        "**Current release: `cla--v",
        "**Current release: `cla--v9",
        TARGETS,
    ),
    (
        # The drift `test_every_named_leaf_hook_exists` was written against: a doc
        # names a guard hook that has no file. Planted in the shipped plugin
        # README, the doc a consuming repo actually reads.
        "the plugin README names a guard hook that does not exist",
        PLUGIN / "README.md",
        "**Blocks:** `block-cd-in-bash` (",
        "**Blocks:** `block-cd-in-shell` (",
        TARGETS,
    ),
    (
        # The `.py` spelling. Without `(?:\.py)?` in the guard's pattern a
        # backticked `name.py` matches nothing, so this mutant survives exactly
        # when that half of the pattern is lost.
        "a doc names a missing guard hook by its file name",
        REPO / "DEVELOPER-GUIDE.md",
        "`warn-heredoc-escape-mangling`",
        "`warn-heredoc-escape-mangler.py`",
        TARGETS,
    ),
    (
        # The defect this pair was written against: a THIRD skill forbids model
        # invocation and the table still shows it as model-invocable, telling a
        # reader Claude may start an unattended orchestrator on a description
        # match. Planted in the source rather than the table, because the
        # frontmatter is the authority and the table follows it. Killed by
        # `test_the_invocation_column_matches_the_frontmatter`.
        "a third skill forbids model invocation and the table does not follow",
        PLUGIN / "skills" / "multi-spec" / "SKILL.md",
        "argument-hint:",
        "disable-model-invocation: true\nargument-hint:",
        TARGETS,
    ),
    (
        # The same defect in the spelling the guard's FIRST draft missed. Review
        # measured five legal YAML spellings of true that the string compare
        # `line.strip() == "disable-model-invocation: true"` did not match, and
        # the inline-comment form is the likely one — both existing skills carry
        # that rationale as a comment already. Without this mutant the batch
        # reports 11 kills while the guard's headline scenario is unguarded for
        # every spelling but one.
        "a third skill declares it with an inline comment, not the bare literal",
        PLUGIN / "skills" / "multi-spec" / "SKILL.md",
        "argument-hint:",
        "disable-model-invocation: true  # merges PRs unattended\nargument-hint:",
        TARGETS,
    ),
    (
        # The other direction: the table keeps a mark the frontmatter dropped.
        # A count-based assertion passes this whenever the right NUMBER of rows
        # carry a mark, which is why the guard compares sets.
        "the table marks a skill whose frontmatter permits model invocation",
        PLUGIN / "README.md",
        "| `spec-to-pr` | you or Claude |",
        "| `spec-to-pr` | **you only** |",
        TARGETS,
    ),
    (
        # The mark moved OUT of the Invoked by cell and into the description of
        # the same row. The guard's first draft searched the whole row, so the
        # column said `you or Claude` while the derived set said user-only and
        # the two halves agreed. Killed by the cell-value assertion.
        "the invocation cell contradicts a mark left in the description",
        PLUGIN / "README.md",
        "| `multi-lite` | **you only** | Chain several",
        "| `multi-lite` | you or Claude | **you only** — chain several",
        TARGETS,
    ),
    (
        # A row loses its Invoked by cell entirely. Both marked sets are
        # untouched, so the set comparison cannot see it; the table renders
        # misaligned from that row down. Killed by the cell-count assertion.
        "an unmarked row loses its invocation cell",
        PLUGIN / "README.md",
        "| `lite-pr` | you or Claude | Lightweight",
        "| `lite-pr` | Lightweight",
        TARGETS,
    ),
    (
        # A real shipped skill relabelled as one of the non-skill rows. Marks
        # untouched again; only the legal-value and row-set assertions see it.
        "a shipped skill is relabelled as a non-skill row",
        PLUGIN / "README.md",
        "| `annotate` | you or Claude |",
        "| `annotate` | n/a — dispatched |",
        TARGETS,
    ),
    (
        # The accumulator bug this guard actually shipped with, restored.
        #
        # ANCHOR IS ONE LINE, deliberately. An earlier form spanned six lines,
        # and `mutate.py`'s docstring forbids `\n` in an anchor: anchors match
        # raw bytes, so on a CRLF checkout the anchor matches nothing, preflight
        # refuses, and — because one bad anchor aborts the whole run — all of
        # this batch's mutants are silently disarmed on Windows.
        #
        # NOTE also the shape. An even earlier form just deleted `delimiters =
        # 0`, which dies of UnboundLocalError — a CRASH, not a detection, and so
        # evidence only that the line is syntactically load-bearing.
        "the frontmatter reader accepts only the bare `true` literal again",
        DEV / "tests" / "consistency" / "test_doc_facts.py",
        '    return value.split("#")[0].strip().strip("\\"\'").lower() in _YAML_TRUE',
        '    return value == "true"',
        TARGETS,
    ),
    (
        # `test_the_phase_table_names_every_shipped_skill` was the one new
        # assertion this batch never reached — and the round-2 argument on this
        # very PR is that a test never shown able to fail is weak evidence.
        # Renaming the row's skill breaks the binding in BOTH directions at once
        # (the table names one that ships no SKILL.md and omits one that does),
        # which is exactly what that test's failure message reports. Every other
        # assertion still passes on it: the cell count is 4, `you or Claude` is
        # legal, and the row still reads as naming a skill, so the kill can only
        # come from the row-set test.
        #
        # Anchor verified to occur exactly once in the file's RAW BYTES, which is
        # what `mutate.py` matches: `README.md` has no `*.md` entry in
        # `.gitattributes`, so with `core.autocrlf=true` it checks out CRLF.
        "the phase table names a skill that ships no SKILL.md",
        PLUGIN / "README.md",
        "| `checkpoint` | you or Claude | Compact",
        "| `checkpint` | you or Claude | Compact",
        TARGETS,
    ),
    (
        # The same derived fact, in the copy that is not the table. A third skill
        # setting the frontmatter key reddens the README assertions while
        # `CLAUDE.md` keeps naming two — the guard's own headline failure mode,
        # one file over. Planted as a WRONG NAME rather than a third skill,
        # because the frontmatter mutants above already cover the source side and
        # this one has to fail on the prose alone.
        "CLAUDE.md names the wrong skill as user-invoked only",
        REPO / "CLAUDE.md",
        "all but `cla-setup`, `codify-learnings`,",
        "all but `checkpoint`, `codify-learnings`,",
        TARGETS,
    ),
    (
        # The vacuity direction of the same pair: the qualification is reworded
        # to name a frontmatter key that does not exist, so no passage mentions
        # the real one and the doc is back to its blanket "invoke it however you
        # like" claim. Killed by the `exactly 1 passage` half, which is the half
        # a wrong-name mutant cannot reach.
        "DEVELOPER-GUIDE.md loses the qualification entirely",
        REPO / "DEVELOPER-GUIDE.md",
        "`disable-model-invocation: true` (the first two",
        "`no-auto-invoke: true` (the first two",
        TARGETS,
    ),
]
