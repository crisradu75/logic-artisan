"""Mutation batch for test_docs_name_shipped_paths.py.

The guard claims a doc cannot tell a consumer to run a path the release does not
contain without a test going red. That claim has two halves and only one of them
is obvious: the comparison, and the EXTRACTION that feeds it. A guard whose
regex has quietly stopped matching how the docs write paths compares an empty
set against the shipped tree and passes — which is the same silent-clean-report
shape as the defect it exists for (issue #264: a consumer gate that resolved
nothing and passed).

**Twelve mutants, in the order they run.** 1-4 reproduce the original defect in
every spelling it really has: prefixed in the shipped README's invocation block,
**bare in a guarded doc's prose** — the spelling it actually shipped in — and in
each of the two published-tree diagrams. 5-6 kill the two halves of the
extraction. 7 and 12 attack the two narrowing rules, which fail in the opposite
direction: a guard that reports paths nobody claimed is a guard someone loosens
until it checks nothing. 8 is a retired single-segment entry named with a prefix,
the case a stripped-token separator test silently dropped. 9 removes the
tag-derived retired-name set, without which the bare spelling is invisible.
10 makes one document's diagram stop parsing — the silent-drop shape a combined
floor could not see. 11 collapses the tag-less branch of the stale-exemption
message, whose remedy is the opposite of the ordinary one.

**Two edits are deliberately NOT in this list, because neither can be killed in
a correct tree** — see root CLAUDE.md, "a SURVIVOR is not automatically a
finding about the code":

  * *Disabling the comparison.* With no violating path present there is nothing
    for the edit to miss. Mutants 1-2 cover that branch from the input side,
    which is where it discriminates.
  * *Zeroing the non-vacuity floors.* The floors bind only when an extraction
    has already broken, so removing them changes nothing on a clean tree. What
    they are worth is shown instead by 5-6 and 10, which are killed BY them.
  * *Merging the fenced blocks back into one stream* (review finding 4). The
    parser would then inherit "inside the published tree" across a fence
    boundary — but no document today has an indented-two-spaces block after a
    diagram, so the edit is unobservable here. That is precisely why the reset
    has a unit test on synthetic input
    (`test_a_fenced_block_boundary_resets_the_diagram_parser`) rather than a
    mutant: a latent defect with no failing input cannot be mutated into one.

**What this batch already found.** Its first run killed 4 of 7 and both
survivors were real: reading only inline backticks missed the README's fenced
invocation block entirely, and a single combined path floor was too coarse to
notice the explicit-prefix half of the extraction dying, because the bare half
alone cleared it. Both are fixed; the one-floor-per-channel split exists because
of that run.

**What the batch did NOT find, and a review did.** Every mutant in that first
version wrote the retired path with a `<plugin>/` prefix — a spelling the guard
handled — while the defect shipped BARE, which the guard could not see at all.
A batch that only exercises the spellings the code already handles reports a
clean run and means nothing by it. Mutants 2-4, 8 and 9 exist because of that, and
the rule they encode is worth more than they are: re-break the defect in the
form it actually took, not in the form convenient to the implementation.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_docs_name_shipped_paths.py
-> all 10 killed.
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"

GUARD = DEV / "tests" / "consistency" / "test_docs_name_shipped_paths.py"
PLUGIN_README = PLUGIN / "README.md"
ROOT_README = DEV.parent / "README.md"
CLAUDE_MD = DEV.parent / "CLAUDE.md"

# Scoped to the ONE guard file: a target red for any other reason reports every
# mutant "killed" and proves nothing.
TARGETS = [GUARD]

# EVERY ANCHOR BELOW IS A SINGLE LINE, and that is a rule rather than a style.
# Two anchors here originally spanned three lines each. They matched while the
# files had been written by this session, and stopped matching the moment a
# rebase re-materialised them through git's line-ending conversion — a `\n` in
# the anchor cannot match a `\r\n` on disk. `mutate.py` aborts the WHOLE batch in
# preflight on one unresolvable anchor, so a multi-line anchor does not degrade
# to one dead mutant; it silently takes the other nine with it, on someone
# else's checkout rather than on yours. A replacement MAY span lines: it is
# written, never matched.


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
        # THE DEFECT IN THE SPELLING IT ACTUALLY SHIPPED IN — bare, no prefix.
        # Mutant 1 uses `<plugin>/`, and a review found that spelling flatters the
        # guard: at cla--v0.10.0 three of the four guarded docs wrote
        # `conformance-checks/` BARE (CLAUDE.md:74, DEVELOPER-GUIDE.md:315, plugin
        # README.md:135) and only files this guard does not cover used the
        # prefixed form. The first version of the guard derived its bare prefixes
        # from the CURRENTLY shipped tree, so it could not see this at all and
        # stayed green. Killed now only by the tag-derived retired-name set, which
        # is the whole reason that set exists.
        "a guarded doc names the retired scope bare, as the shipped defect did",
        CLAUDE_MD,
        "**Deferred work lives in GitHub issues**",
        "Wire `conformance-checks/tests` into your gate.\n\n**Deferred work lives in GitHub issues**",
        TARGETS,
    ),
    (
        # The same defect in the tree diagram — the one place a reader looks to
        # find out what the published tree contains. This is the spelling that
        # actually shipped, and it lived in TWO diagrams: the root README:57 and
        # the plugin README:165 at cla--v0.10.0. The mutant targets the ROOT
        # README specifically, because the first version of this guard read only
        # the plugin README's block and a review verified a retired entry could be
        # inserted here with both tests still green.
        "the root README's published-tree diagram lists a directory that does not ship",
        ROOT_README,
        "  output-styles/               the project's writing convention",
        "  conformance-checks/          portable guards for the fact/procedure split\n  output-styles/               the project's writing convention",
        TARGETS,
    ),
    (
        # The plugin README's own diagram, which is the block a CONSUMER reads.
        # Separate from the mutant above because the parser finds each diagram by
        # locating the `.claude/plugins/cla/` line inside a fenced block, and the
        # two documents place that line differently — at column 0 alone in one,
        # and part-way down a larger repo-root tree in the other.
        "the shipped README's diagram lists a directory that does not ship",
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
        # skill-relative with no prefix at all. Emptying the shipped half of the
        # prefix set drops them, and again nothing fails on the comparison; the
        # bare floor is what notices. Pairs with the retired-half mutant below,
        # which removes the other half of the same set.
        "the shipped half of the bare prefix set is dropped",
        GUARD,
        '    top = {p.split("/")[0] for p in shipped if "/" in p}',
        "    top = set()",
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
        "        if not (_REPO_ROOT / name).exists()",
        "        if True",
        TARGETS,
    ),
    (
        # FINDING 3's defect direction: a RETIRED TOP-LEVEL FILE named with an
        # explicit prefix. `<plugin>/mutate.py` has no separator left once the
        # prefix is stripped, so the first version of `_classify` returned None
        # for it — and the two runners and the three `*-checks/` scopes are all
        # single-segment entries that 0.x guidance names. Killed only because the
        # separator test now runs against the token as written when a plugin
        # prefix is present.
        "a retired single-segment entry is named with an explicit plugin prefix",
        PLUGIN_README,
        "python3 <plugin>/skills/sync-context/scripts/check_fact_paths.py",
        "python3 <plugin>/mutate.py",
        TARGETS,
    ),
    (
        # The retired half of `_bare_prefixes` — the fix for finding 1. Removing
        # it makes a bare `conformance-checks/tests` unrecognisable again, which
        # is precisely the state the guard shipped in and a review caught.
        #
        # It dies through the `_RETIREMENT_NOTES` staleness assertion rather than
        # through a violation, and that is the point worth seeing: the migration
        # notes this change added are themselves bare retired references, so the
        # exemptions covering them go unclaimed the moment the bare channel stops
        # seeing that class. The notes are the guard's own live fixture.
        "the retired-name half of the bare prefix set is dropped",
        GUARD,
        "        for name in top | _retired_top_level_names()",
        "        for name in top",
        TARGETS,
    ),
    (
        # REVIEW FINDING 3, the silent-drop shape. Indent the root README's
        # `.claude/plugins/cla/` marker line and its whole diagram stops parsing:
        # the parser never enters the published half, so that document
        # contributes zero entries. Under the old single combined floor it simply
        # DISAPPEARED from the sum and the other two diagrams carried the total
        # past it — a guarded document going unguarded with the suite green.
        # Killed only by `_DIAGRAM_FLOORS` being a per-document map whose keys
        # must all be present.
        "the root README's tree diagram stops parsing and vanishes from the check",
        ROOT_README,
        ".claude/plugins/cla/           everything below here IS published, and nothing else is",
        "  .claude/plugins/cla/         everything below here IS published, and nothing else is",
        TARGETS,
    ),
    (
        # REVIEW FINDING 2. Collapse the tag-less branch of the stale-exemption
        # message, so a checkout with no release tags is told to "drop the
        # exemption" — deleting correct work to silence a problem that is really
        # `git fetch --tags`. The condition is reachable (shallow clone,
        # --no-tags, fresh fork) and the two remedies are opposites, which is why
        # the branch is asserted directly rather than trusted to be read.
        "a tag-less checkout is told to delete exemptions that are correct",
        GUARD,
        "    if not retired:",
        "    if False:",
        TARGETS,
    ),
    (
        # The ellipsis skip. CLAUDE.md writes `lib/...` as a placeholder for "a
        # script directly under the plugin root"; treating it as a literal path
        # reports a file nobody claimed exists. Same false-positive direction as
        # the mutant above, and the same consequence if it were left in.
        "an ellipsis placeholder is treated as a literal path",
        GUARD,
        '    if "..." in stripped or "*" in stripped:',
        '    if "*" in stripped:',
        TARGETS,
    ),
]
