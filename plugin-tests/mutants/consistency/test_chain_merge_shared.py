"""Mutation batch for test_chain_merge_shared.py.

Each mutant puts back one thing the chain-merge-shared change removed: a chain
merging on its own copy of the command, `multi-pr` merging a head nobody
checked, or a deleted `multi-pr` policy coming back.

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
        "GUARD: the merge-command scanner stops matching the env prefix",
        GUARD,
        '_MERGE_COMMAND = re.compile(r"ALLOW_PR_MERGE=1 gh pr merge\\b")',
        '_MERGE_COMMAND = re.compile(r"ALLOW_PR_MERGE=2 gh pr merge\\b")',
        TARGETS,
    ),
]
