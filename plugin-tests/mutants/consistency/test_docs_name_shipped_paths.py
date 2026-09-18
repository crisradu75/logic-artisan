"""Mutation batch for test_docs_name_shipped_paths.py.

The guard claims a doc cannot tell a consumer to run a path the release does not
contain without a test going red. That claim has two halves and only one of them
is obvious: the comparison, and the EXTRACTION that feeds it. A guard whose
regex has quietly stopped matching how the docs write paths compares an empty
set against the shipped tree and passes — which is the same silent-clean-report
shape as the defect it exists for (issue #264: a consumer gate that resolved
nothing and passed).

**Six mutants.** 1-2 reproduce the original defect in its two real spellings —
the retired `conformance-checks/tests` path reintroduced into the shipped plugin
README's invocation block, and into the layout block a reader consults to learn
what a release holds. 3-4 kill the two halves of the extraction. 5-6 attack the
two narrowing rules, which fail in the opposite direction: a guard that reports
paths nobody claimed is a guard someone loosens until it checks nothing.

**Two edits are deliberately NOT in this list, because neither can be killed in
a correct tree** — see root CLAUDE.md, "a SURVIVOR is not automatically a
finding about the code":

  * *Disabling the comparison.* With no violating path present there is nothing
    for the edit to miss. Mutants 1-2 cover that branch from the input side,
    which is where it discriminates.
  * *Zeroing the non-vacuity floors.* The floors bind only when an extraction
    has already broken, so removing them changes nothing on a clean tree. What
    they are worth is shown instead by 3-4, which are killed BY them.

**What this batch already found.** Its first run killed 4 of 7 and both
survivors were real: reading only inline backticks missed the README's fenced
invocation block entirely (mutant 1), and a single combined path floor was too
coarse to notice the explicit-prefix half of the extraction dying, because the
bare half alone cleared it (mutant 3). Both are fixed in the guard; the
one-floor-per-channel split exists because of this run.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_docs_name_shipped_paths.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"

GUARD = DEV / "tests" / "consistency" / "test_docs_name_shipped_paths.py"
PLUGIN_README = PLUGIN / "README.md"

# Scoped to the ONE guard file: a target red for any other reason reports every
# mutant "killed" and proves nothing.
TARGETS = [GUARD]

MUTANTS = [
    (
        # THE DEFECT, exactly as issue #264 reports it: consumer-facing prose in
        # the file a consuming repo actually receives, telling that repo to run a
        # directory the release has not contained since 1.0.0. The edit reinstates
        # the retired path in the invocation block, which is where a reader copies
        # from.
        "the shipped README tells a consumer to run the retired conformance scope",
        PLUGIN_README,
        "python3 <plugin>/skills/sync-context/scripts/check_fact_paths.py",
        "python3 <plugin>/conformance-checks/tests/test_project_facts_paths.py",
        TARGETS,
    ),
    (
        # The same defect in its other real home — the Layout block, which is the
        # one place a reader looks to find out what the published tree contains.
        # This is the spelling that actually shipped at cla--v0.9.3 and outlived
        # the directory. It is a separate mutant because a separate test covers
        # it: the layout block is parsed, not regex-scanned, so mutant 1 says
        # nothing about whether that parse still works.
        "the README's layout block lists a directory the release does not contain",
        PLUGIN_README,
        "  output-styles/               the project's writing convention",
        "  conformance-checks/          portable guards\n  output-styles/               the project's writing convention",
        TARGETS,
    ),
    (
        # NON-VACUITY, extraction side. Break the explicit-prefix pattern so no
        # `<plugin>/…` or `${CLAUDE_PLUGIN_ROOT}/…` token is ever recognised as a
        # plugin path. Everything still "resolves", because nothing is extracted.
        # The floor is the only thing standing between that and a green run, and
        # this proves the floor fires rather than decorating the function.
        "the plugin-prefix pattern stops matching how the docs spell a plugin path",
        GUARD,
        r'_PLUGIN_PREFIX = re.compile(r"^(?:\$\{CLAUDE_PLUGIN_ROOT\}/|<plugin>/|\.claude/plugins/cla/)")',
        r'_PLUGIN_PREFIX = re.compile(r"^(?:\$\{CLAUDE_PLUGIN_ROOTX\}/|<pluginx>/|\.claude/pluginsx/cla/)")',
        TARGETS,
    ),
    (
        # NON-VACUITY, the other extraction path. Bare `skills/…` tokens are the
        # majority spelling in these docs — most references are written
        # skill-relative with no prefix at all. Returning an empty prefix set
        # drops them, and again nothing fails on the comparison.
        "no bare top-level prefix is accepted, so most references are never read",
        GUARD,
        "    return frozenset(name for name in top if not (_REPO_ROOT / name).exists())",
        "    return frozenset()",
        TARGETS,
    ),
    (
        # The repo-root exclusion in `_bare_prefixes`, which the module docstring
        # calls load-bearing and measured. This mutant is what measured it:
        # dropping the exclusion admits `.claude-plugin`, and CLAUDE.md's
        # `.claude-plugin/marketplace.json` — the REPO-ROOT catalog, not a plugin
        # file — is then read as a plugin path and reported as not shipping. It
        # dies on a false positive rather than a false negative, which is the
        # failure direction that gets a guard loosened until it checks nothing.
        "a shipped top-level name that also exists at the repo root is read as plugin-relative",
        GUARD,
        "    return frozenset(name for name in top if not (_REPO_ROOT / name).exists())",
        "    return frozenset(top)",
        TARGETS,
    ),
    (
        # The ellipsis skip. CLAUDE.md writes `lib/...` as a placeholder for "a
        # script directly under the plugin root"; treating it as a literal path
        # reports a file nobody claimed exists. Same false-positive direction as
        # the mutant above, and the same consequence if it were left in.
        "an ellipsis placeholder is treated as a literal path",
        GUARD,
        'if "/" not in stripped or "..." in stripped:',
        'if "/" not in stripped:',
        TARGETS,
    ),
]
