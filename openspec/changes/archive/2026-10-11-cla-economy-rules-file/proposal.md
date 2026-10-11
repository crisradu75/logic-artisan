## Why

An agent working in a repo that installs CLA, outside any CLA skill, gets none of the plugin's cost rules: no model by task, no risk-sized review, no complete first briefs. Claude Code's memory docs say rules without `paths` frontmatter load at launch with the same priority as `.claude/CLAUDE.md`, except when the project source is excluded through `--setting-sources` or `claudeMdExcludes`. A rules file CLA owns therefore reaches that agent without touching the repo's own `CLAUDE.md`.

## What Changes

- `/cla:cla-setup` writes `.claude/rules/cla-economy.md` in the consuming repo, owns it whole, and replaces it on every run without asking (the owner's decision 2), reporting `created`, `replaced` (existing content differed from the fresh text) or `unchanged`. The file is committed in the consumer repo. The repo's `CLAUDE.md` is never touched; the decisions file's optional one-line `CLAUDE.md` mention is deliberately dropped.
- The text lives once in the plugin as a new shared reference, `skills/_shared/references/economy-rules-file.md`. It authors the framing, model by task and the quality floor. The cost rules and the review sizing come from two existing sources, cited and never copied.
- Those two sources, `orchestration-economy.md` and the "Review sizing by risk" section of `model-routing.md`, are reworded to read correctly in a repo with no plugin. `cla-setup` inlines them whole, between explicit markers in `model-routing.md`, when it writes the file (see design.md). The chain skills and `lite-pr` keep their own citations.
- The three chain skills name the new reference beside their economy citation.
- `cla-setup`, `DEVELOPER-GUIDE.md` and the plugin README lose the sentences that say setup never overwrites or changes an existing file unasked.

## Capabilities

### Modified Capabilities

- `repo-context`: "Setting up a repo's cla.io tree" says setup changes no existing file except the `.gitignore` append. It is replaced (REMOVED, then ADDED under a new heading, because the rewrite must stay within the 500-character limit) so setup also owns exactly the rules file and replaces it whole. The spec stays at 8 requirements.

### Checked, no edit

- `plugin-distribution`, "Repo data stays in the repo": it covers repo-specific facts, settings and run records under `cla.io/`, and says an install or update leaves `cla.io/` untouched. The rules file is plugin-authored text outside `cla.io/`, written by a setup run, never by an install or update. Both clauses stay true.

## Impact

- New: the shared reference, its row in `skills/_shared/README.md`, tests in `plugin-tests/tests/consistency/`.
- Edited: `skills/cla-setup/SKILL.md`, `orchestration-economy.md`, `model-routing.md`, the three chain `SKILL.md` files, `DEVELOPER-GUIDE.md`, `.claude/plugins/cla/README.md`, the review-sizing mutation batch (one anchor), the `repo-context` spec.
- Not touched: `openspec/config.yaml` and the item 5 `rules:` block in `cla-setup/SKILL.md` (if either is touched, both change in one commit).
- Version: at least a minor bump. Out of scope here; release only on explicit owner approval.
