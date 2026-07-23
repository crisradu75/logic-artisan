# multi-pr — per-chain JSONL log schema

Phase 4 step 5 serializes the whole chain's in-context outcomes as a single JSON object and pipes it to `scripts/log_chain_run.py`, which appends it to `cla.io/retro/multi-pr-runs.jsonl`. This is the deliberate **chain-level** sibling of `/cla:spec-to-pr`'s per-CHANGE `references/run-log-schema.md` — it captures the facts a per-change ledger structurally can't see (whether the discovered order held, gate/escalation outcomes, post-merge follow-ups, inter-change breakage, per-change timing-by-complexity).

**Log-only — there is deliberately NO analyzer skill over this yet** (see SKILL.md "What this skill deliberately does not do"). The schema is written now so the data exists when the sample justifies building a `multi-pr-retro` (~8–10 chains). Every field is optional-additive, so a future aggregator counts each metric's denominator only over records that carry it.

## Invocation

```bash
python3 .claude/plugins/cla/skills/multi-pr/scripts/log_chain_run.py <<'JSON'
{"ts":"<ISO-8601>","mode":"auto-discover|explicit","changes":["<name-in-shipped-order>"],"sequence_source":"discover_sequence|explicit|user-corrected","sequence_held":true,"merge_policy":"merge-before-dependents|open-all","unresolved_policy":"full-severity|critical-important|spec-to-pr-default","gate":{"blocked":false,"autonomy_override":true,"infra_remediation_fired":false,"cycle_asked":false},"post_merge_followup_prs":0,"inter_change_breakage":false,"side_quests":["<short label>"],"per_change":[{"change":"<name>","complexity":"large-new-capability|large-extend|small","approx_total_min":0,"revise_findings":0,"output_chars":0}],"total_estimated_min":0,"total_actual_min":0,"total_output_chars":0,"final_master_commit":"<sha>"}
JSON
```

`log_chain_run.py` `json.loads`-validates, size-checks the 4-KiB atomic-append ceiling, and appends UTF-8 bytes directly — so a malformed line can't silently poison the ledger and there's no raw-shell quoting / `printf` / UTF-16-BOM footgun.

**Replace every placeholder with a real value before sending.** The script rejects invalid JSON with exit 1 (non-fatal — note and continue), but a record full of literal `<...>` / enum-alternation placeholders is *valid* JSON that logs garbage. Counts / flags + small arrays only, **no prose** (prose lives in the running-notes file and the PR bodies; an oversize record exits 1).

## Field intent

- `mode` — `auto-discover` (every open change in scope) or `explicit` (a named subset, in the given order).
- `changes` — the change names in **shipped order** (the order they actually merged, which may differ from the proposed order if `sequence_held` is false).
- `sequence_source` — how the order was decided: `discover_sequence` (the script's topo-sort), `explicit` (user-supplied), or `user-corrected` (the script proposed an order the user then overrode).
- `sequence_held` — did the shipped order match the planned one? `false` iff any change's Implement needed an unmerged predecessor, or the order had to be revised mid-run — a `false` flags a `discover_sequence.py` ordering miss worth investigating.
- `merge_policy` / `unresolved_policy` — the two load-bearing Phase-1b gate answers (echoed so a record is self-describing without cross-referencing the transcript).
- `gate` — the pre-flight gate outcomes: `blocked` (did the gate ever hard-stop the chain), `autonomy_override` (did the explicit-autonomy or bounded-window path apply the recommended defaults without asking), `infra_remediation_fired` (did the self-remediation bring a local stack up before asking/hard-blocking), `cycle_asked` (was the dependency-cycle sequence question surfaced).
- `post_merge_followup_prs` — the strict-policy failure mode: a finding that needed fixing AFTER its change already merged, via a retroactive fix-PR. Non-zero means the "fix everything before merging the next dependent change" discipline slipped somewhere.
- `inter_change_breakage` — did Phase 4 step 1's chain-level re-verify catch something that no single change's own Test phase did (a cross-change regression only visible on the fully-merged tree)?
- `side_quests` — unplanned work discovered mid-run (e.g. an orphaned-docs restoration PR, a stranded-upstream-commit fix). Short labels only.
- `per_change[]` — one row per change: `complexity` (`large-new-capability` / `large-extend` / `small`), `approx_total_min` (that change's real measured wall-clock — the delta between the real timestamps Phase 3 steps 2 and 6 capture via `date`, spanning the `/cla:spec-to-pr` run + any step-4 fix round + the step-5 merge; not a prose estimate), `revise_findings` (count of Critical+Important Revise-round findings), `output_chars` (optional — that change's own `/cla:spec-to-pr` run's total printed-report chars, the verbosity-by-complexity companion to the timing-by-complexity `approx_total_min`). This is the timing/verbosity-by-complexity data Phase 1c's upfront chain estimate reads back on the *next* chain — accuracy here directly improves the next run's estimate.
- `total_estimated_min` / `total_actual_min` — the chain-level counterparts: Phase 1c's upfront summed estimate, and the sum of `per_change[].approx_total_min` (plus any inter-change orchestrator overhead) actually measured by the time Phase 4 runs. The gap between the two is the single number a future `multi-pr-retro` would use to judge estimator quality over time.
- `total_output_chars` (optional) — the sum of `per_change[].output_chars` plus any chain-level orchestrator report text (e.g. Phase 4's cleanup summary), mirroring `total_actual_min`. A verbosity proxy for a future `multi-pr-retro`, NOT a full token-spend measure — it covers only printed report text.
- `final_master_commit` — the `master` HEAD sha after the last merge + the chain-log commit's parent (i.e. the tip the whole chain produced), for attributing a ledger line to a concrete tree state.

**Best-effort, non-fatal.** If `log_chain_run.py` exits non-zero (invalid JSON, oversize, or write failure — the stderr names which), note it and continue: a missing chain-log line never blocks the run, the same non-fatal posture as `/cla:spec-to-pr`'s own run-log step.
