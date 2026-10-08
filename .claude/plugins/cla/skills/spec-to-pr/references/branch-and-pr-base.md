# `<branch>` and `<pr-base>` — full rules

Read when `--pr-base` is passed (a stacked chain), or when a branch lookup surprises you. `SKILL.md` carries the short form.

## Why `<branch>` falls back

It was hardcoded as `feature/<change-name>` in the scripts that both CREATE and FIND the branch — and because all three lookups use `git rev-parse --verify --quiet`, a miss exits 1 with empty stderr, so a repo on any other convention reported `branch: false, pr: {open: false}, fix_rounds_applied: 0` — indistinguishable from *nothing has been done yet*. The orchestrator acts on that by redoing completed work and can open a duplicate branch and PR. Resolving ONE configured prefix does not close that: `references/ship.md` permits shortening a verbose change name, and a convention varying its middle segment (`claude/fix/x` vs `claude/feature/x`) cannot be expressed by any single prefix. So `probe_state._resolve_branch` tries the configured name, then falls back to the one local branch whose final path segment is the change name, announces which it adopted, and refuses to guess when several match.

## `<pr-base>`

**`<pr-base>`** — the branch THIS change's work is cut from and its PR opened against. Default: `<base-branch>`, and with no flag the two are identical everywhere. An explicit **`--pr-base <branch>`** argument overrides it — the stacked case, where a dependent change is built on top of its parent's still-open feature branch. The substitution rule is single and total: **wherever a phase names `<base-branch>` as this change's branch-off point, PR base, or diff-scoping anchor** (Ship's branch preflight, `gh pr create --base`, Test's changed-path range, Revise's diff scoping, **and the worktree recipe's branch creation** — `git worktree add ... -b <branch> origin/<pr-base>`, parent already pushed; cutting a stacked child's worktree from `origin/<base-branch>` silently rebuilds the exact missing-parent failure this flag exists to prevent, and every preflight guard then passes), **read `<pr-base>` instead**. Only resolving the repo default itself and Archive's semantics keep meaning the literal default branch. Three consequences to hold: `gh pr create` MUST pass `--base <pr-base>` explicitly (with no flag GitHub defaults the PR to the repo default branch, silently producing a diff that includes the whole parent chain); on a stacked-child RESUME do not act on `probe_state.py`'s `fix_rounds_applied` or branch/PR probes directly — they measure against the repo default, so the parent's commits satisfy them and would skip phases that never ran; recount with `git log origin/<pr-base>..HEAD --grep "fix: review round"` and judge phase completion against `<pr-base>`-anchored evidence; and Handoff's next-steps must NOT print the bare `gh pr merge` line for a stacked child — a stacked PR lands parents-first, retargeted before its parent merges, with merge commits, so name that instead.

## Landing a stack

The user lands a stack built with `--pr-base`, by hand, parents first. Per parent, two commands in
this order:

1. `gh pr edit <child> --base <base-branch>` — retarget the child FIRST.
2. `gh pr merge <parent> --merge --delete-branch`.

Do not rely on GitHub's documented auto-retargeting. In a live landing, `gh`'s `--delete-branch`
deleted the parent branch before any retarget, and GitHub CLOSED the dependent PR; recovery took
restoring the deleted base from the merge commit's second parent. Retargeting first makes the
deletion close nothing.

Use a **merge commit, never a squash**, on a stack. Squashing a parent rewrites its commits, so a
surviving child re-shows the parent's whole diff and conflicts with it (measured on a throwaway
3-deep stack). With a merge commit, each child's diff shrinks to its own work once its parent lands.

If the repo requires squash merges: after each parent lands, rebase its child before merging it —
`git rebase --onto origin/<base-branch> <parent-tip-sha> <child-branch>`, then
`git push --force-with-lease` — where `<parent-tip-sha>` is the parent's head before it was squashed.
