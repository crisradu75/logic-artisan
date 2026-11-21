# overlays — what a repo's overlay may change

A repo's `cla.io/overlays/<skill>.md` adds rules to a skill or narrows its rules. It does not relax a stop, a protected-area rule (as "What is protected" in `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/blocking-findings.md` defines it), or a report field another skill reads.

When an overlay line tries to, the skill follows its own rule and tells the user which overlay line it did not apply. The rest of a report's format (order, wording, extra sections) is the repo's to change.

## Report fields other skills read

Keep a field's spelling as written; the reader matches it.

- `lite-pr` ship report: the branch name and the PR number it opened (read by `multi-lite`, `references/candidate-loop.md`, "Capture the real identifiers").
- `lite-pr` review reports: each blocking finding's severity, file:line, the fix and any surviving mutant (read by `multi-lite`, same step, to count deferred findings).
- `spec-to-pr` Handoff Test row: the `full gate: green|red on <sha>` or `skipped (<reason>)` line (read by `multi-pr`, `references/change-loop.md`, "Record the head, then read the Handoff report").
- `spec-to-pr` Handoff sections "Deferred Known Issues" and "Rejected remedies, still open" (read by `multi-pr`, `references/change-loop.md`, "No-unresolved-issues enforcement").
- `spec-to-pr` Handoff `HONOURED / VIOLATED / NOT ADDRESSED` lines, one per inherited entry (read by `multi-pr`, `references/change-loop.md`, "Count the inherited-obligation verdict lines").
- The `Risk:` line `spec-to-pr` Ship writes in the PR body (read by its own Revise, `references/revise.md`, "Round 1").
