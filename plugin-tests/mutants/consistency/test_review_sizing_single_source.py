"""Mutation batch for test_review_sizing_single_source.py.

Each mutant puts back one thing the risk-sized-review change removed or moved: the `Risk:`
line dropped from the PR body, the old round-2 trigger, a sizing-table row copied into a
skill, a chain skill dropped from the orchestration reference, or the table losing a row.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_review_sizing_single_source.py
"""

from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
DEV = Path(__file__).resolve().parents[2]
SKILLS = PLUGIN / "skills"
ROUTING = SKILLS / "_shared" / "references" / "model-routing.md"
ECONOMY = SKILLS / "_shared" / "references" / "orchestration-economy.md"
REVISE = SKILLS / "spec-to-pr" / "references" / "revise.md"
SHIP = SKILLS / "spec-to-pr" / "references" / "ship.md"
S2P = SKILLS / "spec-to-pr" / "SKILL.md"
LITE_PR = SKILLS / "lite-pr" / "SKILL.md"
MULTI_LITE = SKILLS / "multi-lite" / "SKILL.md"
MULTI_PR = SKILLS / "multi-pr" / "SKILL.md"
MULTI_SPEC = SKILLS / "multi-spec" / "SKILL.md"
REVIEW_GATE = SKILLS / "multi-spec" / "references" / "review-gate.md"
DISCOVER_AND_GATE = SKILLS / "multi-pr" / "references" / "discover-and-gate.md"
HANDOFF = SKILLS / "spec-to-pr" / "references" / "handoff.md"
GUARD = DEV / "tests" / "consistency" / "test_review_sizing_single_source.py"

TARGETS = [GUARD]

MUTANTS = [
    (
        "ship.md's plain PR-create example drops the Risk line",
        SHIP,
        '--body "Closes openspec/changes/<change-name>/. Checks: build + lint passed. Risk: <level> — <reason>; reviewers: <list>."',
        '--body "Closes openspec/changes/<change-name>/. Checks: build + lint passed."',
        TARGETS,
    ),
    (
        "ship.md's stacked PR-create example drops the Risk line",
        SHIP,
        '<parent-PR-number>. Closes openspec/changes/<change-name>/. Checks: build + lint passed. Risk: <level> — <reason>; reviewers: <list>."',
        '<parent-PR-number>. Closes openspec/changes/<change-name>/. Checks: build + lint passed."',
        TARGETS,
    ),
    (
        "the message-style table drops the Risk line",
        S2P,
        " Checks: <the checks that ran>. Risk: <level> — <reason>; reviewers: <list>.` |",
        " Checks: <the checks that ran>.` |",
        TARGETS,
    ),
    (
        "revise.md brings back round 2 after any fix commit",
        REVISE,
        "Round 2 runs only after round 1 fixed a Critical finding and the cap allows it,",
        "Round 2 runs whenever round 1 committed fixes,",
        TARGETS,
    ),
    (
        "the exit gate runs another round after any committed fix",
        REVISE,
        "unless this round fixed a Critical and the cap allows another round",
        "unless this round committed fixes and the cap allows another round",
        TARGETS,
    ),
    (
        "the Flags row brings back round 2 after any fix commit",
        S2P,
        "round 2 runs only after round 1 fixed a Critical; `1` opts out",
        "round 2 runs whenever round 1 committed fixes; `1` opts out",
        TARGETS,
    ),
    (
        "the Revise stub brings back round 2 after any fix commit",
        S2P,
        "round 2 runs only after round 1 fixed a Critical, scoped to that fix diff.",
        "round 2 runs whenever round 1 committed fixes, scoped to that fix diff.",
        TARGETS,
    ),
    (
        "lite-pr copies a sizing-table row instead of citing the table",
        LITE_PR,
        "**Dispatch the review agents directly",
        "| Low risk, code | `code-reviewer` | Sonnet |\n**Dispatch the review agents directly",
        TARGETS,
    ),
    (
        "multi-pr copies a sizing-table row instead of citing the table",
        MULTI_PR,
        "**This skill does not reimplement `/cla:spec-to-pr`.**",
        "| High risk | `code-reviewer` | Opus |\n**This skill does not reimplement `/cla:spec-to-pr`.**",
        TARGETS,
    ),
    (
        "spec-to-pr's SKILL.md copies a sizing-table row",
        S2P,
        "### Revise — PR-review loop",
        "| High risk | `code-reviewer` | Opus |\n### Revise — PR-review loop",
        TARGETS,
    ),
    (
        "multi-pr's discover-and-gate copies a sizing-table row",
        DISCOVER_AND_GATE,
        "3. **`/cla:spec-to-pr` caps.**",
        "| High risk | `code-reviewer` | Opus |\n3. **`/cla:spec-to-pr` caps.**",
        TARGETS,
    ),
    (
        "multi-spec's review gate copies a sizing-table row",
        REVIEW_GATE,
        "## Step 4 — Dispatch three agents, once, over the whole batch (when any change is large)",
        "| High risk | `code-reviewer` | Opus |\n## Step 4 — Dispatch three agents, once, over the whole batch (when any change is large)",
        TARGETS,
    ),
    (
        "multi-spec's review gate points a pre-code spec review at the PR table again",
        REVIEW_GATE,
        "so there is no diff or `Risk:` line to size by:",
        'so reviewer sizing follows "Review sizing by risk" in the same file:',
        TARGETS,
    ),
    (
        "lite-pr stops telling the agent to write the Risk line",
        LITE_PR,
        "put one line in the PR body: `Risk: <level> — <reason>; reviewers: <list>.`",
        "put one line in the PR body.",
        TARGETS,
    ),
    (
        "the sizing section drops the missing-line-means-high rule",
        ROUTING,
        "diff as high risk. The run records that as a Handoff Issue",
        "diff as low risk. The run records that as a Handoff Issue",
        TARGETS,
    ),
    (
        "revise.md stops citing the missing-line-means-high rule",
        REVISE,
        "treat the diff as high risk and record a Handoff Issue, as \"A missing line means high\" in that section says. ",
        "",
        TARGETS,
    ),
    (
        "lite-pr stops citing the missing-line-means-high rule",
        LITE_PR,
        "treat the diff as high risk and say so in your report, as \"A missing line means high\" in that section says. ",
        "",
        TARGETS,
    ),
    (
        "the sizing section brings back round 2 after any fix commit",
        ROUTING,
        "Round 2 reviews the fix diff with the same reviewers.",
        "Round 2 reviews the fix diff with the same reviewers. Round 2 runs whenever round 1 committed fixes.",
        TARGETS,
    ),
    (
        "Handoff's one-line body template drops the Risk clause",
        HANDOFF,
        "Checks: <the checks that ran>. Risk: <level> — <reason>; reviewers: <list>. Known issues:",
        "Checks: <the checks that ran>. Known issues:",
        TARGETS,
    ),
    (
        "Handoff's body-file form drops the Risk clause",
        HANDOFF,
        "the original one-liner, keeping its `Risk:` clause, plus",
        "the original one-liner plus",
        TARGETS,
    ),
    (
        "the sizing section stops defining prose-dominant",
        ROUTING,
        "A docs-only diff outside `skills/` is not prose-dominant.",
        "",
        TARGETS,
    ),
    (
        "spec-to-pr's Revise reference stops citing the table",
        REVISE,
        "Dispatch the reviewers and models that \"Review sizing by risk\" in `model-routing.md` gives for that level.",
        "Dispatch the reviewers.",
        TARGETS,
    ),
    (
        "the sizing table loses its high-risk row",
        ROUTING,
        "| High risk | `code-reviewer` + `silent-failure-hunter` | Opus |",
        "",
        TARGETS,
    ),
    (
        "the sizing section stops saying unsure means high",
        ROUTING,
        "**Unsure means high.**",
        "**Unsure is judged case by case.**",
        TARGETS,
    ),
    (
        "multi-pr stops citing the orchestration reference",
        MULTI_PR,
        " Cost rules for dispatch, tests and debris: `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/orchestration-economy.md`.",
        "",
        TARGETS,
    ),
    (
        "multi-lite stops citing the orchestration reference",
        MULTI_LITE,
        " Cost rules for dispatch, tests and debris: `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/orchestration-economy.md`.",
        "",
        TARGETS,
    ),
    (
        "multi-spec stops citing the orchestration reference",
        MULTI_SPEC,
        " Cost rules for dispatch, tests and debris: `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/orchestration-economy.md`.",
        "",
        TARGETS,
    ),
    (
        "multi-spec copies a rule from the orchestration reference",
        MULTI_SPEC,
        "Standing discipline across every phase below",
        "Run the full suite once. Standing discipline across every phase below",
        TARGETS,
    ),
    (
        "the orchestration reference drops the debris check",
        ECONOMY,
        "git status --porcelain --ignored --untracked-files=all",
        "git status",
        TARGETS,
    ),
]
