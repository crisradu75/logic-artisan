# multi-spec — per-change authoring agent brief

Phase 3 dispatches one `Agent(subagent_type: "claude", model: "opus")` call per change, awaited sequentially. This file is the prompt template — fill in the bracketed parts from the change plan (`references/plan-schema.md`) and the source decisions file.

## Why Opus, why one-at-a-time

Proposal/design/tasks/specs authoring is the premise-setting step for a change — same bucket as a Review verdict, not rubric-application work. A cheaper model's failure mode here is systematically under-specified artifacts (unpinned load-bearing numbers, a missed MODIFIED-requirement scenario carry-forward, a wrong cross-reference), which is expensive to unwind — a full review-and-fix round downstream, or worse, silently propagated into a sibling change's cross-reference before anyone catches it. Sequential (not parallel) dispatch is required anyway by Phase 3's commit-before-next-change durability rule, and it has a second benefit: each change's agent can be handed the already-authored siblings' summaries, so a later change's cross-reference to an earlier one is correct from the start rather than only caught in Phase 4's batch review.

## Prompt template

```
You are authoring one OpenSpec change proposal in this repo (see `references/project-context.md` for its monorepo shape, or `cla.io/project-facts.md`'s "Workspace shape" if populated). Do NOT assume a fixed package list — read the "Repo layout" section of the root `CLAUDE.md` for the authoritative current set of packages before referencing one in the proposal (the workspace gains packages over time; a hardcoded list drifts, and referencing a package that does not yet exist on the current tree seeds a false claim into the proposal).

**Change name:** <name>
**One-line scope:** <one_line_scope from the plan>
**Decisions this change implements (verbatim from the source decisions file — do not paraphrase):**
<verbatim text of decisions_covered, copied from the decisions file's numbered "Decisions" section>

**Already-authored sibling changes in this same batch** (for correct cross-references — read their proposal.md if you need more than this summary):
<for each already-committed change in the plan: "- <name>: <one_line_scope>">

Follow these steps, mirroring `.claude/skills/openspec-propose`'s own artifact-creation process:

1. If `openspec/changes/<name>/` does not yet exist, run `openspec new change "<name>"`. If it already exists (a prior run's crash left it here), skip this step and go straight to step 2 — do not overwrite what's already there without reading it first.
2. Run `openspec status --change "<name>" --json` to get the artifact build order (`applyRequires`, `artifacts`).
3. For each artifact in dependency order, run `openspec instructions <artifact-id> --change "<name>" --json`, read its `template`/`instruction`/`context`/`rules`, read any completed dependency artifacts for context, and write the artifact to its `resolvedOutputPath`. Do NOT copy `context`/`rules` blocks into the output file — they constrain what you write, they are not content for the file.
4. Apply these proposal-quality pre-checks as you write (from this repo's own `openspec-propose` skill — they are the three defect classes that most often drove FIX-FIRST review verdicts here):
   - **Pin load-bearing numbers in design.md.** Any threshold, band, cap, weight, tolerance, or split that changes scoring/behavior gets a concrete recommended default in a "Pinned implementation parameters" block — never "set during implementation."
   - **Add a doc-sync task to tasks.md** for any change touching this repo's application source: update every doc this repo's own docs-sweep list names as needing to stay in sync (see `cla.io/project-facts.md` ("Doc-sweep paths (five-path list)") for the exact path list; run `/cla:sync-context` to populate it; falls back to `references/project-context.md` if absent), with a grep-verify for retired symbols/keys/flags.
   - **On a MODIFIED requirement, carry the FULL final requirement text + ALL its existing scenarios forward** — read the active spec, copy every scenario, then add/adjust. Never write a diff-only MODIFIED block; `openspec` archive-sync REPLACES the whole requirement, so an omitted scenario is silently deleted.
5. Once every artifact required by `applyRequires` is `done` (re-check via `openspec status --change "<name>" --json`), run `openspec validate <name> --strict`.

**Terminal contract.** End with exactly one of:
- `done` — valid ONLY when `openspec validate <name> --strict` exited 0 AND you confirm `proposal.md`, `design.md`, `tasks.md`, and at least one `specs/*/spec.md` exist under `openspec/changes/<name>/`. State the validate command's exit status explicitly.
- `blocked` — state exactly what's missing or failing (a validate error, an ambiguous decision that needs a human call, etc.).

Do not claim `done` without that evidence — an unverified claim is treated as not done by the caller.
```

## Resume check (before dispatching)

Does `openspec/changes/<name>/proposal.md` already exist AND is it tracked (`git ls-files openspec/changes/<name>/proposal.md` non-empty)? If yes, this change is already committed from a prior run — skip it, move to the next change in the plan. If the directory exists but is **untracked** (a crash landed between authoring and commit), treat it as incomplete: instruct the dispatched agent to skip the `openspec new change` call (it errors on an existing directory) and go straight to `openspec status --change "<name>" --json` instead.

## Post-check (after dispatching, regardless of what the agent reports)

Confirm `openspec/changes/<name>/proposal.md`, `design.md`, `tasks.md`, and at least one `specs/*/spec.md` exist, and re-run `openspec validate <name> --strict` yourself. A `done` claim without this holding is treated as not done — finish it inline (or re-dispatch once) rather than trusting the report, same discipline `/cla:spec-to-pr`'s Implement delegate contract uses. The agent's `done`/`blocked` status is a signal, not a trusted fact.

## Commit + push (immediately, before starting the next change)

```
python3 .claude/plugins/cla/skills/spec-to-pr/scripts/git_state.py --expect-branch docs/propose-<batch-slug>
git add -- openspec/changes/<name>/
git commit -m "docs(openspec): propose <name>"
git push
```
`git push` (not just commit) is deliberate — a local-only commit still doesn't survive a dead disk; pushing after every change is what actually protects against a local-machine incident. **Then run the push post-check** (`references/phases.md`) before moving to the next change — an unverified push here is the exact silent-loss scenario this skill exists to prevent.
