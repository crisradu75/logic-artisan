# multi-pr — project context overlay

<!--
Project-specific overlay for the `multi-pr` cla skill. This file is repo-local
(never distributed with the plugin). The generic SKILL.md supplies the procedure; this
file supplies the repo's facts. A skill runs fine against an empty stub — fill in
only the sections its SKILL.md references, delete the rest.
-->

## Repo commands
<!-- build/lint/test/dev commands with this repo's package-manager + workspace tokens -->

## Packages, paths, and app names
<!-- workspace/app/package/dir names and file paths this skill touches -->

## Permission sets
<!-- repo-scoped tool-permission expectations, if the skill uses them -->

## Incident / offense history

**No `/cla:multi-pr` chain has reached Phase 1c in this repo.** There is no
`cla.io/retro/multi-pr-run-notes-*.md` file — the file a chain first writes at Phase 1c step 4, and
appends measured actuals to at Phase 3 step 6. So this repo has no measured per-change timings, no
worktree-pivot precedent, and no stranded-docs precedent to offer; the two incidents below came
from landing a stack by hand, not from a chain.

`grep -rn "overlays/multi-pr" .claude/plugins/cla/skills/multi-pr/` returns 9 pointers into this
file. Counted by hand against what is actually written below:

- **3 resolve** — `SKILL.md:101` (the reference-list entry), `discover-and-gate.md:61` and
  `change-loop.md:42` (both reach the dated 2026-08-14 incidents, which are present).
- **2 ask for something absent and say so** — the worktree pivot (`SKILL.md:30`) and the
  stranded-docs precedent (`discover-and-gate.md:25`). Both were reworded to read correctly when
  the fact is missing.
- **4 ask for something absent and do not hedge** — the infra hard-gate command
  (`discover-and-gate.md:66`), the local-stack status command (`:79`), and the build/lint/test
  fallback in `change-loop.md:32` and `cleanup.md:12`, all of which want the empty "Repo commands"
  section above.

Filling this file is the fix for those 4, not softening more pointers.

**2026-08-14 — host classifier refused `gh pr merge` regardless of configuration.** In this repo,
on Claude Code with `--permission-mode auto`: `Bash(gh *)` present in `.claude/settings.local.json`,
`ALLOW_PR_MERGE=1` prefixed (the plugin's own hook confirmed it was disarmed), and the merge was
still refused by the host's auto-mode permission classifier — and refused again without
`--delete-branch`, and again after adding an explicit `Bash(gh pr merge *)` allowlist entry. This
is the measured basis for the stacked policy's "treat the first refusal as the answer" rule; the
6-PR remediation stack (#63-#68) was landed manually as a result.

**2026-08-14 (same day) — the deletion path closed a dependent PR despite documented retargeting.**
Landing that same stack: merging #63 with the delete flag CLOSED #64 (base: the deleted branch)
rather than retargeting it. Recovery: restore the deleted branch from the merge commit's second
parent, push it, reopen the PR, retarget it to main, delete the scaffold. The stacked landing
recipe is retarget-first because of this incident; the warn-stacked-pr-merge hook's close warning
is measured, not theoretical.
<!-- past failures in this repo that justify a discipline rule in the skill -->

## Product / domain context
<!-- this repo's applications, data, market, concepts -->

## Infrastructure values
<!-- ports, service names, env-var names tied to this repo's processes -->

## Repo file lists
<!-- enumerated specs/docs/files this skill is expected to touch -->
