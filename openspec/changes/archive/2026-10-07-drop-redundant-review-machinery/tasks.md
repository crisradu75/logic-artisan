## 1. Skills

- [x] 1.1 Replace the MODIFIED-block comparison with `openspec validate <change> --strict` in the checklist, dispatch, authoring brief and multi-pr; delete `_shared/references/modified-block-retention.md`.
- [x] 1.2 Shrink `archive-preflight.md`, trim spec-to-pr's Archive stub and `archive.md`, and validate live specs without `--strict` in archive, lite-pr and multi-pr.
- [x] 1.3 Replace the claim shapes with the hidden-claims check; keep the higher severity.
- [x] 1.4 Remove the `review.json` record and skip, and their test.
- [x] 1.5 `cla-init` reports an OpenSpec older than 1.14.1.

## 2. Proof

- manual: A comparison to shipped code is checked: `review-change/references/checklist.md` check 0l and dispatch check 6.
- manual: A MODIFIED block drops a live scenario: the checklist's "Spec validity" check; the CLI behaviour was confirmed on a throwaway copy with openspec 1.14.1.
- manual: Two reviewers disagree on severity: `review-change/references/checklist.md` Step 5.
- manual: A stale delta baseline is checked whether or not a sibling overlaps: `multi-pr/references/discover-and-gate.md` §1a.
- [x] 2.1 `pytest plugin-tests -q -n auto --dist loadfile` and `node --test plugin-tests/node/mechanical-checks.test.mjs` pass.
