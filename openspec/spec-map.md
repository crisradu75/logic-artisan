# Spec map

How the plugin's capabilities, the workflows a user runs, the shipped skills and the specs fit together. Links only: a
rule lives in its spec, and a value lives in its config. `check_spec_proof.py` fails when a spec
is linked from no workflow step here, or a link points at a spec that does not exist.

## Capabilities

- **Take one change to a reviewed pull request.** Delivered by [Take a change to a pull request](#take-a-change-to-a-pull-request).
- **Run a batch of changes without a person in the loop.** Delivered by [Run a batch of changes](#run-a-batch-of-changes).
- **Keep a repo's facts, docs and specs true.** Delivered by [Set up a repo](#set-up-a-repo) and [Keep specs and docs true](#keep-specs-and-docs-true).
- **Stop unsafe agent actions.** Delivered by [Set up a repo](#set-up-a-repo).
- **Comment on a document.** Delivered by [Annotate a document](#annotate-a-document).
- **Ship the plugin to other repos.** Delivered by [Install and release the plugin](#install-and-release-the-plugin).
- **Learn from past runs.** Delivered by [Read the run records](#read-the-run-records).
- **Work in an isolated copy and keep a session's records.** Delivered by [Take a change to a pull request](#take-a-change-to-a-pull-request).
- **Assess a project and choose the model for a task.** Delivered by [Assess a project and choose a model](#assess-a-project-and-choose-a-model).

## Workflows

### Set up a repo

1. Install a pinned release under the `cla` namespace: [plugin-distribution](specs/plugin-distribution/spec.md)
2. Load the guard hooks that block unsafe commands: [guard-hooks](specs/guard-hooks/spec.md)
   - Ask before destructive git commands and refuse direct pushes to the default branch: [git-guards](specs/git-guards/spec.md)
   - Warn about risky actions: [guard-warnings](specs/guard-warnings/spec.md)
3. Run setup to create the repo's facts, overlays and economy rules, and ask the test-proof question: [cla-setup](specs/cla-setup/spec.md)
4. Keep the repo's facts, overlays and recorded paths true: [repo-context](specs/repo-context/spec.md)
5. Read and write the repo's instruction files: [instruction-files](specs/instruction-files/spec.md)
6. Take the offer of a spec map scaffold: [spec-map](specs/spec-map/spec.md)
7. Save a session's tool permissions to the project's local settings: [permission-saving](specs/permission-saving/spec.md)

### Take a change to a pull request

1. Capture feedback, shape a decision and checkpoint a session: [session-records](specs/session-records/spec.md)
2. Start in an isolated worktree that is set up and kept inside: [worktree-setup](specs/worktree-setup/spec.md)
3. Write the specs under the repo's authoring rules and review the plan before building: [change-workflow](specs/change-workflow/spec.md)
4. Prove each requirement with a test or a manual note: [spec-proof](specs/spec-proof/spec.md)
5. Find a failure's root cause from a reproduce loop, with the regression test before the fix: [failure-diagnosis](specs/failure-diagnosis/spec.md)
6. Keep the repo's docs current: [docs-currency](specs/docs-currency/spec.md)
7. Review the pull request with reviewers dispatched under a diff file and a no-git-commands brief: [review-agents](specs/review-agents/spec.md)
8. Record the run: [run-ledgers](specs/run-ledgers/spec.md)

### Run a batch of changes

1. Propose, run in dependency order and stop on a failure: [change-chains](specs/change-chains/spec.md)
2. Run a batch of small changes without specs: [small-change-chains](specs/small-change-chains/spec.md)
3. Keep chain run notes local: [run-ledgers](specs/run-ledgers/spec.md)

### Keep specs and docs true

1. Declare a spec map in the repo's facts: [spec-map](specs/spec-map/spec.md)
2. Check the map, requirements, proof and format limits: [spec-proof](specs/spec-proof/spec.md)
3. Check repo docs against a change: [docs-currency](specs/docs-currency/spec.md)

### Annotate a document

1. Open a document or a whole change on a local page, comment on it and read the comments back: [annotate](specs/annotate/spec.md)

### Install and release the plugin

1. Say what a release contains and publish it: [plugin-distribution](specs/plugin-distribution/spec.md)
2. Offer the plugin, its helper agents and its guards to GitHub Copilot CLI: [copilot-cli](specs/copilot-cli/spec.md)
3. Send a defect in the plugin's shared core back to its source: [upstream-reports](specs/upstream-reports/spec.md)

### Read the run records

1. Summarise recent runs and suggest a retro: [run-ledgers](specs/run-ledgers/spec.md)
2. Turn a session's failures into at most three fixes and log them: [session-learnings](specs/session-learnings/spec.md)

### Assess a project and choose a model

1. Check, review and grade the whole repo without changing it: [project-review](specs/project-review/spec.md)
2. Pick the cheapest model and effort that do a task well: [model-advice](specs/model-advice/spec.md)

## Skills

Each shipped skill and the specs that cover it.

| Skill | Specs |
|---|---|
| `/cla:annotate` | [annotate](specs/annotate/spec.md) |
| `/cla:checkpoint` | [session-records](specs/session-records/spec.md) |
| `/cla:cla-setup` | [cla-setup](specs/cla-setup/spec.md), [repo-context](specs/repo-context/spec.md), [spec-map](specs/spec-map/spec.md) |
| `/cla:codify-learnings` | [session-learnings](specs/session-learnings/spec.md), [instruction-files](specs/instruction-files/spec.md), [run-ledgers](specs/run-ledgers/spec.md) |
| `/cla:diagnose` | [failure-diagnosis](specs/failure-diagnosis/spec.md), [run-ledgers](specs/run-ledgers/spec.md) |
| `/cla:feedback` | [session-records](specs/session-records/spec.md) |
| `/cla:lite-pr` | [change-workflow](specs/change-workflow/spec.md), [review-agents](specs/review-agents/spec.md), [docs-currency](specs/docs-currency/spec.md) |
| `/cla:multi-lite` | [small-change-chains](specs/small-change-chains/spec.md), [run-ledgers](specs/run-ledgers/spec.md) |
| `/cla:multi-pr` | [change-chains](specs/change-chains/spec.md), [run-ledgers](specs/run-ledgers/spec.md) |
| `/cla:multi-spec` | [change-chains](specs/change-chains/spec.md) |
| `/cla:new-worktree` | [worktree-setup](specs/worktree-setup/spec.md) |
| `/cla:project-review` | [project-review](specs/project-review/spec.md) |
| `/cla:report-upstream` | [upstream-reports](specs/upstream-reports/spec.md) |
| `/cla:review-change` | [change-workflow](specs/change-workflow/spec.md) |
| `/cla:right-model` | [model-advice](specs/model-advice/spec.md) |
| `/cla:save-permissions` | [permission-saving](specs/permission-saving/spec.md) |
| `/cla:shape-decision` | [session-records](specs/session-records/spec.md) |
| `/cla:spec-to-pr` | [change-workflow](specs/change-workflow/spec.md), [spec-proof](specs/spec-proof/spec.md), [docs-currency](specs/docs-currency/spec.md), [review-agents](specs/review-agents/spec.md), [run-ledgers](specs/run-ledgers/spec.md) |
| `/cla:spec-to-pr-retro` | [run-ledgers](specs/run-ledgers/spec.md) |
