# Prompt audit, part C: multi-pr, multi-lite, multi-spec, cla-setup, project-review

Read-only. Nothing in the repo was edited. Skills dir: `C:\Code\logic-artisan\.claude\plugins\cla\skills\` (paths below are relative to it).

## Step 0 assumptions

- **Scope:** `multi-pr/`, `multi-lite/`, `multi-spec/`, `cla-setup/`, `project-review/`: every SKILL.md, every reference file, plus the prose parts of two `.py` files (the RULES and RETIRED text in `cla-setup/scripts/seed_openspec_rules.py`, lines 41-87; the docstring there is read for provenance only). `check_cite_drift.py` and `check_fact_paths.py` were read for flag/path existence only. Skipped: `_shared/`, `spec-to-pr`, `lite-pr`, `review-change` (read only to check cross-file agreement), `.claude/settings*`.
- **Target model:** Claude Opus 5.5 (the session that asked), checked against the "Behavioral shifts" parts of the Opus 5.5 and Sonnet 5.5 migration sections. CLA sessions run Sonnet 5.5, so the Sonnet 5.5 shifts were applied to the orchestrator text too. Pinned dispatches audited against their pin: `multi-spec` authoring agent `model: "opus"`, `project-review` Agents 1 and 4 `opus`, Agents 2, 3 and 5 `sonnet`; the review-gate agents (Opus design, Sonnet task and spec) come from `review-change/dispatch.md`, out of scope.
- **Owner decisions** read from `cla.io/decisions/cla-foundation-2026-11-17.md` (D1 stakes, D3 whole-change budget, D4 think broadly write narrowly, D5 one review then filter, D6 rules carry origin and scope, D8 lite default). Its "Order of work" says nothing in CLA changes until the benchmark exists, so D5, D6 and D8 text is not yet implemented anywhere: those findings are "pending decision", not drift, and I propose wording but never as a rule already in force.
- **Provenance:** `git blame` and `log` used. Origin issue numbers in multi-pr and multi-lite (#130, #284, #287, #281, #98/#100/#102, #272) are the kind of origin tag D6 asks for, so they were not treated as history narrative. `docs/evidence.md` covers CLAUDE.md rules only, not these skills, so it gave no verdict on any finding here.

## Inventory (words, as counted by `wc -w` on the whole file)

| File | Words |
|---|---|
| multi-pr/SKILL.md | 3770 |
| multi-pr/references/change-loop.md | 4807 |
| multi-pr/references/discover-and-gate.md | 3927 |
| multi-pr/references/cleanup.md | 1404 |
| multi-pr/scripts/check_cite_drift.py (code, read for flags only) | 1351 |
| multi-lite/SKILL.md | 2866 |
| multi-lite/references/candidate-loop.md | 3164 |
| multi-lite/references/candidate-extraction.md | 760 |
| multi-lite/references/bootstrap-and-tracking.md | 670 |
| multi-lite/references/phase4-and-log.md | 603 |
| multi-spec/SKILL.md | 1951 |
| multi-spec/references/authoring-brief.md (light audit) | 1610 |
| multi-spec/references/review-gate.md | 1802 |
| multi-spec/references/phases.md | 857 |
| multi-spec/references/plan-schema.md | 787 |
| cla-setup/SKILL.md | 2323 |
| cla-setup/references/facts-file.md | 999 |
| cla-setup/references/economy-rules-block.md | 765 |
| cla-setup/references/openspec-rules.md | 602 |
| cla-setup/references/overlay-reconcile.md | 599 |
| cla-setup/references/ledgers-and-run-notes.md | 536 |
| cla-setup/references/spec-map-scaffold.md | 324 |
| cla-setup/scripts/seed_openspec_rules.py: RULES (lines 41-66) | 757 |
| cla-setup/scripts/seed_openspec_rules.py: RETIRED (lines 69-87) | 411 |
| project-review/SKILL.md | 967 |
| project-review/references/review-agents.md | 1806 |
| project-review/references/review-criteria.md | 1572 |
| project-review/references/aggregate-and-log.md | 473 |
| project-review/references/baseline-checks.md | 415 |
| **Prose total (excluding the two checker scripts and the rest of the seed script)** | about 41,000 |

## Summary

Highest-impact findings:

1. **Seeded RULES, facts file and authoring brief disagree on what "protected" means** (F7). The seeded rule hard-codes money, security, personal data, honesty claims and accessibility for every repo. The Stakes section in `facts-file.md` says money, personal data, the user's own files and anything shipped to others. The brief falls back to a third list. D1 says protected areas are per repo. The seeded text lands in every repo's `openspec/config.yaml`, so this is the highest-reach text in scope.
2. **Stakes is already read, but the facts file says no skill reads it** (F1, High). `facts-file.md:33` was written in PR #509 the same day PR #510 made the multi-spec brief read it.
3. **Three owner-decision conflicts in the batch skills** (F13, F14, F15): multi-lite demands a by-hand break-it check on every deferred-finding fix (D5 limits it to protected areas and guard hooks); multi-spec's review gate applies every Critical/Important finding with no filter by stakes (D5); multi-spec's report sends every change to `/cla:multi-pr` (D8: lite by default, full path by stakes). All three are pending-decision, so they carry proposed wording and need the owner's confirmation.

Counts per group (findings, by confidence):

| Group | High | Medium | Low (flag only) | Total |
|---|---|---|---|---|
| 1 Dated prompt text | 0 | 4 | 1 | 5 |
| 2 Brittle skill and config files | 2 | 9 | 2 | 13 |
| 3 Tool descriptions | 0 | 0 | 0 | 0 |
| 4 Request config and architecture | not applicable (no request-building code; the model pins are alias strings with no retired model; roster has no redundant agents) | | | |

No finding is a Group 1a pressure-language finding: the strong wording in multi-pr and multi-lite carries issue-number provenance and a stated reason (keep-list items 5 and 8). Not one `think step by step`, `be thorough`, `hold findings`, prefill, forced tool_choice, `thinking`/sampling parameter, or retired model name appears in scope. No `reasoning`/trace output field is requested of any agent, so the `reasoning_extraction` row has no hit.

Copies that agree (keep-list item 8, one line): the never-end-a-turn / turn-liveness rule is stated in multi-pr SKILL.md:36, change-loop.md:129-142, multi-lite SKILL.md:37, candidate-loop.md:86-100, multi-spec SKILL.md:29, authoring-brief.md:87-98 and spec-to-pr SKILL.md:177; all agree on the two legitimate ways to end a turn (a backgrounded dispatch in flight, or the run complete) and on "status text and the next tool call in the same message"; only the blocker handling differs, and each differs for a reason of its own skill (multi-pr has a closed blocker list and files issues; multi-lite quarantines; multi-spec asks). The project-review verdict table is stated in SKILL.md:49-54 and review-criteria.md:121-126 with identical wording (the table itself has a gap, F11). `chain-merge.md` and the `<base-branch>` rule are single-sourced.

Facts checked and found current: every `${CLAUDE_PLUGIN_ROOT}/skills/_shared/...` file named in scope exists (chain-merge, plugin-root, base-branch-resolution, runtime-rules, orchestration-economy, economy-rules-file, model-routing, bash-discipline, conflict-resolution, required-permissions.json, test-quality-gates, retiring-specs, review-sweeps, instruction-files, terminology-format, git_state.py, check_spec_proof.py); so do `spec-to-pr/scripts/probe_state.py` (which defines `_archived`), `lite-pr/references/mutation-gate.md`, `review-change/references/{checklist,dispatch}.md` (checks 0a-0l, Step 2b, Step 3, INT-CAP/INT-SYC all resolve), `lib/log_run.py`, the hooks `ask-destructive-git.py`, `block-unsafe-recursive-delete.py`, `block-cd-in-bash.py`, and `.claude/skills/openspec-propose`. `check_cite_drift.py` defines `--since`, `--ref`, `--fix`, `--list`.

## Findings (ordered by confidence)

### High

**F1. Location:** `cla-setup/references/facts-file.md:33`
- **Evidence:** "A reconcile keeps an existing section as written. No other skill reads this section yet."
- **Pattern:** Group 2, volatile specifics (a claim the repository contradicts).
- **Why obsolete:** `multi-spec/references/authoring-brief.md:10,33,39` makes the authoring agent read `cla.io/project-facts.md` "especially its Stakes section". Blame: the facts-file line is `af3bd81c` (PR #509, 2026-11-17); the brief is `b89b2369` (PR #510, the same day). The seed script also reads the `Change budget:` line of this section (`seed_openspec_rules.py:115,132-135`).
- **Confidence:** High (repository contradicts it).
- **Action:** rewrite. Diff hunk H1.

**F2. Location:** `multi-spec/references/plan-schema.md:3`
- **Evidence:** `See SKILL.md Phase 2's "Persist the plan now, on the branch."`
- **Pattern:** Group 2, volatile specifics (a named passage that no longer resolves).
- **Why obsolete:** The quoted sentence appears nowhere under `.claude/plugins/cla/` (grep for "Persist the plan now" matches only this line). `SKILL.md` Phase 2 is headed "Batch branch preflight, then persist the plan"; the recipe is in `references/phases.md` Phase 2.
- **Confidence:** High.
- **Action:** rewrite. Diff hunk H2.

### Medium

**F3. Location:** `multi-spec/references/plan-schema.md:42`
- **Evidence:** "Resume always re-derives "is this change done" from the repository itself (Phase 3 step 1's tracked-file check)".
- **Pattern:** Group 2, volatile specifics.
- **Why obsolete:** SKILL.md Phase 3 has no numbered steps. The tracked-file check is the "Resume check" section of `authoring-brief.md:67-69`.
- **Confidence:** Medium (the check exists; only its name is wrong).
- **Action:** rewrite. Hunk H3.

**F4. Location:** `multi-spec/references/plan-schema.md:11`
- **Evidence:** "...(see a per-user note)."
- **Pattern:** Group 2, history narrative and a path outside the project.
- **Why obsolete:** The file ships to every repo that installs the plugin. It cites a private per-user note that exists in no repo. The same reference also appears in `hooks/block-unsafe-recursive-delete.py` and `skills/feedback/SKILL.md`, outside this scope; raised here only because this copy sits in scope.
- **Confidence:** Medium.
- **Action:** rewrite (drop the parenthetical; the incident sentence stays). Hunk H4.

**F5. Location:** `cla-setup/SKILL.md:246-247`
- **Evidence:** "A gate still wiring the `0.x` `conformance-checks/tests` directory checks nothing: say so and recommend this program."
- **Pattern:** Group 1d, fossils and migration-relative phrasing.
- **Why obsolete:** The `conformance-checks/` tree was deleted (archive change `2026-08-23-extract-dev-tree-from-plugin`, task 3.6). The sentence is a diff against a layout the model never saw, in a skill run in repos that never had it. Origin: `25d0fab2` (2026-10-08). The same sentence also sits in `DEVELOPER-GUIDE.md:436`, where a `0.x` upgrade note belongs; that copy is out of scope and untouched.
- **Confidence:** Medium.
- **Action:** remove. Hunk H5.

**F6. Location:** `cla-setup/SKILL.md:25`
- **Evidence:** "It replaces the former `cla-init` and `sync-context` skills, which no longer exist."
- **Pattern:** Group 1d, migration-relative phrasing.
- **Why obsolete:** Neither skill is in the skill list. Nothing in the run depends on the sentence. (`overlay-reconcile.md:14-15` mentions the old `sync-context` pointer as a scaffolding line to drop; that is a live classification rule and stays.)
- **Confidence:** Medium.
- **Action:** remove. Hunk H6.

**F7. Location:** `cla-setup/scripts/seed_openspec_rules.py:54` (RULES), against `cla-setup/references/facts-file.md:25-26` and `multi-spec/references/authoring-brief.md:10`
- **Evidence:** RULES: "Money, security, personal data, honesty claims and accessibility are protected: a rewrite compresses their requirements and never drops them." facts-file Stakes: "Protected areas: (any of money, personal data, the user's own files, anything shipped to other repos; or `none`)". Brief fallback: "the areas the seeded `rules:` name (money, security, personal data, honesty claims, accessibility) plus the user's own files".
- **Pattern:** Group 2, instruction texts that disagree on one point; also conflicts with D1 (per-repo stakes).
- **Why obsolete:** Three lists, three vocabularies. A repo whose Stakes say `none` still has the seeded rule making five areas untouchable; a repo naming "anything shipped to other repos" finds nothing in the seeded rule about it. D1 makes protected areas per repo. Direction: the Stakes wording is newer (`af3bd81c` and `b89b2369`, 2026-11-17; the RULES line is `0ba22eff`, 2026-10-15), so I rewrite the RULES line to defer to the Stakes section, with the old five-area list kept only as the fallback when a repo has no Stakes section. Because the old wording was shipped it moves to `RETIRED`, and the repo's own `openspec/config.yaml` plus the test that checks `RULES` against it change in the same edit. This is a "never drops" safety rule: the rewrite keeps the prohibition and only changes what it is keyed on, but the owner should confirm the fallback list.
- **Confidence:** Medium.
- **Action:** rewrite. Hunks H7a and H7b.

**F8. Location:** `cla-setup/scripts/seed_openspec_rules.py:43, 48, 64` (RULES)
- **Evidence:** "Keep it to about 400 words." (proposal); "Keep it to about 800 words" (design); "Keep each task to about 40 words".
- **Pattern:** Group 1f (numeric output ceilings) and Group 1d (unenforced instructions).
- **Why obsolete:** `check_spec_proof.py` reads only the whole-change budget (requirements and total words, lines 486-612) and the per-requirement limits (500 characters, scenarios); nothing counts a proposal, a design or a task. The owner's own evidence (decision file, "Only script-checked limits held; prose size limits failed in every repo") and D3 ("a hard rule becomes a script; everything else is guidance") say these three are guidance. The whole-change budget already caps the total, which is the enforced limit. Rewrite as qualitative guidance with the reason; a numeric clamp starves nothing on Opus 5.5 but is read literally by Sonnet 5.5 agents. Old wordings go to `RETIRED`. Per D3 and D7 this must hold the mnemo benchmark before it ships, so it is a proposal, not a quiet trim.
- **Confidence:** Medium.
- **Action:** rewrite. Hunks H8a and H8b.

**F9. Location:** `project-review/references/review-agents.md:24` and `project-review/references/aggregate-and-log.md:69`
- **Evidence:** "**Finding caps:** At most **3 strengths** and **5 gaps**. Prioritize the most impactful." and "Keep each finding to 1-2 lines. Aim for ~60-80 lines total — comprehensive but scannable."
- **Pattern:** Group 1f (output-shaping choreography; numeric ceilings removed together).
- **Why obsolete:** Written for models that padded. A stated operational reason (five reports to aggregate) does not make a clamp a keeper; the doc says re-express as audience and outcome. Applies to the Sonnet 5.5 agents 2, 3 and 5, which follow numeric caps literally and can drop a real fourth gap.
- **Confidence:** Medium.
- **Action:** rewrite. Hunks H9a and H9b.

**F10. Location:** `multi-spec/SKILL.md:33` and `project-review/SKILL.md:42`
- **Evidence:** "Effort is not independently dialed on the `Agent(...)` mechanism" and "Effort is not dialable on `Agent`-dispatched work (it inherits the session); only the model is set here."
- **Pattern:** Group 2, volatile specifics (a claim about the host tool with no verification date).
- **Why obsolete:** The `Agent` tool in the session that ran this audit documents an `effort` parameter (set only when the owner asks). The same claim sits in `_shared/references/model-routing.md` (out of scope, not edited; it should follow). The evidence is my own tool schema, not a file in the repo, and a plugin may run on a host without that parameter, so this is Medium, not High. Blame: multi-spec line `ae75f1c8` (2026-08-14).
- **Confidence:** Medium.
- **Action:** rewrite. Hunks H10a and H10b.

**F11. Location:** `project-review/SKILL.md:48-55` and `project-review/references/review-criteria.md:119-126` (same table in both)
- **Evidence:** EXEMPLARY all A/B; STRONG majority A/B, at most one C, no D; SOLID majority B/C, at most one D; NEEDS WORK two or more D, or majority C/D.
- **Pattern:** Group 2, contract accuracy (a rubric the model must compute that is not total).
- **Why obsolete:** Checked by enumeration over five grades. Grades with no matching row: A,A,A,A,D and A,A,A,C,D (one D, but A/B majority fails STRONG because of the D, B/C majority fails SOLID, and NEEDS WORK needs two Ds); A,A,A,C,C (two Cs fail STRONG, B/C is only two, C/D is only two). Rows that both match: A,B,C,C,C matches SOLID and NEEDS WORK. N/A dimensions (allowed by the plugin fallback section, `review-agents.md:58-61`) make "majority of five" undefined. The model resolves each by guessing. Proposed order-based rule below covers every case and keeps every verdict that was previously defined. It moves a score, so it needs a before/after on real reports before it ships; it changes verdicts only for the ambiguous sets above.
- **Confidence:** Medium.
- **Action:** rewrite. Hunks H11a and H11b.

**F12. Location:** `project-review/references/review-agents.md:104-118` (Agent 4) and `:120-133` (Agent 5)
- **Evidence:** "Is the gateway → projection → engine → component chain strictly one-directional? Is the app's root component the single source of truth for its draft/result state...", "Engine purity — is the core generate/compute function pure...", "i18n architecture — is all user-facing text routed through the translation-key mechanism", "Data seam", and in Agent 5 "Engine edge cases ... NaN".
- **Pattern:** Group 2, facts outside the plugin (project-specific assumptions in shipped prompts; CLAUDE.md "Keep facts out of the shipped plugin") and wrong degrees of freedom.
- **Why obsolete:** These items assume one product's architecture (a gateway, an engine, an i18n layer). They are asked of every repo; only items 3, 7 and 8 and the multi-tenant ones carry an "if applicable" or `(none recorded)` escape. The N/A rule that makes that safe sits only in the plugin-repo fallback section (`review-agents.md:58-61`), so an application repo without an engine or i18n layer has no instruction to report N/A and the agent grades down for absence. Fix is small: lift the N/A rule into the standard instructions every agent receives, and leave the five dimension prompts alone.
- **Confidence:** Medium.
- **Action:** add. Hunk H12.

**F13. Location:** `multi-lite/references/candidate-loop.md:54, 58` (and the lead-in at `:49` and `multi-lite/SKILL.md:47`)
- **Evidence:** "Show each fix works, to the same standard `/cla:lite-pr` holds its own fixes to ... Break what the fix touches by hand so the defect is back, run the affected test, and confirm it FAILS." applied to every deferred Critical/Important fix; "A fix whose break no test caught → write `review: unresolved` with the reason `enforcement fix unverified`".
- **Pattern:** Group 2, conflict with an owner decision (D5: "The by-hand mutation check stays only for fixes in protected areas and guard hooks; a second round runs only when a fix touched a protected area").
- **Why obsolete:** The step runs the break-it check for every fix in every repo and turns a miss into a quarantine of the PR's dependents. The same standard sits in `lite-pr/references/mutation-gate.md` (out of scope), so changing only this copy would leave the two skills disagreeing; both need the same edit. Tightening the check is a verification gate, so this finding is the "weakens a safety rule" shape: the proposed text is shown for the owner to confirm, and the direction (decision file newer than the skill text, `b561b82c`, 2026-10-12) is stated as an assumption. D5 is pending the benchmark, so it is not yet drift.
- **Confidence:** Medium.
- **Action:** rewrite, owner confirmation required. Hunk H13.

**F14. Location:** `multi-spec/references/review-gate.md:61` and `multi-spec/SKILL.md:62`
- **Evidence:** "Apply every Critical/Important finding as a direct `Edit`/`Write` fix..."; "Apply every Critical/Important finding, re-validate, and commit the fixes as one follow-up commit".
- **Pattern:** Group 2, conflict with an owner decision (D5: one reviewer reports everything; a filter keyed to the Stakes section keeps only what blocks a merge; non-blocking findings go to TODO.md).
- **Why obsolete:** The gate already runs one review, matching D5's first half. The second half (a filter by stakes) is absent: every Important finding, however low-impact, becomes an edit and an extra commit. The owner's evidence is that 70 percent of findings across six repos were low-impact hardening. Both the SKILL.md stub and this reference carry the rule; the rewrite needs both. Pending the benchmark.
- **Confidence:** Medium.
- **Action:** rewrite, owner confirmation required. Hunk H14.

**F15. Location:** `multi-spec/SKILL.md:70`
- **Evidence:** "point explicitly at `/cla:multi-pr` for the produced change list (or `/cla:spec-to-pr <name>` / `/cla:lite-pr <name>` per-change) as the follow-on".
- **Pattern:** Group 2, conflict with an owner decision (D8: lite is the default; the full spec path is for changes touching a protected area or shipped behaviour; "shape-decision and multi-spec recommend the path per change from the stakes").
- **Why obsolete:** The report makes the full chain the headline next step for every change. Nothing in the plan schema carries a path. Pending decision: D8 is unimplemented and the "which path" mechanism (a `path` field in the plan, or a line in the report) is the owner's call. Proposed wording below recommends in the report only, with no schema change. A related unresolved point: `lite-pr` takes a description, not a change name, so "`/cla:lite-pr <name>`" reads wrongly in the current text too; I did not touch that.
- **Confidence:** Medium.
- **Action:** rewrite, owner confirmation required. Hunk H15.

### Low (report only, not in the diff)

**F16. Location:** `multi-pr/SKILL.md:37`, `references/discover-and-gate.md:137`, `references/change-loop.md:58-64`
- **Evidence:** "'No unresolved Critical or Important issue' is the default policy — stricter than `/cla:spec-to-pr`'s own default"; the Suggestions go to `TODO.md`.
- **Pattern:** Group 2, possible conflict with D5 (filter by stakes) and a safety rule, so `flag`.
- **Why flagged, not fixed:** A standing instruction outside the repo says to fix Critical and Important findings and list Suggestions, which this matches, while D5 narrows "must fix" to findings that block a merge. The two statements disagree, and a stricter default is the safe direction; history cannot say which governs. The owner decides. If D5 wins, the Phase 1 gate's policy question gains a middle option "fix what blocks a merge, list the rest".
- **Confidence:** Low.
- **Action:** flag.

**F17. Location:** `multi-pr/references/discover-and-gate.md:155-160` (§1c), `change-loop.md:11, 121-125` (steps 2, 6, 7)
- **Evidence:** the upfront chain-time estimate: complexity buckets, averages of prior run-notes timings by bucket, a range, per-change point estimates, and an actual-versus-predicted report after every change.
- **Pattern:** Group 1c (arithmetic rubric the model computes), Group 1d (unenforced).
- **Why flagged:** About 600 words of procedure for a number the text itself calls a rough ballpark; the sample is local gitignored run notes on one machine, usually under three records. Whether anyone reads the number is not visible in the repo; a preference for a lean plugin points the same way, but I have no firing count, so this stays a flag.
- **Confidence:** Low.
- **Action:** flag.

**F18. Location:** `cla-setup/scripts/seed_openspec_rules.py:41-66` (RULES)
- **Evidence:** 21 rules, none carrying its origin incident or the protected area it covers.
- **Pattern:** Group 2, conflict with D6 ("each rule carries one line: its origin incident and the protected area it covers").
- **Why flagged:** D6 is order-of-work step 4, not done yet, and tags inside a seeded YAML block land in every repo's config and cost tokens on every authoring run, so where the tags live (the script comment above each rule, or a separate reference) is a design choice for the owner. No edit proposed.
- **Confidence:** Low.
- **Action:** flag.

## Notes that did not become findings

- **authoring-brief.md (light audit):** no rewrite proposed. The "How to write it" section is the benchmark-tested text. Two small cross-file points, both low: the brief allows a behaviour-changing number's default "in a scenario or in design.md" while RULES line 56 says "a default may appear in a scenario" (the RULES line governs requirement text, so they do not clash); the brief says "Write design.md only when a real choice needs recording" while RULES and the post-check say "only when a stock trigger applies, and name the trigger" (the post-check enforces the trigger; the real-choice test is compatible). The 12-line turn-liveness paragraph at the end is a deliberate restatement.
- **The turn-liveness copies:** agree; no change. The restated closing paragraphs in `change-loop.md:129-142` and `candidate-loop.md:86-100` carry an incident story, but D6 asks for origin on rules and keep-list item 10 protects a deliberate recap.
- **Sonnet 5.5 literal-following:** the "Run thin ... read slices, `tail`/`head`" pointer in four SKILL.md files is a cost rule, not tool-use discouragement, and sits in `_shared/runtime-rules.md` (out of scope). Not flagged. (A caution about `tail` on long-running commands belongs in the shared file.)
- **Prefill, thinking, sampling, tool_choice, retired model names, graders and eval vocabulary, anti-formatting rules, instruction re-insertion cadence, visual-input scaffolding, frontend-design lists:** none present.
- **Group 3:** frontmatter descriptions are routing text with plain trigger lists; none is a tool description. 0 findings.
- **Group 4:** no request code. The only model pins are the aliases `opus` and `sonnet` in dispatch instructions; none is a dated model ID.
