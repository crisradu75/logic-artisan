## Why

A review of the outcome-level rewrite of the live specs (`live-specs-at-outcome-level`) found requirements that say more or less than the plugin does: a guard trigger wider than the hook, a merge warning worded as any merge, one heading joining two opposite failure behaviours, safety promises for the small-change chain dropped although tests still prove them, a merge policy a scenario relied on but no requirement defined, an internal hand-off named as the promise, and a partial list of `/cla:spec-to-pr` options.

## What Changes

- guard-hooks: the worktree block names exactly what it blocks, the stacked-merge warning names `gh pr merge --delete-branch`, and all four override variables are named.
- change-chains: multi-pr's run, merging and halt each get their own requirement; the obligation requirement states only the outcome. The small-change chain's four requirements move to a new capability, `small-change-chains`, because change-chains is at its limit of 8.
- small-change-chains: the dropped promises return: findings that cannot be recounted count as open, a pre-confirmed run that names no policy gets `merge-dependencies-only`, and a resumed run never merges an unchecked head.
- change-workflow: every documented `/cla:spec-to-pr` option is named; the authoring-rules requirement points at the shipped `rules:` block instead of copying its numbers.
- repo-context and plugin-distribution: a plain heading for seeding the rules, and the install command gains `--scope project`.
- Outside the specs: test markers are re-pointed, dead spec citations in three files are reworded, and `openspec validate --specs --strict` joins CLAUDE.md's pre-PR gate and the release preconditions.

## Impact

- `openspec/specs/{guard-hooks,change-chains,change-workflow,repo-context,plugin-distribution}`, new `openspec/specs/small-change-chains`.
- Tests carrying `requirement:` markers; `test_mutation_gate_sites_agree.py`, `test_orchestrators_state_turn_liveness.py` and `_shared/references/skill-authoring.md` (wording only).
- `CLAUDE.md` and `.claude/skills/release/SKILL.md`: the OpenSpec CLI is now a release precondition.
