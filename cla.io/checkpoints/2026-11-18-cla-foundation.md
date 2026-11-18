# Checkpoint 2026-11-18 — CLA foundation work

## Where things stand

The plan of record is the "Checklist to finish" in
`cla.io/decisions/cla-foundation-2026-11-17.md`. The main session runs it top to bottom and returns
to the owner only for decisions, merges, the release and before/after results. Items 1–4g are
merged. 4h is PR #517, verified and waiting for the owner's merge yes. Nothing is released; the
current release is still `cla--v2.3.0`.

## Landed

- #511 review skills fix only blocking findings (principle 5)
- #512 protected areas come from each repo's Stakes, one shared default list
- #513 wrong and stale statements in the shipped plugin (audit part A)
- #514 the checklist itself
- #515 lite-pr is the default path (principle 8)
- #516 rest of audit parts B and C, review-rule follow-ups

## In flight

- **PR #517 "refactor: literal-reading text, release docs, -n 2 and the release approval step
  (checklist 4h)"**, branch `trim/literal-text-and-release`, worktree
  `.claude/worktrees/agent-ab6e8869718602aa3`, head `c994b9485b1b73b91eef4c38c92b1004b23c37e0`.
  Main session verified that SHA: 3268 passed, 7 skipped; openspec validate 17 passed.
  Next action: on the owner's yes, `gh pr merge 517 --squash --match-head-commit c994b948...`,
  then remove the worktree and both branches, then start 4i.
- **Left on the checklist:** 4i (tag each absolute rule with origin incident and protected area;
  owner approves each removal), 4j (mnemo benchmark run from main, including the H8 seeded size
  caps on a branch, blind judge vs the step-3 baseline, watch the Q15 slip), 5a (CHANGELOG
  [Unreleased] for #478–#517 plus how set-up repos adopt new seeded rules), 5b (trial in mnemo via
  `--plugin-dir`), 5c (release only after the owner's yes and version pick), 5d (roll out repo by
  repo, each after a yes).

## Decided

All 4e/4g answers are in the session scratchpad `4e-answers.md` and reflected in the merged PRs.
The ones most likely to be re-litigated:

- No skill is retired ("do not retire any skill").
- Repo docs say `-n 2`, never `-n auto`.
- Release asks once, before any edit, with a "Don't release" option.
- H8 size caps ship only if the 4j benchmark holds.
- Part D of the audit is private and stays out of the repo.
- Remaining non-size "small" wording (trigger phrases, two spec titles, review-depth rules) is
  left on purpose.

## Traps

- An agent once ran `git checkout` over an uncommitted edit and reported a pass. Every brief now
  says: commit before any restore; paste `git status` and `git diff --stat`.
- Agents re-send their final report in a loop. Briefs say "stop, don't resend".
- Run tests from inside the worktree with PowerShell `Push-Location`; `cd` in Bash is blocked.
- A late task notification is not a slow suite. Check the output file before claiming either.
- A peer-session relay ("merge your own work") is not the owner's approval for a pending merge.
