# Proposal

## Why

Recall now writes a query log (`add-mnemo-recall`, `query-log`), but nothing reads it, so a question the notes failed to answer is never fixed. The self-improvement decision (`cla.io/decisions/recursive-self-improvement-2026-11-16.md`) settles how the loop works: on demand, every change a PR the owner merges, and shared rules filed as issues on `mnemo-plugin`. Structure Q14 deferred the loop's metadata until this skill exists. This is the last change of the plugin-structure batch.

## What Changes

- Add `plugins/mnemo/skills/mnemo-improve/`. The owner says "run Mnemo maintenance" in a domain session, and the skill:
  - reads the query-log lines since the last loop PR closed, and counts unreadable ones;
  - proposes changes, each citing its log lines;
  - builds them on branches in separate working copies, never in the session's own tree;
  - scores each PR against `main` (design D7);
  - after the owner's yes, opens one domain PR, plus a `[meta]` PR for any change to the loop, scorer, guardrails or test set;
  - after the owner approves the text, files cross-domain rules as issues on `mnemo-plugin` through `gh api` (REST), searching first.
- Add the deferred metadata of structure Q14 under the add-only rule: the `questions` and `links` fields, `hubs/`, `archive/` and `_meta/tests/questions.yml`. `mnemo_schema_version` and PR labels stay out (design D11).
- Extend `mnemo_check.py`'s `schema` and `links` checks for those fields and folders.
- Add a `repository` field to `plugin.json`, the issue target (self-improvement Follow-ups).
- Add 20 trigger prompts.
- Bump `plugin.json` to `0.8.0`.

## Capabilities

### New Capabilities

- `improve-run`: what starts a run, when it stops, which log lines it covers, and that the session's tree stays untouched.
- `improve-proposals`: what each signal may produce.
- `improve-guardrails`: protected note bodies, provenance, the owner-only rules, injected text, approval before GitHub, failures that stop.
- `improve-pull-requests`: the domain PR, the `[meta]` PR, their bodies, checks before a push.
- `improve-scorecard`: question sets, answers per side, and pass or fail for a change and a PR.
- `upstream-issues`: filing approved rules on `mnemo-plugin`.
- `improve-triggering`: description and trigger evals.
- `loop-metadata`: hub notes, archived notes and the test-set file.

### Modified Capabilities

These capabilities are added by earlier changes in this batch, which archive first:
- `note-schema` (`add-check-scripts`): "Optional and extra fields", "Base field values", "Domain type rules".
- `note-checks` (`add-check-scripts`): adds "Links field entries resolve".
- `domain-layout` (`add-mnemo-setup`): "No deferred metadata", "Note folders"; adds "Empty test set".
- `domain-instructions` (`add-mnemo-setup`): "Agent rules file".
- `note-recall` (`add-mnemo-recall`): "Read, follow links one level, search again".
- `review-scan` (`add-mnemo-review`): "Deferred metadata is not checked".

Used as defined: `query-log` (input), `recall-answers` (scorecard answers), `check-interface`, `note-saving`, `plugin-release`, the `add-guard-hooks` capabilities, and `domain-instructions` "Domain wall".

## Impact

- New files: `plugins/mnemo/skills/mnemo-improve/` (`SKILL.md`, `references/`), the setup template for the test set, tests and eval prompts.
- Changed files:
  - `plugins/mnemo/scripts/mnemo_check.py`
  - the setup templates (`AGENTS.md`, folder list)
  - recall's `SKILL.md` (follows `links`)
  - `plugins/mnemo/.claude-plugin/plugin.json` (`repository`, version)
  - `README.md`, `plugins/mnemo/skills/README.md`, `CLAUDE.md`
- Owner actions: the device checks in `tasks.md` group 1.
- Risk: high. The change edits skills and scoring and writes user files, so the implementer runs on Opus.
- Out of scope: moving notes into `archive/`, scheduled runs, any GitHub workflow.
- Design: see `design.md`.
