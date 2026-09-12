---
name: lite-pr
description: "Lightweight end-to-end workflow for small changes that skip full OpenSpec: optional requirements exploration, a plan posted for visibility (not a blocking gate), direct implementation updating code plus spec.md/CLAUDE.md/tests in place, one automated test pass, commit-push-pr, and one PR-review pass with a single fix round. No OpenSpec artifacts, no multi-round review loop — runs straight through; the sole stop point is an unresolved Test-phase failure. No formal size rule vs /cla:spec-to-pr; which to use is your call. Triggers on /cla:lite-pr or natural language like 'quick PR for X', 'lite-pr this', 'small change, just ship it'."
argument-hint: "[description | (empty)]"
---

# lite-pr — lightweight plan-to-PR workflow

Sibling to `/cla:spec-to-pr` for changes that don't need OpenSpec's artifacts or its multi-round PR-review loop. There is no formal routing rule between the two and no mid-flight escalation path — if a change turns out bigger than expected once you're inside Implement, stop and reassess manually (re-plan, split the change, or switch to `/cla:spec-to-pr`) rather than expecting an automatic handoff.

## Mode detection

Parse `$ARGUMENTS`:

- **Empty, with a clear ask already in the conversation** (e.g. just finished a `shape-decision` pass, or the user's last message states a concrete change) → infer the description from context. Announce: `Mode: inferred-from-conversation`.
- **Empty, with no usable context** → ask the user once for a one-line description before continuing.
- **Non-empty** → treat as the free-form description. Announce: `Mode: description`.

## Workflow phases

Order: Explore (optional) → Plan → Implement → Test → Ship → Review.

### Explore (optional)

Skip when the description is already concrete and unambiguous (a clear single change, known files/behavior). When the ask is genuinely open-ended (multiple viable approaches, unclear scope) or the user explicitly asks to explore first, invoke the `shape-decision` skill (`Skill(shape-decision)`, or `/cla:shape-decision`) with `<description>` as the topic — the same interactive Q&A the rest of the repo uses. Use judgment — don't force it on a change that's already obvious.

### Plan

Produce a plan directly in the conversation as plain text — do NOT call `EnterPlanMode`/`ExitPlanMode`. `ExitPlanMode` is itself a user-approval gate, and lite-pr is continuous by design (see Autonomy below): post the plan for visibility, then proceed — don't hold it open for approval. The plan MUST explicitly list, alongside the code files to change:

- which `openspec/specs/<capability>/spec.md` file(s) need updating (or note "new capability — no existing spec" / "behavior-invisible change — no spec update needed"). See `cla.io/overlays/lite-pr.md` for this repo's own architecture-as-a-capability spec path — a structural change (new data-flow layer, new module boundary) belongs there, not in a separate architecture doc.
- if the change touches this repo's own core calculation-engine formulas, whether every doc/spec this repo names as needing to stay in lockstep with those formulas needs updating too — see `cla.io/project-facts.md` ("Allocation-formula lockstep doc set") for the exact file set (run `/cla:sync-context` to populate it; falls back to `cla.io/overlays/lite-pr.md` if absent); a formula/knob change shipped without all of them is a silent spec violation, not just stale docs.
- which test file(s) need adding/updating, and under which workspace package/app they live — see `cla.io/overlays/lite-pr.md` for this repo's own worked examples.

No plan is written to disk. The plan lives in the conversation; its durable record is the doc updates it produces during Implement. Unlike `/cla:spec-to-pr`, nothing is created here that later needs archiving or deleting.

Go straight to Implement once the plan is posted — no pause, no "shall I proceed?" question, no wait for a reply.

### Implement

Tests written in this phase follow `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/test-quality.md` — the rules that decide whether a test can fail at all. Its head says which parts apply to any test and which apply only to a gate.

Direct `Edit`/`Write` calls — do NOT invoke `Skill(openspec-apply-change)` (there's no `tasks.md` to walk; the plan's bullet list from above is the task list). For each item in the plan:

1. Make the code change.
2. Update the spec.md section(s) the plan named — edit the existing `### Requirement:` / `#### Scenario:` blocks in place if the file already uses that structure; for a genuinely new capability with no existing file, plain prose describing the behavior is fine. Prefer this repo's canonical terms from `cla.io/terminology.md` if it exists and covers the concept (soft — proceed on your own judgement if absent or silent on the term). Never create a delta file, never touch `openspec/changes/`.

   **A live spec is a parsed document, not a prose file — validate it before the commit.** This step is the plugin's one write site with no delta and no archive behind it, so nothing downstream re-parses what you just wrote. An ordinary prose edit can leave the file reading correctly to a human while its structure is broken: a `## Requirements` heading duplicated by a replacement that ended with one, for instance, *closes* the section, and every requirement below it becomes invisible to `validate`, `list` and `archive`. In a repo using OpenSpec, run:

   ```
   openspec validate --specs --strict
   ```

   `✗ spec/<cap>` in the output → fix it before committing. Non-zero with **no** `✗` line (`command not found`, `unknown option`) is a tooling fault, not a spec fault — say so rather than attributing it to this edit. `No items found to validate.` is **not** a pass: it means nothing was checked, which is also what a repo not using OpenSpec sees — there, say so once and skip the step rather than recording a vacuous success.
3. Update the `CLAUDE.md` section(s) the plan named (most often "Allocation math" or "Conventions to preserve").
4. Add or update the test file(s) the plan named.

**Show the new test failing before you trust it.** Steps 1–4 write the fix before
the test, which is the ordering that produces a test passing whether the code is
right or not. For a **bug fix**, the cheap check is to stash or revert the fix and
watch the new test go red — a test that never failed against the unfixed code is
evidence of nothing. Read the failure before accepting it: an import error, a
broken fixture, or an unrelated test in the same run is a failure of the *test*,
not proof the test can catch this defect.

Where reverting is impractical — a guard, a scanner, any check whose "feature" is
detecting something — get the same guarantee structurally instead, with a test
asserting the check can still fire at all (`test_the_outcome_detector_is_not_vacuous`,
`test_the_scanner_is_not_vacuous`). That is the stronger form: watching a test fail
is evidence at one moment, whereas a non-vacuity test keeps holding after a later
refactor quietly turns the check into a no-op. Prefer it for anything guard-shaped;
this repo has shipped a guard whose only test would have passed had the function
returned nothing at all.

**Task tracking:** use `TaskCreate` only when part of the plan is genuinely parallel or independently resumable (e.g. several unrelated files touched at once). Skip it for a straightforward linear implementation — the common case, since lite-pr targets small changes. Ignore generic harness `TaskCreate` nudges when they don't fit this rule.

### Test

Nothing is committed at this phase (Ship, which runs `commit-push-pr`, comes later), so derive the changed paths from the **uncommitted working tree, including untracked files** — `git diff` alone would miss brand-new files:

```
git status --porcelain
```

Take the path from each line (strip the two-char status prefix; untracked files show as `??`). If no changed path is source-affecting, there is nothing to gate — skip to Ship. Source-affecting means any path with a `src` component, or any file whose suffix belongs to the repo's own source or config — `.ts .tsx .js .jsx .mjs .cjs .py .go .rs .java .rb .php .sh .sql .vue .svelte .json .yaml .yml .toml .css .scss .html` and anything else this repo actually builds from. **The list is illustrative, not exhaustive: when a suffix is not on it, treat the path as source-affecting.** `.py` is called out because it was once missing, and in a Python repo a real source change then did not register as source-affecting at all — the run reported a clean docs-only skip having gated nothing. A closed list reproduces that defect for every language it omits.

Otherwise read the correctness gates out of `cla.io/project-facts.md` ("Dev / build / test commands", "Workspace shape") — this repo's own record of them, whatever its stack (run `/cla:sync-context` to populate it; falls back to `cla.io/overlays/lite-pr.md` if absent). Split them into two tiers: `smoke` is the cheap lint fast-fail, `full` is the build/typecheck command (primary gate) then the test command. Run smoke first; only run full once smoke is clean (smoke is a pre-filter, not a correctness proof, so full still runs in full). In a workspace/monorepo, the root `build`/`lint`/`test` commands are typically themselves a fan-out across every app/package, so running them at root covers the whole workspace in one shot; there is no separate per-app/package suite to union in. If the file names no commands and the change touches source, say so and treat it as a warning rather than a clean skip. Any standalone smoke/e2e scripts and any hard gate needing external local infra (a live database stack, etc.) are intentionally excluded from this gate — they need external state a plain `npm run` can't provide, and are manual/optional checks, not part of Test. See `cla.io/project-facts.md` ("Dev / build / test commands") for this repo's own concrete examples (falls back to `cla.io/overlays/lite-pr.md` if absent).

Then, smoke tier first, then full:

1. Run every `smoke` command. All pass (or smoke empty) → run every `full` command in order (`build`, then `test`).
2. All pass across both tiers → proceed to Ship.
3. Any failure (in either tier) → **state the cause in one sentence before editing** (a restatement of the symptom is not a cause; read the actual failure output, since a typecheck error or assertion diff *is* the diagnosis), apply one fix via `Edit`, re-run from the failing tier once. **Two rounds on the SAME stated cause with the gate still red → stop editing and escalate to `/cla:diagnose`** — that repetition is the signal the hypothesis is wrong, and it fires while budget remains rather than after a warn ships. `diagnose` builds a deterministic pass/fail loop and ranks falsifiable hypotheses before touching anything, which is the step a third edit skips. **How to escalate depends on whether anyone is there to answer, and this run has two callers.** Invoked by the user → *offer* it, and hand the failure back if they decline. Invoked by `/cla:multi-lite` — a long unattended run whose whole point is that the user can walk away, with no mid-chain pauses — → invoke `Skill(cla:diagnose)` directly and say in the invocation that it runs unattended; never put a question mid-chain to a user who is not there. Either way `diagnose` reports its ranked hypotheses, so the reasoning survives for the user who reads the run afterwards. **Its outcome feeds back here, and it does NOT buy a fresh retry.** A confirmed cause with its fix applied → re-run the failing tier once: green proceeds to Ship, still red falls to step 4. A `diagnose` that stops instead — no buildable loop, or no correct seam — goes straight to step 4 carrying that finding (and the `cla.io/feedback/` note, where it wrote one), never another edit round. Saying this matters most on the unattended arm: without it the nearest applicable rule is step 4's HALT, so a candidate `diagnose` had just FIXED would halt anyway, and `/cla:multi-lite` would quarantine it along with everything downstream of it.
**Test quality is an Implement-phase concern** — see `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/test-quality.md`. If a red gate here forces a test edit, the same rules apply to the edit.

4. Still failing after that one retry → **HALT.** Report the failing check(s) and stop — do not proceed to Ship.

**"Diagnose" means state a cause before editing, not pick a plausible edit.** The one-fix-then-one-retry budget above already stops you firing four changes at once, but it bounds *volume*, not reasoning — a single change made without a stated cause is still a guess, and it spends the whole retry budget. Before the `Edit`:

- **Name the cause in one sentence, specifically enough that the fix follows from it.** "The comparison is case-sensitive but the stored value is lower-cased by the column collation" is a cause. "There's a mismatch in the auth check" is a restatement of the symptom.
- **Read the actual failure output first.** The message usually names the file and line; a stack trace or an assertion diff is the diagnosis, not a hint toward one. Re-reading it beats inferring from the test's name.
- **Say what you expect the re-run to do, before running it.** If the fix is right the named check passes; if it isn't, you have eliminated a cause rather than burned a retry, and the second hypothesis is better-informed than the first.
- **A fix that makes the check pass without explaining why it was failing is a symptom fix.** Loosening an assertion, widening a type, adding a try/except around the failing call, or bumping a timeout all turn the suite green without touching the defect. If the only account you can give is "this makes it more robust", treat the check as still failing and halt at step 4 rather than shipping the suppression.

This is the same discipline `/cla:spec-to-pr`'s Revise phase applies to review findings (a finding is discharged only when the defect is *shown* gone), applied to test failures — where lite-pr has no downstream safety net to catch what a symptom fix hides.

This is the one deliberate stop point in the workflow. It deviates from `/cla:spec-to-pr`'s "warn and continue regardless" policy on purpose: that policy is safe there because spec-to-pr's Revise phase and round caps exist to catch a problem later. lite-pr has neither downstream safety net, so an unresolved test failure has to stop the run here.

### Ship

Pre-commit safety check:

```
python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/git_state.py
```

Exit 0 → proceed. Any non-zero exit → halt and surface via `AskUserQuestion` — same contract as `/cla:spec-to-pr`: never infer "probably fine" on a non-zero exit. This bare invocation passes no `--expect-branch` (lite-pr's feature branch doesn't exist until `commit-push-pr` runs), so a non-zero exit means an in-progress rebase/cherry-pick from another session (exit 2) or an unresolvable/corrupt git state (exit 1) — not a branch mismatch. Resolving an exit-2 in-progress op: `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/conflict-resolution.md`. If another session is active in this same clone, prefer running lite-pr from an isolated worktree (`/cla:new-worktree`) in the first place — a shared-clone `git commit` mid-flow is a real collision risk here, not a hypothetical one (see `cla.io/overlays/lite-pr.md` for a recorded incident in this repo).

**Then, before handing off: every measurement this change asserts names the command that produced it.** This stop is where the change's claims are assembled into a message, which is why the obligation is discharged here rather than while an edit is being typed — a rule that fires at the keyboard fires hundreds of tool calls before the claim is written down. For each measurement the change asserts — a count, a coverage figure, "measured", "verified", "zero X", any number offered as fact — one trailer line goes at the end of the commit message:

```
Measured-by: <the exact command, runnable as written> — <the claim it produced>
```

The command is a real invocation, not "the test suite" and not an elided one; the point of the trailer is that a reader can re-run it. You wrote the claims, so finding them needs no scanner. A claim you cannot pair with a runnable command has two exits and both are edits: **run the command now, or delete the claim** and restate it as the reasoning it actually is ("expected", "by inspection", "should"). There is no third exit in which the claim ships and the command is owed. A change asserting no measurement carries no trailer — never `Measured-by: none`, which certifies a check nobody ran while reading as evidence that one happened. **A measurement is evidence about the tree and conditions that produced it, and nothing else.** Three shapes break that, and each reads as settled fact. A pair asserting sameness — "unchanged", "same counts", "no regression" — must come from one tree, and the trailer must name it; measured on two, the pair asserts a third claim, that conditions matched, with no command behind it. A number measured earlier and restated as current is the same defect with one run missing. A number true under the conditions it ran on — one platform, one shell, one edition — is not true generally until someone runs the others. Three exits, all edits: run the comparison now, restate the numbers as two independent observations, or name the conditions. A before/after delta is the case this does not forbid — it is two trees by construction, so name both, and the claim is about the change rather than either number. The same obligation covers any measurement written into the PR body.

**Session-attribution lines go in the same block as the trailers, with no blank line between them.** `Co-Authored-By:` and `Claude-Session:` sit directly under the last `Measured-by:` line, inside one `-m`. Git parses trailers from the last paragraph only, and that paragraph must be `key: value` lines throughout. Anything else in it — a blank line, a line of prose, a bare `Closes #199` — puts every `Measured-by:` line outside the trailer block. Then `git log --pretty='%(trailers:key=Measured-by,valueonly=true,unfold=true)'` returns nothing.

**Check that it parsed, before the push.** `git log -1 --format=%B | grep -c '^Measured-by:'` and `git log -1 --format='%(trailers:key=Measured-by,valueonly=true,unfold=true)' | grep -c .` must agree — what you wrote against what git's parser sees. Equal passes, including `0` and `0` for a change asserting no measurement. Different means the block is split: `git commit --amend` before pushing. Measured on a controlled pair, a blank line before the attribution lines took three written trailers to **0** parsed. Neither `git log --grep` nor the provenance hook notices — the hook scans the whole message by design — so this command is the only thing that reports it.

**The trigger is a claim this change asserts, not a check that ran.** The standing pre-ship gates — the test suite, the linters, the conformance scripts every commit runs anyway — are not claims the change puts into the diff or the message, so they earn no trailer. Trailering them turns the block into fixed boilerplate on every commit, and a block that is identical every time stops being read, which costs exactly what this step was added to buy.

Then hand off entirely:

```
Skill(commit-commands:commit-push-pr)
```

No pause before this runs — continuous by design (see Autonomy below). Use `commit-push-pr`'s own branch-naming and commit-message conventions as-is; lite-pr does not add any naming logic on top. The `Measured-by:` trailers are message *content* rather than a naming convention, so they are not an exception to that: hand them to `commit-push-pr` as part of the commit message it writes. Hand it the session-attribution lines in that same block too. Git reads trailers from the last paragraph only, and that paragraph must be `key: value` lines throughout. A blank line, or a bare reference line like `Closes #199`, costs every `Measured-by:` line.

### Review

**Dispatch the review agents directly — do NOT chain `Skill(pr-review-toolkit:review-pr)`.** That skill is itself a thin dispatcher that calls the same `pr-review-toolkit:*` agents; the hop adds a 1–2 turn skill-load round trip with no extra capability (same economy `/cla:spec-to-pr`'s "When NOT to use `Skill()`" section applies). Pick the agents by diff content — `code-reviewer` + `silent-failure-hunter` for any logic/behavior code; add `pr-test-analyzer` when tests change, `type-design-analyzer` on a new invariant-bearing type, `comment-analyzer` on a substantial prose/doc block, `plugin-dev:skill-reviewer` on a SKILL.md frontmatter/new-skill change — and route each per `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md`. Launch them in parallel in one message; pass each the diff described by file+symbol (let it read the hunks itself), not the raw diff pasted inline.

**Brief each one per `${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/references/subagent-brief.md`** (scope / task / do-not-touch / report / done-when). These run in parallel over one working tree, which makes the do-not-touch slot load-bearing rather than ceremonial: two agents editing the same file overwrite each other with no merge and no warning. These are review agents, so the brief's own instruction is that they report findings and edit nothing — and where an agent type exists in `.claude/agents/`, prefer a `tools:` allowlist that makes that mechanically true instead of relying on the prose holding.

One pass. Then:

1. Triage every Critical/Important finding: apply a fix via `Edit`/`Write`, or record a one-line deferred rationale if it's genuinely out of scope.
2. Before staging, re-read the diff for each applied fix, and grep the SAME FILE for other call sites that consume the same untrusted/unguarded input the fix just guarded (e.g. a fix added an `isinstance` check before one `.get()` on parsed JSON — grep that file for every other `.get()`/attribute access on data from the same untrusted source). A vaguer "check sibling instances aren't affected" self-prompt is easy to satisfy without actually grepping; naming the concrete technique isn't. This is a quick self-read, NOT a re-dispatch of the review agents — one `Read`/`Grep` call, not another agent round.
2b. **Mutation gate (required before the commit in step 3).** A fix for a Critical/Important
   finding is a change like any other and earns the same evidence the original code needed —
   "the reviewer's finding is now handled" is not that evidence. Break **what the fix
   touches**, not only what it targets: correcting one return path routinely breaks another, which
   is how a real fix here once traded a silent no-op on the default path for the identical no-op on
   the overlay path. Do each one by hand: edit the code so the defect is back, run the affected
   test, confirm it FAILS, then restore the edit exactly — a test that still passes has not been
   shown to catch anything, and an unrestored edit ships the defect. **A test that DOES fail is
   not thereby correct: read the assertion that killed the mutant and confirm it states the
   behaviour you want.** A test written from a wrong mental model kills mutants exactly as
   reliably as a right one, and the green result reads as confirmation. Worst where the mutant
   is the *simpler* form of the code: if the simpler form is right, the test defending the
   original is defending the bug. Full rule and the case that produced it:
   `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/test-quality.md`, "How planting goes wrong".
   Fix a surviving mutant, or name it in the final report with a reason. A clean
   run is evidence about the mutants you thought of and nothing else — two commits in this repo each
   recorded "three mutations checked, all caught" and each shipped a critical a later review found.
3. Stage the fixed files, commit (`fix: address review findings`), push.
4. Do NOT re-dispatch the review agents afterward — no re-verification loop (step 2's self-read is deliberately lighter than that).
5. **Say how big the fix commit is against the reviewed change, and that it is unreviewed.** One line in the final report: the fix commit's insertions versus the reviewed commit's, and the plain statement that nobody has read the fixes. If step 1 committed no fixes, say that instead in one line — the comparison is undefined and inventing a number is worse than omitting it.

   A report line, not a new gate: it re-dispatches nothing and asks nothing. It exists because step 4 is a cost decision rather than a claim the fixes are sound, and a run ending "review complete, fixes applied" reads as though the whole diff was reviewed. It was not — the reviewed artifact is the commit the agents read. The one-pass default still stands; the full triage → fix → re-review loop is `/cla:spec-to-pr`'s Revise phase, and this line is what lets the user opt into a second look without this skill growing one. Worked example, with the run's own numbers: `references/review-fix-weight.md`.

This is a deliberate scope limit: a full triage → fix → re-review loop is `/cla:spec-to-pr`'s Revise phase, and rebuilding it here would reintroduce the cost this skill exists to avoid.

Suggestion-level findings: mention them in the final report; no fix applied automatically.

## Step 7 — Log the run (counts-only ledger)

Always done, after the final report. Append one counts-only JSON line so this skill's
runs can be reviewed in aggregate. It was one of three frequently-used skills keeping no
run data at all; the others are `shape-decision` and `feedback`, given a ledger in the
same change. No claim is made here about which skill runs most — the only per-skill count
that exists is the provenance ledger's `by_skill`, and it attributes most commits to no
skill at all.

```bash
echo '<record-json>' | python3 ${CLAUDE_PLUGIN_ROOT}/lib/log_run.py lite-pr-runs.jsonl
```

```json
{
  "ts": "<ISO-8601>",
  "mode": "inferred-from-conversation|description|asked",
  "phases": {"implement": "ok|warn|skip", "test": "ok|warn|skip",
             "ship": "ok|warn|skip", "review": "ok|warn|skip"},
  "test_halted": true|false,
  "findings": {"critical": N, "important": N, "suggestion": N},
  "fixes_committed": true|false,
  "pr_opened": true|false
}
```

`test_halted` is the one field worth getting exactly right: the Test-phase stop is this
skill's ONLY gate, so how often it fires is the whole question of whether the gate is
placed well. `false` means the phase ran and did not halt; omit the field rather than
writing `false` if Test never ran.

Read it back with the generic summariser — this skill has no bespoke retro, deliberately:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/lib/ledger_summary.py --fleet --ledger lite-pr-runs.jsonl
```

Best-effort: if `log_run.py` exits non-zero, note it and continue. A missing ledger line
never blocks a run.

## Autonomy

Continuous — no "confirm to proceed?" prompts between phases, matching `/cla:spec-to-pr`'s default. Plan does not gate on approval (no `EnterPlanMode`/`ExitPlanMode`) — the plan is posted, then every phase runs straight through: Plan → Implement → Test → Ship → Review. The only stop point in the entire flow is the Test-phase halt on an unresolved failure (see Test above). A user-driven interrupt (Ctrl-C, an explicit "stop"/"wait" message) still halts — that's a hard interrupt, not a model-side pause.

## Scope

Which workflow to use — lite-pr or `/cla:spec-to-pr` — is your judgment call at invocation time (see the intro: no size rule, no automatic escalation). The actionable corollary: reassess mid-run if a change outgrows "lite" — stop, then re-plan or switch to `/cla:spec-to-pr` rather than forcing it through here.

## What this skill deliberately does not do

(For anyone comparing the two workflows.)

- No `proposal.md`/`design.md`/`tasks.md`, no delta specs, no `openspec/changes/` directory, no archive step.
- No multi-round PR-review loop — one pass, one fix round, no re-verification.
- No pre-push confirmation gate.
- No per-run JSONL logging, no retro tooling.

## References

- `${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/git_state.py` — reused directly for the pre-commit safety check.
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/SKILL.md` — the full-weight sibling workflow; see its "Workflow phases" for what a graduated change looks like.
