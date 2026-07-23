# TODO

Deferred ideas and follow-ups, organized by plugin.

## cla

- **Build `multi-lite-retro` / `multi-pr-retro` / `multi-spec-retro` / `project-review-retro`
  once the sample justifies it.** These four skills already log every run to
  `cla.io/retro/*-runs.jsonl` (schema-documented, optional-additive fields incl. the new
  `output_chars`/`report_chars` verbosity proxy), but have no analyzer skill yet — each schema doc
  states the same "log now, build the retro at ~8-10 runs" threshold `spec-to-pr-retro` and
  `codify-retro` used before they existed.
  - **This repo (`logic-artisan`) holds no product code, so it will never itself accumulate these
    runs — that's expected, not a blocker.** `spec-to-pr-retro`/`codify-retro` already exist here
    despite this repo's own `spec-to-pr-runs.jsonl`/`codify-runs.jsonl` being empty; they were
    authored as portable procedure and validated against a *consuming* repo's real log
    (`cla.io/retro/` is deliberately per-repo state, never synced).
  - As of 2026-07-23, real usage in `agentic-air` (the one consuming repo checked) is well under
    the ~8-10 threshold: `multi-pr` 3 runs, `multi-lite` 1, `multi-spec` 1, `project-review` 1.
    `multi-pr` is currently closest. Check other consuming repos too before concluding none has
    crossed it.
  - **`update-cla` only flows source → consumer** (pull-based, run from the repo that wants
    updates) — there's no reverse sync. If a retro skill gets built while working in a consuming
    repo once its count justifies it, it has to be manually contributed back here (copy the skill
    files, open a PR against `logic-artisan`) to become part of the canonical/synced core.
