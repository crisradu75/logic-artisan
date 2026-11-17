# Prompt audit part B: spec-to-pr, lite-pr, review-change

## Assumptions (Step 0)

- **Scope:** `.claude/plugins/cla/skills/spec-to-pr/` (SKILL.md, 10 references, 1 JSON, 2 scripts), `lite-pr/`, `review-change/`. Read-only; nothing applied.
- **Targets:** Claude Opus 5.5 (the session that asked). CLA sessions launch on Sonnet, so the text is also checked against Claude Sonnet 5.5. Pinned `Agent(model:)` text is audited against the pinned model: reviewers `sonnet`/`opus`, Implement delegate `sonnet`, `fact-gatherer`/`doc-sweeper` `haiku`.
- **Skipped:** `_shared/` files (model-routing, run-log-schema, ship, subagent-brief, review-sweeps), `lib/log_run.py` and the retro skill are outside scope. They are read for conflict checks and named as same-edit sites. Root `CLAUDE.md` is likewise read, not audited.
- **Owner decisions weighed:** `cla.io/decisions/cla-foundation-2026-11-17.md`, principles 3, 4, 5 and 8. Where a passage contradicts one, it is a Group 2 finding.
- **Group 3** (tool descriptions): not applicable; no tool definitions in scope. **Group 4** (request config): not applicable; no request code. The roster check is in Open questions.

## Inventory

| File | Words |
|---|---|
| spec-to-pr/SKILL.md | 4,849 |
| spec-to-pr/references/revise.md | 5,100 |
| spec-to-pr/references/design-tradeoffs.md (not read in a run) | 2,641 |
| spec-to-pr/references/handoff.md | 1,198 |
| spec-to-pr/references/implement-delegate.md | 1,113 |
| spec-to-pr/references/concurrent-runs.md | 917 |
| spec-to-pr/references/archive.md | 862 |
| spec-to-pr/references/branch-and-pr-base.md | 600 |
| spec-to-pr/references/workflow-diagram.md | 538 |
| spec-to-pr/references/scope-asks.md | 432 |
| spec-to-pr/references/test-notes.md | 369 |
| spec-to-pr/references/required-permissions-narrow.json | 205 |
| lite-pr/SKILL.md | 4,256 |
| lite-pr/references/measured-by.md | 651 |
| lite-pr/references/review-fix-weight.md | 477 |
| lite-pr/references/diagnose-escalation.md | 444 |
| lite-pr/references/mutation-gate.md | 434 |
| review-change/SKILL.md | 281 |
| review-change/references/checklist.md | 5,736 |
| review-change/references/dispatch.md | 2,529 |
| **Total (20 prose files)** | **about 33,400** |

Also read for comparison: `multi-spec/references/authoring-brief.md` (1,610), the "Review sizing by risk" section of `_shared/references/model-routing.md`, `openspec/config.yaml` rules, `cla.io/project-facts.md` "Stakes", `docs/evidence.md` ("Check 4", "Mutation testing is opt-in").

Fact checks: every `_shared/references/*`, `_shared/scripts/*`, `lib/log_run.py`, `probe_state.py` keys, `_resolve_branch`, `git_state.py --expect-branch`, `spec_to_pr_aggregate.py --nudge`, `multi-pr/references/cleanup.md`, the skills `diagnose`, `shape-decision`, `multi-lite`, `cla-setup` and the agents `fact-gatherer`, `doc-sweeper` all exist. No stale path found. `cla.io/overlays/{spec-to-pr,lite-pr,review-change}.md` do not exist in this repo; the text treats them as optional, so that is not a finding.

## Summary

The three highest-impact findings are all Group 2 conflicts with the 2026-11-17 decisions:

1. **Every Critical and Important finding is still fixed, with no filter (F1, F4, F7).** `revise.md:126` says "A finding never exits unaddressed", the exit gate needs untriaged and open both zero, and the checklist forbids moving a Critical or Important out of the fix lists (`checklist.md:229`). Decision 5 wants one review, then a filter on Stakes, then non-blocking findings to TODO.md.
2. **Round 2 and the mutation gate trigger on severity, not on protected areas (F2, F3).** Round 2 follows a Critical fix or a high-risk Important fix (six sites); the by-hand mutation gate is required for every Critical or Important fix (two copies). Decision 5 keys both to protected areas and guard hooks.
3. **Size is graded per artifact as Important (F5).** `checklist.md:66` counts words per artifact while the repo already has a whole-change budget (`openspec/config.yaml:17-18`) and a script that enforces it (decision 3).

Counts by group (findings tied to a pattern and a reason; Open questions are separate):

| Group | High | Medium | Low | Total |
|---|---|---|---|---|
| 1 Dated prompt text | 0 | 1 | 2 | 3 |
| 2 Brittle skill and config files | 5 | 6 | 3 | 14 |
| 3 Tool descriptions | not applicable | | | 0 |
| 4 Request config | not applicable | | | 0 |
| **Total** | **5** | **7** | **5** | **17** |

Where copies of a rule agree, the audit leaves them alone (keep-list 8). They are: the `${CLAUDE_PLUGIN_ROOT}` paragraph (three SKILL.md files), the diff-review sentence (`revise.md:37`, `lite-pr/SKILL.md:158`), the source-affecting suffix list (`spec-to-pr/SKILL.md:157`, `lite-pr/SKILL.md:102`), the docs check (`revise.md` "Docs currency", `lite-pr/SKILL.md:162`), INT-CAP and INT-SYC (`revise.md:163`, `checklist.md:216-217`), and the two mutation-gate texts. The mutation-gate copies agree with each other and disagree with the decision, which is F3.

## Findings, ordered by confidence

Hunks for F1 to F12 are in `B-diff.md`.

### High confidence

**F1. No merge-blocking filter before triage** (Group 2: conflict with `cla.io/decisions/cla-foundation-2026-11-17.md`, principle 5)
- **Location:** `spec-to-pr/references/revise.md:121-126, 222-232`; `spec-to-pr/SKILL.md:130, 193`; `spec-to-pr/references/handoff.md:52`
- **Evidence:** "Triage every Critical and Important finding into one of three buckets"; "A finding never exits "unaddressed". Suggestions flow to the optional `docs: TODO.md` commit."; "Untriaged — Critical/Important findings in no bucket."
- **Pattern:** Group 2, instruction files that contradict each other; also Group 1d, patch accretion.
- **Why obsolete:** the decision says one independent review, then a filter that keeps only findings that block a merge, with the rest in TODO.md. The text treats the reviewer's severity label as the gate. Across 44 findings in 6 repos, 70% were low-impact hardening, so the rule fixes mostly non-blocking things.
- **Confidence:** High. `git blame` puts `revise.md:126` at 2026-10-08 (9cd5f32f), before the 2026-11-17 decision.
- **Action:** rewrite (add a Stakes filter step 1b on `sonnet`; triage only blocking findings; non-blocking to TODO.md). Hunk F1. Requirement-level risk: the filter must never drop a protected-area finding. The hunk keeps that rule.

**F2. Round 2 triggers on severity, not on a protected-area fix** (Group 2: conflict with the decision, principle 5)
- **Location:** `spec-to-pr/SKILL.md:55, 193`; `revise.md:5, 81, 93, 226`; `lite-pr/SKILL.md:172`; also `_shared/references/model-routing.md:99-104`, `run-log-schema.md:59`, `workflow-diagram.md:70`, `spec-to-pr-retro/SKILL.md:26,31-34`
- **Evidence:** "round 2 runs only after round 1 fixed a Critical, or an Important on a high-risk PR (a docs-currency fix counts as neither)"
- **Pattern:** Group 2, conflict; Group 1d patch accretion (the docs-currency carve-out and "high at round 1's final level" are conditionals on a trigger that goes away).
- **Why obsolete:** the decision runs a second round only when a fix touched a protected area. The existing rule counts severity and a repo-agnostic "high risk" list.
- **Confidence:** High on the conflict. The hunk is medium on blast radius: `log_run.py` validates the round `trigger` values `critical`, `high-important`, `reentry` (grep `high-important` lists six files). Change them in the same edit (CLAUDE.md check 5).
- **Action:** rewrite. Hunk F2 covers the in-scope files and lists the same-edit sites.

**F3. By-hand mutation check is required for every Critical or Important fix** (Group 2: conflict with the decision, principle 5)
- **Location:** `spec-to-pr/references/revise.md:173-194`; `lite-pr/SKILL.md:168-170`; `lite-pr/references/mutation-gate.md:3-28`
- **Evidence:** "Mutation gate (by hand ...; required before the commit in step 3). A fix for a Critical/Important finding earns the same evidence the original code needed"; "the fix commit does not ship without it."
- **Pattern:** Group 2, conflict; Group 1d, history narratives (`mutation-gate.md:7-8, 27-28` cite two incidents).
- **Why obsolete:** the decision keeps the by-hand check only for protected-area fixes and guard hooks. `docs/evidence.md` "Mutation testing is opt-in" gives the same trend: against 16 review findings, mutation runs found 2 test gaps. The 2026-10-14 rule already said no automated batch; the 2026-11-17 rule narrows the by-hand floor.
- **Confidence:** High on the conflict. In this repo nearly everything is a protected area ("anything shipped to other repos", guard hooks), so the gate stays on here; it relaxes only in repos with lighter Stakes.
- **Action:** rewrite. Hunk F3. Root `CLAUDE.md` check 4 and `_shared/references/test-quality-gates.md:138` say "every review fix"; the owner decides whether they follow.

**F4. READY verdict counts every Critical and Important; no place for a non-blocking one** (Group 2: conflict with the decision, principle 5)
- **Location:** `review-change/references/checklist.md:204, 229` (also `:62`)
- **Evidence:** "**READY** — 0 Critical, 0 Important"; "A `[Critical]` or `[Important]` never prints under `### Suggestions`." The consumer `spec-to-pr` applies every Critical and Important and "does nothing with Suggestions".
- **Pattern:** Group 2, conflict. Rule 229 is a reasoned rule (a Critical filed under Suggestions was dropped), so it stays; the fix adds a section, not an exception.
- **Why obsolete:** the decision's filter needs a place for a non-blocking Critical or Important that does not move the verdict.
- **Confidence:** High on the conflict, medium on the exact wording.
- **Action:** rewrite (a "Blocking and non-blocking" subsection and a `### Non-blocking (to TODO.md)` section). Hunk F4.

**F5. Size is graded per artifact and counted Important; the repo has a whole-change budget script** (Group 2: conflict with the decision, principle 3)
- **Location:** `review-change/references/checklist.md:62, 66`
- **Evidence:** "**Size.** A proposal over about 400 words; a design.md over about 800; a task over about 40 words ... The remedy is the cut."; line 62: "Each one that fires is an **Important** finding".
- **Contradicting repo text:** `openspec/config.yaml:17-18` ("at most 25 requirements across all its specs and at most 6,000 words in total"), `multi-spec/references/authoring-brief.md:45,75` ("a script enforces the budget"), decision 3 ("The size check measures a whole change").
- **Pattern:** Group 2, conflict; the owner flagged it ("The review checklist treats size as an Important finding").
- **Why obsolete:** only script-checked limits held; the checklist never mentions the script or the Stakes-set budget.
- **Confidence:** High.
- **Action:** rewrite. Hunk F5: run `check_spec_proof.py`, a budget breach is Important, the per-artifact word guidance is a Suggestion.

### Medium confidence

**F6. A skipped phase is `✗`, and any `✗` blocks the merge line** (Group 2: two files disagree)
- **Location:** `spec-to-pr/references/workflow-diagram.md:51, 111` against `spec-to-pr/references/handoff.md:64` and `spec-to-pr/SKILL.md:203`
- **Evidence:** diagram: "| ✗ skipped | no work to do | e.g. doc-only change has no tests |"; handoff: "**Any ✗:** print "**This PR is NOT ready to merge.**"... do NOT name `gh pr merge`."; SKILL: "Name `gh pr merge` only when every phase is ✓".
- **Pattern:** Group 2, two files give opposite rules. A docs-only change skips Test (`SKILL.md:157`), so it gets "NOT ready".
- **Why obsolete:** the repo contradicts itself; no text says which was meant.
- **Confidence:** Medium. A run may handle the case in practice; nothing here says so.
- **Action:** rewrite (skip glyph `–`, counts as ✓ for gating). Hunk F6. Owner to confirm the intent.

**F7. lite-pr keeps Suggestions in the final report only** (Group 2: conflict with the decision, principle 5, and with spec-to-pr Handoff)
- **Location:** `lite-pr/SKILL.md:166, 179`
- **Evidence:** "Triage every Critical/Important finding: apply a fix ... "; "Suggestion-level findings: mention them in the final report; no fix applied automatically."
- **Pattern:** Group 2. Decision 5 sends non-blocking findings to TODO.md; spec-to-pr Handoff (`handoff.md:37-57`) already writes TODO.md; root CLAUDE.md says TODO.md is the inbox for leftover suggestions. lite-pr has no filter and no TODO.md write.
- **Confidence:** Medium.
- **Action:** rewrite. Hunk F7. lite-pr has one pass and no filter agent, so the orchestrator applies the blocking test itself.

**F8. "No formal routing rule between lite-pr and spec-to-pr"** (Group 2: conflict with the decision, principle 8)
- **Location:** `lite-pr/SKILL.md:12, 187`
- **Evidence:** "There is no formal routing rule between the two"; "is your judgment call at invocation time. The intro says there is no size rule".
- **Pattern:** Group 2. Decision 8 makes lite the default and sends protected-area or shipped-to-others changes to the spec path, recommended from the stakes by `shape-decision` and `multi-spec`.
- **Confidence:** Medium: the decision's order of work puts the rollout after the benchmark, and `shape-decision`/`multi-spec` do not yet make the recommendation (not checked in full).
- **Action:** rewrite. Hunk F8; verify the recommendation exists before landing.

**F9. Reviewer prompts ask for missing edge cases and missing tasks without a stakes limit** (Group 2: gap against `authoring-brief.md`, "think broadly, write narrowly")
- **Location:** `review-change/references/dispatch.md:40, 81`
- **Evidence:** "completeness (missing edge cases — <inject: ...>)"; "**Missing tasks** — <inject: this repo's own list of commonly-forgotten companion tasks ...>".
- **Pattern:** Group 2 conflict between two instruction files. The brief says "only risks touching a protected area become requirements; the rest go in a one-line Risks noted list"; the reviewer asks the reverse, and its findings flow into FIX FIRST, which `spec-to-pr` fixes by adding text. That re-grows what the brief trims.
- **Confidence:** Medium. Protected-area edge cases must stay reportable, so the hunk does not delete the check.
- **Action:** rewrite. Hunk F9.

**F10. Incident story inside lite-pr's source-affecting rule** (Group 2: history narrative)
- **Location:** `lite-pr/SKILL.md:102` (blame 8e4ae654, 2026-08-11)
- **Evidence:** "`.py` is called out because it was once missing, and in a Python repo a real source change then did not register ..."
- **Pattern:** Group 2, history narratives. The rule is "the list is illustrative"; the origin is already in `design-tradeoffs.md:41`.
- **Confidence:** Medium.
- **Action:** rewrite. Hunk F10.

**F11. Two incident narratives and a consumer file name in shipped prose** (Group 2: history narratives; CLAUDE.md "Keep facts out of the shipped plugin")
- **Location:** `review-change/references/checklist.md:158` (blame 7607bf13, 2026-10-07), `:206` (blame 1d40b717, 2026-11-02)
- **Evidence:** "a `seed.ts`-concentrated change gated Small on `a=4` ... (8, zero phantoms)"; "corrupted the `verdict` field's meaning in `/cla:spec-to-pr-retro`'s telemetry (multiple real runs ...)".
- **Pattern:** Group 2, history narratives. The rules (the override threshold, judge by fix nature) stay; the stories go.
- **Confidence:** Medium. I did not run `check_no_project_tokens.py`, so I do not know whether `seed.ts` passes it.
- **Action:** rewrite. Hunk F11.

**F12. "the hook that used to is gone"** (Group 1d: migration-relative phrasing)
- **Location:** `spec-to-pr/references/concurrent-runs.md:5` (blame 5b344487, 2026-08-14)
- **Evidence:** "nothing arbitrates two sessions in one clone — the hook that used to is gone, so the discipline below is the whole protection."
- **Why obsolete:** a diff against a prompt version the model never saw; it implies a hook to look for.
- **Confidence:** Medium.
- **Action:** rewrite. Hunk F12.

### Low confidence (flag only; not in the diff)

**F13. Overlay fallback sentence repeated in three files** (Group 2: fossil of a past move)
- **Location:** `spec-to-pr/SKILL.md:153`, `lite-pr/SKILL.md:14`, `review-change/references/checklist.md:7`
- **Evidence:** "the overlay may still hold it from before the move: tell the user "run /cla:cla-setup to move it"."
- **Why flagged:** the three copies agree, and a consuming repo may still hold old overlays, so it protects a real migration path. Remove once the owner says no repo still has one. No overlay for these skills exists in this repo.

**F14. "a phase boundary gets at most one brief sentence"** (Group 1f: numeric output clamp)
- **Location:** `spec-to-pr/SKILL.md:175`
- **Evidence:** "No finality headers (`## Done`, `## Summary`) before Handoff: a phase boundary gets at most one brief sentence".
- **Why flagged:** Opus 5.5 and Sonnet 5.5 under-narrate, so a clamp on narration can suppress updates the user wants. The line is part of the turn-liveness rule (design-tradeoffs "Autonomy gate and turn liveness"), which is incident-backed, so it stays. If edited: "A phase boundary gets a short status line, in the same message as the next tool call."

**F15. Remedy-rejected re-attempt machinery** (Group 1d: patch accretion)
- **Location:** `spec-to-pr/references/revise.md:124-138, 152-159, 166-169, 223-232` (about 900 words)
- **Evidence:** the three-status contract, "free re-attempt", `Fact corrections:` field, two exit counts, rejected-alternatives snapshot.
- **Why flagged:** once the filter (F1) and the one-fix-pass rule land, most of this guards a path that gets rarer. But its output gates `gh pr merge` (`handoff.md:61`), so trimming weakens a safety rule. Decision 2 says trims are judged on output (the benchmark), not on word count. Owner to decide after the benchmark; no hunk.

**F16. `review-fix-weight.md` is a PR-and-commit narrative** (Group 2: history narratives)
- **Location:** `lite-pr/references/review-fix-weight.md:1-59` (477 words; cites PR #186 and commit ids)
- **Why flagged:** the rule is one sentence at `lite-pr/SKILL.md:173-175`; the file is rationale, read only for the worked example. It also describes what review-after-fix cost, which stays relevant under the new "second round only for a protected-area fix". Low value, low harm.

**F17. `Workflow` fan-out script in `revise.md`** (Group 2: padding)
- **Location:** `spec-to-pr/references/revise.md:43-66` (about 350 words, opt-in path only)
- **Why flagged:** only read by a run that opted into workflows; duplicates what `design-tradeoffs.md:69` explains. Leave it.

## Open questions

These are gaps with no requirement behind them. None is a protected-area risk, so none is a hunk.

1. **Does the risk call read the Stakes?** `model-routing.md:59-76` lists six generic risk signals (writes, money, auth, guard hooks, concurrency, agent instructions). High risk drives the Opus reviewers and `silent-failure-hunter` (revise.md:16, lite-pr:152). Decision 1 says "every sizing choice reads from" Stakes. Should the risk call come from the Stakes section instead of, or beside, that list? `_shared/` is outside this audit, so no hunk.
2. **What does "one independent reviewer" mean in Revise round 1?** `revise.md:31` and `SKILL.md:185` dispatch every matching agent, up to six (`code-reviewer`, `silent-failure-hunter`, `comment-analyzer`, `pr-test-analyzer`, `type-design-analyzer`, `skill-reviewer`), "no budget-based reduction, no degraded mode". Decision 5 says "one independent reviewer reports everything". If that means one review pass, nothing conflicts. If it means one agent, `revise.md:18-31` and `SKILL.md:185` need a rewrite.
3. **spec-to-pr Propose does not pass Stakes or the "think broadly, write narrowly" brief.** `SKILL.md:110` calls `Skill(openspec-propose)` or an `opus` Agent with only the description. The brief lives in `multi-spec/references/authoring-brief.md`. A description-mode run therefore writes specs without the Stakes rubric or `## Risks noted`. Should spec-to-pr Propose read the same brief?
4. **review-change has no check for the reverse gap.** The "Invented requirement" and "Size" checks catch too much. Nothing checks that a protected-area risk has a requirement, or reads a `## Risks noted` list. Add one check (a protected-area risk named in the proposal or the specs with no requirement is Important), or leave it to the Stakes filter?
5. **Is a stale doc a blocking finding?** `revise.md:81` and `lite-pr/SKILL.md:162` make every stale doc an Important finding in round 1. Under the filter, a stale doc blocks only where the doc is a protected area (a shipped skill doc: yes; a README line: no). Decide, and the docs-currency carve-outs in F2 either vanish or stay.
6. **Root `CLAUDE.md` still says "break each fix by hand once" for every review fix.** Decision 5 narrows it (F3). Out of audit scope; the owner decides whether CLAUDE.md and `test-quality-gates.md:138` follow.
7. **`design-tradeoffs.md:75` records the round-2 rule's history** (the 2026-10-13 high-risk Important arm; "37 of 37 changes"). If F2 lands, that paragraph needs a dated "superseded 2026-11-17" note, which is rationale, not instruction.
8. **Pinned-model check.** No text pinned to Sonnet 5.5 or Opus 5.5 asks the model to think less, to be brief by count, or to hold updates. The `(MOST IMPORTANT)` marker appears once per reviewer prompt (`dispatch.md:39, 72, 108`), which is scoped use. The Implement delegate's required test-summary evidence matches the documented low-effort verification gap on Sonnet 5.5. No change proposed.
