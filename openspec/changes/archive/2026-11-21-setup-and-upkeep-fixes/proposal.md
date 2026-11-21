# Proposal

Budget: protected

## Why

Four setup and upkeep skills write the user's own files or a public GitHub repo, and four of their steps are wrong or unsafe today. Saved file-path permissions use a form Claude Code never matches, so every one is dead. The upstream reporter posts a public comment or issue without showing the text first. The learnings skill bans edits to a shipped skill's bundled script while its own routing sends such a script upstream. And its single prompt shows only a title, not the edit. The owner decided the last two as Q20 and Q21 in `cla.io/decisions/warp-patterns-adoption-2026-11-21.md`.

## What Changes

- `save-permissions` saves a file-path rule as `Read(<gitignore-style path>)` and saves no `Glob` or `Grep` path rule, and it scans only calls the user approved at a permission prompt.
- `report-upstream` shows the draft title and body (or comment) and posts only on an explicit yes, separate from confirming a duplicate; a duplicate match must share a concrete detail and is shown to the user.
- `codify-learnings` shows each fix's exact before and after text above its one prompt, and routes a shipped skill's bundled script upstream instead of banning the edit.
- Wording and pointer fixes in the four skills and `cla-setup` and `new-worktree` need no spec change.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `permission-saving`: two ADDED requirements.
- `upstream-reports`: one ADDED requirement, one MODIFIED.
- `session-learnings`: two MODIFIED requirements.

## Impact

Five skill files and their tests. One ledger entry reworded. No script or hook changes.

## Risks noted

- The ban on editing a skill's bundled scripts is replaced by routing; in a repo that holds the plugin's own source the routing table still allows the edit.

## Open questions

None.
