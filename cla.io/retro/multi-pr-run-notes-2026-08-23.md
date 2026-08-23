# multi-pr run notes — 2026-08-23

First `/cla:multi-pr` chain to reach Phase 1c in this repo. `cla.io/overlays/multi-pr.md`
records that there were no prior run-notes files and therefore no measured per-change
timings; `cla.io/retro/spec-to-pr-runs.jsonl` holds one record with no timing fields.

## Chain configuration (Phase 1b gate, answered by the user)

| Decision | Answer |
|---|---|
| Prerequisite (proposals lived only on PR #128) | Merge #128 to `main` first, then merge-before-dependents |
| Merge policy | merge each PR before the next change that depends on it |
| No-unresolved-issues | **All severities** — Critical, Important AND Suggestion. Nothing deferred to `TODO.md`, no Deferred-Known-Issues |
| `/cla:spec-to-pr` caps | **`--review-rounds 0 --pr-rounds 2 --test-rounds 3`** |
| Infra-unavailability | N/A — this repo has no local-stack hard gate |

**`--review-rounds 0` was chosen against the recommendation, knowingly.** It drops the
pre-implementation Review phase for both changes. `extract-dev-tree-from-plugin` is the
exposure: it is the fold of two changes that the multi-spec batch gate only ever reviewed
separately, so it goes into Implement having never been reviewed in its merged form.
Revise (`--pr-rounds 2`) still reviews each implementation on its open PR.

## Phase 2 note

`TaskCreate`/`TaskUpdate` are not available in this session, so the chain's task board
could not be laid down. This file carries the per-change status instead.

## Chain-time estimate (Phase 1c)

**No historical basis.** Zero prior multi-pr chains in this repo, and the one
`spec-to-pr-runs.jsonl` record carries no duration. Both changes predict as `large-extend`
by `review-change/references/checklist.md`'s size gate — but `extract-dev-tree-from-plugin`
is a ~70-file move plus a doc reconciliation plus a new script, which is the heavier of the
two by a wide margin. Task counts: 51 and 105.

Stated as a guess with no measured basis rather than a number: this is a multi-hour run.
Actuals below become the first samples for the next chain.

## Per-change log

| Change | Complexity (predicted) | Start (UTC) | End (UTC) | Actual | PR | Merged |
|---|---|---|---|---|---|---|
| `decouple-skills-from-dev-assets` | large-extend | 2026-08-22T22:54:47Z | 2026-08-23T08:43:59Z | **589 min** | #129 | `1b48903` |
| `extract-dev-tree-from-plugin` | large-extend (heavier) | 2026-08-23T08:47Z | 2026-08-23T12:34:35Z | **227 min** | #131 | `0d3cd28` |

**First measured sample for this repo.** 589 min for a `large-extend` — but read it with the caveat
that it includes two orchestrator pauses at phase boundaries that should not have happened, and a
Revise phase that ran unusually deep because `--review-rounds 0` made it the only review. Treat it as
an upper bound, not a baseline.

## Chain events

- **2026-08-22T22:51:47Z** — PR #128 (`docs(openspec): 2 ship-only-consumer-usable-assets
  change proposals`) squash-merged to `main` as `573c6bd`, per the Phase 1b gate answer.
  Both change directories are now on `main`; branch `docs/propose-ship-only-consumer-usable-assets`
  deleted.
- **2026-08-22T22:54:47Z** — chain start; change 1 of 2 begins.
- **2026-08-23T08:46:07Z** — PR #129 squash-merged to `main` as `1b48903`, per the
  merge-before-dependents policy. Change 2 depends on it and its task 1.1 prerequisites were
  re-verified on `main` before starting: both promoted checkers present, both aggregators renamed,
  and no `${CLAUDE_PLUGIN_ROOT}/mutate.py` invocation left in any skill.
- **Change 1, findings worth carrying:** Revise round 1 found that the promotion had removed this
  repo's only automated conformance gate (five repo-level assertions deleted, nothing invoking the
  programs) — reproduced by planting a curated token and watching `run_tests.py` stay green. Round 2
  then found the *restored* gate was itself partly vacuous: it asserted only `returncode == 0`, and
  exit 0 also covers a trivial pass, so pointing the token list at a missing name disarmed two of the
  four checks and survived. Both fixed and both now pinned by mutants. 22 mutants, all killed.
- **Delegate contract fired once** (Implement fix-pass returned `done` with no evidence) — recorded
  in the run log's routing telemetry.
- **Orchestrator fault:** the run paused at a phase boundary after Revise round 1 instead of
  continuing, against the autonomy gate. Diagnosed as the status-report shape reading as a terminus;
  written to user memory. Candidate for `cla.io/overlays/spec-to-pr.md` "Incident / offense history"
  via `/cla:codify-learnings`.
- **2026-08-23T12:36:07Z** — PR #131 squash-merged to `main` as `0d3cd28`. **Chain complete.**

## Chain outcome

**The goal, measured on merged `main`:** `git ls-files .claude/plugins/cla | wc -l` → **101**, down
from 171 at chain start. Every remaining file matches one of the 14 shipped-asset patterns; the scan
reports 0 violations. 41% of the published payload was validation machinery a consumer could not run.

**Chain-level gate on merged `main`** (the point of running it again — a merge can interact in ways
no single change's own Test phase sees): `pytest plugin-tests` 1136 passed / 1 skipped;
`node --test` 70/70; `check_shipped_tree.py` exit 0.

**Timings — the first measured samples for this repo.** 589 min and 227 min. Read the first with the
caveat already recorded above; the second is the cleaner sample, and it covers a heavier change
(105 tasks, ~70 file moves) in 38% of the time. The difference is not change size — it is that
change 1 absorbed two orchestrator pauses and a Revise phase that ran unusually deep because
`--review-rounds 0` made it the only review.

**What `--review-rounds 0` cost.** The chain skipped pre-implementation review on both changes, so
every defect had to be caught after implementation. It largely was — but two of the most serious
findings were guards that had silently stopped checking, and both were found by Revise rather than
by Review, i.e. after the code was written rather than before. Worth weighing on the next chain.
