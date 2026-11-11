# Proposal

## Why

Behaviour the plugin ships has no requirement, and the specs that should hold it are full (issue 442).

- Reading and writing both `CLAUDE.md` and `AGENTS.md` appears in no spec.
- `/cla:cla-setup` asking the test-proof question appears in no spec.
- The `pre-push` refusal of the remote's own default branch, and the prompt before a push that skips that guard, are covered only by "Direct pushes to main are refused".
- `repo-context` and `plugin-distribution` hold 8 requirements each and mix unrelated concerns.
- Three `guard-hooks` requirements each hold several outcomes, against "one outcome per requirement".

## What Changes

- New `instruction-files`: every instruction file is read; a rule goes to the file the repo already uses; no instruction file is created silently.
- New `cla-setup`: the four setup requirements move out of `repo-context` unchanged, and one is added for the test-proof question.
- New `copilot-cli`: the three Copilot requirements move out of `plugin-distribution` and the two Copilot guard requirements out of `guard-hooks`, all unchanged.
- New `git-guards`: "Destructive git commands ask first" splits into five requirements, and the two `pre-push` refusals and the prompt for a push that skips that guard join them. A prompt for a stash during an unfinished merge, already in the hook, gets its requirement.
- New `guard-warnings`: "Risky actions warn" splits into its five warnings.
- `guard-hooks`: "Unsafe commands are blocked" splits into three.
- Tests keep their place; their `requirement:` lines name the new homes.

## Capabilities

### New Capabilities

- `instruction-files`, `cla-setup`, `copilot-cli`, `git-guards`, `guard-warnings`.

### Modified Capabilities

- `guard-hooks`: three blocking requirements replace the combined one; the ask, warn, push and Copilot requirements leave.
- `repo-context`: four setup requirements leave (4 remain).
- `plugin-distribution`: three Copilot requirements leave (5 remain).

## Impact

Specs, `openspec/spec-map.md` and test comment lines only. No shipped plugin file changes. Owner decision: the skills named in no spec (checkpoint, feedback, new-worktree, project-review, report-upstream, right-model, save-permissions, shape-decision) get no spec; `openspec/spec-map.md` says `CLAUDE.md` governs them.
