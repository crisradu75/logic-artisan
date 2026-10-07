## Why

Review and archive carry machinery that the `openspec` CLI already does, or that has never fired. It
costs about 4,600 words on every spec-to-pr run and half of the `change-review` spec.

## What Changes

- The hand-run MODIFIED-block comparison (six call sites, one 1,033-word reference) is replaced by
  `openspec validate <change> --strict`, which already fails a block that drops a live scenario.
  `cla-init` reports an OpenSpec older than 1.14.1.
- `archive-preflight.md` shrinks from 1,180 to 100 words; spec-to-pr's Archive stub stops repeating
  `archive.md`.
- The four claim shapes become one check: a sentence that depends on code, data, a cited
  implementation or the deployment is a claim to verify.
- The severity tie-break becomes "keep the higher", which the checklist and spec-to-pr already did.
- The `review.json` skip between multi-spec and spec-to-pr is removed; it never ran.
- Live-spec validation drops `--strict`: long-requirement warnings are style, and `--strict` turned
  them into failures that would halt every archive.
