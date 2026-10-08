# multi-spec — per-change authoring agent brief

Phase 3 dispatches one `Agent(subagent_type: "claude", model: "opus")` call per change, awaited sequentially. This file is the prompt template — fill in the bracketed parts from the change plan (`references/plan-schema.md`) and the source decisions file.

Opus, one change at a time: authoring sets the premise every later phase builds on, and each change's agent gets the siblings already written.

## Prompt template

```
You are authoring one OpenSpec change proposal in this repo (its workspace shape is in `cla.io/project-facts.md`'s "Workspace shape"). Check the root `CLAUDE.md` "Repo layout" before naming a package; the list changes.

**Change name:** <name>
**One-line scope:** <one_line_scope from the plan>
**Decisions this change implements (verbatim from the source decisions file — do not paraphrase):**
<verbatim text of decisions_covered, copied from the decisions file's numbered "Decisions" section>

**Already-authored sibling changes in this same batch** (for correct cross-references — read their proposal.md if you need more than this summary):
<for each already-committed change in the plan: "- <name>: <one_line_scope>">

Follow these steps, mirroring `.claude/skills/openspec-propose`'s own artifact-creation process:

1. If `openspec/changes/<name>/` does not yet exist, run `openspec new change "<name>"`. If it already exists (a prior run's crash left it here), skip this step and go straight to step 2 — do not overwrite what's already there without reading it first.
2. Run `openspec status --change "<name>" --json` to get the artifact build order (`applyRequires`, `artifacts`).
3. For each artifact in dependency order, run `openspec instructions <artifact-id> --change "<name>" --json`, read its `template`/`instruction`/`context`/`rules`, read any completed dependency artifacts for context, and write the artifact to its `resolvedOutputPath`. Do NOT copy `context`/`rules` blocks into the output file — they constrain what you write, they are not content for the file. design.md and the spec delta are conditional (step 4's rules say when), so "every artifact" does not mean all four.
4. Apply these pre-checks as you write:
   - **Apply `openspec/config.yaml` `rules:`** as step 3's `openspec instructions` returns them: they set when design.md and a spec delta are written, how live specs are read, what a spec may state, its size, and how each requirement is proven. Where the repo has none, `/cla:cla-setup` seeds or offers them.
   - **Pin load-bearing numbers, when design.md exists.** Any threshold, band, cap, weight, tolerance, or split that changes scoring/behavior gets a concrete recommended default in design.md — never "set during implementation." A change with no such number needs no pinned-parameters block.
   - **On a MODIFIED requirement, carry the full requirement text and all its live scenarios forward**, then adjust. Archive replaces the whole requirement, so an omitted scenario is deleted. `openspec validate <name> --strict` (step 5) fails a block that drops one. Do not rename a live scenario inside the block: validate treats it as dropped.
5. Once every artifact required by `applyRequires` is `done`, re-checked via `openspec status --change "<name>" --json`, run `openspec validate <name> --strict`. With no design.md, OpenSpec still reports `isComplete: false`; that is expected.

**Terminal contract.** End with exactly one of:
- `done` — valid ONLY when `openspec validate <name> --strict` exited 0 AND you confirm `proposal.md`, `tasks.md`, and either at least one `specs/*/spec.md` or `skip_specs: true` in `.openspec.yaml` exist under `openspec/changes/<name>/`. State the validate command's exit status explicitly, and name the stock trigger if you wrote `design.md`.
- `blocked` — state exactly what's missing or failing (a validate error, an ambiguous decision that needs a human call, etc.).

Do not claim `done` without that evidence — an unverified claim is treated as not done by the caller.
```

## Resume check (before dispatching)

Does `openspec/changes/<name>/proposal.md` already exist AND is it tracked (`git ls-files openspec/changes/<name>/proposal.md` non-empty)? If yes, this change is already committed from a prior run — skip it, move to the next change in the plan. If the directory exists but is **untracked** (a crash landed between authoring and commit), treat it as incomplete: instruct the dispatched agent to skip the `openspec new change` call (it errors on an existing directory) and go straight to `openspec status --change "<name>" --json` instead.

## Post-check (after dispatching, regardless of what the agent reports)

Confirm `openspec/changes/<name>/proposal.md`, `tasks.md`, and either at least one `specs/*/spec.md` or `skip_specs: true` in `.openspec.yaml` exist, that a `design.md`, if present, came with a named stock trigger, and re-run `openspec validate <name> --strict` yourself. A `done` claim without this holding is treated as not done — finish it inline (or re-dispatch once) rather than trusting the report, same discipline `/cla:spec-to-pr`'s Implement delegate contract uses. The agent's `done`/`blocked` status is a signal, not a trusted fact.

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
