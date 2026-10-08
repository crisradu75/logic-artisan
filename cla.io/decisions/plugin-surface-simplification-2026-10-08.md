# Plugin surface simplification

Written 2026-10-08, the second half of the simplification program begun in
`retro-and-learning-loop-simplification-2026-10-08.md` (same day, same PR). That doc covers the
run ledgers, the retro skills and `codify-learnings`; this one covers the rest of the plugin
surface: spec-to-pr's size, annotate, overlays, low-use skills, the dev-tree guard layer,
always-on context, the two chain orchestrators, and the fleet list. Shaped with the owner
question by question the same day.

**Note on where this lives.** Deferred work belongs in GitHub issues. This is a plan for one
program of work, kept in `decisions/` like the other shaped-decision docs.

---

## Grounding

Seven read-only investigations over `logic-artisan` at `4b8f50c` and the consuming repos
`interoga-ro` (`98a9b909`), `claude-plugins` (`096800d`), `market-distiller-mcp` (`53d3b4d`)
and `agentic-air` (`0021692`, branch `master`). The commands behind each number are named
inline. Shares marked "estimate" come from sampling or hand classification, not a count.

### P1 — spec-to-pr size

- `python3 plugin-tests/scripts/measure_load.py --skill spec-to-pr`: SKILL.md 9,134 words;
  the typical-run profile 32,624 words over 11 files.
- The profile assumes no delegate. Ledgers: `implement_delegated` true in 107 of 131 records
  carrying it; Review `size_gate` large in 133 of 160. Adding the files those load
  (implement-delegate 907, subagent-brief 3,780, dispatch 2,467) gives a realistic run of
  about **39.8k words** (sum of `measure_load.py` figures).
- SKILL.md's phase stubs restate their mandatory references: Precheck 145 + Ship 678 +
  Revise 911 + Archive 128 + Handoff 746 = **2,608 words** (`sed -n A,Bp SKILL.md | wc -w`).
  The Measured-by rule appears three times (SKILL.md, ship.md §2b, revise.md).
- Rationale share (estimate, line-by-line tally plus a keyword lower bound): revise.md ~30%,
  ship/handoff ~18%, SKILL.md ~11%.
- Dead or stale pointers (grep): SKILL.md "Autonomy modes" section (the heading is
  "Autonomy gate"); `aggregate.py` named in run-log-schema.md, handoff.md and
  retro-skeleton.md (the file is `spec_to_pr_aggregate.py`); run-log-schema.md "SKILL.md
  Handoff step 5" (it is handoff.md §5); "Incident history" overlay section (the heading is
  "Incident / offense history"); SKILL.md hardcodes `npm run build`/`npm run lint` against its
  own rule that commands come from project-facts.md.
- Flags `--narrow`, `--dry-run`, `--gate-on-push`, `--interactive`, `--test-cmd`,
  `--skip-review`, `--no-tree-check`, `--check-permissions`: 0 ledger hits, but the schema
  records only 4 `args` keys, so absence proves nothing.
- Proven load-bearing from the ledgers: `--inherits` (15 runs, 9 caught unaddressed
  obligations); Revise round ≥ 2 (19 of 19 found Critical/Important; `sibling_instance` ≥ 1 in
  18 of 19).

### P2 — annotate

6,060 shipped lines, 24.7% of the shipped plugin (`git ls-files … | xargs cat | wc -l`);
346 of 1,882 tests and 22.1s of 71.6s summed test time (`pytest --durations=0`); the only
third-party test dependency (Playwright). Real use: one annotation file, logic-artisan
2026-09-07. Consumer use: 0 across full fetched history (`git log -G` on its paths and command).
No other skill depends on it.

### P3 — overlays

- Pure template stubs (identical modulo skill name, `diff` after `sed`): interoga-ro 7 of 10,
  claude-plugins 6 of 9, logic-artisan 4 of 10.
- Mechanical checks configured: 0 of 4 repos (`grep -c '"type"' */cla.io/overlays/project-review.md`).
- 25 skill lines say "read project-facts, fall back to the overlay" — the same fact has two
  homes by design.
- Of 77 filled sections (hand classification, estimate): 30 are facts that belong in
  project-facts.md, 28 genuinely skill-specific rules, 11 dated incidents, 8 duplicates.
- `review-change/references/dispatch.md` calls overlay injection "mandatory"; in interoga-ro
  the file is a stub, so the mandatory injection injects nothing.

### P4 — low-use skills

| skill | evidence | outcome |
|---|---|---|
| cla-init | onboarding, run once per repo (interoga #147); `sync-context` already creates `cla.io/` when missing | merge |
| project-review `mechanical-checks.mjs` | 0 active consumers configure a check; 616 lines + 961-line Node suite | delete script |
| diagnose | 4 weeks old; escalation target from spec-to-pr and lite-pr; nothing records its runs | keep, log |
| save-permissions, right-model, checkpoint | weak or no evidence of use | **kept** (owner's call) |
| report-upstream, new-worktree, feedback, sync-context | real use found | keep |

### P5 — the dev-tree guard layer

Per-module catch history from `git log --follow` and commit-body grep (absence of evidence,
not proof): real catches came from the four consumer-facing conformance guards
(`no_hardcoded_plugin_paths`, `no_project_tokens`, and the two shipped-script tests) and two
prose-agreement guards (`check_labels_agree`, `mutation_gate_sites_agree`). The meta tier
(`guards_have_mutant_batches`, `guards_are_not_vacuous`, `shipped_files_are_scanned`,
`check_script_drift`, `measurement_names_its_command`, the counts half of `doc_facts`) caught
only its own bookkeeping, costs about 1.7s of a 16.3s serial run, and accounts for at least 31
upkeep commits. Several of these pin the exact spec-to-pr and CLAUDE.md wording that P1 and
P6 rewrite.

### P6 — always-on context

- `CLAUDE.md` 4,653 words (`wc -w`), loaded every session here. Section split (awk on `^#`):
  roughly 75% is rationale, reference tables (the script table, layout trees) or copies of the
  plugin README and DEVELOPER-GUIDE (estimate). All the restated counts checked true today.
- Seven tests pin restated facts in CLAUDE.md (`test_doc_facts.py` L218, L274, L427, L460, L848;
  `test_docs_name_shipped_paths.py` L161, L176).
- Consumer CLAUDE.md: market-distiller-mcp has a 1,727-word CLA section, stale (lists the
  deleted `update-cla`, "v0.9.3 ships eight" hooks, the retired `conformance-checks/tests`);
  claude-plugins ~435 words of install/pre-push restatement; interoga-ro 114 words.

### P7 — multi-lite and multi-pr

- 23.9k words maintained between them (`wc -w`). Word 5-gram overlap: about 1,200 words per
  side (a script over both trees); a further ~1,000–1,500 words per side say the same thing in
  different words (estimate).
- 33 runs from run-notes across the fleet: multi-lite 0 quarantines; multi-pr 0 Tier-A halts,
  0 stacked, 0 open-all runs (`grep` over the run-notes). multi-lite's `merge-each-clean` was
  added on 2026-09-16, after the last multi-lite run.
- Only multi-lite checks `gh pr checks`, `head_sha` and `--match-head-commit` before merging;
  multi-pr merges without them.

### P8 — agentic-air

`git show origin/master:.claude/settings.json` enables no plugin; the tree vendors
`.claude/plugins/cla` at version 0.0.1 with the old launchers. Last CLA commit 2026-08-08, last
ledger row 2026-07-22. Its 64 spec-to-pr rows were about a third of the five-repo sample. None
of them carries `findings_by_round`, so the Revise evidence in the companion doc is unaffected.

## Decisions (all agreed with the owner, 2026-10-08)

- **P1 — Full spec-to-pr slim.**
  - SKILL.md to about 4,500 words: phase stubs become "read X first" plus only the
    invariants the remaining tests pin; delete the 2,608 duplicated words; rationale moves to
    `design-tradeoffs.md` (read only when revising the skill); fix the dead pointers.
  - revise.md to about 5,000 words; ship.md ~1,800; handoff.md ~1,400; review-sweeps.md ~900;
    archive-preflight.md merges into archive.md; run-log-schema.md splits into the producer
    field list (read at Handoff) and design notes (not read per run).
  - **Must not be cut:** the same-message turn-liveness rule, the `--inherits` hand-off and
    resume step 2b, the exit gate's two counts and the rejected-remedies merge gate, "no
    commands means `warn`, not `skip`", the sibling-instance question, the git_state contract,
    the archive staging scope.
  - Estimate, not measured: ~21.5k words per typical run (from 32.6k), ~27k with a delegate
    (from ~39.8k). Re-measure with `measure_load.py` when it lands.
- **P1a — Log flags, decide later.** Add a `flags` list to the spec-to-pr run record; revisit
  the zero-evidence flags after about 30 runs. Nothing removed now.
- **P2 — Keep annotate as is.** Owner's call, against the recommendation to delete. Its test
  share and Playwright exception stay.
- **P3 — project-facts.md plus optional overlays.**
  - `cla.io/project-facts.md` is the only home for commands, paths, ports, install and env;
    the 25 "fall back to the overlay" clauses go.
  - `cla.io/overlays/<skill>.md` is optional and holds only skill-specific rules; every
    reference reads it "if present". The "mandatory" injection wording and the named
    per-section contracts go.
  - No stub scaffolding. Dated incidents move to `cla.io/lessons-learned/`; generic ones go
    upstream via `/cla:report-upstream`.
  - The machine-parsed `*.local.md` files stay separate: `branch-prefix.local.md` (parsed by
    `_git_common.py`), `project-tokens.local.md` (the token guard's input), `fleet.local.md`
    (per machine).
- **P4 — Merge `cla-init` into `sync-context` and rename the result `cla-setup`.** One skill
  scaffolds `cla.io/` when missing and populates or refreshes the facts. `/cla:cla-init` and
  `/cla:sync-context` go away, which changes commands consumers type — the reason this
  program releases as 2.0.0.
- **P4a — Delete `project-review`'s `mechanical-checks.mjs` and its Node suite.** The pre-PR
  gate becomes pytest only; CLAUDE.md's "configured by 1 of 4" row and the `node --test` lines
  go.
- **P4b — Keep `diagnose`, and log escalations to it** as a count on the spec-to-pr run record
  (alongside P1a's `flags`). Re-measure in about a month.
- **P4c — Keep `save-permissions`, `right-model` and `checkpoint`.** Owner's call.
- **P5 — Delete the meta guard tier** (about 5,600 lines, estimate):
  `guards_have_mutant_batches` (mutation batches become optional), `guards_are_not_vacuous`,
  `shipped_files_are_scanned` (the scanners walk every shipped file instead of keeping
  exemption maps), `check_script_drift` (replaced by one small behavioural test that the
  ledger writer and reader resolve the same directory), `measurement_names_its_command`;
  shrink `doc_facts` to release-version agreement plus the invocation table. Keep the four
  consumer-facing conformance guards, `check_labels_agree`, `mutation_gate_sites_agree`, and
  the small local-safety checks.
  *Implemented differently:* the scanners were left as they are, because walking every shipped
  file would flag the plugin's own README (it names this repo and `.claude/plugins/cla` for the
  install commands); only the coverage-map guard was deleted. So nothing flags a new shipped file
  that no scanner opens (today `.claude-plugin/plugin.json`, `.gitattributes`, `README.md`,
  `hooks/git/pre-push` — the deleted guard's `EXEMPT` map, `git show
  c9db69f^:plugin-tests/tests/conformance/test_shipped_files_are_scanned.py`). `doc_facts` also
  kept its check that every named hook exists.
- **P6 — CLAUDE.md becomes rules-only** (about 1,100–1,300 words, estimate). The script table
  and layout trees move to DEVELOPER-GUIDE §11, rationale to §12, versioning history to
  "Release and distribution history"; copies of the plugin README are deleted. CLAUDE.md drops
  out of the count-pinning tests; the release line stays, because `/release` edits it.
- **P6a — Consumer CLAUDE.md CLA sections become a short pointer** (~50–100 words: plugin
  installed, run `cla-setup`, where `cla.io/` lives, repo-specific exceptions). One PR per
  consuming repo, after the release.
- **P7 — Extract the shared chain merge mechanics** into one `_shared/references/` file:
  pre-merge checks, `ALLOW_PR_MERGE`, confirming MERGED, host refusal, the pre-push fallback,
  bootstrap and autonomy override. multi-pr adopts multi-lite's `gh pr checks` / `head_sha` /
  `--match-head-commit` guards in the process. The two skills stay separate, and the
  turn-liveness copies stay where they are.
- **P7a — Delete multi-pr's stacked and open-all policies.** multi-pr keeps
  merge-before-dependents. multi-lite's `merge-each-clean` stays (too new to judge).
- **P8 — Remove agentic-air from `cla.io/fleet.local.md`** — done in this PR, with the reason
  recorded in that file. Re-add it only after re-onboarding.

## Delivery

- **Same PR as the two companion docs**, as a separate decision doc. The program's order across
  all three docs is stated here once.
- **Order.**
  1. **P5 first.** It removes the guards that pin the wording P1 and P6 rewrite, so those
     changes stop fighting the tests.
  2. **`spec-level-and-style-2026-10-08.md`:** its rule changes (S1–S6), then the S7 rewrite of
     this repo's live specs — so every later change is authored at the new level.
  3. **`retro-and-learning-loop-simplification-2026-10-08.md`'s chain** (validated run records,
     slim codify-learnings, slim spec-to-pr-retro, revise defaults, retire unread ledgers).
  4. **This doc's chain:** P1 (with P1a, P4b), P6, P3 + P4 (overlays and `cla-setup` touch the
     same files), P4a, P7 + P7a.
- **One release, 2.0.0**, at the end of all of it. This supersedes the retro doc's "one minor
  release": the `cla-setup` rename makes the combined program a major.
- **After the release:** one PR per consuming repo — `cla-setup` (spec rules, orphan ledgers),
  the retro doc's D3a record migration where old-shape rows exist, and the P6a CLAUDE.md
  trims.
