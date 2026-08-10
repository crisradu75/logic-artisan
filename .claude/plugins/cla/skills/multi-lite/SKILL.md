---
name: multi-lite
description: "Chains multiple /cla:lite-pr runs extracted from a decision-shaped markdown doc: pulls out every lite-pr-sized candidate, sequences them dependency-first (falling back to document order), confirms the plan once up front, then runs /cla:lite-pr on each in order — merging a PR before its dependents but leaving independent PRs open, and quarantining a failed candidate plus its downstream subtree while continuing with the rest. Designed for long, unattended small-change runs off a single decisions/feedback doc. Triggers on /cla:multi-lite or natural language like 'extract all lite-pr candidates from this decision file and run them in sequence', 'chain these small changes end to end', 'lite-pr everything in this doc'."
argument-hint: "[decision-shaped-doc-path | (empty = most recent under cla.io/decisions/)]"
# Opens and merges pull requests unattended, so it must never self-trigger on a
# description match — only an explicit `/cla:multi-lite` starts it. Safe to set:
# this is a top-level entry point that CALLS `Skill(cla:lite-pr)` (which stays
# model-invocable); nothing invokes multi-lite itself. Also keeps this long
# description out of the always-loaded skill listing until the command is typed.
disable-model-invocation: true
---

# /cla:multi-lite — chain multiple lite-pr runs from one decision-shaped doc

Orchestrates `/cla:lite-pr` across a **sequence** of small candidates extracted from a single decision-shaped markdown doc. Where `/cla:lite-pr` drives one small change from description to an opened PR and then stops, `multi-lite` adds the layer on top: extract every lite-pr-sized candidate the doc describes, figure out what order they must run in, confirm that plan once, run the full `/cla:lite-pr` workflow on each, and keep going through the whole set unattended — serializing only the genuine dependencies and quarantining a failure without abandoning the independents.

**Resolving `${CLAUDE_PLUGIN_ROOT}`.** Commands in this skill and its reference
files name plugin files as `${CLAUDE_PLUGIN_ROOT}/...`. That placeholder is this
plugin's install directory, and Claude Code substitutes it into skill content --
but it is **not** an environment variable in the Bash tool. If you ever see the
literal text `${CLAUDE_PLUGIN_ROOT}` in a command you are about to run, resolve
it yourself first; never pass it through to a shell, where an unset variable
expands to nothing and the command silently runs against `/skills/...`.

This is the `lite-pr` analogue of `/cla:multi-pr` (which chains `/cla:spec-to-pr` over OpenSpec changes). Use `multi-lite` when the work is a batch of **small** changes that don't need OpenSpec artifacts — the same "which workflow" judgment call `lite-pr` vs `spec-to-pr` already asks, applied to a batch.

**This skill does not reimplement `/cla:lite-pr`.** Every actual Explore/Plan/Implement/Test/Ship/Review step for a single candidate is `/cla:lite-pr`'s job — invoke it via `Skill(cla:lite-pr, args="<one-line description>")`. `multi-lite` owns exactly four things `/cla:lite-pr` doesn't: **candidate extraction**, **sequencing + the upfront confirmation gate**, **dependency-aware merge-before-dependents**, and **failure quarantine + the final report**.

## Skill-level rules (hoisted — read first)

- **`<base-branch>` means THIS repo's default branch, resolved — never assumed.** See `${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/references/base-branch-resolution.md` (shared verbatim with `multi-pr`/`multi-spec`) for the resolution rule every command below that names `<base-branch>` depends on.

- **This is a long unattended run. Get the plan confirmed BEFORE the chain starts, not mid-chain.** The whole point is that the user can walk away. Extract, sequence, and confirm the candidate list in Phase 1; then run start-to-finish with no "ready to continue?" pauses between candidates (matching `/cla:lite-pr`'s own continuous-by-design autonomy — it has no inter-phase approval gate).
- **Runs from the primary clone on `<base-branch>` by default — that is what keeps its base management correct.** `multi-lite` does many real commits/pushes/PRs (and, for dependencies, merges) back-to-back, so — exactly like `/cla:multi-pr` — it operates on `<base-branch>` in the primary clone and syncs between candidates with `git checkout <base-branch>` then `git pull` (two separate commands). **A linked worktree cannot check out `<base-branch>`** (git refuses — the primary clone already holds it), so the base-branch-checkout steps below are valid only from the primary clone; do not "start this in a worktree." If another live session contends for the primary clone, pivot **reactively** to a dedicated worktree the way `/cla:multi-pr` does — `git fetch origin <base-branch>` then `git worktree add .claude/worktrees/<id> -b <branch> origin/<base-branch>` (two separate commands), basing each candidate off `origin/<base-branch>` rather than checking out `<base-branch>`. In that reactive-worktree case the run may not end on `<base-branch>`, so the run-log commit (see `references/phase4-and-log.md`) is best-effort and may be skipped.
- **Never run `git add -A`.** Same rule as `/cla:lite-pr`/`/cla:spec-to-pr`, inherited transitively through every `Skill(cla:lite-pr, ...)` call, and equally binding on any direct git command (merges, checkouts, syncs) `multi-lite` itself runs. Path-scope every stage per `${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/references/bash-discipline.md`.
- **Verify `git_state` before every commit `multi-lite` itself makes, and verify each push landed.** Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/scripts/git_state.py [--expect-branch <name>]` before the enforcement-round commit (Phase 3 step 7) and the run-log commit (a non-zero exit halts and surfaces); after a push, confirm `git rev-parse HEAD` matches `git ls-remote origin <branch>` (compared in-context). The per-candidate `/cla:lite-pr` runs do their own git_state checks internally.
- **Merging is a real, hard-to-reverse action against shared state** — and `/cla:lite-pr` deliberately never does it. `multi-lite` is allowed to merge **only** a candidate that a later candidate genuinely depends on, and only because the confirmed Phase 1 plan authorized that dependency edge for this run. An independent candidate's PR is always left open for the user to merge. This authorization is scoped to this one run, not a standing permission.
- **A failure quarantines its own dependency subtree, not the whole chain** (this is DIFFERENT from `/cla:multi-pr`'s whole-chain-halt on an unresolved issue — preserve this downstream-only semantics; never substitute whole-chain-halt behavior here). A candidate fails one of two ways: `/cla:lite-pr`'s Test-phase halt (it never opened a PR), or an unresolved **Critical/Important review finding** that survives the enforcement round (Phase 3 step 7). Either quarantines that candidate + everything downstream and continues with independents. Only a corrupt/unresolvable git state halts the whole run.
- **`multi-lite` does not run its own `review-pr` pass — it *enforces* `/cla:lite-pr`'s.** `/cla:lite-pr`'s Review phase opens the PR even when it *defers* Critical/Important findings (it never halts on them). `multi-lite` is the layer that refuses to let a deferred Critical/Important finding ride silently into a merge — see Phase 3 step 7. This is the scaled-down analogue of `/cla:multi-pr`'s no-unresolved-issues escalation: **one additional enforcement round on the findings `/cla:lite-pr` deferred** (not a re-run of `lite-pr`'s own already-spent fix round, and not a loop). **Never merge a candidate carrying an unresolved Critical/Important finding** — that candidate is quarantined or left open-with-a-flag instead (Phase 3 step 7).
- **The run-notes ledger (`cla.io/retro/multi-lite-run-notes-<date>.md`) is the deterministic identity source, not a guess.** Branch/PR are captured after the fact the moment `/cla:lite-pr` opens a PR (Phase 3 step 6), and every later resume/merge decision keys off this file's recorded values — `multi-lite` can't predict a candidate's branch name up front the way `/cla:multi-pr` can (branch naming is `commit-push-pr`'s call, derived from content), so a re-derived guess is never a substitute for reading this file back.
- **Run thin — keep raw material out of context.** `multi-lite` is an orchestrator (chains `/cla:lite-pr` across candidates, layering merge/quarantine/review-enforcement logic around it) — apply `${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/references/runtime-rules.md`'s delegation, I/O-hygiene, batching, and terse-output disciplines throughout the run, not just at one trigger point.

## Input resolution

Parse `$ARGUMENTS`:

- **A path is given** → use it directly; halt and report if it doesn't exist.
- **Empty, `cla.io/decisions/*.md` has ≥1 file** → default to the most-recently-modified one there (mtime is a convenience default, not exact). Announce `Mode: file (<path>, most recent)`.
- **Empty, `cla.io/decisions/` missing or empty** → infer the topic from conversation context and ask once whether to shape it first (`Skill(cla:shape-decision)`) or point at an existing doc — don't guess a candidate list from transient conversation state.

**Input contract.** Any markdown doc with a numbered-decision / candidate-list shape and `/cla:lite-pr`-flavored "next step" cues is valid — not just `/cla:shape-decision` output; a `/cla:feedback`-style consolidated doc shaped the same way works too. Read the resolved doc in full before Phase 1.

## Phase 0 — Bootstrap + working-tree precheck

**Read `references/bootstrap-and-tracking.md` first** for the full precheck recipe. Run before Phase 1: the permissions check (apply on approval) and `git_state.py` from `spec-to-pr/scripts/` — resolve any non-zero exit before continuing; a dirty/mid-op tree poisons every subsequent candidate. Then confirm HEAD is on a clean, up-to-date `<base-branch>` (per the hoisted base-management rule) so the first candidate branches off a current base.

## Phase 1 — Extract candidates, sequence, and confirm (the one gate)

**Read `references/candidate-extraction.md` first** for the extraction filter, the sequencing rule, and the exact confirmation-gate question shape. Mechanically: (1a) pull every lite-pr-sized candidate out of the doc as `{id, one-line description, depends_on}`, routing non-lite items to an explicit out-of-scope list; (1b) order by `depends_on` first, document order as tiebreak — never group candidates into one PR; (1c) confirm the derived plan once via `AskUserQuestion` before any `/cla:lite-pr` runs. This is the run's only stop (see hoisted rules), pre-confirmed only under an explicit-autonomy override.

## Phase 2 — Task tracking + the run-notes ledger

**Read `references/bootstrap-and-tracking.md`** (same file as Phase 0) for the `TaskCreate` setup and the run-notes-file recipe. The ledger invariant is stated in the hoisted rules above — this phase is where the file is created and the tasks laid down.

## Phase 3 — Per-candidate loop

**Read `references/candidate-loop.md` first** for the full 8-step per-candidate procedure (quarantine-skip check, ledger-keyed resume check, base checkout, the `/cla:lite-pr` invocation, outcome classification, identifier capture, the review-finding enforcement round, and the conditional merge) plus the resume mechanics it enables. The step order is fixed; do not reorder or skip a step for a non-quarantined candidate. The correctness invariants governing this loop — merge-authorization scope, downstream-only quarantine, the enforcement-round boundary, ledger-keyed identifier capture — are stated in the hoisted rules above and bind every iteration even without re-reading the reference.

## Phase 4 — Final report

**Read `references/phase4-and-log.md` first** for the exact report section shape (shipped-and-merged / shipped-and-left-open / failed / blocked-by-upstream / review-fix-rounds-run / out-of-scope / next-steps) and the run-notes commit. Emit the report after every candidate has been run, merged-if-a-dependency, quarantined, or skipped; the commit is best-effort and non-fatal — it never blocks the run.

## Resume behavior

Re-invoking `/cla:multi-lite` on the same doc after an interruption picks up cleanly, keyed off the run-notes ledger (the hoisted-rule invariant above). See `references/candidate-loop.md` "Resume mechanics" for the full behavior — quarantine re-derivation, the same-session-vs-fresh-session confirmation-skip rule, and the degraded best-effort fallback when the ledger file was lost.

## What this skill deliberately does not do

- Does not reimplement Explore/Plan/Implement/Test/Ship/Review — that's `/cla:lite-pr`'s job, invoked as a sub-skill. It runs no `review-pr` pass of its own; it only *enforces* the deferred Critical/Important findings from `/cla:lite-pr`'s own single pass (Phase 3 step 7), with one bounded additional enforcement round.
- Does not merge an **independent** candidate's PR — only a candidate a later one genuinely depends on, and only under the confirmed Phase 1 plan. Independents are always left open for the user.
- Does not group multiple candidates into one PR (that's `/cla:multi-spec`'s grouping model for OpenSpec changes) — one candidate, one `/cla:lite-pr`, one PR.
- Does not force a non-lite item through `lite-pr` — it flags it out of scope and points at `/cla:spec-to-pr`/`/cla:multi-spec` instead.
- Does not build a bespoke sequencing script — candidate extraction and ordering are open-ended reasoning over prose, done inline (the same choice `/cla:multi-pr` and `/cla:multi-spec` make in their own Phase 1).
- Does not build a `multi-lite-retro` analyzer yet — log-only until enough runs accumulate.

## References

- `${CLAUDE_PLUGIN_ROOT}/skills/lite-pr/SKILL.md` — the single-candidate workflow this skill chains; its Test-phase halt and Review scope define what "failed" means in Phase 3.
- `${CLAUDE_PLUGIN_ROOT}/skills/multi-pr/SKILL.md` — the `spec-to-pr` analogue; source of the merge-before-dependents, autonomy-override, and worktree-pivot patterns reused here.
- `${CLAUDE_PLUGIN_ROOT}/skills/multi-spec/SKILL.md` — the inline-reasoning-over-prose precedent for extraction/sequencing without a bespoke script.
- `references/bootstrap-and-tracking.md` — Phase 0's bootstrap/precheck recipe and Phase 2's `TaskCreate`/run-notes-ledger setup recipe (mandatory-read from both stubs).
- `references/candidate-extraction.md` — Phase 1's extraction filter, sequencing rule, and confirmation-gate question shape (mandatory-read from the Phase 1 stub).
- `references/candidate-loop.md` — Phase 3's 8-step per-candidate procedure and the resume mechanics it enables (mandatory-read from the Phase 3 stub and the Resume-behavior section).
- `references/phase4-and-log.md` — the Phase 4 final-report shape and the run-notes commit (mandatory-read from the Phase 4 stub).
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/scripts/git_state.py` — reused directly for the Phase 0 precheck (a `spec-to-pr`/`multi-pr` bootstrap script, not `lite-pr`'s).
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/references/required-permissions.json` — the pattern set the Phase 0 permissions check compares against.
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/references/bash-discipline.md` — the hard bash-shape rules binding every git command this skill runs.
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/references/runtime-rules.md` — the thin-orchestrator runtime disciplines this skill follows as an orchestrator (pointed at from the hoisted rules).
- `${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/references/base-branch-resolution.md` — the `<base-branch>` resolution rule, shared verbatim with `multi-pr`/`multi-spec`.
