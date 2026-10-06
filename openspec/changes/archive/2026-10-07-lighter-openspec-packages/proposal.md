## Why

CLA's authoring and review skills make OpenSpec change packages far heavier than OpenSpec's own `spec-driven` schema asks for (issue #291): design.md is mandatory, the review rubric can only add text, and a multi-spec change is reviewed twice. Nothing links a scenario to a test, which is also issue #280 seen from the task side. The aim is packages as light as OpenSpec intends, with the scenario-to-test rule as the quality counterweight.

## What Changes

- **design.md becomes conditional.** multi-spec's authoring brief and post-check, multi-spec's PR body, and review-change's checklist require proposal, tasks and a spec delta. design.md is required only when a stock trigger applies, and the author names it. Review reads an absent design.md as "(absent)" instead of stopping. The pinned-parameters block becomes conditional, and the doc-sync task is dropped.
- **cla-init seeds `openspec/config.yaml` `rules:`** with the stock limits. When the file already exists, it prints the block instead of merging, which keeps never-clobber. This repo's own config gets the same block.
- **Size is a review finding.** Breaking a stock limit, or restating the proposal or specs, is Important. Cutting is a listed FIX FIRST remedy and is preferred over adding. Design decisions stop counting toward the size gate.
- **Scenario-to-test link.** Each scenario a change adds or rewrites gets a test task or a `manual: <reason>` note. Review flags a scenario with neither. spec-to-pr's Implement post-check greps for each test a ticked task names (closes #280).
- **Lifecycle cuts.** spec-to-pr and multi-pr skip the checklist pass for a change multi-spec already reviewed. multi-spec's batch review uses the per-change size gate. The review report drops the parallelism plan and the three-verified-claims minimum.
- **No invented requirements.** A change with no externally visible behaviour change sets `skip_specs: true` and writes no delta. Review reports a requirement with no observable behaviour change as Important.
- **Cheap spec reads.** Skills that read live specs for context start with `openspec list --specs` and `openspec show <id> --type spec --json --no-scenarios`, and read in full only the specs the change touches.
- **multi-pr records Suggestions by default.** Critical and Important findings are still fixed. The full-severity policy stays available as a Phase 1 choice.
- **Resume probe.** `probe_state.py` treats a change as apply-ready when every `applyRequires` artifact is done. Without this, a change with no design.md never reports `isComplete`.

Non-goals: a plan gate (spec-to-pr stays continuous), splitting the live `cla-plugin` spec, and a test-marker convention.

## Capabilities

### New Capabilities

### Modified Capabilities
- `cla-plugin`: adds requirements for conditional design.md, size findings, the scenario-to-test link, the review cuts, and cla-init's config seeding.

## Impact

Skills under `.claude/plugins/cla/skills/`: `multi-spec` (SKILL.md, `references/authoring-brief.md`, `phases.md`, `review-gate.md`), `review-change` (SKILL.md, `references/checklist.md`), `spec-to-pr` (SKILL.md, `references/workflow-diagram.md`, `scripts/probe_state.py`), `spec-to-pr-retro/SKILL.md`, `multi-pr` (SKILL.md, `references/change-loop.md`, `references/discover-and-gate.md`), `cla-init/SKILL.md`, and `_shared/references/` (`test-quality.md`, `run-log-schema.md`). Also `openspec/config.yaml`, `DEVELOPER-GUIDE.md`, `plugin-tests/tests/skills/spec-to-pr/test_probe_state.py` with its mutant batch, two new consistency tests with their mutant batches, and a refreshed measurement comment in `plugin-tests/tests/conformance/test_no_hardcoded_plugin_paths.py` with its batch's anchor. No new dependency.
