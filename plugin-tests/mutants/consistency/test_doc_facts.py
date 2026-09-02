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
        "README understates the skill count",
        REPO / "README.md",
        "20 workflow skills",
        "18 workflow skills",
        TARGETS,
    ),
    (
        "README's pytest-scope count goes stale",
        REPO / "README.md",
        "# every pytest scope (1 today)",
        "# every pytest scope (8 today)",
        TARGETS,
    ),
    (
        # Anchored on the PREFIX, not on a version. Pinning the literal
        # `cla--v0.10.0` meant every release broke this batch in preflight — and
        # mutate.py aborts the whole batch on one bad anchor, so a stale anchor
        # here silently disarmed the other mutants too. Caught by
        # `test_every_batch_is_loadable_and_declares_real_targets` while cutting
        # 1.0.0. Injecting a digit after the `v` drifts the line from plugin.json
        # whatever the current version is.
        "CLAUDE.md's release line drifts from plugin.json",
        REPO / "CLAUDE.md",
        "**Current release: `cla--v",
        "**Current release: `cla--v9",
        TARGETS,
    ),
    (
        "CLAUDE.md's skills-with-tests count goes stale",
        REPO / "CLAUDE.md",
        "— 6 areas under `skills/`, one",
        "— 9 areas under `skills/`, one",
        TARGETS,
    ),
    (
        "a doc names a plugin path that no longer exists",
        REPO / "DEVELOPER-GUIDE.md",
        "pytest plugin-tests    # all pytest scopes (1)",
        "pytest .claude/plugins/cla/gone    # all pytest scopes (1)",
        TARGETS,
    ),
    (
        # The scope walk starts at the REPO root, and this repo's own
        # `new-worktree` skill (and the Agent tool's worktree isolation) puts a
        # full second checkout at `.claude/worktrees/<name>/`. Without the
        # exclusion the walk finds that copy's `plugin-tests/` and reports 2
        # scopes, failing four doc claims that are correct. Killed by
        # `test_a_worktree_copy_is_not_counted_as_a_second_scope`, which plants
        # the worktree rather than relying on one being live — on a clean clone
        # there is otherwise nothing for this mutant to trip over.
        "a worktree checkout counts as a second pytest scope",
        DEV / "tests" / "consistency" / "test_doc_facts.py",
        "        if _is_nested_checkout(directory):",
        "        if False and _is_nested_checkout(directory):",
        TARGETS,
    ),
    (
        # The exclusion's other half. Matched against absolute parts it is scoped
        # to the whole filesystem rather than to the repo, so a clone living at
        # `.claude/worktrees/agent-<id>/` excludes its OWN entire tree and the
        # count becomes 0 — the fix for the mutant above, applied wrongly, turns
        # `assert 2 in [1]` into `assert 0 in [1]`. Killed by
        # `test_the_exclusion_reads_repo_relative_parts_not_absolute_ones`.
        "the exclusion is matched against absolute path parts",
        DEV / "tests" / "consistency" / "test_doc_facts.py",
        "        rel = path.relative_to(_REPO_ROOT)",
        "        rel = Path(*path.parts)",
        TARGETS,
    ),
    (
        # The over-exclusion side. Keying on the directory NAME hides a real
        # scope that merely sits under one called `worktrees` — the first cut of
        # this fix did exactly that. Killed by
        # `test_a_directory_merely_named_worktrees_is_still_counted`.
        "the exclusion goes back to keying on the directory name",
        DEV / "tests" / "consistency" / "test_doc_facts.py",
        '_EXCLUDED_DIRS = {"__pycache__", ".pytest_cache", ".git", ".venv", "node_modules"}',
        '_EXCLUDED_DIRS = {"__pycache__", ".pytest_cache", ".git", ".venv", "node_modules", "worktrees"}',
        TARGETS,
    ),
    (
        # The defect this pair was written against: a THIRD skill forbids model
        # invocation and the table still shows it as model-invocable, telling a
        # reader Claude may start it on a description match. Planted in the
        # source rather than the table, because the frontmatter is the authority
        # and the table is what must follow it. Killed by
        # `test_the_invocation_column_matches_the_frontmatter`.
        "a third skill forbids model invocation and the table does not follow",
        PLUGIN / "skills" / "multi-spec" / "SKILL.md",
        "argument-hint:",
        "disable-model-invocation: true\nargument-hint:",
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
        # The accumulator bug this guard actually shipped with, caught by the
        # test failing on a correct tree: `found` was used as the past-the-
        # opening-delimiter signal, so the first file to match made every LATER
        # file break on its own opening `---` and go unread. `multi-pr` vanished
        # from the derived set while the table was right.
        # NOTE the shape. An earlier version of this mutant just deleted
        # `delimiters = 0`, which dies of UnboundLocalError — a CRASH, not a
        # detection, and so evidence only that the line is syntactically
        # load-bearing. This one restores the exact accumulator logic the guard
        # shipped with, so the guard runs clean and returns a WRONG set.
        "frontmatter delimiters are counted across files instead of per file",
        DEV / "tests" / "consistency" / "test_doc_facts.py",
        '            if line.rstrip() == "---":\n'
        "                delimiters += 1\n"
        "                if delimiters == 2:\n"
        "                    break\n"
        "                continue\n"
        '            if delimiters == 1 and line.strip() == "disable-model-invocation: true":',
        '            if line.rstrip() == "---" and found:\n'
        "                break\n"
        '            if line.strip() == "disable-model-invocation: true":',
        TARGETS,
    ),
]

# NOT mutated, and recorded rather than left as a silent gap:
#
# `_is_nested_checkout`'s `directory != _REPO_ROOT` guard. Removing it survives,
# correctly. `_excluded` walks ancestors STRICTLY BELOW the root — it assigns
# `directory = directory / part` before the first check — so the helper is never
# called with the root, and the guard is unreachable from its only caller. What
# actually keeps the root's own `.git` harmless is that starting point, and
# `test_the_repo_roots_own_git_does_not_exclude_the_whole_tree` pins the property
# regardless of which mechanism provides it. A mutant that cannot die would make
# this batch permanently red while proving nothing.
