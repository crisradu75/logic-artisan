# multi-spec — per-change authoring agent brief

Phase 3 dispatches one `Agent(subagent_type: "claude", model: "opus")` call per change, awaited sequentially. This file is the prompt template — fill in the bracketed parts from the change plan (`references/plan-schema.md`) and the source decisions file.

## Why Opus, why one-at-a-time

Proposal/design/tasks/specs authoring is the premise-setting step for a change — same bucket as a Review verdict, not rubric-application work. A cheaper model's failure mode here is systematically under-specified artifacts (unpinned load-bearing numbers, a missed MODIFIED-requirement scenario carry-forward, a wrong cross-reference), which is expensive to unwind — a full review-and-fix round downstream, or worse, silently propagated into a sibling change's cross-reference before anyone catches it. Sequential (not parallel) dispatch is required anyway by Phase 3's commit-before-next-change durability rule, and it has a second benefit: each change's agent can be handed the already-authored siblings' summaries, so a later change's cross-reference to an earlier one is correct from the start rather than only caught in Phase 4's batch review.

## Prompt template

```
You are authoring one OpenSpec change proposal in this repo (see `cla.io/overlays/multi-spec.md` for its monorepo shape, or `cla.io/project-facts.md`'s "Workspace shape" if populated). Do NOT assume a fixed package list — read the "Repo layout" section of the root `CLAUDE.md` for the authoritative current set of packages before referencing one in the proposal (the workspace gains packages over time; a hardcoded list drifts, and referencing a package that does not yet exist on the current tree seeds a false claim into the proposal).

**Change name:** <name>
**One-line scope:** <one_line_scope from the plan>
**Decisions this change implements (verbatim from the source decisions file — do not paraphrase):**
<verbatim text of decisions_covered, copied from the decisions file's numbered "Decisions" section>

**Already-authored sibling changes in this same batch** (for correct cross-references — read their proposal.md if you need more than this summary):
<for each already-committed change in the plan: "- <name>: <one_line_scope>">

Follow these steps, mirroring `.claude/skills/openspec-propose`'s own artifact-creation process:

1. If `openspec/changes/<name>/` does not yet exist, run `openspec new change "<name>"`. If it already exists (a prior run's crash left it here), skip this step and go straight to step 2 — do not overwrite what's already there without reading it first.
2. Run `openspec status --change "<name>" --json` to get the artifact build order (`applyRequires`, `artifacts`).
3. For each artifact in dependency order, run `openspec instructions <artifact-id> --change "<name>" --json`, read its `template`/`instruction`/`context`/`rules`, read any completed dependency artifacts for context, and write the artifact to its `resolvedOutputPath`. Do NOT copy `context`/`rules` blocks into the output file — they constrain what you write, they are not content for the file. Two artifacts are conditional, so "every artifact" does not mean all four:
   - **design.md only on a stock trigger:** a cross-cutting change, a new dependency or data model, security, performance or migration complexity, or real ambiguity. With none, write no design.md. With one, write it short, never restating the proposal or specs, and name the trigger in your report.
   - **No spec delta for a change with no externally visible behaviour change** (a refactor, tooling, docs): set `skip_specs: true` in `.openspec.yaml` instead. Never invent a requirement to satisfy validation.
   - **Read live specs overview-first:** `openspec list --specs`, then `openspec show <id> --type spec --json --no-scenarios`. Read in full, with scenarios, only the capabilities your delta touches.
4. Apply these pre-checks as you write:
   - **Stock limits:** proposal one page; one behaviour per ADDED requirement in ≤500 characters, detail in scenarios. They are spelled out in `openspec/config.yaml` `rules:` where the repo has them (cla-init prints the block).
   - **Every scenario the change adds, or whose text it changes, names its proof:** a tasks.md test task whose test carries a comment line `scenario: <spec> / <heading>` above it (after the language's comment token, e.g. `# scenario: cla-plugin / Authoring a scenario`), and the task names that marker; or a tasks.md line `manual: <heading>: <reason>`, naming the heading so a guard can match it. A pure heading rename and a scenario carried forward unchanged in a MODIFIED block are exempt.
   - **Scenario headings are unique within one spec**, so `<spec> / <heading>` names exactly one scenario. Before adding one, check the live spec and your delta for the same heading, and rename yours if it is taken.
   - **Pin load-bearing numbers, when design.md exists.** Any threshold, band, cap, weight, tolerance, or split that changes scoring/behavior gets a concrete recommended default in design.md — never "set during implementation." A change with no such number needs no pinned-parameters block.
   - **On a MODIFIED requirement, carry the FULL final requirement text + ALL its existing scenarios forward** — read the active spec, copy every scenario, then add/adjust. Never write a diff-only MODIFIED block; `openspec` archive-sync REPLACES the whole requirement, so an omitted scenario is silently deleted. Check your own block against the live requirement before you finish, by the procedure below. (Canonical copy, for whoever edits this next — not for you to open: `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/modified-block-retention.md`, `## Procedure`.)

     1. Parse `## RENAMED Requirements` in the **same delta file** and build the FROM->TO map.
     2. For each `### Requirement: <Name>` under `## MODIFIED Requirements`, resolve `<Name>` through that
        map to the name it carries **in the live spec**, then locate that requirement there.
     3. Enumerate `#### Scenario:` headings in the delta's block and in the live requirement's block.
        Block boundary: from the `### Requirement:` line to the next line beginning `### ` or `## `, or
        end of file.
     4. Report one line per compared requirement, including a clean one:

        `<capability>/<requirement name>: live N -> delta M (+K added, -J missing)`

        then, only when `K` or `J` is non-zero, one line per differing scenario, heading verbatim:
        `  - <live heading absent from the delta>` / `  + <delta heading absent from the live spec>`

     Adjudicate each missing scenario to exactly one of **renamed**, **intentionally removed**, or
     **dropped**. Only `dropped` is a finding, and it is **Critical** — it deletes a live `SHALL`.
     `intentionally removed` with no supporting sentence in the change's own artifacts is **Important**.
     Added-only (`J = 0`) is never a finding. **An unadjudicated flag is treated as `dropped`, not
     waived.** Nothing here refuses, halts, or edits a change; it flags, and a human adjudicates.
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
