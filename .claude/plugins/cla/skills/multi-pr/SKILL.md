---
name: multi-pr
description: "Chains multiple OpenSpec changes end-to-end: determines implementation order, runs /cla:spec-to-pr on each change in sequence, enforces that every Critical/Important review finding is actually fixed (never left as a deferred TODO) before moving on, merges each PR before starting the next dependent change, and finishes with a full repo cleanup pass. Designed for long, unattended multi-change runs. Triggers on /cla:multi-pr or natural language like 'drive all my openspec changes to PRs', 'chain these changes end to end', 'work through every open change and merge as you go', 'run spec-to-pr on everything'."
argument-hint: "[change-name-1 change-name-2 ... | (empty = auto-discover every open change)]"
---

# /cla:multi-pr — chain multiple OpenSpec changes to merged PRs

Orchestrates `/cla:spec-to-pr` across a **sequence** of OpenSpec changes rather than one. Where `/cla:spec-to-pr` drives a single change from idea to an opened, archived PR and then stops, `multi-pr` adds the layer on top: figure out which order the open changes must ship in, run the full `/cla:spec-to-pr` workflow on each one, make sure nothing gets left half-resolved, merge before moving on to whatever depends on it, and end with a clean repo. This is the skill for "I'm about to be away for a few hours — take every open change to done."

**This skill does not reimplement `/cla:spec-to-pr`.** Every actual propose/review/implement/test/ship/revise/archive step for a single change is `/cla:spec-to-pr`'s job — invoke it via `Skill(cla:spec-to-pr, args="<change-name> ...")`. `multi-pr` owns exactly four things `/cla:spec-to-pr` doesn't: **sequencing**, **the upfront confirmation gate**, **the no-unresolved-issues escalation**, and **inter-change merge + final cleanup**.

## Skill-level rules (hoisted — read first)

- **This is a long unattended run. Get every blocking question answered BEFORE the chain starts, not mid-chain.** A clarifying question fired three changes in defeats the purpose — see Phase 1's pre-flight gate below. Once answered, run start-to-finish with no "ready to continue?" pauses between changes, mirroring `/cla:spec-to-pr`'s own autonomy-gate contract one level up.
- **"No unresolved issues, at ANY severity" is the default policy — stricter than `/cla:spec-to-pr`'s own default** (which accepts Deferred-Known-Issue + `TODO.md` Suggestion residue as done). Neither is acceptable here unless the user's Phase 1 answer explicitly picks a looser alternative — there's no point in the run where the user comes back to triage a leftover list themselves.
- **Never run `git add -A`.** Same rule as `/cla:spec-to-pr`, inherited transitively through every `Skill(cla:spec-to-pr, ...)` call this skill makes, and equally binding on any direct git command `multi-pr` itself runs (merges, branch cleanup, prunes).
- **Verify `git_state` before every commit `multi-pr` itself makes.** Run `python3 .claude/plugins/cla/skills/spec-to-pr/scripts/git_state.py [--expect-branch <name>]` before the Phase 4 chain-log commit and any direct follow-up commit (a non-zero exit halts and surfaces — never special-case it). The per-change `/cla:spec-to-pr` runs already do their own git_state checks internally; this covers the commits `multi-pr` makes directly.
- **A structural failure in one change's run halts the chain; a content finding never does.** Ship never opening a PR, Archive not reaching the PR, or an unresolved `git_state` fault stop the run and leave every later change untouched (its prerequisite isn't confirmed shipped) — don't conflate that with "the Revise agents found bugs," which is normal, fix-and-continue operation. Full split: Phase 3 step 3.
- **Merging is a real, hard-to-reverse action against shared state, and `/cla:spec-to-pr` itself refuses to do it at all.** `multi-pr` is the one layer explicitly authorized to merge — and only for a change confirmed done, only under the user's Phase 1 merge-policy answer, and (under the recommended "merge before dependents" default) only when a later change actually depends on it — independents stay open.
- **On a `guard-worktree-isolation.py` block mid-chain, pivot to a dedicated worktree — never the hook's `ALLOW_SHARED_CLONE_MUTATION=1` escape hatch.** Follow `/cla:spec-to-pr`'s own "Concurrent runs" pattern (`git fetch origin master`, then `git worktree add .claude/worktrees/<change> -b feature/<change> origin/master`, as two separate commands) and continue the chain from inside that worktree — the hatch doesn't reliably carry across a chained run's separate Bash calls and overriding doesn't make the primary clone any less genuinely contended. See `references/project-context.md` for a real precedent where the pivot worked and the override attempt didn't.
- **Run thin (thin-orchestrator standing discipline).** Delegate bulk raw-material handling so only conclusions return; read slices/`tail`/`head`, not whole files/full output; batch independent tool calls into one message; prefer terse structured agent output over prose. Full rules: `.claude/plugins/cla/skills/spec-to-pr/references/runtime-rules.md` (this skill is itself an orchestrator, so the same discipline applies).

## Mode / argument parsing

- **Empty arguments** → auto-discover mode. Every open change under `openspec/changes/` (excluding `archive/`) is in scope.
- **One or more change names** → explicit mode. Only the named changes are in scope, in the order given (skip the sequencing step's auto-ordering — the user already ordered them). Still run the Phase 1 gate; still validate each name is a real, not-yet-archived change directory before starting (fail fast on a typo rather than discovering it mid-chain).

Announce the mode and the resolved change list as the first line of output, e.g. `Mode: auto-discover (3 changes found)` or `Mode: explicit (2 changes given)`.

## Phase 0: Bootstrap + working-tree precheck

Run `/cla:spec-to-pr`'s own bootstrap exactly once before the chain starts (not once per change — it's idempotent and cheap to re-check, but there's no reason to ask the permission question more than once even implicitly):

```
python3 .claude/plugins/cla/skills/spec-to-pr/scripts/check_permissions.py --check
```

Exit 0 → proceed silently. Exit non-zero → surface the missing patterns exactly as `/cla:spec-to-pr`'s own "Bootstrap permissions" section describes and apply on approval. This is the *only* halt-and-ask that happens outside Phase 1 — same exception carve-out `/cla:spec-to-pr` itself makes for its own bootstrap gate.

Then run the working-tree precheck once, the same way `/cla:spec-to-pr` does at its own startup:

```
python3 .claude/plugins/cla/skills/spec-to-pr/scripts/git_state.py
```

Non-zero exit → resolve exactly per `/cla:spec-to-pr`'s "Working-tree precheck" section (in-progress op, wrong branch, or dirty tree with out-of-scope paths) before continuing. A dirty tree at chain-start poisons every subsequent phase, so this is worth getting right before Phase 1 rather than after.

**Starting-branch check (beyond the dirty-tree check above).** `git_state.py`'s dirty-tree check covers uncommitted *files*; it does not by itself flag "the current branch simply isn't `master`." Separately check `git rev-parse --abbrev-ref HEAD`: if it's not `master` and carries one or more local commits not yet on `master` (`git log master..HEAD --oneline`) that are unrelated to any in-scope change, treat that branch as pre-existing state outside this run's scope — do NOT merge, rebase, or push it as part of the chain. Simply `git checkout master && git pull` before Phase 1 discovery, leaving the other branch untouched for the user to handle separately. Untracked in-scope change directories under `openspec/changes/` survive a branch checkout (they're untracked, not branch-scoped) — a quick `git status --porcelain` after the checkout confirms they're still present.

## Phase 1: Discover + sequence + pre-flight gate

**Read `references/discover-and-gate.md` first** — the `discover_sequence.py` mechanics + trust-but-verify caveats, the full pre-flight-gate question wording, and the chain-time-estimate recipe. Load-bearing invariants (hold these even if the reference isn't reloaded):

- **A dependency cycle (`cycle_members`/`blocked_by_cycle` non-empty) is never guessed past** — it's always its own explicit question, before Phase 2 starts, regardless of autonomy mode.
- **Ask everything upfront, in ONE `AskUserQuestion` call (max 4 questions), then run continuous.** This is the **only** point in the whole run where a multi-question stop happens; every phase after it runs autonomously with no "ready to continue?" pauses.
- **Recommended defaults** (applied verbatim under the explicit-autonomy override, and offered as the default choice otherwise): merge each PR before the next change that depends on it, independents left open; full-severity no-unresolved-issues (Critical/Important/Suggestion — nothing deferred to `TODO.md`); `/cla:spec-to-pr` caps at its own defaults `1/2/3`; an unavailable local-infra hard gate hard-blocks the chain (after a self-remediation attempt to bring the stack up).
- **Explicit-autonomy override** (an invocation stating "operate autonomously" / "don't ask, just run") and **bounded-window autonomy** (interactive at the start, autonomous once the user signals departure) both apply the recommended defaults above without calling `AskUserQuestion` — except the cycle question, which is never skipped.

## Phase 2: Task tracking

Use `TaskCreate` once at the start to lay down the chain itself — one task per change (`"<name>: spec-to-pr + merge"`) plus a final `"Final cleanup pass"` task. This is the one place in the `/cla:spec-to-pr` family where task tracking is genuinely the right tool (per spec-to-pr's own "Task tracking" section: *"gated by external state, or recoverable across sessions"* — a multi-hour, multi-change chain is exactly that shape), unlike inside a single `/cla:spec-to-pr` run where it's noise. Use `TaskUpdate` to transition each change's task to `in_progress` when its `/cla:spec-to-pr` invocation starts and to `completed` only after that change is merged (or, under the "open all, merge nothing" policy, after it's archived).

## Phase 3: Per-change loop

**Read `references/change-loop.md` first** — the full per-change procedure (resume check, real start/end timestamps, invoking `/cla:spec-to-pr`, the merge commands, the actual-vs-predicted timing report) and the resume-behavior mechanics. Load-bearing invariants (hold these even if the reference isn't reloaded):

- **Tier A (structural failure) halts the chain here; Tier B (content findings) never does.** Ship never opening a PR, Archive not reaching the PR, or an unresolved `git_state` fault → stop, surface, and do not touch any later change in the sequence (its prerequisite isn't confirmed shipped). A Revise/Test finding of any severity, however many rounds it takes, is normal operation — proceed to enforcement below.
- **No-unresolved-issues enforcement (per the confirmed Phase 1 policy).** A change never counts done while a Deferred-Known-Issue or (under the default full-severity policy) `TODO.md` Suggestion residue remains for it — fix it, re-verify narrowly, and land it on the same branch (or, if already merged, a small follow-up PR) before moving on.
- **Merge only under the confirmed "merge before dependents" policy, and only a change a later change genuinely depends on** — independents stay open regardless of policy.

## Phase 4: Final cleanup pass

**Read `references/cleanup.md` first** — the full verify/prune/confirm/log/commit sequence, run once after every change in the sequence is done. Load-bearing invariant: this is the one point worth re-running the repo's full build/lint/test (+ any local-infra hard gate) at the CHAIN level even though every change already passed it standalone — a later merge can interact with an earlier one in ways no single change's own Test phase would catch. The chain-log commit at the end (Phase 4 step 5-6) uses path-scoped `git add` only, never `-A`.

## Resume behavior

Re-invoking `/cla:multi-pr` after an interruption picks up cleanly — full mechanics in `references/change-loop.md` ("Resume behavior"). Invariant: skip Phase 1's `AskUserQuestion` gate only on a genuine same-session resume; a fresh session always re-asks, since it has no way to know what the previous session decided.

## What this skill deliberately does not do

- Does not reimplement Review/Implement/Test/Ship/Revise/Archive — that's `/cla:spec-to-pr`'s job, invoked as a sub-skill.
- Does not merge without the Phase 1 policy explicitly authorizing it for this run — merging is a hard-to-reverse action against shared state, and that authorization is scoped to this one run, not a standing permission.
- Does not build a `multi-pr-retro` analyzer skill. It keeps a **log-only** chain-level ledger (`cla.io/retro/multi-pr-runs.jsonl`, one line per run, Phase 4 step 5) for facts `/cla:spec-to-pr`'s per-change ledger structurally can't see (sequencing quality, gate/escalation outcomes, inter-change breakage, per-change timing-by-complexity) — but deliberately ships NO aggregator over it yet: at a handful of chains, cross-chain pattern-mining would over-fit anecdote, and the qualitative chain-level learnings are already handled well by `/cla:codify-learnings` + the per-run running-notes file. Revisit building a `multi-pr-retro` once ~8–10 chains have accumulated in the ledger — by then the "log now" data exists and the sample justifies an analyzer. (Per-CHANGE retrospective analysis stays `/cla:spec-to-pr-retro`'s job, over the per-change `spec-to-pr-runs.jsonl` each `/cla:spec-to-pr` invocation already appends to.)
- Does not guess past a dependency cycle or an ambiguous merge decision — those are genuinely the user's calls, surfaced once, up front.

## References

- `references/discover-and-gate.md` — Phase 1's full mechanics: `discover_sequence.py` usage + trust-but-verify caveats, the pre-flight-gate question wording (merge/no-unresolved-issues/caps/infra policies), the explicit-autonomy and bounded-window-autonomy modes, infra self-remediation, and the chain-time-estimate recipe (mandatory-read from the Phase 1 stub)
- `references/change-loop.md` — Phase 3's full per-change procedure (resume check, timestamps, invoking `/cla:spec-to-pr`, the deferred-finding fix recipe, the merge commands, the actual-vs-predicted timing report) and the Resume-behavior mechanics (mandatory-read from the Phase 3 stub and the Resume-behavior stub)
- `references/cleanup.md` — Phase 4's full verify/prune/confirm/log/commit sequence (mandatory-read from the Phase 4 stub)
- `references/run-log-schema.md` — the chain-level per-run JSONL schema + per-field obligations (Phase 4 step 5; the contract a future `multi-pr-retro` would consume)
- `references/project-context.md` — this repo's project-context overlay: repo commands, and the dated incidents/statistics that justify individual guardrails or recommended defaults (read only when revising a rule or reasoning about this repo specifically)
