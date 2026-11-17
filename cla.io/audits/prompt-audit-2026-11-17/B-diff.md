# Prompt audit part B: proposed diff (never applied)

Scope: `spec-to-pr/` (SKILL.md and references), `lite-pr/`, `review-change/`. One finding per hunk,
high and medium confidence only. Paths are relative to `C:\Code\logic-artisan\.claude\plugins\cla\skills\`.
Line numbers are the current ones. Long lines use git word-diff markers, `[-old-]{+new+}`, so each
hunk shows only the words that change; everything outside the markers stays as is. Hunk headers are
illustrative, not apply-ready.

Edits that must land in the same change as a hunk (CLAUDE.md check 5) are listed under it as
"Same-edit sites". They are outside the audited scope, so no hunk is proposed for them.

Not proposed as hunks: the low-confidence items in B-report.md and everything under its Open questions.

---

## F1. Add the merge-blocking filter before triage (decision 5)

Reviewers keep reporting everything. A filter keeps only findings that block a merge, using the
repo's Stakes as its rubric. Non-blocking findings go to TODO.md.

```diff
--- a/spec-to-pr/references/revise.md
+++ b/spec-to-pr/references/revise.md
@@ -119,8 +119,16 @@
    **SEV-MAX:** the same underlying finding rated differently by two agents is triaged at the **higher** severity, always. A `Workflow` merge does this when both key it to the same `(file, line)`; apply it by hand when they describe one issue at different lines or with none.

-2. **Triage every Critical and Important finding into one of three buckets:**
+1b. **Filter: which findings block a merge?** Reviewers report everything; only a blocking finding enters triage. Dispatch one `Agent(model: sonnet)` with the Stakes section of `cla.io/project-facts.md` as its rubric and the merged findings, each with its quoted evidence. It labels every finding `blocks` or `non-blocking`, with one line of why. A finding blocks a merge when it could lose, corrupt or leak what a protected area covers, breaks something shipped to other repos, is wrong behaviour a user would see, or makes a requirement false or unprovable. A reviewer's Critical or Important label is an input, not the answer. With no Stakes section, protect money, security, personal data, honesty claims, accessibility and the user's own files. Every `non-blocking` finding leaves triage and goes to Handoff's TODO.md section as a Suggestion; none is fixed in this PR. A finding that names a protected area is never labelled `non-blocking`; the orchestrator re-reads each `non-blocking` row that mentions one.
+
+2. **Triage every blocking finding into one of three buckets:**
    - **Applied** — the fix lands this round via Edit/Write. *Closed.*
@@ -126,1 +134,1 @@
-   A finding never exits "unaddressed". Suggestions flow to the optional `docs: TODO.md` commit.
+   A blocking finding never exits "unaddressed". Suggestions and non-blocking findings flow to the `docs: TODO.md` commit.
```

```diff
@@ -222,4 +230,4 @@
    **Exit gate — TWO counts, and both must be zero to exit clean.**
-   - **Untriaged** — Critical/Important findings in no bucket.
+   - **Untriaged** — blocking findings in no bucket.
```

```diff
--- a/spec-to-pr/SKILL.md
+++ b/spec-to-pr/SKILL.md
@@ -193,1 +193,1 @@  (word-diff; the rest of the line is unchanged)
... every [-Critical and Important-]{+blocking finding (after the Stakes filter in `revise.md` 1b)+} is triaged, and counts as Applied only when the defect is shown gone; ...
@@ -130,1 +130,1 @@
... Apply every [-Critical and Important-]{+blocking Critical and Important (checklist Step 5: the rest go to TODO.md)+} to `openspec/changes/<name>/` and re-check each landed. ...
```

```diff
--- a/spec-to-pr/references/handoff.md
+++ b/spec-to-pr/references/handoff.md
@@ -52,1 +52,1 @@
-**Suggestions** (low-priority PR-review residue):
+**Suggestions** (low-priority PR-review residue, plus every finding the Stakes filter judged non-blocking):
```

Same-edit sites: `_shared/references/run-log-schema.md` (what `findings_by_round.found` counts: blocking
findings only; say so), `spec-to-pr-retro/SKILL.md` (round yield is now over blocking findings).

Requirement-level risk (protected area): the filter must never drop a finding that concerns a
protected area. The last two sentences of 1b carry that; keep them in any rewrite.

---

## F2. Round 2 runs only after a fix that touched a protected area (decision 5)

```diff
--- a/spec-to-pr/SKILL.md
+++ b/spec-to-pr/SKILL.md
@@ -55,1 +55,1 @@  (word-diff)
| `--pr-rounds N` | Revise — the **code** on the open PR, after Ship. Default 2; round 2 runs only after round 1 [-fixed a Critical, or an Important on a high-risk PR (a docs-currency fix counts as neither)-]{+applied a fix that touches a protected area (the Stakes list)+}; `1` opts out; `0` skips Revise. A re-entry for still-open findings also runs. |
@@ -193,1 +193,1 @@  (word-diff, same line as F1)
Cap: `--pr-rounds N` (default `2`): round 2 runs only after round 1 [-fixed a Critical, or an Important on a high-risk PR, scoped to that fix diff; a docs-currency fix counts toward neither (`references/revise.md` "Docs currency")-]{+applied a fix touching a protected area, scoped to that fix diff+}. ...
```

```diff
--- a/spec-to-pr/references/revise.md
+++ b/spec-to-pr/references/revise.md
@@ -5,1 +5,1 @@
-Cap: `--pr-rounds N` (default `2`). Round 2 runs only after round 1 fixed a Critical finding, or an Important one on a high-risk pull request (high at round 1's final level), and the cap allows it. A docs-currency fix (see "Docs currency" below) does not count toward either trigger. It is scoped to that fix diff (or a re-entry for still-open findings). `--pr-rounds 1` opts out, `0` skips Revise.
+Cap: `--pr-rounds N` (default `2`). Round 2 runs only after round 1 applied a fix that touches a protected area (the Stakes section of `cla.io/project-facts.md`; with none, the seeded protected areas), and the cap allows it. It is scoped to that fix diff (or a re-entry for still-open findings). `--pr-rounds 1` opts out, `0` skips Revise.
@@ -81,1 +81,1 @@  (word-diff; delete the trailing carve-out)
... Fixing one is a **docs-currency fix** [-(the fix of a stale-doc finding that this check reported; no other doc edit is one), and it does not count toward round 2's triggers: a round whose only fixes are docs-currency fixes does not trigger round 2, while a round with other fixes is judged by the normal rule on those other fixes alone, as if the doc edits were not there. Only a Critical or Important fix can trigger round 2, so a Suggestion-level fix does not count as one of those other fixes.-]{+. A doc edit triggers round 2 only when the doc is itself a protected area, as any other fix would.+} List it in Handoff's Issues section. ...
@@ -93,1 +93,1 @@
-On a resume, if you cannot tell whether the previous round fixed a Critical, or an Important one on a high-risk pull request (a docs-currency fix counts as neither), run the next round. Failing safe costs one round.
+On a resume, if you cannot tell whether the previous round's fixes touched a protected area, run the next round. Failing safe costs one round.
@@ -226,1 +226,1 @@  (word-diff on the "Both 0" paragraph)
**Both 0** → status `ok` and exit the loop, **unless this round applied a fix touching a protected area, and the cap allows another round** — then run it, scoped to that fix diff. On a resume, if you cannot tell, run the next round if the cap allows: failing safe costs one round. [-On a low-risk pull request, a round whose fixes were all Important or lower does not trigger another.-] When any round committed fixes and no later round reviewed them, Revise still ends `ok`, and the Handoff report says in one line that those fixes were not reviewed again.
```

```diff
--- a/lite-pr/SKILL.md
+++ b/lite-pr/SKILL.md
@@ -172,1 +172,1 @@  (word-diff)
4. **A second pass only for a fix that touches a protected area.** When step 1 applied a fix touching a protected area (the Stakes list in `cla.io/project-facts.md`; with none, the seeded protected areas), dispatch the same sizing-table reviewers once more, ... [-High risk here is the level the Review used: the `Risk:` line said high, you raised it, or the line was missing, unreadable or named an unknown level.-] Run steps 1–3 on what they find, then stop: there is no third pass. Otherwise do NOT re-dispatch the review agents ...
```

Same-edit sites (blast radius, outside the audited scope): `_shared/references/model-routing.md:99-104`
(the "second review pass" paragraph and its docs-currency clause), `_shared/references/run-log-schema.md:59`,
`workflow-diagram.md:70`, `lib/log_run.py` (the round `trigger` enumeration: `critical` and
`high-important` become one value such as `protected`; the retro refuses an unknown value),
`spec-to-pr-retro/SKILL.md:26,31-34` and `spec_to_pr_aggregate.py` (the `by_trigger` arms),
`spec-to-pr/references/design-tradeoffs.md:75` (the 2026-10-13 history now describes a retired rule),
`spec-to-pr/references/handoff.md` (`trigger` mentions). A grep for `high-important` lists the six files.

---

## F3. The by-hand mutation check runs for protected-area fixes and guard hooks only (decision 5)

```diff
--- a/spec-to-pr/references/revise.md
+++ b/spec-to-pr/references/revise.md
@@ -173,4 +173,6 @@
-2b. **Mutation gate (by hand, not an automated mutation batch; required before the commit in step 3).** A fix for a Critical/Important
-   finding earns the same evidence the original code needed — "the reviewer's finding is now
-   handled" is not that evidence. Break **what the fix touches**, not only what it targets:
+2b. **Mutation gate (by hand, not an automated mutation batch; required before the commit in step 3, only for a fix that touches a protected area or a guard hook).** Any other fix ships with a test that fails without it and no hand-mutation. A fix in the
+   gated set earns the same evidence the original code needed — "the reviewer's finding is now
+   handled" is not that evidence. Break **what the fix touches**, not only what it targets:
```

```diff
--- a/lite-pr/SKILL.md
+++ b/lite-pr/SKILL.md
@@ -168,3 +168,3 @@
-2b. **Mutation gate (by hand, not an automated mutation batch; required before the commit in step 3).** When step 1 applied any Critical/Important fix,
-   read `${CLAUDE_PLUGIN_ROOT}/skills/lite-pr/references/mutation-gate.md` before staging and follow it in full; the fix
-   commit does not ship without it.
+2b. **Mutation gate (by hand, not an automated mutation batch; required before the commit in step 3).** When step 1 applied a fix that touches a protected area (the Stakes list) or a guard hook,
+   read `${CLAUDE_PLUGIN_ROOT}/skills/lite-pr/references/mutation-gate.md` before staging and follow it in full; that
+   fix commit does not ship without it. Other fixes need only a test that fails without them.
```

```diff
--- a/lite-pr/references/mutation-gate.md
+++ b/lite-pr/references/mutation-gate.md
@@ -3,2 +3,2 @@
-2b. **Mutation gate (by hand, not an automated mutation batch; required before the commit in step 3).** A fix for a Critical/Important
-   finding is a change like any other and earns the same evidence the original code needed —
+2b. **Mutation gate (by hand, not an automated mutation batch; required before the commit in step 3 for a protected-area or guard-hook fix).** A fix in that set
+   is a change like any other and earns the same evidence the original code needed —
@@ -7,3 +7,2 @@
-   touches**, not only what it targets: correcting one return path routinely breaks another, which
-   is how a real fix in the CLA source repo once traded a silent no-op on the default path for the identical no-op on
-   the overlay path. Do each one by hand: ...
+   touches**, not only what it targets: correcting one return path routinely breaks another. Do each one by hand: ...
@@ -26,3 +25,2 @@
-   run is evidence about the mutants you thought of and nothing else — two commits in the CLA source repo each
-   recorded "three mutations checked, all caught" and each shipped a critical a later review found.
+   run is evidence about the mutants you thought of and nothing else.
```

(The two deleted stories are in `docs/evidence.md`, "Check 4" and "A clean mutation run".)

Same-edit sites: root `CLAUDE.md` check 4 and its table row ("break each fix by hand once") and
`_shared/references/test-quality-gates.md:138`. Both say the by-hand check applies to every review fix.
Decision 5 narrows it; the owner decides whether CLAUDE.md follows.

Requirement-level risk (protected area): in this repo guard hooks and anything shipped to other repos
are protected, so the gate still runs for most fixes here. The hunk narrows it for repos whose Stakes
are lighter. A fix in a guard hook always keeps the gate.

---

## F4. Review verdict counts blocking findings; non-blocking ones get a section (decision 5)

The rule at checklist.md:229 ("A `[Critical]` or `[Important]` never prints under `### Suggestions`")
would block any non-blocking filter. A separate section keeps the rule intact.

```diff
--- a/review-change/references/checklist.md
+++ b/review-change/references/checklist.md
@@ -204,1 +204,1 @@
-- **READY** — 0 Critical, 0 Important, **and every Step 2b inherited obligation `HONOURED`.** A non-`HONOURED` entry is a Critical, so it is already excluded by the count — ...
+- **READY** — 0 blocking Critical or Important findings (see "Blocking and non-blocking" below), **and every Step 2b inherited obligation `HONOURED`.** A non-`HONOURED` entry is a Critical, so it is already excluded by the count — ...
@@ -229,0 +229,0 @@
 ### Report constraints
@@ +227,6 @@  (new subsection, placed before "Report constraints")
+### Blocking and non-blocking
+
+The reviewer reports everything; the verdict counts only findings that block a merge. A finding blocks when it could lose, corrupt or leak what a protected area covers (the Stakes section of `cla.io/project-facts.md`; with none, money, security, personal data, honesty claims, accessibility and the user's own files), breaks something shipped to other repos, makes a requirement false or unprovable, or fails `openspec validate --strict`. Any other finding is non-blocking: print it under `### Non-blocking (to TODO.md)` with its original label, and it does not move the verdict. A non-blocking finding naming a protected area is a mistake in the filter; re-read those. Inherited obligations and Step 2b are always blocking.
```

And the constraint at line 229, one clause added:
```diff
-- **A `[Critical]` or `[Important]` never prints under `### Suggestions`.**
+- **A `[Critical]` or `[Important]` never prints under `### Suggestions`.** A non-blocking one prints under `### Non-blocking (to TODO.md)` instead.
```

---

## F5. Size check reads the whole-change budget script (decision 3)

The repo's `openspec/config.yaml` rule (lines 17-18) already sets 25 requirements and 6,000 words for a
whole change, and `check_spec_proof.py` enforces it. The checklist still grades per-artifact word counts
as Important findings.

```diff
--- a/review-change/references/checklist.md
+++ b/review-change/references/checklist.md
@@ -62,1 +62,1 @@  (word-diff)
... Each one that fires is an **Important** finding, except the dropped-scenario case under Spec validity, the dropped protected rule under Rewrite, [-and-]{+the Size case below (a budget breach is Important; the rest is a Suggestion),+} and the marker case under Requirement proof (not Marker honesty, which is Important). ...
@@ -66,1 +66,1 @@
-- **Size.** A proposal over about 400 words; a design.md over about 800; a task over about 40 words, or one that states more than one behaviour or no acceptance criterion a test or a command can check; any artifact that restates the proposal or the specs instead of pointing to them. The remedy is the cut.
+- **Size.** Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/check_spec_proof.py` and read its budget lines for this change (the script measures the whole change against the budget its Stakes set; it flags every new requirement `uncovered` before implementation, so ignore that and its exit code). A budget breach is **Important**; the remedy is the cut, never a split into more capabilities. A proposal over about 400 words, a design.md over about 800, a task over about 40 words or one that states more than one behaviour or no checkable acceptance criterion, or an artifact that restates the proposal or the specs, is a **Suggestion** unless the budget is also breached.
```

(The phrase about `uncovered` copies `multi-spec/references/authoring-brief.md:75`; the two must agree.)

---

## F6. A skipped phase does not block the merge line

`workflow-diagram.md:111` makes "no work to do" a `✗`; `handoff.md:64` and `SKILL.md:203` print "NOT ready
to merge" on any `✗`. A docs-only change skips Test (`SKILL.md:157`), so it gets "NOT ready".

```diff
--- a/spec-to-pr/references/workflow-diagram.md
+++ b/spec-to-pr/references/workflow-diagram.md
@@ -111,1 +111,1 @@
-| ✗ skipped | no work to do | e.g. doc-only change has no tests |
+| – skipped | no work to do; does not hold back the merge line | e.g. doc-only change has no tests |
@@ -112,1 +112,1 @@
-| ✗ aborted | orchestration failure (rare; halt) | only user-decline at gate or bootstrap |
+| ✗ aborted | orchestration failure (rare; halt); holds back the merge line | only user-decline at gate or bootstrap |
```
Also change the Test box at line 51 (`✗ skipped (no source-affecting paths)`) to `– skipped (...)`.

```diff
--- a/spec-to-pr/references/handoff.md
+++ b/spec-to-pr/references/handoff.md
@@ -62,1 +62,1 @@  (word-diff)
-- **All ✓:** print ...
+- **All ✓ (a `–` skipped phase counts as ✓):** print ...
```

Medium confidence: no file states which was intended, so confirm with the owner whether a skip was meant to hold the merge line back.

---

## F7. lite-pr sends non-blocking findings to TODO.md (decision 5)

```diff
--- a/lite-pr/SKILL.md
+++ b/lite-pr/SKILL.md
@@ -166,1 +166,1 @@
-1. Triage every Critical/Important finding: apply a fix via `Edit`/`Write`, or record a one-line deferred rationale if it's genuinely out of scope.
+1. Filter, then triage. The reviewers report everything; keep only findings that block a merge (could lose, corrupt or leak what a protected area in `cla.io/project-facts.md` "Stakes" covers, break something shipped to other repos, wrong behaviour a user would see, or a requirement that is false or unprovable). Judge each against that list yourself: lite-pr has one review pass and no filter agent. Apply a fix via `Edit`/`Write` for each blocking finding, or record a one-line deferred rationale if it's genuinely out of scope.
@@ -179,1 +179,1 @@
-Suggestion-level findings: mention them in the final report; no fix applied automatically.
+Suggestion-level and non-blocking findings: append them to the repo-root `TODO.md` (create it if absent) in the fix commit, and list the count in the final report; no fix applied automatically.
```

Same-edit sites: lite-pr's "What this skill deliberately does not do" has no TODO.md line, so nothing to
delete there. The `commit-push-pr` handoff in Ship is unaffected (TODO.md is written in Review).

---

## F8. lite-pr is the default path; spec-to-pr is for protected-area changes (decision 8)

```diff
--- a/lite-pr/SKILL.md
+++ b/lite-pr/SKILL.md
@@ -12,1 +12,1 @@
-Sibling to `/cla:spec-to-pr` for changes that don't need OpenSpec's artifacts or its multi-round PR-review loop. There is no formal routing rule between the two and no mid-flight escalation path — if a change turns out bigger than expected once you're inside Implement, stop and reassess manually (re-plan, split the change, or switch to `/cla:spec-to-pr`) rather than expecting an automatic handoff.
+Sibling to `/cla:spec-to-pr` and the default path: plan, build, one review. Use `/cla:spec-to-pr` instead when the change touches a protected area (the Stakes section of `cla.io/project-facts.md`) or behaviour that ships to other repos. There is no mid-flight escalation path — if a change turns out bigger than expected once you're inside Implement, stop and reassess manually (re-plan, split the change, or switch to `/cla:spec-to-pr`) rather than expecting an automatic handoff.
@@ -187,1 +187,1 @@
-Which workflow to use, lite-pr or `/cla:spec-to-pr`, is your judgment call at invocation time. The intro says there is no size rule for choosing the workflow and no automatic escalation. The rename/docs-only tier in Test sizes the checking inside lite-pr. It does not choose the workflow. The actionable corollary: reassess mid-run if a change outgrows "lite". Stop, then re-plan or switch to `/cla:spec-to-pr` rather than forcing it through here.
+Which workflow to use follows the stakes (see the intro); `shape-decision` and `multi-spec` recommend one per change and the owner can override. The rename/docs-only tier in Test sizes the checking inside lite-pr. It does not choose the workflow. Reassess mid-run if a change outgrows "lite": stop, then re-plan or switch to `/cla:spec-to-pr` rather than forcing it through here.
```

Same-edit site: `shape-decision/SKILL.md` and `multi-spec` must actually make the recommendation. Check that
before landing; the line above promises it.

---

## F9. Reviewer prompts must not ask for edge-case requirements outside a protected area (decision 4)

```diff
--- a/review-change/references/dispatch.md
+++ b/review-change/references/dispatch.md
@@ -40,1 +40,1 @@
-> 2. Feasibility, completeness (missing edge cases — <inject: this repo's own domain-specific edge-case examples per affected area>), unstated risks, scope, architecture fit (<inject: ...>).
+> 2. Feasibility, completeness, unstated risks, scope, architecture fit (<inject: ...>). A missing edge case or risk that touches a protected area (<inject: the protected areas from the Stakes section of `cla.io/project-facts.md`, or `(none recorded)`>) needs a requirement: report it as Important, with the inputs from <inject: this repo's own domain-specific edge-case examples per affected area>. Any other missing edge case is a Suggestion saying it belongs in one line under `## Risks noted` in proposal.md, never a new requirement.
@@ -81,1 +81,1 @@
-> 4. **Missing tasks** — <inject: this repo's own list of commonly-forgotten companion tasks per affected area (dataset/array updates, prop threading, regenerated types, policy tests, doc updates)>.
+> 4. **Missing tasks** — tasks the existing requirements need to be implemented and proven: <inject: this repo's own list of commonly-forgotten companion tasks per affected area (dataset/array updates, prop threading, regenerated types, policy tests, doc updates)>. A task that serves no requirement is not missing.
```

---

## F10. lite-pr Test: drop the incident story from the source-affecting rule

```diff
--- a/lite-pr/SKILL.md
+++ b/lite-pr/SKILL.md
@@ -102,1 +102,1 @@  (word-diff)
... **The list is illustrative, not exhaustive: when a suffix is not on it, treat the path as source-affecting.** [-`.py` is called out because it was once missing, and in a Python repo a real source change then did not register as source-affecting at all — the run reported a clean docs-only skip having gated nothing. A closed list reproduces that defect for every language it omits.-]{+A closed list would report a clean docs-only skip, and gate nothing, in any language it omits.+}
```

The origin stays in `spec-to-pr/references/design-tradeoffs.md:41`. Medium: the rule survives; only the
archaeology goes.

---

## F11. review-change checklist: drop two incident narratives

```diff
--- a/review-change/references/checklist.md
+++ b/review-change/references/checklist.md
@@ -158,1 +158,1 @@  (word-diff)
**Complexity-concentration override (a change can be conceptually large while geographically narrow).** File count under-weights a change whose whole weight lands in one already-large file — `a` reads "small" while the change is anything but. Treat as **Large** (dispatch the 3 agents) even when `a ≤ 5`, when the change is concentrated in one or two files AND carries `b ≥ 15` subtasks. [-Evidence this is real, not hypothetical: a `seed.ts`-concentrated change gated Small on `a=4`, got the in-context review, and its post-implementation Revise round then surfaced **more** real Important findings (8, zero phantoms) than either genuinely-Large change in the same chain (4 each) — the in-context pass under-covered exactly because the file-count gate said "small."-] When the override fires, announce it: ...
@@ -206,1 +206,1 @@  (word-diff)
... **Do not shortcut this to "any Critical → RETHINK"** [-— that literal reading contradicted this same rubric's own principle in an earlier version and corrupted the `verdict` field's meaning in `/cla:spec-to-pr-retro`'s telemetry (multiple real runs had Criticals that were single-edit fixes, correctly resolved in one Review round, yet got mislabeled RETHINK). Judge by the fix's nature, always.-]{+: judge by the fix's nature, always; the retro reads the verdict.+}
```

The `seed.ts` file name is one consumer repo's file in shipped prose (CLAUDE.md, "Keep facts out of the
shipped plugin"). The evidence stays in `cla.io/lessons-learned/` (see the SKILL's own pointer) or
`docs/evidence.md`.

---

## F12. concurrent-runs.md: state the rule as the only rule

```diff
--- a/spec-to-pr/references/concurrent-runs.md
+++ b/spec-to-pr/references/concurrent-runs.md
@@ -5,1 +5,1 @@
-A single `/cla:spec-to-pr` run needs no special setup — it creates `<branch>` in place and nothing arbitrates two sessions in one clone — the hook that used to is gone, so the discipline below is the whole protection.
+A single `/cla:spec-to-pr` run needs no special setup: it creates `<branch>` in place. Nothing arbitrates two sessions in one clone, so the discipline below is the whole protection.
```
