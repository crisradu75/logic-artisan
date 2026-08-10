---
name: multi-spec
description: "Turn a shape-decision decisions file into a batch of full OpenSpec change proposals (proposal.md/design.md/tasks.md/specs/ each), authored and committed one change at a time so a local-machine crash or accidental delete never loses more than the change in flight, then reviewed once as a batch via review-change's 3-agent dispatch before opening a single PR. Stops at proposals-only — does not implement. Triggers on /cla:multi-spec or natural language like 'turn these decisions into changes', 'author all the proposals from this decisions file', 'batch-propose the shaped decisions'."
argument-hint: "[decisions-file-path | (empty = most recent under cla.io/decisions/)]"
---

# /cla:multi-spec — decisions file → batch of committed OpenSpec proposals

Automates a manual precedent set in this repo's own history (see `cla.io/overlays/multi-spec.md` for the named commit/PR): one shape-decision output authored out into N full OpenSpec change proposals, reviewed once as a batch, opened as one PR. **Proposals only** — implementation is `/cla:spec-to-pr` (per-change) or `/cla:multi-pr` (the whole produced sequence), invoked separately afterward.

**Resolving `${CLAUDE_PLUGIN_ROOT}`.** Commands in this skill and its reference
files name plugin files as `${CLAUDE_PLUGIN_ROOT}/...`. That placeholder is this
plugin's install directory, and Claude Code substitutes it into skill content --
but it is **not** an environment variable in the Bash tool. If you ever see the
literal text `${CLAUDE_PLUGIN_ROOT}` in a command you are about to run, resolve
it yourself first; never pass it through to a shell, where an unset variable
expands to nothing and the command silently runs against `/skills/...`.

**The durability requirement is the reason this skill exists as more than a loop over `openspec-propose`.** A batch of N proposal directories sitting uncommitted for the whole run is a real, already-realized loss mode in this repo's own history (see `cla.io/overlays/multi-spec.md`) while sitting untracked. Every phase below is ordered to keep the loss window to at most one change.

## Skill-level rules (hoisted — read first)

- **`<base-branch>` means THIS repo's default branch, resolved — never assumed.** See `${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/references/base-branch-resolution.md` (shared verbatim with `multi-lite`/`multi-pr`) for the resolution rule every command below that names `<base-branch>` depends on.

- **Commit each change immediately after authoring and validating it — never batch commits to the end.** One `git commit` (and `git push`) per change, before starting the next. This is not a style preference; it is the actual anti-data-loss mechanism.
- **Never run `git add -A`.** Path-scope every stage (per Phase, name the exact paths: the plan JSON, one `openspec/changes/<name>/`, or the whole `openspec/changes/` only in Phase 4's fixes commit — see `${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/references/bash-discipline.md`, the same hard rules bind here).
- **Verify `git_state.py --expect-branch docs/propose-<batch-slug>` before every commit multi-spec makes** (the plan-persist commit, each per-change commit, the review-fixes commit, the run-log commit) — any non-zero exit halts and surfaces via `AskUserQuestion`, never a special-cased "probably fine."
- **Verify every push actually reached the remote.** After each push anywhere in this skill, compare `git rev-parse HEAD` to `git ls-remote origin docs/propose-<batch-slug>` in Claude's own context. Mismatch → halt via `AskUserQuestion`, never silently retry. This skill's whole value is "a pushed commit survives a dead disk" — an unverified push would silently reproduce the exact loss scenario it exists to prevent. Full rationale: `references/phases.md`.
- **Per-change authoring dispatches to `Agent(subagent_type: "claude", model: "opus")`, one call per change, awaited sequentially — never parallel.** Sequential is what makes "commit before starting the next" possible; proposal authoring is judgment-critical (same tier as a Review verdict), not mechanical rubric work. Route every other dispatched agent per `${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/references/model-routing.md` (the single source of truth for model/effort). Effort is not independently dialed on the `Agent(...)` mechanism — do not introduce `Workflow` as a workaround.
- **This is a proposals-only skill.** Never invoke `Skill(cla:spec-to-pr)`, `Skill(cla:lite-pr)`, or `Skill(cla:multi-pr)` from inside `multi-spec` — point at them in the final report instead. Likewise, the batch review gate (Phase 4) always runs BEFORE the PR opens (Phase 5) — never the reverse.
- **Ignore harness `TaskCreate` nudges for the per-change authoring loop.** It is sequential by design — the loop itself is already linear, single-file progress tracking; duplicating it in `TaskCreate` adds noise, same rule `/cla:spec-to-pr` applies to its own Implement loop.
- **Run thin — keep raw material out of the parent context.** `multi-spec` IS an orchestrator (Phase 1's grouping judgment, Phase 3's per-change dispatch loop, Phase 4's batch review dispatch): delegate bulk raw-material handling to a sub-agent so only conclusions return, read file slices not whole files, `tail`/`head` large command output, batch independent tool calls into one message, prefer terse schema'd agent output over prose. Standing discipline across every phase below, not a per-trigger step. Full rules: `${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/references/runtime-rules.md`.

## Input resolution

Parse `$ARGUMENTS`:

- **A path is given** → use it directly; halt and report if it doesn't exist.
- **Empty, `cla.io/decisions/*.md` has ≥1 file** → default to the most-recently-modified file there. Announce `Mode: file (<path>, most recent)`.
- **Empty, `cla.io/decisions/` missing or empty** → infer the topic from the conversation, then run (or emulate) `Skill(cla:shape-decision)` on it and let it WRITE a real decisions file **with the user's explicit confirmation, per that skill's own "Persisting the decision" step.** Never proceed to Phase 1 from transient conversation state — the durability guarantee only holds if there is a committed decisions file to resume from. Announce `Mode: inferred-then-shaped (<path written>)`.

Read the resolved decisions file in full before Phase 1.

## Phase 1 — Discover the change plan

Derive an ordered change plan (each change's `name`, decisions covered, one-line scope, `depends_on`) from the file's own Sequencing section, or by grouping judgment when no such section exists — do not default to one change per decision. Full mechanics + the sub-Opus escalate-up rule: `references/phases.md`. Print the plan before authoring starts; hold it in working context only — **do not** write or commit it here (Phase 2 persists it, once the branch that its `batch_slug`/`branch` fields depend on actually exists).

## Phase 2 — Batch branch preflight, then persist the plan

All N changes land in **one** PR on **one** dedicated branch, `docs/propose-<batch-slug>` (not one branch per change). Full branch-slug derivation, preflight, and plan-persist-commit recipe: `references/phases.md`. This phase's first push **must** set the upstream (`-u`) — every push after it is bare.

## Phase 3 — Author each change, sequentially, committing as you go

For each change in the plan, in dependency order: resume-check it, dispatch the Opus authoring agent, post-check the evidence regardless of what it reports, then **commit and push immediately, before starting the next change** — this one-at-a-time commit is the load-bearing anti-data-loss property this skill exists for (a crash mid-batch loses at most the change in flight, never the whole batch). Full resume-check, dispatch prompt, post-check, and commit/push recipe: `references/authoring-brief.md`.

## Phase 4 — Batch review gate

Once every change is authored, validated, and committed, run **one** 3-agent review dispatch over the **whole batch** (same model routing as `review-change`'s checklist: Design Reviewer → opus, Task/Spec-and-Codebase → sonnet). **A batch of exactly one change skips the 3-agent dispatch** and goes straight to the single-change `review-change` checklist instead — there's no cross-change staleness class to catch. Apply every Critical/Important finding, re-validate, and commit the fixes as one follow-up commit **before Phase 5 opens the PR** — this ordering (review-then-PR) is load-bearing, never the reverse. Full dispatch mechanics, agent prompts, and the fix-application/commit recipe: `references/review-gate.md`.

## Phase 5 — Open the PR

Opening a PR is not a deployment action (same boundary `/cla:spec-to-pr`'s Ship phase relies on) — only merge/push-to-`<base-branch>`/publish are out of scope. Full PR-create recipe + the pre-create resume check: `references/phases.md`.

## Report

Emit a terminal report: batch slug, decisions file, PR URL, the change list (name + one-line scope + dependency order), the review verdict per change, and — the load-bearing next step — **point explicitly at `/cla:multi-pr` for the produced change list** (or `/cla:spec-to-pr <name>` / `/cla:lite-pr <name>` per-change) as the follow-on that actually implements them. `multi-spec` stopping here is deliberate, not a truncated run.


## Resume behavior

Every phase resumes from git-tracked repo state, never from a log or the plan file — the plan file is a convenience, not the durability backstop (same "derive from repo state" philosophy `/cla:spec-to-pr`'s `probe_state.py` already uses). Re-invoking `/cla:multi-spec` on the same decisions file picks up cleanly:

- Phase 1/2 — `references/plan-schema.md`'s "Resume read path" (plan file exists → load it, skip re-deriving) for the plan file, and `references/phases.md` Phase 2 for the branch-preflight resume (branch already exists/checked-out → resume, not collision).
- Phase 3 — `references/authoring-brief.md`'s resume check (tracked change dir → skip; untracked → resume authoring in place).
- Phase 4/5 — the resume notes in `references/review-gate.md` (Step 7) and `references/phases.md` (Phase 5).

## What this skill deliberately does not do

- Does not implement anything — no `Skill(cla:spec-to-pr)`, `Skill(cla:lite-pr)`, or `Skill(cla:multi-pr)` call. Proposing and implementing are different unattended-run shapes with different risk profiles; bundling them here would blur that boundary for no benefit.
- Does not merge the PR it opens, or push to `<base-branch>` directly.
- Does not build a bespoke resumable-state script — Phase 1's fallback grouping is genuinely open-ended reasoning over prose, so it stays inline/dispatched reasoning rather than a script. Nor does it keep a run ledger: its own was deleted unread, and resume re-derives state from `openspec/changes/` itself (see "Resume read path" in `references/plan-schema.md`).
- Does not build a `multi-spec-retro` analyzer skill yet — same "wait for enough runs" posture noted above.

## References

- `references/phases.md` — Phase 1/2/5 full mechanics, and the shared push post-check procedure used everywhere a push happens.
- `references/plan-schema.md` — the change-plan JSON shape, where it lives, and exactly what resume reads from it vs. re-derives from git.
- `references/authoring-brief.md` — Phase 3's full mechanics: the resume check, the per-change Opus dispatch prompt template, the post-check, and the commit/push recipe.
- `references/review-gate.md` — Phase 4's full mechanics: the batch adaptation of `review-change`'s checklist (agent prompts, model routing, verdict rubric) plus the fix-application/commit recipe.
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/references/model-routing.md` — model/effort routing single source of truth (reused verbatim, not forked).
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/references/bash-discipline.md` — the hard bash-shape rules binding every commit/stage call in this skill.
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/references/runtime-rules.md` — the thin-orchestrator runtime disciplines this skill follows throughout.
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/references/base-branch-resolution.md` — the `<base-branch>` resolution rule, shared verbatim with `multi-lite`/`multi-pr`.
- `${CLAUDE_PLUGIN_ROOT}/skills/review-change/references/checklist.md` — the single-change review workflow `references/review-gate.md` adapts to batch scope.
- `cla.io/overlays/multi-spec.md` — this repo's project-context overlay: the named precedent, the loss incident, and the grouping-judgment precedent.
