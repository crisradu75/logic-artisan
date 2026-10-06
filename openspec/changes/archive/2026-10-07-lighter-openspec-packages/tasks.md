Order: group 1 first. Every later `checklist.md` edit lands after 1.2, and the probe (group 5) lands before the SKILL.md text that describes it (6.3).

## 1. The rules block and conditional design.md (plan A)

- [x] 1.1 This repo's `openspec/config.yaml`: add the canonical `rules:` block (proposal one page; design only on a named stock trigger, never restating proposal or specs; one behaviour per ADDED requirement in ≤500 characters, detail in scenarios; each ADDED or MODIFIED scenario has a test task or a `manual: <heading>: <reason>` line). Confirm `openspec instructions proposal --change lighter-openspec-packages --json` returns it.
- [x] 1.2 `review-change/references/checklist.md`: stop only when proposal.md is missing (`:25`); an absent design.md reads as "(absent)" (`:23,34`); agent prompts paste "(no design.md)" (`:227,263`).
- [x] 1.3 `multi-spec/references/authoring-brief.md` `done` (`:53`) and post-check (`:65`): proposal, tasks and a spec delta or `skip_specs`; design.md only on a named stock trigger. Step 3 (`:26`) writes design.md only when a trigger applies.
- [x] 1.4 `multi-spec/SKILL.md` (description `:3`, Phase 4 `:71`), `multi-spec/references/phases.md:47`, `DEVELOPER-GUIDE.md:132`: describe the artifacts actually present and the size-gated review.
- [x] 1.5 `multi-spec/references/review-gate.md:18`: an absent design.md reads as "(absent)".
- [x] 1.6 `cla-init/SKILL.md`: the `openspec/config.yaml` manifest item, copying 1.1's block (seed when `openspec/` exists and holds neither `config.yaml` nor `config.yml`; otherwise print). Update the description, the Report section and the Non-goals line that says it only writes under `cla.io/overlays/`.

## 2. authoring-brief.md additions (plans A, B, C, D)

- [x] 2.1 Remove the stale `openspec-propose` attribution (`:27`); pinned-parameters block only when design.md and a load-bearing number exist (`:28`); drop the doc-sync task (`:29`); one line restating the stock limits with a pointer to the config rules; each ADDED or MODIFIED scenario gets a test task or a `manual: <heading>: <reason>` line. Leave the MODIFIED carry-forward procedure and "before starting the next change" unchanged.

## 3. Review checklist (plans B, C, D)

- [x] 3.1 Step 3 size gate: drop `d` from the inputs, the announce lines and the report mode lines; the complexity-concentration override keeps its concentration condition (one or two files) and fires on `b ≥ 15` only, losing its `d ≥ 4` leg. Keep the heading `## Step 3: Size gate`.
- [x] 3.2 Beside the testability check: the size finding (MODIFIED exempt from length) and the scenario-without-proof finding, both Important. Add cutting to the FIX FIRST remedies and prefer it. Keep `- **READY** — 0 Critical` and `- **FIX FIRST**`.
- [x] 3.3 Drop Step 5 (the parallelism plan) and its report section, and the three-verified-claims minimum; the old Step 6 becomes Step 5, which is intended. Keep the `0l` sweep row and `### Verified claims`. Update the restatements in `review-change/SKILL.md`, `spec-to-pr/SKILL.md` (Review) and `spec-to-pr-retro/SKILL.md`.

## 4. multi-spec batch review (plan D)

- [x] 4.1 `review-gate.md:26-28`: apply checklist Step 3 per change; dispatch the three agents over the batch only when a change grades large, otherwise review inline.

## 5. Resume probe

- [x] 5.1 `spec-to-pr/scripts/probe_state.py` `_implement_done`: true on `isComplete`, or when `applyRequires` is a non-empty list and each id has `status == "done"` in `artifacts[]` (keys `id`, `status`); missing or empty `applyRequires` is false. Grep for other callers first.

## 6. spec-to-pr and multi-pr (plans C, D)

- [x] 6.1 `spec-to-pr/SKILL.md` Review: the already-reviewed skip per design.md decision 1, gated on multi-spec's `review.json`, keeping Step 2b, the retention comparison and the doc-sweep.
- [x] 6.2 `_shared/references/run-log-schema.md`: a skipped Review logs `status: skip` with a `reason` and omits `size_gate`, `verdict` and `verified_claims_count`; rewrite `:122` and `:125`. Grep `lib/log_run.py` and `spec-to-pr-retro/scripts/spec_to_pr_aggregate.py` to confirm neither rejects a Review record without them.
- [x] 6.3 `spec-to-pr/SKILL.md` Implement: step 2 (`:237`) and the post-check (`:267`) use the probe's `applyRequires` rule; the post-check greps for each test a ticked task names and sends a miss down the done-without-evidence path; the sample is drawn from measurement- or test-bearing tasks (`:272`). Note the no-design.md case at `:249`. Update `references/workflow-diagram.md:39`.
- [x] 6.4 `multi-pr/references/change-loop.md:11`: Review may run reduced for a multi-spec-reviewed change.
- [x] 6.5 `_shared/references/test-quality.md`: a one-line pointer to the scenario-proof rule.
- [x] 6.6 `multi-spec/references/review-gate.md` Step 7 (and `multi-spec/SKILL.md` Phase 4): write `review.json` into every reviewed change, whatever the verdict, with a digest of its staged artifacts, in the gate's commit; a batch of one reaches Step 7 too.

## 7. Scope addition E (approved 2026-10-06)

- [x] 7.1 skip_specs: `authoring-brief.md` states the rule and its `done`/post-check accept `skip_specs`; the config `rules:` block (1.1, 1.6) carries it; `checklist.md` reports a requirement with no observable behaviour change as Important, remedy drop it and set `skip_specs`.
- [x] 7.2 Cheap spec reads: `authoring-brief.md`, `checklist.md` (Step 2 and the Agent 3 prompt) and `spec-to-pr/SKILL.md` (Propose, Review) read live specs overview-first with `openspec list --specs` and `openspec show <id> --type spec --json --no-scenarios`. The MODIFIED carry-forward (`authoring-brief.md:30-49`) is unchanged.
- [x] 7.3 multi-pr: `discover-and-gate.md:180` makes Critical/Important-fixed, Suggestions-recorded the recommended default, with full-severity as a named alternative; update `change-loop.md:38-44`, `multi-pr/SKILL.md:26,69,81`, the explicit-autonomy override (`discover-and-gate.md:190`) and `change-loop.md:34`. Check the "full-severity" wording in `spec-to-pr/references/revise.md:149`, `handoff.md:23` and `spec-to-pr/SKILL.md`: it describes spec-to-pr's own Critical/Important fix lists, so it stays.

## 8. Proofs

- [x] 8.1 Test, `test_probe_state.py`: a no-design status (`isComplete: false`, `applyRequires: ["tasks"]`, tasks `done`) gives `implement: true`; an `applyRequires` artifact `ready` gives false; missing and empty `applyRequires` give false. Markers: `# scenario: cla-plugin / Resume on a change with no design.md`, `/ Required artifact not done`, `/ No applyRequires`. Add a mutant per new branch to `plugin-tests/mutants/spec-to-pr/test_probe_state.py` and run the batch. measured: `pytest plugin-tests/tests/skills/spec-to-pr/test_probe_state.py -q` 42 passed; `python3 plugin-tests/mutate.py plugin-tests/mutants/spec-to-pr/test_probe_state.py` 12 of 12 killed.
- [x] 8.2 Test, `plugin-tests/tests/consistency/test_reviewed_change_trigger.py`: the record path and fields spec-to-pr's Review reads match what multi-spec's `review-gate.md` writes; the gate writes a record whatever the verdict, a batch of one included; both sides compute the same `artifacts` digest, and the writer takes it from the staged fixes; the skip condition is READY, or FIX FIRST with `all_applied` and no deferral; a missing or unreadable record means a full review; deferred findings reach a full review; the verdicts match the checklist's rubric; the skip logs its verdict. Scope: writer/reader agreement only, not the skip's runtime. Markers: `# scenario: cla-plugin / A change multi-spec passed`, `/ A change multi-spec did not pass`, `/ A change with no usable review record`, `/ A change edited after multi-spec's review`, `/ An edit squashed in after multi-spec's review`, `/ A READY change gets a review record`, `/ A finding deferred out of scope`; 8.4 covers their runtime half. measured: `pytest plugin-tests/tests/consistency/test_reviewed_change_trigger.py -q` 11 passed; `python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_reviewed_change_trigger.py` 16 of 16 killed.
- [x] 8.3 cla-init is a prose skill with no script. Run its seed item's bash block in temp git repos. measured with a scratch script that extracts the block from `cla-init/SKILL.md` and runs it via Git Bash in four temp git repos: no config → `created`, and `openspec instructions <artifact> --change probe-x --json` carried the seeded rule for proposal, design, specs and tasks; `config.yaml` present → sha256 unchanged, block printed; `config.yml` present → no `config.yaml` created, sha256 unchanged, block printed; no `openspec/` → nothing created, block printed with the `openspec init` reason; `ROOT` unset → exit 127 with the `ROOT unset` message, nothing printed or written.
  - manual: No config.yaml: the seed is a prose bash block; run in a temp repo by 8.3, block pinned by 8.10
  - manual: An existing config.yaml: run in a temp repo by 8.3
  - manual: An existing config.yml: run in a temp repo by 8.3, condition pinned by 8.10
  - manual: Re-run is idempotent and never clobbers existing project data: run in a temp repo by 8.3
- [x] 8.4 The skip's runtime branches are prose run by the model, with no executable surface. Re-read the 6.1 text against the runtime half of each scenario 8.2 names, and against "A passed batch merged with a merge commit". measured with a scratch Python script driving `git` in a temp repo, the writer's digest taken after staging the fixes and the reader's after merging: equal on the branch, after a clean squash merge, and after a `--no-ff` merge over an unrelated commit on main; different after a squash merge that carried a post-review edit to `design.md`.
  - manual: A passed batch merged with a merge commit: the digest is content-only; measured by 8.4's merge-commit run
  - manual: A change multi-spec passed: runtime half is orchestrator prose; re-read by 8.4
  - manual: A change multi-spec did not pass: runtime half is orchestrator prose; re-read by 8.4
  - manual: A change with no usable review record: runtime half is orchestrator prose; re-read by 8.4
  - manual: A change edited after multi-spec's review: runtime half measured by 8.4's later-edit run
  - manual: An edit squashed in after multi-spec's review: runtime half measured by 8.4's squash-with-edit run
- [x] 8.5 design.md is optional, so it is a prose rule with no executable surface. measured: `grep -rnE "all four artifacts|design\.md is missing" .claude/plugins/cla plugin-tests DEVELOPER-GUIDE.md CLAUDE.md` returned 0 hits; the `done` list in `authoring-brief.md` names proposal, tasks and a spec delta or `skip_specs`.
  - manual: A change without design.md passes the authoring post-check: prose rule, grepped by 8.5
  - manual: A design.md names its trigger: prose rule, grepped by 8.5
  - manual: A change without design.md is reviewed: prose rule, grepped by 8.5
- [x] 8.6 The authoring brief's optional blocks are prose. measured: `grep -rnE "Pinned implementation parameters|doc-sync task" .claude/plugins/cla` returned 0 hits; `grep -n "when design.md exists" .claude/plugins/cla/skills/multi-spec/references/authoring-brief.md` returns the conditional pin rule; `grep -n "Stock limits" .claude/plugins/cla/skills/multi-spec/references/authoring-brief.md` returns the one line pointing to `openspec/config.yaml`.
  - manual: A change with no load-bearing number: prose rule, grepped by 8.6
  - manual: Tasks without a doc-sync task: prose rule, grepped by 8.6
  - manual: The brief states the limits: prose rule, grepped by 8.6
- [x] 8.7 The size gate and report shape are checklist prose. measured: `grep -nE "d ≥ 4|### D|Implementation Parallelism|at least 3 positive" .claude/plugins/cla/skills/review-change/references/checklist.md` returned 0 hits; the open questions keep the `0l` row.
  - manual: Many decision headings in a narrow change: checklist prose, grepped by 8.7
  - manual: A small change is reviewed: checklist prose, grepped by 8.7
- [x] 8.8 The review findings are checklist prose. measured: `grep -nE "500 characters|MODIFIED.*exempt|cutting|skip_specs" .claude/plugins/cla/skills/review-change/references/checklist.md` returns each rule at its site.
  - manual: An ADDED requirement is too long: checklist prose, grepped by 8.8
  - manual: A long MODIFIED requirement: checklist prose, grepped by 8.8
  - manual: A finding that a cut resolves: checklist prose, grepped by 8.8
  - manual: An invented requirement: checklist prose, grepped by 8.8
- [x] 8.9 The authoring rules are brief prose. measured: `grep -nE "skip_specs|--no-scenarios" .claude/plugins/cla/skills/multi-spec/references/authoring-brief.md` returns each rule; 8.10 pins the same rules in the config block.
  - manual: A docs-only change: brief prose, grepped by 8.9
  - manual: Authoring a change that touches one capability: brief prose, grepped by 8.9
- [x] 8.10 Test, `plugin-tests/tests/consistency/test_cla_init_rules_match_config.py`: the `rules:` block cla-init seeds equals this repo's `openspec/config.yaml` block, every item containing `: ` is quoted, and the seed condition treats `config.yml` as existing. Partly proves "No config.yaml" and "An existing config.yml". measured: `pytest plugin-tests/tests/consistency/test_cla_init_rules_match_config.py -q` 3 passed; `python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_cla_init_rules_match_config.py` 4 of 4 killed.
- [x] 8.11 The Implement post-check and multi-pr's policy are orchestrator prose. measured: `grep -n "names a test" .claude/plugins/cla/skills/spec-to-pr/SKILL.md`, `grep -n "size gate" .claude/plugins/cla/skills/multi-spec/references/review-gate.md`, and `grep -n "full-severity" .claude/plugins/cla/skills/multi-pr/references/discover-and-gate.md` each return the rule at its site.
  - manual: A ticked test task whose test is missing: orchestrator prose, grepped by 8.11
  - manual: A batch of small changes: orchestrator prose, grepped by 8.11
  - manual: A change ships with a Suggestion open: orchestrator prose, grepped by 8.11
  - manual: The user picks full-severity: orchestrator prose, grepped by 8.11
- [x] 8.12 Exempt, no proof owed: the MODIFIED cla-init requirement's other four scenarios are carried forward unchanged in text and behaviour; only the scope sentence and the re-run scenario's last line widen to name the config file, proven by 8.3.
- [x] 8.13 `openspec validate lighter-openspec-packages --strict` passes.
- [x] 8.14 OpenSpec's tolerance of an extra file is the CLI's behaviour, not this repo's. measured in a scratch copy with OpenSpec 1.14.1 and this repo's `config.yaml`: a change carrying `review.json` passed `openspec validate mini --strict` (exit 0) and `openspec archive mini --yes` (exit 0, record carried into the archive); a `review:` key in `.openspec.yaml` instead failed `--strict` with an unrecognized-key warning.
  - manual: A review record passes strict validation: OpenSpec CLI behaviour, measured in a scratch copy by 8.14
- [x] 8.15 Test, `plugin-tests/tests/consistency/test_scenario_proof_format.py`: the authoring brief, the review checklist and the `rules:` block state the marker, the `manual: <heading>: <reason>` line, the rename exemption and unique headings alike, and no shipped file, config or live spec keeps the old `manual: <reason>` form. Convention from crisradu75/interoga-ro#711; the guard port is a later change. Markers: `# scenario: cla-plugin / Authoring a scenario`, `/ A pure heading rename`, `/ Authoring a heading that is already taken`, `/ A scenario with no proof`, `/ A repeated scenario heading`, `/ A test task that names no marker`. measured: `pytest plugin-tests/tests/consistency/test_scenario_proof_format.py -q` 7 passed; `python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_scenario_proof_format.py` 8 of 8 killed.
  - manual: Authoring a scenario: the authoring agent's runtime is prose; 8.15 pins only the brief and the rules
  - manual: A pure heading rename: the authoring agent's runtime is prose; 8.15 pins only the stated exemption
  - manual: Authoring a heading that is already taken: the authoring agent's runtime is prose; 8.15 pins only the stated rule
