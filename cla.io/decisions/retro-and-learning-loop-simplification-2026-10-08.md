# Run ledgers, retro skills and the learning loop — simplification

Written 2026-10-08, from an analysis of the run ledgers, the two retro skills and
`codify-learnings` across five repos. Shaped with the owner question by question the same day.
Follows `self-improvement-remaining-2026-09-05.md` and supersedes its open items (see "Against
the 2026-09-05 plan" below).

**Note on where this lives.** Deferred work belongs in GitHub issues. This is a plan for one
program of work, kept in `decisions/` like the other shaped-decision docs; anything that
becomes standalone deferred work gets filed as an issue.

---

## Grounding

Five repos, read from fresh clones: `logic-artisan` at `4b8f50c`, `interoga-ro` at `98a9b909`,
`claude-plugins` at `096800d`, `agentic-air` at `0021692`, `market-distiller-mcp` at
`53d3b4d`. **Not read:** `future-champs` and `verto-ai`, which `cla.io/fleet.local.md` lists
as having no ledger rows. Every number below is about those five trees only.

```
# record counts per ledger
wc -l <repo>/cla.io/retro/*.jsonl

# spec-to-pr, whole fleet window
python3 .claude/plugins/cla/skills/spec-to-pr-retro/scripts/spec_to_pr_aggregate.py --limit 0 \
  --log <5 repos>/cla.io/retro/spec-to-pr-runs.jsonl
  -> runs_analyzed 201 (11 / 62 / 55 / 64 / 9); window 2026-06-24 .. 2026-10-06
  -> shape_drift_records 40 (phases 40, asks 3, revise_findings_by_tier 9)
  -> cap_exhaustion.revise 25/154; review 0/154; test 1/149
  -> revise_findings (found / phantom / runs): silent-failure-hunter 293/0/77,
     code-reviewer 195/1/80, pr-test-analyzer 194/3/74, type-design-analyzer 80/0/38,
     comment-analyzer 40/9/69, plugin-dev:skill-reviewer 4/0/5

# codify, whole fleet window
python3 .claude/plugins/cla/skills/codify-retro/scripts/codify_aggregate.py --limit 0 \
  --log <5 repos>/cla.io/retro/codify-runs.jsonl
  -> runs_analyzed 60; suggestions 236/236 applied, 0 rejected; memory 152/152
  -> effectiveness.records 8: prevented 112, re_offended 15, not_exercised 162

# generic ledgers (logic-artisan, interoga-ro, claude-plugins)
python3 .claude/plugins/cla/lib/ledger_summary.py --log <paths>
  -> lite-pr 46 records, shape-decision 19 (took_recommendation 115 of 134 questions), feedback 1
  (market-distiller-mcp adds lite-pr 2, shape-decision 2; agentic-air has neither)
```

Other measurements, each by an inline script over the JSONL:

- **spec-to-pr record shape:** 40 of 201 records (20%) have `phases` as an object, and 34
  have no `ts`. By repo: interoga-ro 34, logic-artisan 4, claude-plugins 2. In interoga-ro
  they are mostly changes run inside `multi-pr` chains, which write `date` and a dict-shaped
  `phases`.
- **`findings_by_round`:** present on 26 records; 19 ran a Revise round ≥ 2, in three repos
  and six repo/date groups (interoga-ro 09-16, 09-19, 09-20, 10-03; claude-plugins 09-19;
  market-distiller-mcp 10-02). Round ≥ 2 found ≥ 1 Critical/Important on **19 of 19**.
- **Re-offense slugs:** 88 re-offenses across 60 codify runs carry **78 distinct slugs**;
  only 9 slugs ever recur. Repeat detection keyed on slug cannot work.
- **Memory share:** 152 of 388 applied codify items (39%) were memory writes, which land in
  `~/.claude/projects/<path>/memory/` — outside git (per `cla.io/overlays/codify-learnings.md`
  "Memory index glob").

From git history of the first three repos (`git fetch --depth=3000 origin main`, then
`git log --grep`):

- **Retro skill runs found:** `codify-retro` twice (claude-plugins #314 on 07-15, #354 on
  08-01); `spec-to-pr-retro` once (claude-plugins #288 on 07-03). None since early August.
  #314 added 3 lines to two SKILL.md files ("canonical re-offense slugs" — did not stick, see
  above); #354 changed 4 lines of `codify-retro/SKILL.md` itself.
- **Commits that only touch `cla.io/retro/`:** logic-artisan 49, interoga-ro 25,
  claude-plugins 16 — some are whole PRs ("chore(retro): record the … run").
- **Commits touching the retro machinery** (retro skills, aggregators, `log_run`,
  `ledger_summary`, schema, drift check): logic-artisan 38, claude-plugins 15, interoga-ro 6.

Sizes (`wc -w`, `wc -l`): retro skills 1,940 + 1,772 words; `retro-skeleton.md` 613;
`run-log-schema.md` 2,337; `codify-learnings` SKILL.md 3,025 + references 5,673
(`failure-modes.md` 2,703, 51 bullets); aggregators 916 + 741 lines, `ledger_summary.py` 320,
`log_run.py` 181; their tests about 2,400 lines.

## What the evidence says

1. **spec-to-pr's ledger carries real signal; its reader is mostly drift-handling.** Round-cap
   hits, per-agent yield and `findings_by_round` are worth keeping. Half the retro's
   heuristics exist to interpret records the model wrote in the wrong shape, and 20% of
   records are still dropped from the phase metrics.
2. **One spec-to-pr-retro heuristic cannot fire.** "`escalate_up_fired` ≥ 50%" reads a field
   `spec_to_pr_aggregate.py` never emits (`grep -c escalate` → 0). Emitted but unread:
   `report_chars`, `deferred_to_todo_total`, `round_counts`, `retired_agent_keys`.
3. **The `findings_by_round` reversal condition is met** (19 changes, three repos, 19 of 19).
   Caveat: round ≥ 2 ran only when the exit gate triggered it, so the sample is pre-selected.
4. **`comment-analyzer` is the weakest Revise agent**: 40 findings over 69 runs (0.58 per run,
   against 2.4–3.8 for the others dispatched on most runs) and 9 phantoms (23%).
5. **`codify-retro` has no remaining job.** Apply rate never moves; repeat offences can't be
   joined across runs; the prevention rate is self-graded and logged on 8 of 60 runs; the
   per-repo size metrics are suppressed in fleet mode. Its runs mostly retuned its own prose.
6. **`codify-learnings` works where it is small**: the ≤ 3-suggestion cap tied to a quoted
   session failure, prefer-fixes-over-docs, and plugin-writability routing to
   `report-upstream` (logic-artisan#290 came from it). The rest costs about 20k words of
   reading per run (SKILL + mandatory references + a ~12k-word live log) for a gate that never
   refuses (users answer "all"), a self-graded tally, and lessons that 39% of the time land
   outside git.
7. **The three generic ledgers have no decision behind them.** `shape-decision` answered its
   one question (86% of recommendations taken). `feedback` has 1 record. `lite-pr` is
   descriptive only.
8. **Orphan ledgers sit in consuming repos**: `commit-provenance` (427 rows across three
   repos) and the files left by deleted writers (`right-model`, `multi-pr`, `multi-spec`,
   `multi-lite`, `project-review`). Nothing removes them.

## Decisions (all agreed with the owner, 2026-10-08)

- **D1 — Delete `codify-retro`.** Its one useful job, noticing a lesson failing again, moves
  into `codify-learnings` (D4).
- **D2 — One decision doc** for the ledgers, the retros and `codify-learnings` (this file).
- **D3 — Validate run records at write time; reject and print.**
  `log_run.py` checks each ledger's required keys AND value shapes (e.g. `phases` is a list of
  objects, `ts` is ISO-8601), defined once in code, and refuses an off-shape record with the
  reason. The calling skill prints the reason and continues — a refused write is never fatal.
  Every producer recipe is updated in the same change. This revives the 2026-09-05
  proposal 1 on exactly the two conditions it was dropped for.
  - **D3a — Migrate the 40 off-shape spec-to-pr records once** (a one-off script per repo;
    the dict shape maps onto the list one). No reader-side compatibility path survives it.
- **D4 — Slim `codify-learnings` to about 1,000 words and one reference.**
  1. List the session's failures (corrections, reverts, denials, wasted turns).
  2. For each, search for an existing rule (CLAUDE.md, `cla.io/overlays/`, hooks, memory). A
     hit is a re-offense **keyed by that artifact's path or hook name**, escalated one rung.
  3. Propose ≤ 3 fixes, tool/script/hook first, routed by plugin writability.
  4. One prompt (`y` / `n` / indices), apply.
  5. Log a short entry (≤ 150 words: fixes and re-offenses) and one ledger line
     `{ts, applied: [{target, rung}], re_offenses: [{artifact, escalated_to}]}`.

  Removed: the gate's long rules and apply counts, the prevented / not-exercised tally,
  Step 3.5, the size-maintenance step, full-log reads (grep instead), the log-only summary
  sections.
- **D5 — Memory is for personal preferences only.** Repo lessons go to the repo's CLAUDE.md or
  `cla.io/overlays/`, so git, cloud sessions and reviewers see them.
- **D6 — Shrink `failure-modes.md` to about 15 bullets.** Keep the highest-yield prompts;
  retire bullets whose lessons already graduated to a hook or CLAUDE.md.
- **D7 — Keep `spec-to-pr-retro` as a slim skill** (about 300 words over a slim script). The
  script reads the fleet by default and emits only: warn reasons, cap exhaustion, per-agent
  found/phantom, ask distribution, and the `findings_by_round` reversal check computed outright.
  Drop the dead heuristic, the unread fields, and (after D3) the drift buckets.
  `retro-skeleton.md` folds in.
- **D8a — Revise round 2 runs automatically whenever round 1 committed fixes,** scoped to that
  fix diff. The cap stays 2. This answers the archived reversal condition; `revise.md`'s
  "not made unconditional" paragraph and the `run-ledgers` spec requirement are updated in the
  same change, with the evidence above.
- **D8b — Narrow `comment-analyzer`'s Revise trigger** to diffs that add or change substantial
  comments, docstrings or prose files; skip it on code-only diffs.
- **D9 — Stop logging `lite-pr`, `shape-decision` and `feedback`.** Delete
  `lib/ledger_summary.py` and its tests. With D1 and D7 the fleet resolver drops to one copy,
  and `check_script_drift.py`'s fleet group goes.
- **D10 — Ledger rows ride the work PR.** Every ledger line and run-notes update is committed on
  the feature branch of the PR it describes (`multi-lite` / `multi-pr`: the chain's last PR).
  No standalone "record the run" commits or PRs.
- **D11 — `cla-init` (merged into `cla-setup` by the companion doc's P4) reports orphan
  ledgers and offers to delete them.** It carries a list of
  retired ledger names; a re-run lists the ones present and deletes only on an explicit yes.
  Works in every consuming repo, including ones not read here.
- **D12 — spec-to-pr's Handoff prints a one-line retro nudge** when, over the last 5 ledger
  lines, Revise or Test hit its round cap in ≥ 3, or the same warn reason appears in ≥ 2.
  Printed only, never blocks.
- **D13 — Delivery: `multi-spec` → `multi-pr`.** Author the five changes below from this doc,
  review them, then run them as one dependency-ordered chain. Released together with the
  companion doc `plugin-surface-simplification-2026-10-08.md` as 2.0.0 (see its "Delivery").

**Kept as is:** the `multi-lite` / `multi-pr` run-notes (resume keys, head SHAs, timing
estimates — working state, not retro data).

## Against the 2026-09-05 plan

| # | 2026-09-05 proposal | what happened | here |
|---|---|---|---|
| 1 | Validate at write time | dropped at review | revived with its two conditions — D3 |
| 3 | Close on outcome | shipped (`effectiveness`) | self-graded, 8 of 60 runs log it — replaced by D4 step 2 |
| 4 | Shrink the gate | shipped (cap, no default) | cap works; the no-default prompt is answered "all" — D4 |
| 5 | Delete dead heuristics | partly | D7 |
| 6 | `commit-provenance` | hook deleted 09-23 | orphan files remain — D11 |
| 7 | Cover lite-pr / shape-decision / feedback | ledgers added (#224) | no decision reads them — D9 |

## Changes, in order

1. **validated-run-records** — D3, D3a (validator, producer recipes, one-off migration).
2. **slim-codify-learnings** — D1, D4, D5, D6. Depends on 1 for the new codify record shape.
3. **slim-spec-to-pr-retro** — D7, D12. Depends on 1 (drops the drift buckets).
4. **revise-defaults-from-ledger** — D8a, D8b. Independent of 1–3.
5. **retire-unread-ledgers** — D9, D10, D11. After 2 and 3, which remove two of the resolver
   copies.

Released with the companion doc as 2.0.0, after its P5 guard change lands first. Estimate, not measured: retro and
learning prose from about 15k words to about 3k; ledger code from about 2,160 lines to roughly
600–700. Re-measure with `wc` and `plugin-tests/scripts/measure_load.py` when the changes land.

## Stale text to fix along the way

- Both retro SKILL.md files: "this repo's 8 spec-to-pr records … the fleet's 156" — the five
  repos read here hold 201 spec-to-pr records (11 in this repo).
- `codify-learnings` Step 4: "219 suggestions proposed, 219 applied" — the five repos read
  here hold 236 of 236.
