"""Mutation batch for test_chain_merge_shared.py.

Each mutant puts back one thing the chain-merge-shared change removed: a chain
merging on its own copy of the command, `multi-pr` merging a head nobody
checked, a resume merging findings nobody fixed, a rule the move dropped, or a
deleted `multi-pr` policy coming back.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_chain_merge_shared.py
"""

from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
DEV = Path(__file__).resolve().parents[2]
SKILLS = PLUGIN / "skills"
SHARED = SKILLS / "_shared" / "references" / "chain-merge.md"
PR_LOOP = SKILLS / "multi-pr" / "references" / "change-loop.md"
PR_SKILL = SKILLS / "multi-pr" / "SKILL.md"
LITE_LOOP = SKILLS / "multi-lite" / "references" / "candidate-loop.md"
PR_CLEANUP = SKILLS / "multi-pr" / "references" / "cleanup.md"
README = PLUGIN / "README.md"
GUIDE = DEV.parent / "DEVELOPER-GUIDE.md"
SPEC_REFS = SKILLS / "spec-to-pr" / "references"
GUARD = DEV / "tests" / "consistency" / "test_chain_merge_shared.py"

TARGETS = [GUARD]

MUTANTS = [
    (
        "multi-pr's merge step stops sending the merge through the shared file",
        PR_LOOP,
        "exactly as `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/chain-merge.md` states,",
        "as below,",
        TARGETS,
    ),
    (
        "multi-lite's step 8b stops sending the merge through the shared file",
        LITE_LOOP,
        "Run them as `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/chain-merge.md` states,",
        "Run them as below,",
        TARGETS,
    ),
    (
        "multi-pr carries its own merge command again, without the head guard",
        PR_LOOP,
        "   - **`MERGED` confirmed** →",
        "   - Run `ALLOW_PR_MERGE=1 gh pr merge <#> --squash --delete-branch`.\n   - **`MERGED` confirmed** →",
        TARGETS,
    ),
    (
        "the shared merge stops passing the checked head",
        SHARED,
        "--squash --delete-branch --match-head-commit <head_sha>",
        "--squash --delete-branch",
        TARGETS,
    ),
    (
        "the pre-merge checks stop reading the remote checks",
        SHARED,
        "Run `gh pr checks <pr> --json name,bucket` and read the result",
        "Read the result",
        TARGETS,
    ),
    (
        "the pre-merge checks stop comparing the PR head with the recorded head",
        SHARED,
        "`headRefOid` must equal `head_sha`;",
        "`headRefOid` is read for the record;",
        TARGETS,
    ),
    (
        "multi-pr stops recording the head when the PR opens",
        PR_LOOP,
        "record this change's `branch`, `pr_number` and `head_sha` in the running notes",
        "record this change's `branch` and `pr_number` in the running notes",
        TARGETS,
    ),
    (
        "a multi-pr resume merges a moved head",
        PR_LOOP,
        "; a moved head is never merged (",
        "; a moved head is re-checked and merged (",
        TARGETS,
    ),
    (
        "a needed merge that fails no longer halts multi-pr",
        PR_LOOP,
        "That is a **Tier A halt** (step 3): print step 3's status enumeration, naming the reason, and start no later change.",
        "Leave it open and continue with the next change.",
        TARGETS,
    ),
    (
        "the stacked policy comes back to multi-pr",
        PR_SKILL,
        "Genuine independents — neither edge — stay open.",
        "Genuine independents — neither edge — stay open; under the stacked policy nothing merges.",
        TARGETS,
    ),
    (
        "a multi-pr resume merges a head with no enforced marker",
        PR_LOOP,
        "with the `head_sha` the running notes recorded, **but only when its row's `status` is `enforced`** (written once step 4b passes);",
        "with the `head_sha` the running notes recorded;",
        TARGETS,
    ),
    (
        "a multi-pr resume infers lost findings fixed",
        PR_LOOP,
        "**Never infer them fixed.** The reason is `findings lost on resume`: a change a later one needs merged is a Tier A halt (step 3);",
        "Treat them as fixed and go to step 5;",
        TARGETS,
    ),
    (
        "step 4b stops writing the enforced marker",
        PR_LOOP,
        "   **Passing → write `status: enforced` to this change's row.** It is the marker step 1 reads on a resume.",
        "   It is what step 1 reads on a resume.",
        TARGETS,
    ),
    (
        "a resume merges a change with no recorded head",
        PR_LOOP,
        ", and neither is one with no recorded `head_sha`.",
        ".",
        TARGETS,
    ),
    (
        "a resumed change goes back to spec-to-pr without comparing its head",
        PR_LOOP,
        "gets the head comparison in `chain-merge.md` \"Record the head\" before step 2 hands it back to `/cla:spec-to-pr`: a different head is `head moved since review` — a Tier A halt if a later change needs it merged, else left open with that reason.",
        "goes to step 2, which hands it back to `/cla:spec-to-pr`.",
        TARGETS,
    ),
    (
        "step 4's commit no longer becomes the recorded head",
        PR_LOOP,
        "Push it, then run the three commit checks in `chain-merge.md` \"Record the head\", which make it the new `head_sha`.",
        "Push it.",
        TARGETS,
    ),
    (
        "a failed commit check in step 4 neither halts nor leaves the PR open",
        PR_LOOP,
        "with the reason `fix not committed` or `push not verified`: a change a later one needs merged is a Tier A halt (step 3); an independent one is left open with that reason in its row.",
        "and the chain moves on.",
        TARGETS,
    ),
    (
        "step 3 stops recording the head after a spec-to-pr re-run",
        PR_LOOP,
        "Record the head again after every later `/cla:spec-to-pr` call on this change in steps 3–4, since that call may have pushed. ",
        "",
        TARGETS,
    ),
    (
        "the shared file records the head only when the PR first opens",
        SHARED,
        "Whenever the skill the chain runs hands back an open PR, read its head with",
        "The moment an item's PR opens, read its head with",
        TARGETS,
    ),
    (
        "a failed base pull after a merge no longer halts the next item",
        SHARED,
        "**a pull that fails there halts the run**",
        "a pull that fails there is retried",
        TARGETS,
    ),
    (
        "the bootstrap carries on past a failed pull",
        SHARED,
        "A failed pull halts",
        "A failed pull is noted for",
        TARGETS,
    ),
    (
        "the merge is no longer confirmed on the local base",
        SHARED,
        "`git pull`, then confirm `git log --oneline -1` shows `merge_commit`.",
        "`git pull`.",
        TARGETS,
    ),
    (
        "BEHIND loses its explanation",
        SHARED,
        "Squash applies onto the current base, so GitHub can still merge it; branch protection that requires an up-to-date branch reports `BLOCKED` instead. ",
        "",
        TARGETS,
    ),
    (
        "multi-pr's final report drops the merge notes",
        PR_CLEANUP,
        "`behind base: merged tree not tested`, `gate skipped: no source-affecting paths`, `base not updated`, ",
        "",
        TARGETS,
    ),
    (
        "a hand-resolved conflict merges with no note that it was not re-reviewed",
        PR_LOOP,
        " The hand-resolved merge is gated but not re-reviewed, so write `conflicts resolved, not re-reviewed` in the row's notes; the final report names it.",
        "",
        TARGETS,
    ),
    (
        "the squash alternative for a hand-built stack is lost",
        SPEC_REFS / "branch-and-pr-base.md",
        "`git rebase --onto origin/<base-branch> <parent-tip-sha> <child-branch>`, then",
        "a rebase, then",
        TARGETS,
    ),
    (
        "the stacking row comes back to the README",
        README,
        "merging each before its dependents |",
        "merging each before its dependents (or stacking PRs on their parents when merging is unavailable) |",
        TARGETS,
    ),
    (
        "the guide's batch section names a stacked policy again",
        GUIDE,
        "**The one place CLA merges.**",
        "**The one place CLA merges (or stacks, under the stacked policy).**",
        TARGETS,
    ),
    (
        "GUARD: the scanner stops seeing 'stacking'",
        GUARD,
        'r"stack(?:ed|ing)|open all',
        'r"stacked|open all',
        TARGETS,
    ),
    (
        "GUARD: the merge-command scanner stops matching the env prefix",
        GUARD,
        '_MERGE_COMMAND = re.compile(r"ALLOW_PR_MERGE=1 gh pr merge\\b")',
        '_MERGE_COMMAND = re.compile(r"ALLOW_PR_MERGE=2 gh pr merge\\b")',
        TARGETS,
    ),
]
