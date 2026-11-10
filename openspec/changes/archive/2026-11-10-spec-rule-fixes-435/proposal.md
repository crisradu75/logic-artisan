# Proposal

## Why

Two requirements bend the spec-writing rules (issue 435, owner decisions of 2026-11-10).

- `plugin-distribution`: a test asserts that the Copilot manifest in a release tag carries no "untested" claim, but no requirement states that outcome. The test cites "Listing for GitHub Copilot CLI", which does not say it.
- `review-agents`: "A reviewer is dispatched with a diff file, a ban on state changes and a named model" carries three outcomes in one requirement, against "one outcome per requirement".

## What Changes

- State in `plugin-distribution` that a released plugin does not claim its own install is untested. It names the outcome, not the manifest.
- Replace the combined `review-agents` requirement with three: a reviewer gets a diff file named in its brief; a reviewer makes no git or file changes; a reviewer runs on a named model.
- Point the tests at the new requirement names.

## Capabilities

### Modified Capabilities

- `plugin-distribution`: "Listing for GitHub Copilot CLI" gains a scenario stating the outcome (the spec holds 8 requirements, and a second outcome becomes a scenario). The requirement text is unchanged.
- `review-agents`: one requirement removed, three added. Nothing is dropped; each existing scenario moves under the requirement whose outcome it checks.

## Impact

`openspec/specs/plugin-distribution/spec.md`, `openspec/specs/review-agents/spec.md`, `plugin-tests/tests/consistency/test_reviewer_dispatch.py`. The manifest test already cites "Listing for GitHub Copilot CLI" and is unchanged. No shipped plugin file changes.
