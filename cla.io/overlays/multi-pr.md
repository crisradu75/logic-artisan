# multi-pr — project context overlay

<!--
Project-specific overlay for the `multi-pr` cla skill. This file is repo-local
(never distributed with the plugin). The generic SKILL.md supplies the procedure; this
file holds this skill's own rules and incidents here; facts are in `cla.io/project-facts.md`.
The file is optional.
-->

## Incident / offense history

**One `/cla:multi-pr` chain has reached Phase 1c in this repo**, on 2026-08-23. Its notes,
`cla.io/retro/multi-pr-run-notes-2026-08-23.md`, are tracked from before run notes went local, and
hold this repo's only measured per-change timings (two `large-extend` changes). There is no
worktree-pivot or stranded-docs precedent to offer; the two incidents below came from landing a
stack by hand, not from a chain.

**2026-08-14 — host classifier refused `gh pr merge` regardless of configuration.** In this repo,
on Claude Code with `--permission-mode auto`: `Bash(gh *)` present in the machine-local `settings.local.json`,
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
