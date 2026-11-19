# Proposal

## Why

`/cla:diagnose` and `/cla:codify-learnings` have no requirement of their own: they appear only as names inside `run-ledgers` and `cla-setup`. Both change how an agent works in a user's repo (one edits code to fix a failure, the other writes lessons and fixes into the repo's own files), so their outcomes need a spec and tests that hold the skill text to it.

## What Changes

- New `failure-diagnosis`: a reproduce loop before any fix, ranked falsifiable hypotheses written before any edit (pruned by the user only when one is present), the regression test before the fix or a recorded finding when no test can reach the cause, no debug tag left behind, and a commit that names the cause.
- New `session-learnings`: failures from the whole session, at most three fixes each quoting its failure, a tool before a doc, a repeated failure escalated above the rule that missed it, one prompt before any write, a read-only plugin's fix sent upstream, and a dated log entry with the old entries archived.
- Fix found while writing the spec: `/cla:diagnose` Phase 6 and the shared ship reference say the debug-tag pattern lives in two files; the staged-debug-tag guard hook holds it too. Both now name all three.
- `openspec/spec-map.md` links both specs.

## Capabilities

### New Capabilities

- `failure-diagnosis`, `session-learnings`.

### Modified Capabilities

None.

## Impact

Two new specs, tests for each requirement, one prose fix in two shipped files, the rule ledger and the spec map.
