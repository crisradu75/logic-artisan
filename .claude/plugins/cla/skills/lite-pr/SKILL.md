---
name: lite-pr
description: "Lightweight end-to-end workflow for small changes you don't want to run through full OpenSpec: optional requirements exploration, a plan posted for visibility (not a blocking approval gate), direct implementation that updates code plus the relevant spec.md/CLAUDE.md/tests in place, one automated test pass, commit-push-pr, and one PR-review pass with a single fix round. No OpenSpec artifacts and no multi-round PR-review loop — runs straight through, continuous end-to-end, with the sole stop point being an unresolved Test-phase failure. No formal size rule vs /cla:spec-to-pr; which to use is your call. Triggers on /cla:lite-pr or natural language like 'quick PR for X', 'lite-pr this', 'small change, just ship it'."
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

- which `openspec/specs/<capability>/spec.md` file(s) need updating (or note "new capability — no existing spec" / "behavior-invisible change — no spec update needed"). See `references/project-context.md` for this repo's own architecture-as-a-capability spec path — a structural change (new data-flow layer, new module boundary) belongs there, not in a separate architecture doc.
- if the change touches this repo's own core calculation-engine formulas, whether every doc/spec this repo names as needing to stay in lockstep with those formulas needs updating too — see `cla.io/project-facts.md` ("Allocation-formula lockstep doc set") for the exact file set (run `/cla:sync-context` to populate it; falls back to `references/project-context.md` if absent); a formula/knob change shipped without all of them is a silent spec violation, not just stale docs.
- which test file(s) need adding/updating, and under which workspace package/app they live — see `references/project-context.md` for this repo's own worked examples.

No plan is written to disk. The plan lives in the conversation; its durable record is the doc updates it produces during Implement. Unlike `/cla:spec-to-pr`, nothing is created here that later needs archiving or deleting.

Go straight to Implement once the plan is posted — no pause, no "shall I proceed?" question, no wait for a reply.

### Implement

Direct `Edit`/`Write` calls — do NOT invoke `Skill(openspec-apply-change)` (there's no `tasks.md` to walk; the plan's bullet list from above is the task list). For each item in the plan:

1. Make the code change.
2. Update the spec.md section(s) the plan named — edit the existing `### Requirement:` / `#### Scenario:` blocks in place if the file already uses that structure; for a genuinely new capability with no existing file, plain prose describing the behavior is fine. Never create a delta file, never touch `openspec/changes/`.
3. Update the `CLAUDE.md` section(s) the plan named (most often "Allocation math" or "Conventions to preserve").
4. Add or update the test file(s) the plan named.

**Task tracking:** use `TaskCreate` only when part of the plan is genuinely parallel or independently resumable (e.g. several unrelated files touched at once). Skip it for a straightforward linear implementation — the common case, since lite-pr targets small changes. Ignore generic harness `TaskCreate` nudges when they don't fit this rule.

### Test

Nothing is committed at this phase (Ship, which runs `commit-push-pr`, comes later), so derive the changed paths from the **uncommitted working tree, including untracked files** — `git diff` alone would miss brand-new files:

```
git status --porcelain
```

Take the path from each line (strip the two-char status prefix; untracked files show as `??`). Then discover the correctness gates (staged):

```
python3 .claude/plugins/cla/skills/spec-to-pr/scripts/discover_tests.py --staged <changed-paths>
```

`discover_tests.py --staged` reads the root `package.json`'s `scripts` map and, when at least one changed path is source-affecting, partitions whichever of `build`, `lint`, `test` exist into `{"smoke": [...], "full": [...]}` — `smoke` is the cheap `npm run lint` fast-fail, `full` is `npm run build` (primary gate) then `npm run test`. Run smoke first; only run full once smoke is clean (smoke is a pre-filter, not a correctness proof, so full still runs in full). In a workspace/monorepo, the root `build`/`lint`/`test` scripts are typically themselves a fan-out across every app/package — see `cla.io/project-facts.md` ("Dev / build / test commands", "Workspace shape") for this repo's own exact fan-out mechanism and app/package list (run `/cla:sync-context` to populate it; falls back to `references/project-context.md` if absent). So the root-only discovery already covers the whole workspace in one shot; there is no separate per-app/package suite to union in. Any standalone smoke/e2e scripts and any hard gate needing external local infra (a live database stack, etc.) are intentionally excluded from this gate — they need external state a plain `npm run` can't provide, and are manual/optional checks, not part of Test. See `cla.io/project-facts.md` ("Dev / build / test commands") for this repo's own concrete examples (falls back to `references/project-context.md` if absent).

Then, smoke tier first, then full:

1. Run every `smoke` command. All pass (or smoke empty) → run every `full` command in order (`build`, then `test`).
2. All pass across both tiers → proceed to Ship.
3. Any failure (in either tier) → diagnose, apply one fix via `Edit`, re-run from the failing tier once.
4. Still failing after that one retry → **HALT.** Report the failing check(s) and stop — do not proceed to Ship.

This is the one deliberate stop point in the workflow. It deviates from `/cla:spec-to-pr`'s "warn and continue regardless" policy on purpose: that policy is safe there because spec-to-pr's Revise phase and round caps exist to catch a problem later. lite-pr has neither downstream safety net, so an unresolved test failure has to stop the run here.

### Ship

Pre-commit safety check:

```
python3 .claude/plugins/cla/skills/spec-to-pr/scripts/git_state.py
```

Exit 0 → proceed. Any non-zero exit → halt and surface via `AskUserQuestion` — same contract as `/cla:spec-to-pr`: never infer "probably fine" on a non-zero exit. This bare invocation passes no `--expect-branch` (lite-pr's feature branch doesn't exist until `commit-push-pr` runs), so a non-zero exit means an in-progress rebase/cherry-pick from another session (exit 2) or an unresolvable/corrupt git state (exit 1) — not a branch mismatch. If another session is active in this same clone, prefer running lite-pr from an isolated worktree (`/cla:new-worktree`) in the first place — a shared-clone `git commit` mid-flow is a real collision risk here, not a hypothetical one (see `references/project-context.md` for a recorded incident in this repo).

Then hand off entirely:

```
Skill(commit-commands:commit-push-pr)
```

No pause before this runs — continuous by design (see Autonomy below). Use `commit-push-pr`'s own branch-naming and commit-message conventions as-is; lite-pr does not add any naming logic on top.

### Review

**Dispatch the review agents directly — do NOT chain `Skill(pr-review-toolkit:review-pr)`.** That skill is itself a thin dispatcher that calls the same `pr-review-toolkit:*` agents; the hop adds a 1–2 turn skill-load round trip with no extra capability (same economy `/cla:spec-to-pr`'s "When NOT to use `Skill()`" section applies). Pick the agents by diff content — `code-reviewer` + `silent-failure-hunter` for any logic/behavior code; add `pr-test-analyzer` when tests change, `type-design-analyzer` on a new invariant-bearing type, `comment-analyzer` on a substantial prose/doc block, `plugin-dev:skill-reviewer` on a SKILL.md frontmatter/new-skill change — and route each per `.claude/plugins/cla/skills/spec-to-pr/references/model-routing.md`. Launch them in parallel in one message; pass each the diff described by file+symbol (let it read the hunks itself), not the raw diff pasted inline.

One pass. Then:

1. Triage every Critical/Important finding: apply a fix via `Edit`/`Write`, or record a one-line deferred rationale if it's genuinely out of scope.
2. Before staging, re-read the diff for each applied fix, checking specifically whether the same class of issue recurs elsewhere in the change (e.g. a fix to one instance of a pattern — check sibling instances aren't affected too). This is a quick self-read, NOT a re-dispatch of the review agents — one `Read` call, not another agent round.
3. Stage the fixed files, commit (`fix: address review findings`), push.
4. Do NOT re-dispatch the review agents afterward — no re-verification loop (step 2's self-read is deliberately lighter than that).

This is a deliberate scope limit: a full triage → fix → re-review loop is `/cla:spec-to-pr`'s Revise phase, and rebuilding it here would reintroduce the cost this skill exists to avoid.

Suggestion-level findings: mention them in the final report; no fix applied automatically.

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

- `.claude/plugins/cla/skills/spec-to-pr/scripts/git_state.py` — reused directly for the pre-commit safety check.
- `.claude/plugins/cla/skills/spec-to-pr/scripts/discover_tests.py` — reused directly for root-package test discovery.
- `.claude/plugins/cla/skills/spec-to-pr/SKILL.md` — the full-weight sibling workflow; see its "Workflow phases" for what a graduated change looks like.
