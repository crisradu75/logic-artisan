---
name: multi-pr
description: "Chains multiple OpenSpec changes end-to-end: determines implementation order, runs /cla:spec-to-pr on each change in sequence, enforces that every Critical/Important review finding is actually fixed (never left as a deferred TODO) before moving on, lands the chain per the confirmed merge policy (merge each PR before its dependents, or stack each dependent PR on its parent when merging is unavailable or deliberately deferred), and finishes with a full repo cleanup pass. Designed for long, unattended multi-change runs. Triggers on /cla:multi-pr or natural language like 'drive all my openspec changes to PRs', 'chain these changes end to end', 'work through every open change and merge as you go', 'run spec-to-pr on everything'."
argument-hint: "[change-name-1 change-name-2 ... | (empty = auto-discover every open change)]"
# Merges pull requests, so it must never self-trigger on a description match —
# only an explicit `/cla:multi-pr` starts it. Safe to set: nothing invokes this
# skill programmatically (it is a top-level entry point that CALLS
# `Skill(cla:spec-to-pr)`, which stays model-invocable), and `/cla:multi-spec`
# explicitly forbids invoking it. Also keeps this long description out of the
# always-loaded skill listing until the command is actually typed.
disable-model-invocation: true
---

# /cla:multi-pr — chain multiple OpenSpec changes to landed PRs

Orchestrates `/cla:spec-to-pr` across a **sequence** of OpenSpec changes rather than one. Where `/cla:spec-to-pr` drives a single change from idea to an opened, archived PR and then stops, `multi-pr` adds the layer on top: figure out which order the open changes must ship in, run the full `/cla:spec-to-pr` workflow on each one, make sure nothing gets left half-resolved, give every dependent its parent's code before starting it (a merge under the default policy; a stacked branch under the stacked one), and end with a clean repo. This is the skill for "I'm about to be away for a few hours — take every open change to done."

**This skill does not reimplement `/cla:spec-to-pr`.** Every actual propose/review/implement/test/ship/revise/archive step for a single change is `/cla:spec-to-pr`'s job — invoke it via `Skill(cla:spec-to-pr, args="<change-name> ...")`. `multi-pr` owns exactly four things `/cla:spec-to-pr` doesn't: **sequencing**, **the upfront confirmation gate**, **the no-unresolved-issues escalation**, and **inter-change landing (merge or stack) + final cleanup**.

## Skill-level rules (hoisted — read first)

- **`<base-branch>` means THIS repo's default branch, resolved — never assumed.** See `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/base-branch-resolution.md` (shared verbatim with `multi-lite`/`multi-spec`) for the resolution rule every command below that names `<base-branch>` depends on.

- **This is a long unattended run. Get every blocking question answered BEFORE the chain starts, not mid-chain.** A clarifying question fired three changes in defeats the purpose — see Phase 1's pre-flight gate below. Once answered, run start-to-finish with no "ready to continue?" pauses between changes, mirroring `/cla:spec-to-pr`'s own autonomy-gate contract one level up.
- **"No unresolved issues, at ANY severity" is the default policy — stricter than `/cla:spec-to-pr`'s own default** (which accepts Deferred-Known-Issue + `TODO.md` Suggestion residue as done). Neither is acceptable here unless the user's Phase 1 answer explicitly picks a looser alternative — there's no point in the run where the user comes back to triage a leftover list themselves.
- **Never run `git add -A`.** Same rule as `/cla:spec-to-pr`, inherited transitively through every `Skill(cla:spec-to-pr, ...)` call this skill makes, and equally binding on any direct git command `multi-pr` itself runs (merges, branch cleanup, prunes).
- **Verify `git_state` before every commit `multi-pr` itself makes.** Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/git_state.py [--expect-branch <name>]` before the Phase 4 chain-log commit and any direct follow-up commit (a non-zero exit halts and surfaces — never special-case it). Resolving an exit-2 in-progress op: `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/conflict-resolution.md`. The per-change `/cla:spec-to-pr` runs already do their own git_state checks internally; this covers the commits `multi-pr` makes directly.
- **A structural failure in one change's run halts the chain; a content finding never does.** Ship never opening a PR, Archive not reaching the PR, or an unresolved `git_state` fault stop the run and leave every later change untouched (its prerequisite isn't confirmed shipped) — don't conflate that with "the Revise agents found bugs," which is normal, fix-and-continue operation. Full split: Phase 3 step 3.
- **Merging is a real, hard-to-reverse action against shared state, and `/cla:spec-to-pr` itself refuses to do it at all.** `multi-pr` is the one layer explicitly authorized to merge — and only for a change confirmed done, only under the user's Phase 1 merge-policy answer, and (under the recommended "merge before dependents" default) only when a later change actually depends on it — independents stay open.
- **If another live session is working in the primary clone, pivot to a dedicated worktree.** Nothing detects this for you any more — the hook that used to block a contended commit was deleted, so the contention shows up as confusing git state rather than a refusal. Follow `/cla:spec-to-pr`'s own "Concurrent runs" pattern (`git fetch origin <base-branch>`, then `git worktree add .claude/worktrees/<change> -b <branch> origin/<base-branch>` — for a stacked child, fetch and cut from `origin/<pr-base>` instead (both commands), or the child silently loses its parent's code; the pivot already creates the child's branch, so SKIP change-loop step 2's `git checkout <parent-branch>` (the original worktree holds it, and the checkout is no longer needed) — as two separate commands — `<branch>` as `/cla:spec-to-pr` defines it, which is `feature/<change>` only when nothing overrides the prefix) and continue the chain from inside that worktree. See `cla.io/overlays/multi-pr.md` for a real precedent where the pivot worked.
- **Run thin (thin-orchestrator standing discipline).** Delegate bulk raw-material handling so only conclusions return; read slices/`tail`/`head`, not whole files/full output; batch independent tool calls into one message; prefer terse structured agent output over prose. Full rules: `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/runtime-rules.md` (this skill is itself an orchestrator, so the same discipline applies).

## Mode / argument parsing

Bind the invocation argument once: **`<arg>` = `$ARGUMENTS`**.
Every rule below reads `<arg>`.

- **`<arg>` empty** → auto-discover mode. Every open change under `openspec/changes/` (excluding `archive/`) is in scope.
- **`<arg>` names one or more changes** → explicit mode. Only the named changes are in scope, in the order given (skip the sequencing step's auto-ordering — the user already ordered them). Still run the Phase 1 gate; still validate each name before starting (fail fast on a typo rather than discovering it mid-chain): a real, not-yet-archived change directory passes; a name that is archived AND has an open PR on its branch is a completed stacked change — treat it as already done (the same condition change-loop step 1 defines), keep it as a parent for `--pr-base`, and reject only names matching neither.

Announce the mode and the resolved change list as the first line of output, e.g. `Mode: auto-discover (3 changes found)` or `Mode: explicit (2 changes given)`.

## Phase 0: Bootstrap + working-tree precheck

Run `/cla:spec-to-pr`'s own permissions bootstrap exactly once before the chain starts (not once per change — there's no reason to ask the permission question more than once even implicitly): compare `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/required-permissions.json` against `.claude/settings.local.json`.

All present → proceed silently. Any missing → surface them exactly as `/cla:spec-to-pr`'s own "Bootstrap permissions" section describes and apply on approval. This is the *only* halt-and-ask that happens outside Phase 1 — same exception carve-out `/cla:spec-to-pr` itself makes for its own bootstrap gate.

Then run the working-tree precheck once, the same way `/cla:spec-to-pr` does at its own startup:

```
python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/git_state.py
```

Non-zero exit → resolve exactly per `/cla:spec-to-pr`'s "Working-tree precheck" section (in-progress op, wrong branch, or dirty tree with out-of-scope paths) before continuing. A dirty tree at chain-start poisons every subsequent phase, so this is worth getting right before Phase 1 rather than after.

**Starting-branch check.** `git_state.py` does NOT inspect the working tree at all — its `no_in_progress_op` field means only that no rebase/cherry-pick/merge is mid-flight. Uncommitted *files* need a separate `git status --porcelain`, and neither check flags "the current branch simply isn't `<base-branch>`." Separately check `git rev-parse --abbrev-ref HEAD`: if it's not `<base-branch>` and carries one or more local commits not yet on `<base-branch>` (`git log <base-branch>..HEAD --oneline`) that are unrelated to any in-scope change, treat that branch as pre-existing state outside this run's scope — do NOT merge, rebase, or push it as part of the chain. Simply `git checkout <base-branch> && git pull` before Phase 1 discovery, leaving the other branch untouched for the user to handle separately. Untracked in-scope change directories under `openspec/changes/` survive a branch checkout (they're untracked, not branch-scoped) — a quick `git status --porcelain` after the checkout confirms they're still present.

## Phase 1: Discover + sequence + pre-flight gate

**Read `references/discover-and-gate.md` first** — how to discover and order the changes, the full pre-flight-gate question wording, and the chain-time-estimate recipe. Load-bearing invariants (hold these even if the reference isn't reloaded):

- **A dependency cycle is never guessed past** — it's always its own explicit question, before Phase 2 starts, regardless of autonomy mode.
- **An unresolved prerequisite is never guessed past either.** Phase 1a's sweep resolves every *change* a proposal cites — not just every doc — against the directories that actually exist under `openspec/changes/` and `changes/archive/`. A cited change that is neither archived nor in-chain (typically one existing only as an open, proposal-only PR) is its own explicit question before Phase 2, same standing as the cycle. Skipping this is a quiet failure: the chain looks healthy for hours until a dependent reads code nobody wrote.
- **Ask everything upfront, in ONE `AskUserQuestion` call (max 4 questions), then run continuous.** This is the **only** point in the whole run where a multi-question stop happens; every phase after it runs autonomously with no "ready to continue?" pauses.
- **Recommended defaults** (applied verbatim under the explicit-autonomy override, and offered as the default choice otherwise): merge each PR before the next change that depends on it, independents left open; full-severity no-unresolved-issues (Critical/Important/Suggestion — nothing deferred to `TODO.md`); `/cla:spec-to-pr` caps at its own defaults `1/2/3`; an unavailable local-infra hard gate hard-blocks the chain (after a self-remediation attempt to bring the stack up).
- **Explicit-autonomy override** (an invocation stating "operate autonomously" / "don't ask, just run") and **bounded-window autonomy** (interactive at the start, autonomous once the user signals departure) both apply the recommended defaults above without calling `AskUserQuestion` — except the two structural questions (dependency cycle, unresolved prerequisite), which are never skipped.

## Phase 2: Task tracking

Use `TaskCreate` once at the start to lay down the chain itself — one task per change (`"<name>: spec-to-pr + land"`) plus a final `"Final cleanup pass"` task. This is the one place in the `/cla:spec-to-pr` family where task tracking is genuinely the right tool (per spec-to-pr's own "Task tracking" section: *"gated by external state, or recoverable across sessions"* — a multi-hour, multi-change chain is exactly that shape), unlike inside a single `/cla:spec-to-pr` run where it's noise. Use `TaskUpdate` to transition each change's task to `in_progress` when its `/cla:spec-to-pr` invocation starts and to `completed` only after that change is merged (or, under the stacked and "open all" policies, after it's archived with its PR open against the right base).

## Phase 3: Per-change loop

**Read `references/change-loop.md` first** — the full per-change procedure (resume check, real start/end timestamps, invoking `/cla:spec-to-pr`, the merge commands, the actual-vs-predicted timing report) and the resume-behavior mechanics. Load-bearing invariants (hold these even if the reference isn't reloaded):

- **Tier A (structural failure) halts the chain here; Tier B (content findings) never does.** Ship never opening a PR, Archive not reaching the PR, or an unresolved `git_state` fault → stop, surface, and do not touch any later change in the sequence (its prerequisite isn't confirmed shipped). A Revise/Test finding of any severity, however many rounds it takes, is normal operation — proceed to enforcement below.
- **No-unresolved-issues enforcement (per the confirmed Phase 1 policy).** A change never counts done while a Deferred-Known-Issue or (under the default full-severity policy) `TODO.md` Suggestion residue remains for it — fix it, re-verify narrowly, and land it on the same branch (or, if already merged, a small follow-up PR) before moving on.
- **Merge only under the confirmed "merge before dependents" policy, and only a change a later change genuinely depends on** — independents stay open regardless of policy. **Under the stacked policy the run performs no merges from the point the policy is in force** (a mixed run may have merged earlier changes before falling back): a dependent starts via step 2's stacked clause — `git checkout <parent-branch>`, then `/cla:spec-to-pr` with `--pr-base <parent-branch>` (see spec-to-pr's `<pr-base>` rule) — and the chain ends with the ordered, parents-first landing commands handed to the user (merge commits, never squash on a stack — change-loop step 5-alt).

## Phase 4: Final cleanup pass

**Read `references/cleanup.md` first** — the full verify/prune/confirm/log/commit sequence, run once after every change in the sequence is done. Load-bearing invariant: this is the one point worth re-running the repo's full build/lint/test (+ any local-infra hard gate) at the CHAIN level even though every change already passed it standalone — a later merge can interact with an earlier one in ways no single change's own Test phase would catch. **Under the stacked policy the gate target changes** — each stack leaf AND each independent's branch, plus `<base-branch>` only in a mixed run — and stack branches are NOT removed while their PRs are open (cleanup step 0). The chain-log commit at the end (Phase 4 step 5-6) uses path-scoped `git add` only, never `-A`.

## Resume behavior

Re-invoking `/cla:multi-pr` after an interruption picks up cleanly — full mechanics in `references/change-loop.md` ("Resume behavior"). Invariant: skip Phase 1's `AskUserQuestion` gate only on a genuine same-session resume; a fresh session always re-asks, since it has no way to know what the previous session decided.

## What this skill deliberately does not do

- Does not reimplement Review/Implement/Test/Ship/Revise/Archive — that's `/cla:spec-to-pr`'s job, invoked as a sub-skill.
- Does not merge without the Phase 1 policy explicitly authorizing it for this run — merging is a hard-to-reverse action against shared state, and that authorization is scoped to this one run, not a standing permission.
- Does not keep a chain-level ledger, and does not build a `multi-pr-retro` analyzer over one. It kept a log-only ledger until that ledger reached 4 records across five repos with no skill reading it, and was deleted along with the other two unread chain ledgers. Chain-level learnings are carried by `/cla:codify-learnings` plus the per-run running-notes file; per-CHANGE retrospective analysis stays `/cla:spec-to-pr-retro`'s job, over the `spec-to-pr-runs.jsonl` each `/cla:spec-to-pr` invocation appends to.
- Does not guess past a dependency cycle or an ambiguous merge decision — those are genuinely the user's calls, surfaced once, up front.

## References

- `references/discover-and-gate.md` — Phase 1's full mechanics: discovering and ordering the changes, the pre-flight-gate question wording (merge/no-unresolved-issues/caps/infra policies), the explicit-autonomy and bounded-window-autonomy modes, infra self-remediation, and the chain-time-estimate recipe (mandatory-read from the Phase 1 stub)
- `references/change-loop.md` — Phase 3's full per-change procedure (resume check, timestamps, invoking `/cla:spec-to-pr`, the deferred-finding fix recipe, the merge commands, the actual-vs-predicted timing report) and the Resume-behavior mechanics (mandatory-read from the Phase 3 stub and the Resume-behavior stub)
- `references/cleanup.md` — Phase 4's full verify/prune/confirm/log/commit sequence (mandatory-read from the Phase 4 stub)
- `cla.io/overlays/multi-pr.md` — this repo's project-context overlay: repo commands, and the dated incidents/statistics that justify individual guardrails or recommended defaults (read only when revising a rule or reasoning about this repo specifically)
- `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/base-branch-resolution.md` — the `<base-branch>` resolution rule, shared verbatim with `multi-lite`/`multi-spec`.
