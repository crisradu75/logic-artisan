# Spec map

How the plugin's capabilities, the workflows a user runs and the specs fit together. Links only: a
rule lives in its spec, and a value lives in its config. `check_spec_proof.py` fails when a live spec
is linked from no workflow step here, or a link points at a spec that does not exist.

## Capabilities

- **Take one change to a reviewed pull request.** Delivered by [Take a change to a pull request](#take-a-change-to-a-pull-request).
- **Run a batch of changes without a person in the loop.** Delivered by [Run a batch of changes](#run-a-batch-of-changes).
- **Keep a repo's facts, docs and specs true.** Delivered by [Set up a repo](#set-up-a-repo) and [Keep specs and docs true](#keep-specs-and-docs-true).
- **Stop unsafe agent actions.** Delivered by [Set up a repo](#set-up-a-repo).
- **Comment on a document.** Delivered by [Annotate a document](#annotate-a-document).
- **Ship the plugin to other repos.** Delivered by [Install and release the plugin](#install-and-release-the-plugin).
- **Learn from past runs.** Delivered by [Read the run records](#read-the-run-records).

## Workflows

### Set up a repo

1. Install a pinned release under the `cla` namespace: [plugin-distribution](specs/plugin-distribution/spec.md)
2. Load the guard hooks that block unsafe commands and direct pushes to the default branch: [guard-hooks](specs/guard-hooks/spec.md)
3. Run setup to create the repo's facts, overlays and economy rules: [repo-context](specs/repo-context/spec.md)

### Take a change to a pull request

1. Write the specs under the repo's authoring rules and review the plan before building: [change-workflow](specs/change-workflow/spec.md)
2. Prove each requirement with a test or a manual note: [spec-proof](specs/spec-proof/spec.md)
3. Keep the repo's docs current: [docs-currency](specs/docs-currency/spec.md)
4. Review the pull request with the plugin's own reviewers: [review-agents](specs/review-agents/spec.md)
5. Record the run: [run-ledgers](specs/run-ledgers/spec.md)

### Run a batch of changes

1. Propose, run in dependency order and stop on a failure: [change-chains](specs/change-chains/spec.md)
2. Run a batch of small changes without specs: [small-change-chains](specs/small-change-chains/spec.md)
3. Keep chain run notes local: [run-ledgers](specs/run-ledgers/spec.md)

### Keep specs and docs true

1. Declare the spec map and check that every spec is linked: [spec-proof](specs/spec-proof/spec.md)
2. Check requirements, proof and format limits: [spec-proof](specs/spec-proof/spec.md)
3. Check repo docs against a change: [docs-currency](specs/docs-currency/spec.md)

### Annotate a document

1. Open a document or a whole change on a local page, comment on it and read the comments back: [annotate](specs/annotate/spec.md)

### Install and release the plugin

1. Say what a release contains and publish it: [plugin-distribution](specs/plugin-distribution/spec.md)

### Read the run records

1. Summarise recent runs and suggest a retro: [run-ledgers](specs/run-ledgers/spec.md)
