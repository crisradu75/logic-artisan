# Proposed diff, part C (never applied)

One finding per hunk set, high and medium confidence only. Paths are under
`C:\Code\logic-artisan\.claude\plugins\cla\skills\`. Line numbers are those read on 2026-11-17 and are approximate where the
hunk context was shortened. Flag-only findings (F16, F17, F18) have no hunk.

None of these edits touches the history-editing check of an API harness (no request code is involved).

Order: sure fixes first (H1 to H6), then wording changes the owner may decline (H7 to H12), then the owner-decision conflicts
(H13 to H15), which must be confirmed against `cla.io/decisions/cla-foundation-2026-11-17.md` before anyone applies them: D5 and D8
are decided but not yet built, and the decision file says nothing in CLA changes until its benchmark exists.

A removal is complete only when everything referencing it goes too. Cross-effects are named under each hunk.

---

## H1 (F1, High) stale "no other skill reads this section"

```diff
--- a/cla-setup/references/facts-file.md
+++ b/cla-setup/references/facts-file.md
@@ -32,2 +32,3 @@
   owner may also edit the numbers in the config; the checker reads whatever sentence is there. A
-  reconcile keeps an existing section as written. No other skill reads this section yet.
+  reconcile keeps an existing section as written. `/cla:multi-spec`'s authoring brief reads the
+  section to decide which risks become requirements.
```

Cross-effects: grep the repo's tests for the removed sentence before applying (a test could pin it).

## H2 (F2, High) a quoted passage that exists nowhere

```diff
--- a/multi-spec/references/plan-schema.md
+++ b/multi-spec/references/plan-schema.md
@@ -3,1 +3,1 @@
-Phase 1 derives the grouping this file records; **Phase 2 writes and commits it once, on the batch branch, before any change is authored** — its own small commit ahead of any proposal work, so the grouping/sequencing judgment itself is protected by the same durability discipline as everything downstream. (It's written in Phase 2 rather than Phase 1 because two of its required fields — `batch_slug` and `branch` — are only derived once the branch is set up in Phase 2, and because a Phase-1 commit would land on `<base-branch>`, which this skill may never push, so a "durability" commit there couldn't actually be pushed to survive a dead disk. See SKILL.md Phase 2's "Persist the plan now, on the branch.")
+Phase 1 derives the grouping this file records; **Phase 2 writes and commits it once, on the batch branch, before any change is authored** — its own small commit ahead of any proposal work, so the grouping/sequencing judgment itself is protected by the same durability discipline as everything downstream. (It's written in Phase 2 rather than Phase 1 because two of its required fields — `batch_slug` and `branch` — are only derived once the branch is set up in Phase 2, and because a Phase-1 commit would land on `<base-branch>`, which this skill may never push, so a "durability" commit there couldn't actually be pushed to survive a dead disk. The recipe is in `references/phases.md`, Phase 2.)
```

## H3 (F3, Medium) a step that has no number

```diff
--- a/multi-spec/references/plan-schema.md
+++ b/multi-spec/references/plan-schema.md
@@ -42,1 +42,1 @@
-**Not a live status ledger.** It does not track which changes are authored/committed/reviewed — that would create a second source of truth that could drift from the actual git-tracked state of `openspec/changes/<name>/`. Resume always re-derives "is this change done" from the repository itself (Phase 3 step 1's tracked-file check), never from a status field in this plan. This mirrors `/cla:spec-to-pr`'s own resume philosophy: `probe_state.py` reads repo state, not a log file, specifically because a log can go stale or get lost in exactly the kind of local-machine incident this skill exists to survive — a plan file that also tried to be a status ledger would be exactly as fragile as the problem it's meant to solve.
+**Not a live status ledger.** It does not track which changes are authored/committed/reviewed — that would create a second source of truth that could drift from the actual git-tracked state of `openspec/changes/<name>/`. Resume always re-derives "is this change done" from the repository itself (the resume check in `references/authoring-brief.md`), never from a status field in this plan. This mirrors `/cla:spec-to-pr`'s own resume philosophy: `probe_state.py` reads repo state, not a log file, specifically because a log can go stale or get lost in exactly the kind of local-machine incident this skill exists to survive — a plan file that also tried to be a status ledger would be exactly as fragile as the problem it's meant to solve.
```

## H4 (F4, Medium) a private memory file named in a shipped reference

```diff
--- a/multi-spec/references/plan-schema.md
+++ b/multi-spec/references/plan-schema.md
@@ -11,1 +11,1 @@
-Colocated with the source decisions file (`cla.io/decisions/<stem>.md`) — same directory, same stem, `.multi-spec-plan.json` suffix instead of `.md`. This keeps the plan discoverable next to the thing it was derived from, and matches this repo's existing convention that `cla.io/decisions/*` is committed, not gitignored — a convention learned the hard way, when an *untracked* decisions doc destroyed in an `rm -rf` worktree-junction incident had to be reconstructed by hand and only then committed (see memory `feedback-worktree-rmrf-junction-risk`).
+Colocated with the source decisions file (`cla.io/decisions/<stem>.md`) — same directory, same stem, `.multi-spec-plan.json` suffix instead of `.md`. This keeps the plan discoverable next to the thing it was derived from, and matches this repo's existing convention that `cla.io/decisions/*` is committed, not gitignored — a convention learned the hard way, when an *untracked* decisions doc destroyed in an `rm -rf` worktree-junction incident had to be reconstructed by hand and only then committed.
```

## H5 (F5, Medium) a `0.x` migration sentence in a skill that runs in repos that never had it

```diff
--- a/cla-setup/SKILL.md
+++ b/cla-setup/SKILL.md
@@ -246,2 +246,1 @@
-again; a repo that wants it standing wires it into its own gate. A gate still wiring the `0.x`
-`conformance-checks/tests` directory checks nothing: say so and recommend this program.
+again; a repo that wants it standing wires it into its own gate.
```

Cross-effects: `DEVELOPER-GUIDE.md:436` carries the same upgrade note, where a `0.x` note belongs; leave it. Grep the tests for the sentence before applying.

## H6 (F6, Medium) migration-relative sentence

```diff
--- a/cla-setup/SKILL.md
+++ b/cla-setup/SKILL.md
@@ -25,1 +25,1 @@
-without a yes, except that it replaces the economy rules file with the plugin's current text and appends the run-notes line to `.gitignore` when that is missing. It replaces the former `cla-init` and `sync-context` skills, which no longer exist.
+without a yes, except that it replaces the economy rules file with the plugin's current text and appends the run-notes line to `.gitignore` when that is missing.
```

## H7 (F7, Medium) "protected" keyed on the repo's Stakes, not on a fixed list

Two hunks in one file; the second keeps the shipped wording on the retired list so the seed script reports it as `-` in repos that
carry it. The repo's own `openspec/config.yaml` and the test that compares `RULES` against it must change in the same edit
(`seed_openspec_rules.py` docstring: "a test checks `RULES` against this repo's own `openspec/config.yaml`"). Also reword the
brief's fallback sentence (authoring-brief.md:10) to read "the areas the seeded `rules:` name" with no list of its own, so there is one list.

```diff
--- a/cla-setup/scripts/seed_openspec_rules.py
+++ b/cla-setup/scripts/seed_openspec_rules.py
@@ -54,1 +54,1 @@
-    - "Money, security, personal data, honesty claims and accessibility are protected: a rewrite compresses their requirements and never drops them. A REMOVED entry paired with an ADDED rewrite of the same outcome is not a drop."
+    - "Protected areas are the ones the Stakes section of cla.io/project-facts.md names; a repo with no Stakes section protects money, security, personal data, honesty claims, accessibility and the user's own files. A rewrite compresses a protected requirement and never drops it. A REMOVED entry paired with an ADDED rewrite of the same outcome is not a drop."
@@ -81,0 +82,1 @@
+    - "Money, security, personal data, honesty claims and accessibility are protected: a rewrite compresses their requirements and never drops them. A REMOVED entry paired with an ADDED rewrite of the same outcome is not a drop."
```

(In the second hunk the added line goes at the end of the `specs:` list inside `RETIRED`, after the line that begins `"Name a configurable value by its config key as configured`.)

## H8 (F8, Medium) prose size caps nothing counts

Same cross-effects as H7 (old wordings to `RETIRED`, repo config and test updated). Ships only if the mnemo benchmark holds (D3, D7).

```diff
--- a/cla-setup/scripts/seed_openspec_rules.py
+++ b/cla-setup/scripts/seed_openspec_rules.py
@@ -43,1 +43,1 @@
-    - Keep it to about 400 words. Point to the specs and design instead of restating them.
+    - Keep it short enough to read in one sitting, and point to the specs and design instead of restating them.
@@ -48,1 +48,1 @@
-    - "Keep it to about 800 words: for each decision, the choice, one line of why, and one line per rejected alternative. No history or transcripts."
+    - "Keep it to what a reviewer needs: for each decision, the choice, one line of why, and one line per rejected alternative. No history or transcripts."
@@ -64,1 +64,1 @@
-    - "Keep each task to about 40 words, stating one behaviour with an acceptance criterion a test or a command can check, and no file path with a line number. An out-of-scope note per task is allowed."
+    - "Keep each task to one behaviour with an acceptance criterion a test or a command can check, and no file path with a line number. An out-of-scope note per task is allowed."
```

Retired-list additions (one line each, in the matching artifact block of `RETIRED`): the three old lines above, verbatim.

## H9 (F9, Medium) numeric ceilings in the project-review agent output

```diff
--- a/project-review/references/review-agents.md
+++ b/project-review/references/review-agents.md
@@ -24,1 +24,1 @@
-> **Finding caps:** At most **3 strengths** and **5 gaps**. Prioritize the most impactful.
+> **Findings:** Report the strengths and gaps that would change a grade or a decision, most impactful first. The orchestrator reads five reports, so leave out what would not move one.
--- a/project-review/references/aggregate-and-log.md
+++ b/project-review/references/aggregate-and-log.md
@@ -69,1 +69,1 @@
-Keep each finding to 1-2 lines. Aim for ~60-80 lines total — comprehensive but scannable.
+Write each finding in a line or two. The report should be scannable in one screen.
```

## H10 (F10, Medium) the `Agent` tool now documents an `effort` parameter

```diff
--- a/multi-spec/SKILL.md
+++ b/multi-spec/SKILL.md
@@ -33,1 +33,1 @@
-- **Per-change authoring dispatches to `Agent(subagent_type: "claude", model: "opus")`, one call per change, awaited sequentially — never parallel.** Sequential is what makes "commit before starting the next" possible; proposal authoring is judgment-critical (same tier as a Review verdict), not mechanical rubric work. Route every other dispatched agent per `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md` (the single source of truth for model/effort). Effort is not independently dialed on the `Agent(...)` mechanism — do not introduce `Workflow` as a workaround.
+- **Per-change authoring dispatches to `Agent(subagent_type: "claude", model: "opus")`, one call per change, awaited sequentially — never parallel.** Sequential is what makes "commit before starting the next" possible; proposal authoring is judgment-critical (same tier as a Review verdict), not mechanical rubric work. Route every other dispatched agent per `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md` (the single source of truth for model/effort). Effort inherits the session unless the owner asks for a level (the `Agent` tool's `effort` parameter); do not introduce `Workflow` as a workaround.
--- a/project-review/SKILL.md
+++ b/project-review/SKILL.md
@@ -42,1 +42,1 @@
-Effort is not dialable on `Agent`-dispatched work (it inherits the session); only the model is set here. On a session already at Opus, routing Agents 2/3/5 down to sonnet is the real economy; on a sub-Opus session, routing Agents 1/4 up to opus protects the highest-leverage judgment. Apply the routing whenever the session model differs from a dimension's target tier.
+Effort inherits the session unless the owner asks for a level (the `Agent` tool's `effort` parameter); the model is always set here. On a session already at Opus, routing Agents 2/3/5 down to sonnet is the real economy; on a sub-Opus session, routing Agents 1/4 up to opus protects the highest-leverage judgment. Apply the routing whenever the session model differs from a dimension's target tier.
```

Cross-effects: `_shared/references/model-routing.md` (out of scope) states the same claim ("inherited"); it should follow, and the plugin-tests that pin it, if any, need a grep first.

## H11 (F11, Medium) verdict rubric that covers every set of grades

Moves a score for ambiguous sets only (grades that matched two rows or none). Before/after on real reports needed before it ships.

```diff
--- a/project-review/SKILL.md
+++ b/project-review/SKILL.md
@@ -48,7 +48,7 @@
-**Compute verdict from dimension grades:**
+**Compute verdict from dimension grades.** Leave N/A dimensions out of every count. Take the first row that matches:
 | Verdict | Criteria |
 |---------|----------|
-| **EXEMPLARY** | All dimensions A or B, none below B |
-| **STRONG** | Majority A/B, at most one C, no D |
-| **SOLID** | Majority B/C, no more than one D |
-| **NEEDS WORK** | Two or more D grades, or majority C/D |
+| **NEEDS WORK** | Two or more D grades, or more than half of the graded dimensions C or D |
+| **EXEMPLARY** | Every graded dimension A or B |
+| **STRONG** | No D, at most one C |
+| **SOLID** | Any other set of grades |
--- a/project-review/references/review-criteria.md
+++ b/project-review/references/review-criteria.md
@@ -119,8 +119,8 @@
-Derived from dimension grades:
+Derived from dimension grades. Leave N/A dimensions out of every count. Take the first row that matches:
 
 | Verdict | Criteria |
 |---------|----------|
-| **EXEMPLARY** | All dimensions A or B, no dimension below B |
-| **STRONG** | Majority A/B, at most one C, no D |
-| **SOLID** | Majority B/C, no more than one D |
-| **NEEDS WORK** | Two or more D grades, or majority C/D |
+| **NEEDS WORK** | Two or more D grades, or more than half of the graded dimensions C or D |
+| **EXEMPLARY** | Every graded dimension A or B |
+| **STRONG** | No D, at most one C |
+| **SOLID** | Any other set of grades |
```

Cross-effects: `aggregate-and-log.md:32` says the rubric is "kept inline" in SKILL.md; unchanged. Grep plugin-tests for a test that pins the table text.

## H12 (F12, Medium) N/A rule moved to where every agent reads it

```diff
--- a/project-review/references/review-agents.md
+++ b/project-review/references/review-agents.md
@@ -22,2 +22,3 @@
 > **Attribution:** Where the repo has several apps or packages, every finding MUST name the app/package it applies to (e.g. one worked example per app/package this repo has), and its evidence MUST cite a specific path + line or grep result. A dimension whose quality differs sharply across components should say so in its summary rather than averaging it into one bland grade.
 >
+> **Not applicable:** A criterion whose subject does not exist in this repo (no engine, gateway, i18n layer, datastore or tenant model) is reported N/A with one line of why, never graded down for absence.
 > **Finding caps:** At most **3 strengths** and **5 gaps**. Prioritize the most impactful.
```

(If H9 is also taken, the last context line is the `Findings:` line instead; the two hunks touch neighbouring lines, so apply H9 first, then insert the `Not applicable` line before it.)

---

## Owner-decision conflicts: confirm the direction before applying

These three rewrite text that is the older of the two sides (skill text from 2026-08 to 2026-10, decision file 2026-11-17), so the
direction is an assumption. All three touch a verification or review rule, so they are proposed, not applied on a blanket request.

## H13 (F13, Medium) the break-it check only where the stakes call for it (D5)

Change `lite-pr/references/mutation-gate.md` (out of scope) the same way, or the two skills disagree.

```diff
--- a/multi-lite/references/candidate-loop.md
+++ b/multi-lite/references/candidate-loop.md
@@ -54,1 +54,1 @@
-     **Show each fix works, to the same standard `/cla:lite-pr` holds its own fixes to** (its Review step 2b, whose rule is `${CLAUDE_PLUGIN_ROOT}/skills/lite-pr/references/mutation-gate.md`). Break what the fix touches by hand so the defect is back, run the affected test, and confirm it FAILS. Then restore the edit exactly by that step's unattended route. A fix whose break no test catches is not shown to work. **A test that does fail is not thereby correct: read the assertion that killed the mutant and confirm it states the behaviour the finding asked for.** A test written from a wrong mental model kills mutants as reliably as a right one. Full rule: `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/test-quality-gates.md`, "How planting goes wrong". An assertion that defends the wrong behaviour counts as a fix not shown to work.
+     **When the fix touches an area the Stakes section of `cla.io/project-facts.md` protects, or a guard hook, show it works to the same standard `/cla:lite-pr` holds its own fixes to** (its Review step 2b, whose rule is `${CLAUDE_PLUGIN_ROOT}/skills/lite-pr/references/mutation-gate.md`). Break what the fix touches by hand so the defect is back, run the affected test, and confirm it FAILS. Then restore the edit exactly by that step's unattended route. A fix whose break no test catches is not shown to work. **A test that does fail is not thereby correct: read the assertion that killed the mutant and confirm it states the behaviour the finding asked for.** A test written from a wrong mental model kills mutants as reliably as a right one. Full rule: `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/test-quality-gates.md`, "How planting goes wrong". An assertion that defends the wrong behaviour counts as a fix not shown to work. Any other fix needs only the narrow gate and the changed-file tests above.
@@ -58,1 +58,1 @@
-     - **A fix whose break no test caught** → write `review: unresolved` with the reason `enforcement fix unverified`, and take the unresolved branch below.
+     - **A protected-area or guard-hook fix whose break no test caught** → write `review: unresolved` with the reason `enforcement fix unverified`, and take the unresolved branch below.
```

(Line 57, "every finding's fix passed the break-it check and the three commit checks above", reads "every protected-area fix passed the break-it check, and every fix passed the narrow gate and the three commit checks above" under the same change.)

## H14 (F14, Medium) apply what blocks the merge, list the rest (D5)

```diff
--- a/multi-spec/references/review-gate.md
+++ b/multi-spec/references/review-gate.md
@@ -61,1 +61,1 @@
-2. Apply every Critical/Important finding as a direct `Edit`/`Write` fix to the relevant change's artifacts (routed by its `[<change-name>]` prefix from Step 5).
+2. Apply every finding that blocks the merge as a direct `Edit`/`Write` fix to the relevant change's artifacts (routed by its `[<change-name>]` prefix from Step 5): a Critical finding, an Important one that touches an area the Stakes section of `cla.io/project-facts.md` protects, and any finding that makes `openspec validate --strict` or check B1 fail. List every other finding in the batch report and the PR body for the owner; they are noted, not applied (Step 6's "apply it or explicitly note it's out of scope" is met by that listing).
--- a/multi-spec/SKILL.md
+++ b/multi-spec/SKILL.md
@@ -62,1 +62,1 @@
-Once every change is authored, validated, and committed, run **one** review over the **whole batch**. The checklist's size gate grades each change, and the batch's summed claim count (`e`) is graded too: if any change is large, or the batch makes 25 or more claims in total, dispatch the three agents once over the batch (same model routing as `review-change`'s checklist: Design Reviewer → opus, Task/Spec-and-Codebase → sonnet); otherwise, review inline. **A batch of exactly one change** goes straight to the single-change `review-change` checklist instead — there's no cross-change staleness class to catch. Apply every Critical/Important finding, re-validate, and commit the fixes as one follow-up commit **before Phase 5 opens the PR** — this ordering (review-then-PR) is load-bearing, never the reverse. Full dispatch mechanics, agent prompts, and the fix-application/commit recipe: `references/review-gate.md`.
+Once every change is authored, validated, and committed, run **one** review over the **whole batch**. The checklist's size gate grades each change, and the batch's summed claim count (`e`) is graded too: if any change is large, or the batch makes 25 or more claims in total, dispatch the three agents once over the batch (same model routing as `review-change`'s checklist: Design Reviewer → opus, Task/Spec-and-Codebase → sonnet); otherwise, review inline. **A batch of exactly one change** goes straight to the single-change `review-change` checklist instead — there's no cross-change staleness class to catch. Apply every finding that blocks the merge (Step 7 of `references/review-gate.md` says which), re-validate, and commit the fixes as one follow-up commit **before Phase 5 opens the PR** — this ordering (review-then-PR) is load-bearing, never the reverse. Full dispatch mechanics, agent prompts, and the fix-application/commit recipe: `references/review-gate.md`.
```

## H15 (F15, Medium) name a path per change instead of one headline next step (D8)

Recommends in the report only, with no plan-schema change; whether the path becomes a plan field is the owner's call.

```diff
--- a/multi-spec/SKILL.md
+++ b/multi-spec/SKILL.md
@@ -70,1 +70,1 @@
-Emit a terminal report: batch slug, decisions file, PR URL, the change list (name + one-line scope + dependency order), the review verdict per change, each change's open questions and any budget problem (so the owner sees them before merging), and — the load-bearing next step — **point explicitly at `/cla:multi-pr` for the produced change list** (or `/cla:spec-to-pr <name>` / `/cla:lite-pr <name>` per-change) as the follow-on that actually implements them. `multi-spec` stopping here is deliberate, not a truncated run.
+Emit a terminal report: batch slug, decisions file, PR URL, the change list (name + one-line scope + dependency order), the review verdict per change, each change's open questions and any budget problem (so the owner sees them before merging), and — the load-bearing next step — **name the follow-on path for each change**: `/cla:lite-pr` by default, and `/cla:spec-to-pr <name>` (or `/cla:multi-pr` for the whole produced sequence) for a change that touches an area the Stakes section of `cla.io/project-facts.md` protects or behaviour shipped to other repos; the owner can override. `multi-spec` stopping here is deliberate, not a truncated run.
```
