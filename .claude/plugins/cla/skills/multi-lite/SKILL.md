---
name: multi-lite
description: "Chains multiple /cla:lite-pr runs extracted from a decision-shaped markdown doc: pulls out every lite-pr-sized candidate, sequences them dependency-first (falling back to document order), confirms the plan once up front, then runs /cla:lite-pr on each in order — under the confirmed merge policy either merging every clean PR as the chain goes (recommended) or merging only a PR its dependents need, and quarantining a failed candidate plus its downstream subtree while continuing with the rest. Designed for long, unattended small-change runs off a single decisions/feedback doc. Triggers on /cla:multi-lite or natural language like 'extract all lite-pr candidates from this decision file and run them in sequence', 'chain these small changes end to end', 'lite-pr everything in this doc'."
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

To resolve it: the harness prepends a `Base directory for this skill: <absolute
path>` line when it loads a skill. The plugin root is that path with the trailing
`/skills/<skill-name>` removed. Failing that, take the absolute path of any file
you have already read from this plugin and cut it at the `.../plugins/cla`
segment. If you cannot establish it either way, say so and stop rather than
guessing a path.

Measured, so you know which half is load-bearing: a `SKILL.md` body arrives with
the placeholder ALREADY substituted, so commands written here are safe. A
`references/` file is opened with `Read`, which returns the raw bytes — the
placeholder arrives literal there, and that is the case this rule exists for.

This is the `lite-pr` analogue of `/cla:multi-pr` (which chains `/cla:spec-to-pr` over OpenSpec changes). Use `multi-lite` when the work is a batch of **small** changes that don't need OpenSpec artifacts — the same "which workflow" judgment call `lite-pr` vs `spec-to-pr` already asks, applied to a batch.

**This skill does not reimplement `/cla:lite-pr`.** Every actual Explore/Plan/Implement/Test/Ship/Review step for a single candidate is `/cla:lite-pr`'s job — invoke it via `Skill(cla:lite-pr, args="<one-line description>")`. `multi-lite` owns exactly four things `/cla:lite-pr` doesn't: **candidate extraction**, **sequencing + the upfront confirmation gate**, **policy-driven merging**, and **failure quarantine + the final report**.

## Skill-level rules (hoisted — read first)

- **`<base-branch>` means THIS repo's default branch, resolved — never assumed.** See `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/base-branch-resolution.md` (shared verbatim with `multi-pr`/`multi-spec`) for the resolution rule every command below that names `<base-branch>` depends on.

- **This is a long unattended run. Get the plan confirmed BEFORE the chain starts, not mid-chain.** The whole point is that the user can walk away. Extract, sequence, and confirm the candidate list in Phase 1; then run start-to-finish with no "ready to continue?" pauses between candidates (matching `/cla:lite-pr`'s own continuous-by-design autonomy — it has no inter-phase approval gate).
- **Never end a turn with nothing in flight.** The no-pause rule forbids *asking permission* to continue. This failure asks nothing: the orchestrator announces the next candidate, ends the turn believing it is continuing, and the chain does not pause — it **stops**, silently, until a human notices. The distinction that matters is not "did I ask a question" but **"is there a pending event that will re-invoke this session?"** A backgrounded `Agent` or `Bash(run_in_background: true)` is safe, because its completion notification wakes the session; so is the ordinary `Skill(cla:lite-pr, args="…")` call this loop already makes, for the simpler reason that a tool call does not end the turn at all. An idle turn has no wake signal. **The mechanical form, because the judgement version has lost in practice: status text and the next tool call go in the SAME message.** If you have no tool call to pair the text with, the candidate is not over — start the next one instead of narrating the last. Ending a turn is legitimate in exactly two cases, the same two `${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/SKILL.md` names: a backgrounded dispatch is genuinely in flight, or the run is complete. Nothing else — **announcing the next step is not a mechanism**, and "Is there a tool call in this message?" needs no judgement. A blocker is not a third case: this skill quarantines a failed candidate and continues with the independents rather than waiting, and anything that genuinely needs the user goes out as an `AskUserQuestion`, which is itself a tool call. Where a seam genuinely has nothing to dispatch, arm a watchdog before ending the message — `Bash(command: "python3 -c \"import time; time.sleep(1500)\"", run_in_background: true)`, spelled with `python3` because `sleep` matches no pattern in `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/required-permissions.json` and would prompt, which is the stall it exists to prevent — and re-arm it whenever it fires while work remains. Source for the cost of this gap: GitHub issue #130, on `/cla:multi-pr`, which shares this loop shape.
- **Runs from the primary clone on `<base-branch>` by default — that is what keeps its base management correct.** `multi-lite` does many real commits/pushes/PRs (and, for dependencies, merges) back-to-back, so — exactly like `/cla:multi-pr` — it operates on `<base-branch>` in the primary clone and syncs between candidates with `git checkout <base-branch>` then `git pull` (two separate commands). **A linked worktree cannot check out `<base-branch>`** (git refuses — the primary clone already holds it), so the base-branch-checkout steps below are valid only from the primary clone; do not "start this in a worktree." If another live session contends for the primary clone, pivot **reactively** to a dedicated worktree the way `/cla:multi-pr` does — `git fetch origin <base-branch>` then `git worktree add .claude/worktrees/<id> -b <branch> origin/<base-branch>` (two separate commands), basing each candidate off `origin/<base-branch>` rather than checking out `<base-branch>`. In that reactive-worktree case the run may not end on `<base-branch>`, so the run-log commit (see `references/phase4-and-log.md`) is best-effort and may be skipped.
- **Never run `git add -A`.** Same rule as `/cla:lite-pr`/`/cla:spec-to-pr`, inherited transitively through every `Skill(cla:lite-pr, ...)` call, and equally binding on any direct git command (merges, checkouts, syncs) `multi-lite` itself runs. Path-scope every stage per `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/bash-discipline.md`.
- **Verify `git_state` before every commit `multi-lite` itself makes, and verify each push landed.** Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/git_state.py [--expect-branch <name>]` before the enforcement-round commit (Phase 3 step 7) and the run-log commit (a non-zero exit halts and surfaces); after a push, confirm `git rev-parse HEAD` matches `git ls-remote origin <branch>` (compared in-context). The per-candidate `/cla:lite-pr` runs do their own git_state checks internally.
- **Merging is a real, hard-to-reverse action against shared state** — and `/cla:lite-pr` deliberately never does it. `multi-lite` merges only under the merge policy confirmed at the Phase 1 gate, and that authorization is scoped to this one run, not a standing permission. Two policies exist, and every file in this skill uses exactly these names:
  - **`merge-each-clean`** (the recommended default at the gate) — merge every candidate that passes step 8's clean check, dependency or not, as soon as it passes. Each later candidate then branches off a base that already holds every earlier merge, so its own Test phase runs on the combined tree, and the run ends with open PRs only for candidates that could not be merged, each carrying its reason.
  - **`merge-dependencies-only`** — merge only a candidate a later candidate needs merged; every other PR is left open for the user. A candidate needs merging when a later one `depends_on` it, **or** when it moves shared environment state (a migration, seeded fixture data, a provisioning step), since that state has already moved for every later branch. Phase 1a routes out every item the doc says moves shared state, and shows its derivation for each admitted candidate. An implementation can still add a migration or seed nobody predicted, so step 8a also checks each PR's changed files for one and merges it as a merge-before-next edge.
  - **The explicit-autonomy override applies only a policy the invocation names.** Naming none means `merge-dependencies-only`, because an override that silently widened merging would turn a pre-confirmed plan into an authorization nobody gave.
  - **Every merge, under either policy, passes step 8's pre-merge checks first.** They include the full Test gate on the exact head being merged, because `/cla:lite-pr` commits its review fixes after its own Test phase. A merge counts only once GitHub reports it `MERGED` and the local base contains it. A host that refuses `gh pr merge` stops all further merging for the run (see `references/candidate-loop.md` step 8).
- **A failure quarantines its own dependency subtree, not the whole chain** (this is DIFFERENT from `/cla:multi-pr`'s whole-chain-halt on an unresolved issue — preserve this downstream-only semantics; never substitute whole-chain-halt behavior here). A candidate fails one of three ways: `/cla:lite-pr`'s Test-phase halt (it never opened a PR), an unresolved **Critical/Important review finding** that survives the enforcement round (Phase 3 step 7), or a **merge that could not happen** for a candidate something depends on (Phase 3 step 8: a pre-merge check failed, or the host refused the merge). Each quarantines that candidate + everything downstream and continues with independents. A merge that could not happen for a candidate nothing depends on quarantines nothing — its PR is left open and flagged. Only a corrupt/unresolvable git state halts the whole run.
- **`multi-lite` does not run its own `review-pr` pass — it *enforces* `/cla:lite-pr`'s.** `/cla:lite-pr`'s Review phase opens the PR even when it *defers* Critical/Important findings (it never halts on them). `multi-lite` is the layer that refuses to let a deferred Critical/Important finding ride silently into a merge — see Phase 3 step 7. This is the scaled-down analogue of `/cla:multi-pr`'s no-unresolved-issues escalation: **one additional enforcement round on the findings `/cla:lite-pr` deferred** (not a re-run of `lite-pr`'s own already-spent fix round, and not a loop). **Never merge a candidate carrying an unresolved Critical/Important finding** — that candidate is quarantined or left open-with-a-flag instead (Phase 3 step 7).
- **The run-notes ledger (`cla.io/retro/multi-lite-run-notes-<date>.md`) is the deterministic identity source, not a guess.** Branch/PR are captured after the fact the moment `/cla:lite-pr` opens a PR (Phase 3 step 6), and every later resume/merge decision keys off this file's recorded values — `multi-lite` can't predict a candidate's branch name up front the way `/cla:multi-pr` can (branch naming is `commit-push-pr`'s call, derived from content), so a re-derived guess is never a substitute for reading this file back. **An open PR is not automatically done on resume.** The ledger also records each candidate's `head_sha`, its deferred findings, and its step 7 `review` outcome. An open PR whose `review` is `clean` re-enters step 8 instead of being skipped. Otherwise a run interrupted between step 7 and step 8 leaves a clean PR open that the policy promised to merge. **Resume never infers clean:** `/cla:lite-pr` keeps deferred findings only in context, so a candidate with no recorded findings resumes as `unresolved`.
- **Run thin — keep raw material out of context.** `multi-lite` is an orchestrator (chains `/cla:lite-pr` across candidates, layering merge/quarantine/review-enforcement logic around it) — apply `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/runtime-rules.md`'s delegation, I/O-hygiene, batching, and terse-output disciplines throughout the run, not just at one trigger point.

## Input resolution

Parse `$ARGUMENTS`:

- **A path is given** → use it directly; halt and report if it doesn't exist.
- **Empty, `cla.io/decisions/*.md` has ≥1 file** → default to the most-recently-modified one there (mtime is a convenience default, not exact). Announce `Mode: file (<path>, most recent)`.
- **Empty, `cla.io/decisions/` missing or empty** → infer the topic from conversation context and ask once whether to shape it first (`Skill(cla:shape-decision)`) or point at an existing doc — don't guess a candidate list from transient conversation state.

**Input contract.** Any markdown doc with a numbered-decision / candidate-list shape and `/cla:lite-pr`-flavored "next step" cues is valid — not just `/cla:shape-decision` output; a `/cla:feedback`-style consolidated doc shaped the same way works too. Read the resolved doc in full before Phase 1.

## Phase 0 — Bootstrap + working-tree precheck

**Read `references/bootstrap-and-tracking.md` first** for the full precheck recipe. Run before Phase 1: the permissions check (apply on approval) and `git_state.py` from `spec-to-pr/scripts/` — resolve any non-zero exit before continuing; a dirty/mid-op tree poisons every subsequent candidate. Then confirm HEAD is on a clean, up-to-date `<base-branch>` (per the hoisted base-management rule) so the first candidate branches off a current base.

## Phase 1 — Extract candidates, sequence, and confirm (the one gate)

**Read `references/candidate-extraction.md` first** for the extraction filter, the sequencing rule, and the exact confirmation-gate question shape. Mechanically: (1a) pull every lite-pr-sized candidate out of the doc as `{id, one-line description, depends_on}`, routing non-lite items to an explicit out-of-scope list; (1b) order by `depends_on` first, document order as tiebreak — never group candidates into one PR; (1c) confirm the derived plan and the merge policy (`merge-each-clean` recommended, or `merge-dependencies-only`) once via `AskUserQuestion` before any `/cla:lite-pr` runs. This is the run's only stop (see hoisted rules), pre-confirmed only under an explicit-autonomy override.

## Phase 2 — Task tracking + the run-notes ledger

**Read `references/bootstrap-and-tracking.md`** (same file as Phase 0) for the `TaskCreate` setup and the run-notes-file recipe. The ledger invariant is stated in the hoisted rules above — this phase is where the file is created and the tasks laid down.

## Phase 3 — Per-candidate loop

**Read `references/candidate-loop.md` first** for the full 8-step per-candidate procedure (quarantine-skip check, ledger-keyed resume check, base checkout, the `/cla:lite-pr` invocation, outcome classification, identifier capture, the review-finding enforcement round, and the policy-driven merge with its pre-merge checks) plus the resume mechanics it enables. The step order is fixed; do not reorder or skip a step for a non-quarantined candidate. The correctness invariants governing this loop — merge-authorization scope, downstream-only quarantine, the enforcement-round boundary, ledger-keyed identifier capture — are stated in the hoisted rules above and bind every iteration even without re-reading the reference.

## Phase 4 — Final report

**Read `references/phase4-and-log.md` first** for the exact report section shape (merge-policy / shipped-and-merged / shipped-and-left-open / failed / blocked-by-upstream / review-fix-rounds-run / out-of-scope / next-steps) and the run-notes commit. Emit the report after every candidate has been run, merged or left open per the confirmed policy, quarantined, or skipped; the commit is best-effort and non-fatal — it never blocks the run.

## Resume behavior

Re-invoking `/cla:multi-lite` on the same doc after an interruption picks up cleanly, keyed off the run-notes ledger (the hoisted-rule invariant above). See `references/candidate-loop.md` "Resume mechanics" for the full behavior — quarantine re-derivation, the same-session-vs-fresh-session confirmation-skip rule, and the degraded best-effort fallback when the ledger file was lost.

## What this skill deliberately does not do

- Does not reimplement Explore/Plan/Implement/Test/Ship/Review — that's `/cla:lite-pr`'s job, invoked as a sub-skill. It runs no `review-pr` pass of its own; it only *enforces* the deferred Critical/Important findings from `/cla:lite-pr`'s own single pass (Phase 3 step 7), with one bounded additional enforcement round.
- Does not merge anything the confirmed Phase 1 policy does not authorize. Under `merge-dependencies-only` an independent candidate's PR is left open for the user; under `merge-each-clean` it merges once clean. Neither policy merges a candidate that fails step 8's clean check.
- Does not auto-rebase a conflicting PR. A rebase changes the code that was tested and reviewed, so a conflicting candidate is left open and flagged instead.
- Does not group multiple candidates into one PR (that's `/cla:multi-spec`'s grouping model for OpenSpec changes) — one candidate, one `/cla:lite-pr`, one PR.
- Does not force a non-lite item through `lite-pr` — it flags it out of scope and points at `/cla:spec-to-pr`/`/cla:multi-spec` instead.
- Does not build a bespoke sequencing script — candidate extraction and ordering are open-ended reasoning over prose, done inline (the same choice `/cla:multi-pr` and `/cla:multi-spec` make in their own Phase 1).
- Does not build a `multi-lite-retro` analyzer yet — log-only until enough runs accumulate.

## References

- `${CLAUDE_PLUGIN_ROOT}/skills/lite-pr/SKILL.md` — the single-candidate workflow this skill chains; its Test-phase halt and Review scope define what "failed" means in Phase 3.
- `${CLAUDE_PLUGIN_ROOT}/skills/multi-pr/SKILL.md` — the `spec-to-pr` analogue; source of the merge-policy gate, first-refusal-is-the-answer, autonomy-override, and worktree-pivot patterns reused here.
- `${CLAUDE_PLUGIN_ROOT}/skills/multi-spec/SKILL.md` — the inline-reasoning-over-prose precedent for extraction/sequencing without a bespoke script.
- `references/bootstrap-and-tracking.md` — Phase 0's bootstrap/precheck recipe and Phase 2's `TaskCreate`/run-notes-ledger setup recipe (mandatory-read from both stubs).
- `references/candidate-extraction.md` — Phase 1's extraction filter, sequencing rule, and confirmation-gate question shape (mandatory-read from the Phase 1 stub).
- `references/candidate-loop.md` — Phase 3's 8-step per-candidate procedure and the resume mechanics it enables (mandatory-read from the Phase 3 stub and the Resume-behavior section).
- `references/phase4-and-log.md` — the Phase 4 final-report shape and the run-notes commit (mandatory-read from the Phase 4 stub).
- `${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/git_state.py` — reused directly for the Phase 0 precheck (a `spec-to-pr`/`multi-pr` bootstrap script, not `lite-pr`'s).
- `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/required-permissions.json` — the pattern set the Phase 0 permissions check compares against.
- `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/bash-discipline.md` — the hard bash-shape rules binding every git command this skill runs.
- `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/runtime-rules.md` — the thin-orchestrator runtime disciplines this skill follows as an orchestrator (pointed at from the hoisted rules).
- `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/base-branch-resolution.md` — the `<base-branch>` resolution rule, shared verbatim with `multi-pr`/`multi-spec`.
