Order: group 1 first. Every later `checklist.md` edit lands after 1.2, and the probe (group 5) lands before the SKILL.md text that describes it (6.3).

## 1. The rules block and conditional design.md (plan A)

- [x] 1.1 This repo's `openspec/config.yaml`: add the canonical `rules:` block (proposal one page; design only on a named stock trigger, never restating proposal or specs; one behaviour per ADDED requirement in ≤500 characters, detail in scenarios; each ADDED or MODIFIED scenario has a test task or a `manual: <reason>` note). Confirm `openspec instructions proposal --change lighter-openspec-packages --json` returns it.
- [x] 1.2 `review-change/references/checklist.md`: stop only when proposal.md is missing (`:25`); an absent design.md reads as "(absent)" (`:23,34`); agent prompts paste "(no design.md)" (`:227,263`).
- [x] 1.3 `multi-spec/references/authoring-brief.md` `done` (`:53`) and post-check (`:65`): proposal, tasks and a spec delta or `skip_specs`; design.md only on a named stock trigger. Step 3 (`:26`) writes design.md only when a trigger applies.
- [x] 1.4 `multi-spec/SKILL.md` (description `:3`, Phase 4 `:71`), `multi-spec/references/phases.md:47`, `DEVELOPER-GUIDE.md:132`: describe the artifacts actually present and the size-gated review.
- [x] 1.5 `multi-spec/references/review-gate.md:18`: an absent design.md reads as "(absent)".
- [x] 1.6 `cla-init/SKILL.md`: the `openspec/config.yaml` manifest item, copying 1.1's block (seed when `openspec/` exists and holds neither `config.yaml` nor `config.yml`; otherwise print). Update the description, the Report section and the Non-goals line that says it only writes under `cla.io/overlays/`.

## 2. authoring-brief.md additions (plans A, B, C, D)

- [x] 2.1 Remove the stale `openspec-propose` attribution (`:27`); pinned-parameters block only when design.md and a load-bearing number exist (`:28`); drop the doc-sync task (`:29`); one line restating the stock limits with a pointer to the config rules; each ADDED or MODIFIED scenario gets a test task or a `manual: <reason>` note. Leave the MODIFIED carry-forward procedure and "before starting the next change" unchanged.

## 3. Review checklist (plans B, C, D)

- [x] 3.1 Step 3 size gate: drop `d` from the inputs, the announce lines and the report mode lines; the complexity-concentration override keeps its concentration condition (one or two files) and fires on `b ≥ 15` only, losing its `d ≥ 4` leg. Keep the heading `## Step 3: Size gate`.
- [x] 3.2 Beside the testability check: the size finding (MODIFIED exempt from length) and the scenario-without-proof finding, both Important. Add cutting to the FIX FIRST remedies and prefer it. Keep `- **READY** — 0 Critical` and `- **FIX FIRST**`.
- [x] 3.3 Drop Step 5 (the parallelism plan) and its report section, and the three-verified-claims minimum; the old Step 6 becomes Step 5, which is intended. Keep the `0l` sweep row and `### Verified claims`. Update the restatements in `review-change/SKILL.md`, `spec-to-pr/SKILL.md` (Review) and `spec-to-pr-retro/SKILL.md`.

## 4. multi-spec batch review (plan D)

- [x] 4.1 `review-gate.md:26-28`: apply checklist Step 3 per change; dispatch the three agents over the batch only when a change grades large, otherwise review inline.

## 5. Resume probe

- [x] 5.1 `spec-to-pr/scripts/probe_state.py` `_implement_done`: true on `isComplete`, or when `applyRequires` is a non-empty list and each id has `status == "done"` in `artifacts[]` (keys `id`, `status`); missing or empty `applyRequires` is false. Grep for other callers first.

## 6. spec-to-pr and multi-pr (plans C, D)

- [x] 6.1 `spec-to-pr/SKILL.md` Review: the already-reviewed skip per design.md decision 1, keeping Step 2b, the retention comparison and the doc-sweep.
- [x] 6.2 `_shared/references/run-log-schema.md`: a skipped Review logs `status: skip` with a `reason` and omits `size_gate`, `verdict` and `verified_claims_count`; rewrite `:122` and `:125`. Grep `lib/log_run.py` and `spec-to-pr-retro/scripts/spec_to_pr_aggregate.py` to confirm neither rejects a Review record without them.
- [x] 6.3 `spec-to-pr/SKILL.md` Implement: step 2 (`:237`) and the post-check (`:267`) use the probe's `applyRequires` rule; the post-check greps for each test a ticked task names and sends a miss down the done-without-evidence path; the sample is drawn from measurement- or test-bearing tasks (`:272`). Note the no-design.md case at `:249`. Update `references/workflow-diagram.md:39`.
- [x] 6.4 `multi-pr/references/change-loop.md:11`: Review may run reduced for a multi-spec-reviewed change.
- [x] 6.5 `_shared/references/test-quality.md`: a one-line pointer to the scenario-proof rule.

## 7. Scope addition E (approved 2026-10-06)

- [x] 7.1 skip_specs: `authoring-brief.md` states the rule and its `done`/post-check accept `skip_specs`; the config `rules:` block (1.1, 1.6) carries it; `checklist.md` reports a requirement with no observable behaviour change as Important, remedy drop it and set `skip_specs`.
- [x] 7.2 Cheap spec reads: `authoring-brief.md`, `checklist.md` (Step 2 and the Agent 3 prompt) and `spec-to-pr/SKILL.md` (Propose, Review) read live specs overview-first with `openspec list --specs` and `openspec show <id> --type spec --json --no-scenarios`. The MODIFIED carry-forward (`authoring-brief.md:30-49`) is unchanged.
- [x] 7.3 multi-pr: `discover-and-gate.md:180` makes Critical/Important-fixed, Suggestions-recorded the recommended default, with full-severity as a named alternative; update `change-loop.md:38-44`, `multi-pr/SKILL.md:26,69,81`, the explicit-autonomy override (`discover-and-gate.md:190`) and `change-loop.md:34`. Check the "full-severity" wording in `spec-to-pr/references/revise.md:149`, `handoff.md:23` and `spec-to-pr/SKILL.md`: it describes spec-to-pr's own Critical/Important fix lists, so it stays.

## 8. Proofs

- [x] 8.1 Test, `test_probe_state.py`: a no-design status (`isComplete: false`, `applyRequires: ["tasks"]`, tasks `done`) gives `implement: true`; an `applyRequires` artifact `ready` gives false; missing and empty `applyRequires` give false. Proves "Resume on a change with no design.md", "Required artifact not done", "No applyRequires". Add a mutant per new branch to `plugin-tests/mutants/spec-to-pr/test_probe_state.py` and run the batch. measured: `pytest plugin-tests/tests/skills/spec-to-pr/test_probe_state.py -q` 42 passed; `python3 plugin-tests/mutate.py plugin-tests/mutants/spec-to-pr/test_probe_state.py` 12 of 12 killed.
- [x] 8.2 Test, `plugin-tests/tests/consistency/test_reviewed_change_trigger.py`: the two subjects spec-to-pr's Review keys on match what multi-spec writes, the review-fix commit in `review-gate.md` and the PR title in `phases.md`. Scope: subject drift only, not the skip's runtime. Partly proves "A change merged from a multi-spec PR". measured: 4 passed; `python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_reviewed_change_trigger.py` 4 of 4 killed.
- [x] 8.3 manual: cla-init is a prose skill with no script. Run its seed item's bash block in temp git repos. Proves "No config.yaml", "An existing config.yaml", "An existing config.yml", and the MODIFIED cla-init requirement's re-run scenario. measured with a scratch script that extracts the block from `cla-init/SKILL.md` and runs it via Git Bash in four temp git repos: no config → `created`, and `openspec instructions <artifact> --change probe-x --json` carried the seeded rule for proposal, design, specs and tasks; `config.yaml` present → sha256 unchanged, block printed; `config.yml` present → no `config.yaml` created, sha256 unchanged, block printed; no `openspec/` → nothing created, block printed.
- [x] 8.4 manual: the skip's runtime branches are prose run by the model, with no executable surface. Re-read the 6.1 text against "A change merged from a multi-spec PR" (runtime half; 8.2 pins the subjects), "A change edited after multi-spec's review" and "A squash-merged PR with a later edit".
- [x] 8.5 manual: design.md is optional, so it is a prose rule with no executable surface. Proves "A change without design.md passes the authoring post-check", "A design.md names its trigger", "A change without design.md is reviewed". measured: `grep -rnE "all four artifacts|design\.md is missing" .claude/plugins/cla plugin-tests DEVELOPER-GUIDE.md CLAUDE.md` returned 0 hits; the `done` list in `authoring-brief.md` names proposal, tasks and a spec delta or `skip_specs`.
- [x] 8.6 manual: the authoring brief's optional blocks are prose. Proves "A change with no load-bearing number", "Tasks without a doc-sync task", "The brief states the limits". measured: `grep -rnE "Pinned implementation parameters|doc-sync task" .claude/plugins/cla` returned 0 hits; `grep -n "when design.md exists" .claude/plugins/cla/skills/multi-spec/references/authoring-brief.md` returns the conditional pin rule; `grep -n "Stock limits" .claude/plugins/cla/skills/multi-spec/references/authoring-brief.md` returns the one line pointing to `openspec/config.yaml`.
- [x] 8.7 manual: the size gate and report shape are checklist prose. Proves "Many decision headings in a narrow change" and "A small change is reviewed". measured: `grep -nE "d ≥ 4|### D|Implementation Parallelism|at least 3 positive" .claude/plugins/cla/skills/review-change/references/checklist.md` returned 0 hits; the open questions keep the `0l` row.
- [x] 8.8 manual: the review findings are checklist prose. Proves "An ADDED requirement is too long", "A long MODIFIED requirement", "A finding that a cut resolves", "A scenario with no proof", "An invented requirement". measured: `grep -nE "500 characters|MODIFIED.*exempt|cutting|manual: <reason>|skip_specs" .claude/plugins/cla/skills/review-change/references/checklist.md` returns each rule at its site.
- [x] 8.9 manual: the authoring rules are brief prose. Proves "Authoring a scenario", "A docs-only change", "Authoring a change that touches one capability". measured: `grep -nE "manual: <reason>|skip_specs|--no-scenarios" .claude/plugins/cla/skills/multi-spec/references/authoring-brief.md` returns each rule; 8.10 pins the same rules in the config block.
- [x] 8.10 Test, `plugin-tests/tests/consistency/test_cla_init_rules_match_config.py`: the `rules:` block cla-init seeds equals this repo's `openspec/config.yaml` block, every item containing `: ` is quoted, and the seed condition treats `config.yml` as existing. Partly proves "No config.yaml" and "An existing config.yml". measured: `pytest plugin-tests/tests/consistency/test_cla_init_rules_match_config.py -q` 3 passed; `python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_cla_init_rules_match_config.py` 4 of 4 killed.
- [x] 8.11 manual: the Implement post-check and multi-pr's policy are orchestrator prose. Proves "A ticked test task whose test is missing", "A batch of small changes", "A change ships with a Suggestion open", "The user picks full-severity". measured: `grep -n "names a test" .claude/plugins/cla/skills/spec-to-pr/SKILL.md`, `grep -n "size gate" .claude/plugins/cla/skills/multi-spec/references/review-gate.md`, and `grep -n "full-severity" .claude/plugins/cla/skills/multi-pr/references/discover-and-gate.md` each return the rule at its site.
- [x] 8.12 manual: the MODIFIED cla-init requirement's other four scenarios are carried forward unchanged in text and behaviour; only the scope sentence and the re-run scenario's last line widen to name the config file, proven by 8.3.
- [x] 8.13 `openspec validate lighter-openspec-packages --strict` passes.
