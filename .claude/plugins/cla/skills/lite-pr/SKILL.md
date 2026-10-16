---
name: lite-pr
description: "Lightweight end-to-end path for a small change without OpenSpec artifacts: plan, implement with docs and tests, one test pass, open the PR, one review round with a single fix round (a second, on the fix diff, for a high-risk fix). Stops only on an unresolved test failure. Triggers: /cla:lite-pr, 'quick PR for X', 'small change, just ship it'."
argument-hint: "[description | (empty)]"
---

# lite-pr — lightweight plan-to-PR workflow

Sibling to `/cla:spec-to-pr` for changes that don't need OpenSpec's artifacts or its multi-round PR-review loop. There is no formal routing rule between the two and no mid-flight escalation path — if a change turns out bigger than expected once you're inside Implement, stop and reassess manually (re-plan, split the change, or switch to `/cla:spec-to-pr`) rather than expecting an automatic handoff.

**Where this repo's facts and rules live.** Commands, paths and file sets come from `cla.io/project-facts.md` only (run `/cla:cla-setup` when it is missing or stale). If `cla.io/project-facts.md` lacks a fact this skill needs and this skill's overlay exists, the overlay may still hold it from before the move: tell the user "run /cla:cla-setup to move it". `cla.io/overlays/lite-pr.md`, if present, adds rules specific to this skill in this repo; apply them alongside the steps below.

**Resolving `${CLAUDE_PLUGIN_ROOT}`.** This `SKILL.md` arrives with the placeholder substituted, but a
`references/` file opened with `Read` carries it literally, and it is not an environment variable in
Bash — an unset variable silently runs the command against `/skills/...`. Before running a command
that contains the literal text, replace it with the plugin root: the `Base directory for this skill`
path with `/skills/<name>` removed, or the absolute path of any plugin file you have read, cut
at `.../plugins/cla`. If neither works, say so and stop. Detail:
`${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/plugin-root.md`.

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

- which `openspec/specs/<capability>/spec.md` file(s) need updating (or note "new capability — no existing spec" / "no outcome or interface change — no spec update needed").
- if the change touches this repo's own core calculation-engine formulas, whether every doc/spec this repo names as needing to stay in lockstep with those formulas needs updating too — see the lockstep set of files `cla.io/project-facts.md` lists for them, under whatever heading; a formula/knob change shipped without all of them is a silent spec violation, not just stale docs.
- which test file(s) need adding/updating, and under which workspace package/app they live — see `cla.io/project-facts.md` ("Test-file locations").
- which docs from `cla.io/project-facts.md` ("Doc-sweep paths"; with no list, the docs a reader of the repo would open) the change updates, or `none affected: <reason>`. Every plan has this line: the docs check has no skip rule (see the Review phase).

No plan is written to disk. The plan lives in the conversation; its durable record is the doc updates it produces during Implement. Unlike `/cla:spec-to-pr`, nothing is created here that later needs archiving or deleting.

Go straight to Implement once the plan is posted — no pause, no "shall I proceed?" question, no wait for a reply.

### Implement

Tests written in this phase follow `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/test-quality.md` — the rules that decide whether a test can fail at all. It covers any test; read `test-quality-gates.md` beside it only when the test is a gate or you are proving one by planting a failure.

Direct `Edit`/`Write` calls — do NOT invoke `Skill(openspec-apply-change)` (there's no `tasks.md` to walk; the plan's bullet list from above is the task list). For each item in the plan:

1. Make the code change.
2. Update the spec.md section(s) the plan named, only to change an outcome or interface they state, applying `openspec/config.yaml` `rules.specs` — edit the existing `### Requirement:` / `#### Scenario:` blocks in place, or for a genuinely new capability start the file in that structure. Prefer this repo's canonical terms from `cla.io/terminology.md` if it exists and covers the concept (soft — proceed on your own judgement if absent or silent on the term). Never create a delta file, never touch `openspec/changes/`.

   **A live spec is a parsed document, not a prose file — validate it before the commit.** This is the plugin's one write site with no delta or archive behind it, so nothing downstream re-parses it, and a prose edit can break structure while reading fine: a duplicated `## Requirements` heading *closes* the section, hiding every requirement below it from `validate`, `list` and `archive`. In a repo using OpenSpec, run:

   ```
   openspec validate --specs
   openspec validate <capability> --type spec --strict   # each spec you edited
   ```

   The first checks structure, not the limits in `rules.specs`: older requirements over them are rewritten when a change touches them. In the second, a `very long` warning on a requirement you edited (`requirements[<n>]`, the n-th `### Requirement:` from 0) is a fix before committing; on one you did not touch, it is that older text.

   `✗ spec/<cap>` in the output → fix it before committing. Non-zero with **no** `✗` line (`command not found`, `unknown option`) is a tooling fault, not a spec fault — say so rather than attributing it to this edit. `No items found to validate.` is **not** a pass: it means nothing was checked, which is also what a repo not using OpenSpec sees — there, say so once and skip the step rather than recording a vacuous success.
3. Update the `CLAUDE.md` section(s) and the docs the plan named (`CLAUDE.md` most often "Allocation math" or "Conventions to preserve").
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

Otherwise read the correctness gates out of `cla.io/project-facts.md` ("Dev / build / test commands", "Workspace shape") — this repo's own record of them, whatever its stack. Split them into two tiers: `smoke` is the cheap lint fast-fail, `full` is the build/typecheck command (primary gate) then the test command. Run smoke first; only run full once smoke is clean (smoke is a pre-filter, not a correctness proof, so full still runs in full). In a workspace/monorepo, the root `build`/`lint`/`test` commands are typically themselves a fan-out across every app/package, so running them at root covers the whole workspace in one shot; there is no separate per-app/package suite to union in. If the file names no commands and the change touches source, say so and treat it as a warning rather than a clean skip. Any standalone smoke/e2e scripts and any hard gate needing external local infra (a live database stack, etc.) are intentionally excluded from this gate — they need external state a plain `npm run` can't provide, and are manual/optional checks, not part of Test. See `cla.io/project-facts.md` ("Dev / build / test commands") for this repo's own concrete examples.

Then, smoke tier first, then full:

1. Run every `smoke` command. All pass (or smoke empty) → run every `full` command in order (`build`, then `test`).
2. All pass across both tiers → proceed to Ship.
3. Any failure (in either tier) → **state the cause in one sentence before editing** (a restatement of the symptom is not a cause; read the actual failure output, since a typecheck error or assertion diff *is* the diagnosis), apply one fix via `Edit`, re-run from the failing tier once. **That is the whole edit budget: one fix, one retry. Still red after that retry, on the same stated cause or a new one → stop editing and escalate to `/cla:diagnose`** — read `${CLAUDE_PLUGIN_ROOT}/skills/lite-pr/references/diagnose-escalation.md` at that point, before you offer or invoke it: it holds how to escalate attended versus unattended and where its outcome feeds back. (Short form: user present, offer it; under `/cla:multi-lite`, invoke it and never ask. Either way `diagnose` leaves its fix uncommitted; Ship commits it.)
   **Test quality is an Implement-phase concern** — see `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/test-quality.md`. If a red gate here forces a test edit, the same rules apply to the edit.

4. Still failing after the `/cla:diagnose` path in step 3 (its confirmed fix re-run once still red, a `diagnose` that stopped, or the user declined the offer) → **HALT.** Report the failing check(s) and stop — do not proceed to Ship.

**"Diagnose" means state a cause before editing, not pick a plausible edit.** The one-fix-then-one-retry budget above already stops you firing four changes at once, but it bounds *volume*, not reasoning — a single change made without a stated cause is still a guess, and it spends the whole retry budget. Before the `Edit`:

- **Name the cause in one sentence, specifically enough that the fix follows from it.** "The comparison is case-sensitive but the stored value is lower-cased by the column collation" is a cause. "There's a mismatch in the auth check" is a restatement of the symptom.
- **Read the actual failure output first.** The message usually names the file and line; a stack trace or an assertion diff is the diagnosis, not a hint toward one. Re-reading it beats inferring from the test's name.
- **Say what you expect the re-run to do, before running it.** If the fix is right the named check passes; if it isn't, you have eliminated a cause rather than guessed blind. A red retry goes to step 3's `/cla:diagnose` escalation; a red re-run after `diagnose` goes to step 4's HALT.
- **A fix that makes the check pass without explaining why it was failing is a symptom fix.** Loosening an assertion, widening a type, adding a try/except around the failing call, or bumping a timeout all turn the suite green without touching the defect. If the only account you can give is "this makes it more robust", treat the check as still failing, so it goes to step 3's escalation or step 4's halt, rather than shipping the suppression.

This is the same discipline `/cla:spec-to-pr`'s Revise phase applies to review findings (a finding is discharged only when the defect is *shown* gone), applied to test failures — where lite-pr has no downstream safety net to catch what a symptom fix hides.

This is the one deliberate stop point in the workflow. It deviates from `/cla:spec-to-pr`'s "warn and continue regardless" policy on purpose: that policy is safe there because spec-to-pr's Revise phase and round caps exist to catch a problem later. lite-pr has neither downstream safety net, so an unresolved test failure has to stop the run here.

### Ship

Pre-commit safety check:

```
python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/git_state.py
```

Exit 0 → proceed. Any non-zero exit → halt and surface via `AskUserQuestion` — same contract as `/cla:spec-to-pr`: never infer "probably fine" on a non-zero exit. This bare invocation passes no `--expect-branch` (lite-pr's feature branch doesn't exist until `commit-push-pr` runs), so a non-zero exit means an in-progress rebase/cherry-pick from another session (exit 2) or an unresolvable/corrupt git state (exit 1) — not a branch mismatch. Resolving an exit-2 in-progress op: `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/conflict-resolution.md`. If another session is active in this same clone, prefer running lite-pr from an isolated worktree (`/cla:new-worktree`) in the first place — a shared-clone `git commit` mid-flow is a real collision risk here, not a hypothetical one.

**Before the commit message is written: does this change assert a measurement** (a count, a coverage figure, "measured", "verified", "zero X", any number offered as fact, or a sameness claim such as "unchanged" or "no regression", in the commit message or the PR body)? Then read `${CLAUDE_PLUGIN_ROOT}/skills/lite-pr/references/measured-by.md` first and follow it: the `Measured-by:` trailer rules, the trailer-block layout and the parse check to run before the push. Unsure whether a sentence is a measurement: read it.

Then hand off entirely:

```
Skill(commit-commands:commit-push-pr)
```

No pause before this runs — continuous by design (see Autonomy below). Before it opens the PR, make the risk call from the diff and put one line in the PR body: `Risk: <level> — <reason>; reviewers: <list>.` Keep the Risk line on one line with no `\n#`. The level and reviewers come from "Review sizing by risk" in `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md`; unsure means high. Use `commit-push-pr`'s own branch-naming and commit-message conventions as-is; lite-pr does not add any naming logic on top. The `Measured-by:` trailers are message *content* rather than a naming convention, so they are not an exception to that: hand them to `commit-push-pr` as part of the commit message it writes. Hand it the session-attribution lines in that same block too. The block layout that keeps the trailers parsing is in `measured-by.md`.

### Review

**Dispatch the review agents directly — do NOT chain `Skill(pr-review-toolkit:review-pr)`.** That skill is itself a thin dispatcher of reviewer agents; the hop adds a 1–2 turn skill-load round trip with no extra capability (the same economy as `/cla:spec-to-pr`'s "No `Skill()` hops" rule). Pick the reviewers and their models from the risk line in the PR body, per "Review sizing by risk" in `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md`. Raise the level to high if the diff shows a risk signal the line missed. If the line is missing, unreadable or names an unknown level, treat the diff as high risk. Say so in your report, as "A missing line means high" in that section says. Add `pr-test-analyzer` when tests change, and `type-design-analyzer` on a new invariant-bearing type. Route each per `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md`. Add `plugin-dev:skill-reviewer` on Sonnet when a SKILL.md frontmatter changed or a new skill was created. On a prose-dominant diff the sizing section already adds it on Opus; run it once, on Opus. Dispatch `code-reviewer`, `silent-failure-hunter` and `comment-analyzer` as `cla:code-reviewer`, `cla:silent-failure-hunter` and `cla:comment-analyzer` (passing `model: opus` to `code-reviewer` on the high-risk row); the other agents keep their own plugin's prefix. Before dispatching, save the diff (`git diff <base>...<branch> -- <paths>`) to a file outside the working tree — the session scratchpad; when none is listed, a `mktemp` file passed as a native path (`cygpath -w` in Git Bash on Windows) — and delete it when the round ends. Launch them in parallel in one message; pass each the diff described by file+symbol plus the absolute path of its diff file, not the raw diff pasted inline. The three `cla:` reviewers have no shell and read only that file.

**Brief each one per `${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/references/subagent-brief.md`** (scope / task / do-not-touch / report / done-when). These run in parallel over one working tree, which makes the do-not-touch slot load-bearing rather than ceremonial: two agents editing the same file overwrite each other with no merge and no warning. These are review agents, so the brief's own instruction is that they report findings and edit nothing — and where an agent type exists in `.claude/agents/`, prefer a `tools:` allowlist that makes that mechanically true instead of relying on the prose holding.

**Docs check, made by you rather than the reviewers** (they read only the diff, and a stale doc lies outside it). It runs on every change, whatever rules the repo has: lite-pr has no `tasks.md` to carry the duty, so nothing gates it. Where the repo has no doc list, judgement stands in: take the docs a reader would open for this change (the README, the developer guide, and any doc a search finds naming what the diff alters), and where none applies, put `none affected: <reason>` in the final report. List the names the diff alters (flags, commands, skill and file names, headings, counts) and search for them every doc on that list that the diff does not touch, including one the plan excused with `none affected:`. A doc that still states the old behaviour is an Important finding for step 1. Its fix is a doc edit with no test to break, so step 2b's mutation gate does not apply to it, and fixing it is a docs-currency fix, which does not by itself earn step 4's second pass.

One pass, and a second only in the case step 4 names. Then:

1. Triage every Critical/Important finding: apply a fix via `Edit`/`Write`, or record a one-line deferred rationale if it's genuinely out of scope.
2. Before staging, re-read the diff for each applied fix, and grep the SAME FILE for other call sites that consume the same untrusted/unguarded input the fix just guarded (e.g. a fix added an `isinstance` check before one `.get()` on parsed JSON — grep that file for every other `.get()`/attribute access on data from the same untrusted source). A vaguer "check sibling instances aren't affected" self-prompt is easy to satisfy without actually grepping; naming the concrete technique isn't. This is a quick self-read, NOT a re-dispatch of the review agents — one `Read`/`Grep` call, not another agent round.
2b. **Mutation gate (required before the commit in step 3).** When step 1 applied any Critical/Important fix,
   read `${CLAUDE_PLUGIN_ROOT}/skills/lite-pr/references/mutation-gate.md` before staging and follow it in full; the fix
   commit does not ship without it.
3. Stage the fixed files, commit (`fix: address review findings`), push.
4. **A second pass only for a high-risk fix.** When this Review ran at high risk and step 1 fixed a Critical or Important finding other than a docs-currency fix (if step 1 also fixed anything else, it is judged on those other fixes alone), dispatch the same sizing-table reviewers once more, at the same models, over the fix commit's diff only. Add a narrow agent only if the fix diff still meets its trigger. High risk here is the level the Review used: the `Risk:` line said high, you raised it, or the line was missing, unreadable or named an unknown level. Run steps 1–3 on what they find, then stop: there is no third pass. Otherwise do NOT re-dispatch the review agents — no re-verification loop (step 2's self-read is deliberately lighter than that).
5. **Say how big the last fix commit is against what the last pass reviewed, and that it is unreviewed unless a second pass read it.** One line in the final report: the last fix commit's insertions versus the reviewed diff's, and the plain statement that nobody has read those fixes. If a second pass reviewed the fixes and committed none, say that the fixes were reviewed once more and nothing changed. If the first pass committed no fixes, say that instead in one line — the comparison is undefined and inventing a number is worse than omitting it.

   A report line, not a new gate: it re-dispatches nothing and asks nothing. It exists because step 4 is a cost decision rather than a claim the fixes are sound, and a run ending "review complete, fixes applied" reads as though the whole diff was reviewed. It was not — the reviewed artifact is the commit the agents read. The default stays one pass, with step 4's second pass only for a high-risk fix; the full triage → fix → re-review loop is `/cla:spec-to-pr`'s Revise phase, and this line is what lets the user ask for another look beyond the one step 4 allows. Worked example, with the run's own numbers: `${CLAUDE_PLUGIN_ROOT}/skills/lite-pr/references/review-fix-weight.md`.

This is a deliberate scope limit: a full triage → fix → re-review loop is `/cla:spec-to-pr`'s Revise phase, and rebuilding it here would reintroduce the cost this skill exists to avoid.

Suggestion-level findings: mention them in the final report; no fix applied automatically.

## Autonomy

Continuous — no "confirm to proceed?" prompts between phases, matching `/cla:spec-to-pr`'s default. Plan does not gate on approval (no `EnterPlanMode`/`ExitPlanMode`) — the plan is posted, then every phase runs straight through: Plan → Implement → Test → Ship → Review. The only stop point in the entire flow is the Test-phase halt on an unresolved failure (see Test above). A user-driven interrupt (Ctrl-C, an explicit "stop"/"wait" message) still halts — that's a hard interrupt, not a model-side pause.

## Scope

Which workflow to use — lite-pr or `/cla:spec-to-pr` — is your judgment call at invocation time (see the intro: no size rule, no automatic escalation). The actionable corollary: reassess mid-run if a change outgrows "lite" — stop, then re-plan or switch to `/cla:spec-to-pr` rather than forcing it through here.

## What this skill deliberately does not do

(For anyone comparing the two workflows.)

- No `proposal.md`/`design.md`/`tasks.md`, no delta specs, no `openspec/changes/` directory, no archive step.
- No multi-round PR-review loop — one pass, plus one pass over the fix diff of a high-risk change; never a third.
- No pre-push confirmation gate.

## References

- `${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/git_state.py` — reused directly for the pre-commit safety check.
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/SKILL.md` — the full-weight sibling workflow; see its "Workflow phases" for what a graduated change looks like.
