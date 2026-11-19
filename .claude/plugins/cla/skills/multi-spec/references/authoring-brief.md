# multi-spec — per-change authoring agent brief

Phase 3 dispatches one `Agent(subagent_type: "claude", model:)` call per change, on the model the `multi-spec` authoring row of `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md` names, awaited sequentially. This file is the prompt template — fill in the bracketed parts from the change plan (`references/plan-schema.md`) and the source decisions file.

One change at a time: authoring sets the premise every later phase builds on, and each change's agent gets the siblings already written.

## Prompt template

```
You are writing one OpenSpec change from the owner's decisions. Before writing, read `cla.io/project-facts.md`, especially its Stakes section (who uses this repo, what a bug costs, and which areas are protected) and its "Workspace shape". With no Stakes section, treat as protected the default list in `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/blocking-findings.md`; its floor always applies. Check the repo's instruction files (`CLAUDE.md` and `AGENTS.md`) for its layout before naming a package.

**Change name:** <name>
**One-line scope:** <one_line_scope from the plan>
**Decisions this change implements (verbatim from the source decisions file — do not paraphrase):**
<verbatim text of decisions_covered, copied from the decisions file's numbered "Decisions" section>

**Already-authored sibling changes in this same batch** (for correct cross-references — read their proposal.md if you need more than this summary):
<for each already-committed change in the plan: "- <name>: <one_line_scope>">

## How to write it

Specify what the decisions decided, in the owner's terms. A decision the owner made is settled: don't reopen it. If you think one is wrong, specify it as decided and raise your concern under `## Open questions`; never change it in the spec.

Think broadly, then write narrowly.

1. Before writing, list for yourself what could go wrong when this change runs in real use. Consider:
   - hangs, partial failures, retries and interrupted runs;
   - what the next run does with what an earlier run left behind, such as work not yet sent or a half-finished step, including when nothing new has changed;
   - data the change reads but must not alter;
   - a fallback a decision defines, and which failures must never take it;
   - a comparison or score measured against the wrong baseline, such as one that lacks the thing being measured.
2. Sort each risk:
   - **It touches a protected area** (it could lose, corrupt or leak what the Stakes protect, or break something shipped to others): write it as a requirement, stating the outcome the owner would notice, with a scenario. These matter most; never cut one to save words.
   - **Otherwise:** one line under `## Risks noted` in proposal.md. Don't design machinery against it. Keep that section to about 5 lines: name the likeliest risks.
3. For each protected-area risk, check whether a decision rules out the obvious fix. If it does, keep the decision, and raise the conflict under `## Open questions` with your proposed fix.

Requirements state outcomes, not how to build them. Write design.md only when a real choice needs recording. A number that changes behaviour (a time limit, a retry count) gets a concrete default, in a scenario or in design.md. A check or score says what counts as a pass, or asks. design.md and the specs must agree; where they would differ, the spec wins and design.md follows it.

Tests and manual checks run on copies or scratch data, never on what the Stakes protect.

Where the decisions are silent on something the change truly needs, list it under `## Open questions` in proposal.md, with your recommended answer. Search the decisions before listing one: a question the decisions already answer is a defect.

Add nothing beyond what the decisions, a protected-area risk and the `rules:` in `openspec/config.yaml` require: no extra options, commands, metadata, docs or test machinery.

`openspec/config.yaml` `rules:` set the format, the proof each requirement carries, how code and spec mismatches are fixed and the change budget, and a script enforces the budget. If the protected-area requirements can't fit in it, say so in your report rather than cutting them (the post-check surfaces it to the owner).

## Mechanics

Follow these steps, mirroring `.claude/skills/openspec-propose`'s own artifact-creation process:

1. If `openspec/changes/<name>/` does not yet exist, run `openspec new change "<name>"`. If it already exists (a prior run's crash left it here), skip this step and go straight to step 2 — do not overwrite what's already there without reading it first.
2. Run `openspec status --change "<name>" --json` to get the artifact build order (`applyRequires`, `artifacts`).
3. For each artifact in dependency order, run `openspec instructions <artifact-id> --change "<name>" --json`, read its `template`/`instruction`/`context`/`rules`, read any completed dependency artifacts for context, and write the artifact to its `resolvedOutputPath`. Do NOT copy `context`/`rules` blocks into the output file — they constrain what you write, they are not content for the file. design.md and the spec delta are conditional (step 4's rules say when), so "every artifact" does not mean all four.
4. Apply these pre-checks as you write:
   - **Apply `openspec/config.yaml` `rules:`** as step 3's `openspec instructions` returns them: they set when design.md and a spec delta are written, how live specs are read, what a spec may state, its size, and how each requirement is proven. Where the repo has none, `/cla:cla-setup` seeds or offers them.
   - **On a MODIFIED requirement, carry the full requirement text and all its live scenarios forward**, then adjust. Archive replaces the whole requirement, so an omitted scenario is deleted. `openspec validate <name> --strict` (step 5) fails a block that drops one. Do not rename a live scenario inside the block: validate treats it as dropped.
   - **Retiring specs.** If this change replaces internal or platform specs with outcome-level ones, read `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/retiring-specs.md` and follow it: `retire_capabilities: true` in `.openspec.yaml`, every requirement of a retired spec REMOVED, each owner-visible outcome folded into a product spec, and a `## Removed requirements` table in `tasks.md`. Grep the earlier changes' tables for `pending` rows naming your specs and restate each.
5. Once every artifact required by `applyRequires` is `done`, re-checked via `openspec status --change "<name>" --json`, run `openspec validate <name> --strict`. With no design.md, OpenSpec still reports `isComplete: false`; that is expected.

**Terminal contract.** End with exactly one of:
- `done` — valid ONLY when `openspec validate <name> --strict` exited 0 AND you confirm `proposal.md`, `tasks.md`, and either at least one `specs/*/spec.md` or `skip_specs: true` in `.openspec.yaml` exist under `openspec/changes/<name>/`. State the validate command's exit status explicitly, and name the stock trigger if you wrote `design.md`.
- `blocked` — state exactly what's missing or failing (a validate failure or a missing input). A gap in the decisions goes under Open questions, not here.

Do not claim `done` without that evidence — an unverified claim is treated as not done by the caller.
```

## Resume check (before dispatching)

Does `openspec/changes/<name>/proposal.md` already exist AND is it tracked (`git ls-files openspec/changes/<name>/proposal.md` non-empty)? If yes, this change is already committed from a prior run — skip it, move to the next change in the plan. If the directory exists but is **untracked** (a crash landed between authoring and commit), treat it as incomplete: instruct the dispatched agent to skip the `openspec new change` call (it errors on an existing directory) and go straight to `openspec status --change "<name>" --json` instead.

## Post-check (after dispatching, regardless of what the agent reports)

Confirm `openspec/changes/<name>/proposal.md`, `tasks.md`, and either at least one `specs/*/spec.md` or `skip_specs: true` in `.openspec.yaml` exist, that a `design.md`, if present, came with a named stock trigger, and re-run `openspec validate <name> --strict` yourself. A `done` claim without this holding is treated as not done — finish it inline (or re-dispatch once) rather than trusting the report, same discipline `/cla:spec-to-pr`'s Implement delegate contract uses. The agent's `done`/`blocked` status is a signal, not a trusted fact.

Also record, for the PR body and the final report, the change's `## Open questions` in `proposal.md` (one line each) and a budget result. Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/check_spec_proof.py` once over the repo and read only its budget lines that name this change, plus any protected-area requirement the agent says it could not fit. The script checks the whole repo and flags every new requirement `uncovered` on a proposals-only branch, so its exit code and `uncovered` lines do not fail the post-check. An exit 2 is recorded as "budget not checked: <its message>". The budget result is information for the owner: it is not `done` evidence, and it does not block the commit or trigger a re-dispatch.

## Commit + push (immediately, before starting the next change)

```
python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/git_state.py --expect-branch docs/propose-<batch-slug>
git add -- openspec/changes/<name>/
git commit -m "docs(openspec): propose <name>"
git push
```
`git push` (not just commit) is deliberate — a local-only commit still doesn't survive a dead disk; pushing after every change is what actually protects against a local-machine incident. **Then run the push post-check** (`references/phases.md`) before moving to the next change — an unverified push here is the exact silent-loss scenario this skill exists to prevent.

This is the one point in the loop with nothing pending: the previous change's `Agent` has returned,
its commit is pushed, and the next dispatch has not been made yet. A post-check result reads as a
natural place to stop, and the batch then stops rather than pauses, with nothing blocked and nobody
waiting.

The hoisted turn-liveness rule in `SKILL.md` binds here, and is restated because this is exactly the
point at which that file has been closed and the orchestrator is running on its summary.
Mechanically: the post-check result and the next change's dispatch go **in the same message**. If
there is no tool call to pair the result with, the change is not over. The test is whether a
**pending event** will re-invoke this session, not whether you asked the user anything — announcing
the next change **is not a mechanism**, while the next `Agent` dispatch is, because a tool call does
not end the turn at all.
