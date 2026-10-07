## Why

The live specs were hard to read: long requirements full of history, measurements, coined terms and
restated skill procedure. Readers and every skill that loads a spec paid for it.

## What Changes

- Rewrite all six live specs in plain words: each requirement states its behaviour in a few
  sentences, and the scenarios carry the cases. Removed: history, incident narratives, measurement
  transcripts, issue numbers, "this is distinct from X" paragraphs, and how-to that the skill files
  already hold.
- Merge requirements that were split only to fit a length limit; merge duplicate scenarios.
- Fix text that no longer matched the tree: overlay location, the deleted sync engine, test-gate
  wording, the source-repo-only marker, and how a dispatched agent's return is classified (the
  skill checks the status token; the spec now says so).
- Delete the `rationale.md` files beside `annotate` and `run-ledgers`.

The skills' behaviour does not change; the specs now describe it more plainly, so this change
carries no spec delta (`skip_specs`).
