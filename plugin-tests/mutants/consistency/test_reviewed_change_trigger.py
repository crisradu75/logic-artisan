"""Mutation batch for test_reviewed_change_trigger.py.

Each mutant rewords one side of the subject contract between multi-spec, which
writes the subjects, and spec-to-pr's Review, which skips the checklist on them.
A reworded side reads fine on its own and silently stops the skip firing — or,
for the last mutant, lets a post-review edit squash in unseen.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_reviewed_change_trigger.py
"""

from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
DEV = Path(__file__).resolve().parents[2]
SKILLS = PLUGIN / "skills"
SPEC_TO_PR = SKILLS / "spec-to-pr" / "SKILL.md"
REVIEW_GATE = SKILLS / "multi-spec" / "references" / "review-gate.md"
PHASES = SKILLS / "multi-spec" / "references" / "phases.md"
AUTHORING_BRIEF = SKILLS / "multi-spec" / "references" / "authoring-brief.md"

TARGETS = [DEV / "tests" / "consistency" / "test_reviewed_change_trigger.py"]

MUTANTS = [
    (
        "multi-spec rewords its review-fix commit, so spec-to-pr's skip never fires",
        REVIEW_GATE,
        'git commit -m "docs(openspec): apply review fixes to <batch-slug> proposals"',
        'git commit -m "docs(openspec): review fixes for <batch-slug>"',
        TARGETS,
    ),
    (
        "multi-spec retitles its PR, so a squash-merged batch is reviewed twice",
        PHASES,
        'gh pr create --title "docs(openspec): <N> <batch-slug> change proposals"',
        'gh pr create --title "docs(openspec): <batch-slug> proposals (<N>)"',
        TARGETS,
    ),
    (
        "spec-to-pr drops the squash-form subject from its trigger",
        SPEC_TO_PR,
        "`docs(openspec): <N> <slug> change proposals (#<pr>)`",
        "`docs(openspec): <slug> proposals`",
        TARGETS,
    ),
    (
        "spec-to-pr stops checking the squashed PR's last commit, so a post-review "
        "edit is skipped unseen",
        SPEC_TO_PR,
        "`gh pr view <pr> --json commits --jq '.commits[-1].messageHeadline'`, starts with "
        "`docs(openspec): apply review fixes to ` or `docs(openspec): propose `",
        "the PR title, matches",
        TARGETS,
    ),
    (
        "spec-to-pr loosens the squash check to any docs(openspec) subject, so a "
        "post-review docs edit is skipped unseen",
        SPEC_TO_PR,
        "starts with `docs(openspec): apply review fixes to ` or `docs(openspec): propose `",
        "starts with `docs(openspec): `",
        TARGETS,
    ),
    (
        "multi-spec rewords its propose commit, so a READY batch never skips",
        AUTHORING_BRIEF,
        'git commit -m "docs(openspec): propose <name>"',
        'git commit -m "docs(openspec): add <name>"',
        TARGETS,
    ),
]
