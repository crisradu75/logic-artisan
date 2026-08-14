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
