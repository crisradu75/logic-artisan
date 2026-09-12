"""Mutation batch for test_marketplace_manifest.py.

The guard claims the marketplace catalog stays loadable and keeps pointing at this
plugin at the version it says it publishes.

**Every mutant here breaks the INPUT, not the guard, and that is the design.**
This guard is almost entirely assertions about two JSON files, so the interesting
question is not "does the assertion run" but "does each field actually matter" —
and the release procedure makes that concrete. `CLAUDE.md` describes publishing as
a deliberate three-file edit (plugin `version`, catalog `ref`, the release line),
with "a test fails when they disagree" as the thing that makes it safe. Mutants
1-2 are that claim, broken from each end.

**Mutants 1 and 2 are the same disagreement reached from opposite sides**, and
both are kept because the release procedure can fail either way: bumping the
plugin and forgetting the catalog, or bumping the catalog against a version that
was never cut. A single mutant proves the comparison reacts; it does not prove the
comparison is anchored to both files rather than to one and a constant.

**Not covered, and it is the guard's own stated boundary:** that a `ref` resolves
to a tag that exists. The guard's docstring declines that deliberately — the tag
does not exist until a release is cut, so the test would fail until then and be
disabled. Mutant 2 therefore breaks agreement between the two files, not
reachability of the tag; nothing here would catch `cla--v9.9.9` in both files at
once.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_marketplace_manifest.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
REPO = DEV.parent
PLUGIN = REPO / ".claude" / "plugins" / "cla"

GUARD = DEV / "tests" / "consistency" / "test_marketplace_manifest.py"
MANIFEST = REPO / ".claude-plugin" / "marketplace.json"
PLUGIN_JSON = PLUGIN / ".claude-plugin" / "plugin.json"

# Scoped to the ONE guard file: a target red for any other reason reports every
# mutant "killed" and proves nothing.
TARGETS = [GUARD]

MUTANTS = [
    (
        # THE RELEASE DEFECT, catalog side: the plugin is bumped and the catalog
        # is not. A consumer then installs the tag named here while the plugin
        # inside it reports a different version, and has no way to tell which is
        # true.
        "the catalog publishes a ref for a version the plugin no longer claims",
        MANIFEST,
        '"ref": "cla--v1.0.1"',
        '"ref": "cla--v1.0.0"',
        TARGETS,
    ),
    (
        # The same disagreement from the other end: the plugin is bumped and the
        # catalog is not. Kept as its own mutant because mutant 1 alone cannot
        # show the comparison reads `plugin.json` at all — it would die exactly
        # the same way against a hardcoded expected string.
        "the plugin version moves without the catalog ref following it",
        PLUGIN_JSON,
        '"version": "1.0.1"',
        '"version": "1.0.2"',
        TARGETS,
    ),
    (
        # A typo in the subdirectory installs an empty plugin: Claude Code finds
        # no manifest at the path and the install is inert, which a user reads as
        # "the plugin does nothing" rather than as a bad path.
        "the catalog points at a subdirectory that is not this plugin",
        MANIFEST,
        '"path": ".claude/plugins/cla"',
        '"path": ".claude/plugins/cla-harness"',
        TARGETS,
    ),
    (
        # The channel silently tracking the repository default branch. Consumers
        # would then pick up whatever is on `main`, unreviewed and unreleased —
        # the opposite of the exact-tag pinning the whole distribution model rests
        # on. Spelled as a rename rather than a deletion so the JSON stays valid
        # and the failure is the guard's, not the parser's.
        "the catalog entry loses its ref and tracks the default branch",
        MANIFEST,
        '"ref": "cla--v1.0.1"',
        '"unused_ref": "cla--v1.0.1"',
        TARGETS,
    ),
    (
        # A marketplace registered under a name Anthropic reserves stops loading
        # entirely, and the failure reads as "untrusted source" rather than "bad
        # name" — which is why the guard carries the reserved list at all.
        "the marketplace takes a name reserved for official Anthropic use",
        MANIFEST,
        '"name": "cris-logic-artisan"',
        '"name": "claude-plugins-official"',
        TARGETS,
    ),
    (
        # `/cla:report-upstream` reads `repository` to know where to file, and
        # refuses to guess — portable core must not name a repository in prose.
        # Without this field the skill stops and asks the user every single time,
        # which is a silent degradation rather than an error.
        "the plugin stops declaring the repository report-upstream files against",
        PLUGIN_JSON,
        '"repository": "https://github.com/crisradu75/logic-artisan"',
        '"homepage": "https://github.com/crisradu75/logic-artisan"',
        TARGETS,
    ),
]
