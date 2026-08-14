---
name: spec-to-pr
description: "Drive an OpenSpec change end-to-end from idea (or existing-change name, or /opsx:explore result) to an opened, archived PR with PR-review fixes applied. Stops before merge — no merge, no deploy. Triggers on /cla:spec-to-pr or natural language like 'take this change to a PR', 'spec-to-pr the X feature', 'orchestrate the full dev workflow'."
argument-hint: "[change-name | description | (empty)]"
---

# /cla:spec-to-pr — full-workflow orchestrator

Drives one OpenSpec change from `/opsx:propose`-input to an opened PR with PR-review fixes applied. Composes existing skills only where they add real value. **Review reads `${CLAUDE_PLUGIN_ROOT}/skills/review-change/references/checklist.md` directly and executes it inline** — the checklist is the single source of truth for review behavior, shared with the standalone `/cla:review-change` slash-command path, so verdicts stay consistent across entry points without a skill-load round trip. Phases that previously delegated to skills which then bounced their workflow back to Claude (pr-review, commit-push-pr) now invoke `Agent`, run inline directly, or (Revise round 1 only) run a `Workflow` fan-out. See `references/workflow-diagram.md` for the phase order at a glance. The generic enforcement-tier vocabulary behind the guardrails throughout this skill lives in `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/past-offenses.md`; the dated, repo-specific incidents that justify individual rules live in `cla.io/overlays/spec-to-pr.md` — read either only when revising a rule; a normal run never needs them.

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

## Skill-level rules (hoisted — read first)

- **`<base-branch>` means THIS repo's default branch, resolved — never assumed.** Every command below that names it is a placeholder, not a literal: substitute the real name before running anything. Resolve it once, at the start of the run, with `git symbolic-ref --quiet refs/remotes/origin/HEAD` (take the segment after the last `/`); if that is unset, use whichever of `main` / `master` actually exists. The harness used to hardcode `master`, which silently broke every `main`-default repo — a `master..HEAD` range there fails outright with `unknown revision` rather than returning a wrong answer, and `git checkout master` cannot succeed at all.

**`<branch>`** — the feature branch this run creates and looks up. Resolved by `scripts/_git_common.branch_name()`: the `CLA_BRANCH_PREFIX` env var, else a `cla.io/overlays/branch-prefix.local.md` overlay (a `*.local.md`, so it is never synced), else `feature/`. It was hardcoded as `feature/<change-name>` in the scripts that both CREATE and FIND the branch — and because all three lookups use `git rev-parse --verify --quiet`, a miss exits 1 with empty stderr, so a repo on any other convention reported `branch: false, pr: {open: false}, fix_rounds_applied: 0` — indistinguishable from *nothing has been done yet*. The orchestrator acts on that by redoing completed work and can open a duplicate branch and PR. Resolving ONE configured prefix does not close that: `references/ship.md` permits shortening a verbose change name, and a convention varying its middle segment (`claude/fix/x` vs `claude/feature/x`) cannot be expressed by any single prefix. So `probe_state._resolve_branch` tries the configured name, then falls back to the one local branch whose final path segment is the change name, announces which it adopted, and refuses to guess when several match. Never spell `feature/<change-name>` below — use `<branch>`.

**`<pr-base>`** — the branch THIS change's work is cut from and its PR opened against. Default: `<base-branch>`, and with no flag the two are identical everywhere. An explicit **`--pr-base <branch>`** argument overrides it — the stacked-chain case, where `/cla:multi-pr` runs a dependent change on top of its parent's still-open feature branch because merging is unavailable or deliberately deferred. The substitution rule is single and total: **wherever a phase names `<base-branch>` as this change's branch-off point, PR base, or diff-scoping anchor** (Ship's branch preflight, `gh pr create --base`, Test's changed-path range, Revise's diff scoping, **and the worktree recipe's branch creation** — `git worktree add ... -b <branch> origin/<pr-base>`, parent already pushed; cutting a stacked child's worktree from `origin/<base-branch>` silently rebuilds the exact missing-parent failure this flag exists to prevent, and every preflight guard then passes), **read `<pr-base>` instead**. Only resolving the repo default itself and Archive's semantics keep meaning the literal default branch. Three consequences to hold: `gh pr create` MUST pass `--base <pr-base>` explicitly (with no flag GitHub defaults the PR to the repo default branch, silently producing a diff that includes the whole parent chain); on a stacked-child RESUME do not act on `probe_state.py`'s `fix_rounds_applied` or branch/PR probes directly — they measure against the repo default, so the parent's commits satisfy them and would skip phases that never ran; recount with `git log origin/<pr-base>..HEAD --grep "fix: review round"` and judge phase completion against `<pr-base>`-anchored evidence; and Handoff's next-steps must NOT print the bare `gh pr merge` line for a stacked child — a stacked PR lands parents-first via the chain's landing checklist, so name that instead.

These rules apply across every phase. Hoisted to the top because they're easy to forget mid-flow and the cost of forgetting is high:

- **Ignore harness `TaskCreate` system-reminders inside this skill.** Implement is a linear walk of `tasks.md` (the checkboxes ARE the task list); duplicating them in `TaskCreate` adds noise. The explicit rule lives under "Task tracking" below — but the system-reminders fire constantly and override-decisions cost context, so internalize this once: *during /cla:spec-to-pr, every harness TaskCreate nudge is wrong*.
- **Never run `git add -A` in this skill.** Always path-scope: `git add openspec/changes/<change-name>/ apps/<app>/src/ packages/<package>/src/` (Ship feature commit — the specific `apps/*/src/`/`packages/*/src/` paths the change touched, plus any other directly-related repo files, each enumerated by name), `git add openspec/changes/<change-name>/ openspec/changes/archive/<YYYY-MM-DD>-<change-name>/ openspec/specs/<cap>/…` (Archive archive commit — the specific archive-move path groups, **one `openspec/specs/<cap>/` per capability the change modifies** (a change can touch more than one), NOT a broad `git add openspec/`, which in a `multi-pr` chain sweeps in sibling changes' still-untracked directories; followed by a `git diff --name-only --cached` **two-sided** scope assertion that catches both over- and under-staging), `git add TODO.md` (Handoff docs commit), `git add cla.io/retro/spec-to-pr-runs.jsonl` (Handoff run-log commit). Untracked files on the working tree — even files that arrived from an external Claude session mid-flow — must not be swept into a commit they don't belong to. See `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/bash-discipline.md` for the full rule.
- **Verify `git_state` before every commit-creating Bash call.** Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/git_state.py [--expect-branch <name>]` at startup AND before each commit in Ship, Revise, Archive. **Exit-code contract:** 0 = proceed; **any non-zero exit halts and surfaces to the user via `AskUserQuestion`** — never special-case "exit 1 is probably fine". Specifically: 1 = fail-closed (cannot resolve `.git`, malformed worktree marker, `git rev-parse` failed); 2 = in-progress op (cherry-pick / merge / rebase / revert / bisect from a parallel session); 3 = on the wrong branch. `git status --porcelain` alone is NOT sufficient — an external cherry-pick on a different branch is invisible to it.
- **Rebase/merge conflict resolution: show before applying.** `git checkout --theirs` in a rebase context means the commits being rebased (opposite of merge context). Read the conflict markers FIRST (`cat <file> | head -30`), name which side is which, THEN resolve. See `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/bash-discipline.md` "Conflict resolution discipline".
- **Route every dispatched agent per `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md`.** That file is the single source of truth for which model (and, for the Revise round-1 Workflow fan-out, which effort) each sub-agent runs at. Every `Agent(...)` call in Implement/Revise passes an explicit `model:`; Revise round 1 runs as one `Workflow` fan-out. On a **sub-Opus session**, apply the escalate-up rule (Propose authoring + RETHINK-borderline Review verdict → opus). Do not route inline main-loop work — only dispatched work is routable.
- **Run thin — keep raw material out of the parent context (`${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/runtime-rules.md`).** Delegate bulk raw-material handling (large diffs, wide file sets, verbose output, big claim-verification sweeps) to a sub-agent so only conclusions return; read file slices not whole files; `tail`/`head` large command output; scratch-file-then-delegate large intermediate material; batch independent tool calls into one message; prefer terse schema'd agent output over prose. This is a standing discipline across every phase, not a per-trigger step. Full rules: `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/runtime-rules.md`.

## Mode detection

Parse `$ARGUMENTS` and announce the mode in the **first line** of output before any other action.

- **explore-result mode** — `$ARGUMENTS` is empty. Infer the change description from the current Claude Code conversation context (typically a just-finished `/opsx:explore`). Announce: `Mode: explore-result`.
- **existing-change mode** — `$ARGUMENTS` matches a directory `openspec/changes/{name}/` containing a `proposal.md`. Skip the propose phase; resume from the next not-done phase. Announce: `Mode: existing-change ({name})`.
- **description mode** — any other non-empty value. Treat as a free-form description for `openspec-propose`. Announce: `Mode: description`.

Tie-break: directory existence wins. If both interpretations apply, use existing-change.

**Empty `$ARGUMENTS` with no conversation context.** If `$ARGUMENTS` is empty and there is no usable conversation context to infer a description from (e.g. a fresh session), but exactly one complete change directory exists under `openspec/changes/` (a `proposal.md` present — tracked or still untracked), resolve to **existing-change mode** for that change. Only fall back to prompting the user if zero or multiple such directories exist.

### Investigation-first changes are a poor fit for autonomous /cla:spec-to-pr

If a change's first task group is "reverse-engineer / investigate an unknown binary format" (or otherwise produces *facts the rest of the change depends on*), do that investigation in `/opsx:explore` mode and re-derive the proposal/design/tasks from confirmed facts **before** running `/cla:spec-to-pr`. An autonomous run over unconfirmed format assumptions forces mid-flight design rewrites: Implement discovers the model is wrong, pauses, and the design/spec/tasks have to be re-edited while the workflow is mid-stream.

**Ask-not-halt format.** If you detect this shape in existing-change mode, surface it to the user via `AskUserQuestion` with **three explicit paths** rather than a free-text halt-and-explain:

- **(a) Pause — validate first in `/opsx:explore`.** Stop `/cla:spec-to-pr`; user runs the investigation task in explore mode (or points at the required artifact); rerun `/cla:spec-to-pr` once the facts are settled.
- **(b) Proceed autonomously — trust current assumptions.** Treat the existing reverse-engineering as authoritative; defer the cross-validation task(s) to TODO.md; run Review→Handoff now. Accept the risk that a hidden assumption may force a follow-up PR.
- **(c) User has the artifact — point at it.** User provides the path/file the investigation needs (e.g. an alternate save, a sibling install path); run the investigation task in this session before Implement.

Do NOT free-text the question — the three-paths shape forces a clear choice and the deferral semantics are unambiguous.

## Bootstrap permissions

Before any workflow step, read `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/required-permissions.json` (`permissions.allow`) and the repo's `.claude/settings.local.json`, and compare the two lists.

- Every required pattern already present → proceed silently.
- Any missing → print them. Ask the user **once**:
  > "Add these N pattern(s) to `.claude/settings.local.json`? [Y/n]"
- On approval, `Edit` the missing patterns into `permissions.allow`. **Additive only** — add entries, never remove or rewrite any other key, and create the file with just `{"permissions": {"allow": [...]}}` if it is absent.
- On decline, **halt immediately** and print the missing patterns as a copy-paste block.

The flag `/cla:spec-to-pr --check-permissions` short-circuits to that comparison and exits without doing any other work.

**Narrow mode** (`--narrow`): compare against `references/required-permissions-narrow.json` — the per-subcommand pattern set — instead of the wildcard default. Useful when the user prefers stricter allowlisting. One trap: adding the narrow set while the wildcard patterns are still present leaves the broader patterns in force, so the apparent tightening does nothing. When switching to narrow, remove the wildcard-default entries in the same edit, and say which ones you removed.

The bootstrap halt is the **only** halt the orchestrator performs other than user-decline at the optional confirmation gate (see "Autonomy modes" below).

## Working-tree precheck (run after permissions, before Propose)

`/cla:spec-to-pr` should NOT pick up uncommitted changes that belong to a different scope and sweep them into the feature branch's first commit. **The precheck must also detect in-progress git ops on other branches** — an in-progress cherry-pick/rebase/merge on another branch's HEAD is invisible to `git status --porcelain` on the current branch, so relying on `git status` alone lets it sweep unrelated untracked files into a later commit. See step 1 below. (Dated incident: `cla.io/overlays/spec-to-pr.md`.)

Run after the permissions check, before announcing the mode:

**Step 1 — Check for in-progress git operations and verify branch state:**
```
python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/git_state.py
```
Exit 0 → proceed. Exit 2 → in-progress cherry-pick / merge / rebase / revert / bisect detected (the stderr names which one). Surface to the user via `AskUserQuestion` with three explicit paths: (a) abort the in-progress op (`git cherry-pick --abort` / `git rebase --abort` / etc.) and proceed, (b) halt /cla:spec-to-pr and let the user finish the op manually, (c) inspect first (read `.git/CHERRY_PICK_HEAD` etc.) before deciding. Do NOT proceed until resolved — a stale in-progress op poisons every subsequent `git add` and commit.

**Step 2 — Inspect the working-tree dirty paths:**
```
git status --porcelain
```

Classify every output line by path:
- **In-scope:** anything under `openspec/changes/<change-name>/`, the affected app/package's source under `apps/*/src/` or `packages/*/src/`, or a directly-related repo file the change legitimately touches (e.g. a per-app stylesheet, a smoke-test script, a config file, `docs/` for the change, or a sub-app's own doc file for a sub-app-scoped change — see `cla.io/overlays/spec-to-pr.md` for this repo's worked examples).
- **Out-of-scope:** everything else — typically `.claude/`, root `CLAUDE.md`, root `TODO.md`, files belonging to an unrelated change, etc.

**If every dirty path is in-scope OR the working tree is clean:** proceed silently. (In existing-change mode, the change-directory edits are obviously in-scope; in description / explore-result mode, only a clean tree is expected — non-in-scope dirty paths still trigger the prompt.)

**If any path is out-of-scope:** surface to the user via `AskUserQuestion` with **three explicit paths** (the same shape used by the investigation-first detector):

- **(a) Commit out-of-scope changes to <base-branch> first.** Stage and commit ONLY the out-of-scope paths to <base-branch> with a one-line subject (e.g. `docs: lessons-learned log entries from prior session`), push, then return to clean working tree and proceed with Propose.
- **(b) Include out-of-scope changes in this PR.** Stage them along with the feature work in Ship by adding each out-of-scope path to the `git add` call alongside the in-scope `apps/*/src/`/`packages/*/src/` paths. The orchestrator never runs `git add -A`; out-of-scope paths must be enumerated explicitly. Use when the changes are intentionally part of the same logical unit and the user is consciously overriding the commit-to-base-branch convention.
- **(c) Stash and proceed.** `git stash push --include-untracked -m "spec-to-pr precheck stash for <change-name>"` before Propose; the stash is the user's responsibility to pop later. Use when uncertain — keeps the tree clean for this PR without losing work.

Print the list of out-of-scope paths in the question's `description` field so the user sees exactly what's at stake. Default to (a) when the paths are all under `.claude/` (per the memory rule); default to (a) is also presented as a recommendation in the option label when applicable. Do NOT proceed until the user picks.

This precheck is the only check between Bootstrap permissions and Propose. Skip entirely with `--no-tree-check` (escape hatch — useful when re-running mid-flow after a known intentional dirty state).

## Commit + PR message style — minimal

This is a single-developer project. Commit subjects and PR bodies are read once (by the dev, at PR-merge time) and the diff itself carries the detail. Default to **subject-only commits** and **single-line PR bodies**. Don't write multi-paragraph commit bodies, don't write Test-plan checklists, don't restate what `proposal.md` already says.

| Artifact | Shape |
|---|---|
| `feat:` commit (Ship) | subject only — `feat: <change-name>` |
| `fix:` commit (Revise) | subject only — `fix: review round <N>` |
| `chore:` commit (Archive) | subject only — `chore: archive <change-name>` |
| `docs:` commit (Handoff, optional) | subject only — `docs: TODO.md` |
| `chore:` commit (Handoff, run log) | subject only — `chore: spec-to-pr run log` (the retro JSONL line; feature-branch only) |
| PR body (Ship) | one line — `Closes openspec/changes/<name>/. Checks: build + lint passed.` |
| PR body update (Handoff, only when issues exist) | one line if issues fit on one line; otherwise a single short Markdown file |

Because every default-path message is a single line, **no scratch files are needed in the happy path.** Use `git add -- <paths>` then `git commit -m "<subject>"`, and `gh pr create --body "<one-line body>"`. The `gh pr create --body "..."` parser bug is triggered by *newline-followed-by-`#`*, not by long single lines without `#`, so a one-liner is safe.

## Per-run scratch directory (created on demand)

Only created when Handoff needs to mirror multi-line issues into the PR body. Path:

```
temp/spec-to-pr-issues-<change-name>.md
```

(Single fixed name per change; overwritten on re-run. No timestamped directory.) Written only when the Issues section is non-empty AND too long to fit a single-line `--body`. Then `gh pr edit <#> --body-file temp/spec-to-pr-issues-<change-name>.md`.

If you find yourself wanting to write a multi-paragraph commit or PR body anyway — don't. The proposal.md and the diff are the spec; the commit/PR are markers.

**No per-phase JSON logs.** The orchestrator synthesizes the Handoff report directly from in-context phase outcomes. Mid-run resume across separate Claude sessions still works via `probe_state.py` (which reads repo state, not log files); the previous session's per-phase summaries are not recoverable, but resume picks up at the right phase regardless.

**One per-RUN JSONL line is fine and required.** After printing the Handoff report, Handoff step 5 appends a single counts-only JSON line via `lib/log_run.py` to the repo's `cla.io/retro/spec-to-pr-runs.jsonl`, and Handoff step 6 commits that line onto the feature branch (`chore: spec-to-pr run log`) so it merges with the PR and syncs across machines via git — never left dangling as an uncommitted file (override the dir with `CLAUDE_RETRO_DIR`, in which case the commit is skipped). This is the data source for `/cla:spec-to-pr-retro`, which proposes orchestrator improvements based on patterns across runs (cap-exhaustion rates, agent dispatch frequency, ask choice distribution, recurring warn reasons). Per-phase mid-run logs remain forbidden; per-run terminal logs are the explicit exception.

## Task tracking

Do NOT use `TaskCreate` for per-phase progress — phase outcomes live in the orchestrator's working context and are emitted in the Handoff terminal report.

**Use `TaskCreate` when sub-work is parallel, gated by external state, or recoverable across sessions** — for example, applying 4 PR-review fixes from independent agents that the user might want to inspect mid-run, or diagnosing N test failures where the next session needs to know which were fixed. **Skip when sub-work is linearly sequential** (e.g. a 25-subtask Implement implementation that flows top-to-bottom from `tasks.md` — the tasks.md checkboxes ARE the task list; duplicating them in `TaskCreate` adds noise without adding signal). When in doubt, skip.

The harness may emit `<system-reminder>` nudges to use `TaskCreate`. These are generic; the rule above takes precedence.

## When NOT to use `Skill()`

Many sub-skills don't *execute* — they re-prompt Claude with their workflow text and ask Claude to run the same tool calls it would have run anyway. This costs 1–2 turns of indirection per invocation with no extra capability. Specifically:

- `Skill(pr-review-toolkit:review-pr)` — itself a dispatcher that calls `Agent` with `code-reviewer`/`silent-failure-hunter`/etc. Skip the hop and dispatch the agents directly.
- `Skill(commit-commands:commit-push-pr)` — re-prompts with the diff and asks Claude to run the same 4 shell commands. Inline them in Ship.
- `Skill(openspec-archive-change)` — wraps a single CLI call. Run `openspec archive --yes` directly in Archive.

Use `Skill()` only when the sub-skill genuinely encapsulates capability the orchestrator lacks (e.g. an MCP tool integration, a stateful workflow with its own internal probes). For review/commit/PR work, prefer `Agent(...)` (parallel, isolated context) or inline execution.

**Implement is the exception.** `Skill(openspec-apply-change)` carries non-trivial workflow logic (read tasks.md → for each subtask, locate the implementing module/test → edit → tick the checkbox → re-validate). The work is not a thin shell wrapper, so the indirection is worth it. **When to inline instead:** use direct `Edit`/`Write` calls when you already hold the relevant artifact + source text in context from Review and adding a `Skill()` hop would be pure indirection, OR when the work needs repo-specific side knowledge the skill doesn't carry (e.g. a packaging gotcha you need to apply mid-flight). Use judgment, not a subtask-count threshold.

## Concurrent runs (worktree-per-session)

A single `/cla:spec-to-pr` run needs no special setup — it creates `<branch>` in place and nothing arbitrates two sessions in one clone — the hook that used to is gone, so the discipline below is the whole protection.

To run **two or more `/cla:spec-to-pr` flows at once** in the same repo, give each session its own `git worktree` (own directory + own HEAD; the primary clone stays on `<base-branch>`). This is required because a run's file edits (Review/Implement/Revise) go to the *session's* working directory via Edit/Write — you cannot edit in one clone and commit from another, so the session itself must live in the worktree (`git -C <worktree>` does NOT solve this). See `cla.io/project-facts.md` ("Worktree convention") for this repo's worktree-directory convention (run `/cla:sync-context` to populate it; falls back to `cla.io/overlays/spec-to-pr.md` if absent). Per-session setup, from the primary clone:

```
git fetch origin <base-branch>
git worktree add <worktrees-dir>/<change> -b <branch> origin/<base-branch>
# then launch Claude in <worktrees-dir>/<change> and run: /cla:spec-to-pr <change>
```

**Branch off `origin/<base-branch>` explicitly, never bare `git worktree add ... -b <branch>`.** Omitting the base branches off whatever the primary clone's *local* `<base-branch>` ref happens to point to, which drifts stale the moment any other change in a chain squash-merges (squash rewrites history, so a local `<base-branch>` that hasn't been fetched/pulled since diverges from `origin/<base-branch>` even with zero local commits of its own). A branch cut from that stale base produces a PR `gh` reports as not-cleanly-mergeable — recoverable (a cherry-pick-onto-a-fresh-branch-plus-force-push repair; see `cla.io/overlays/spec-to-pr.md` for a real recovery precedent), but avoidable for a one-line fix. `git fetch origin <base-branch>` first makes `origin/<base-branch>` current without touching the primary clone's checked-out branch, so this is safe even while another session holds the primary clone.

- The worktree is created **on `<branch>`**, so Ship's branch preflight takes the "already on `<branch>`" path (skips collision-check + checkout) — see the Ship stub's branch-preflight invariant (full recipe in `references/ship.md`).
- **existing-change mode:** the change dir must already be committed (so `git worktree add` from `<base-branch>` includes it). **description / explore-result mode:** the artifacts are created inside the worktree during Propose — fine.
- The two runs are fully isolated: different worktrees, different HEADs, different change dirs. Shared-file merge conflicts are limited to append-only `cla.io/retro/spec-to-pr-runs.jsonl` and `TODO.md` (trivial "keep both lines" resolutions if both PRs touch them).
- **Cleanup:** the worktree persists after the run (the session lives in it). After the PR merges, remove it from the primary clone: `git worktree remove <worktrees-dir>/<change>` (the branch is already deleted by `gh pr merge --delete-branch`).

## Session-model routing & escalate-up

The routable dispatches (Implement/Revise agents) follow `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md`. The **inline** judgment moments — Propose authoring, the Review verdict, Revise triage — run at the session model, which the skill cannot change mid-run. To protect quality on a **sub-Opus session**, escalate the two highest-leverage of those *up*:

- **Propose authoring** (description / explore-result modes): dispatch the proposal/design/tasks authoring to an `opus` `Agent`, then continue inline.
- **RETHINK-borderline Review verdict**: when the inline review lands at the FIX-FIRST/RETHINK boundary, second it with an `opus` `Agent` fed the context brief before committing to the verdict.

On an **Opus session this is a no-op** (inline already is Opus). No flag — read the session model from the environment context. Record whether it fired in the run log (`routing.escalate_up_fired`, Handoff step 5). Full rationale + table: `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md`.

## Workflow phases

Order: Precheck → Propose → Review → Implement → Test → Ship → Revise → Archive → Handoff.

### Propose

| Mode | Action |
|---|---|
| description | `Skill(openspec-propose, args="<description>")`, then run the post-check below. |
| explore-result | Same as description, with description inferred from conversation context. |
| existing-change | Run the post-check inline (one `openspec validate <name> --strict` call). |

**Post-check:** `openspec validate <name> --strict`. Exit 0 → status `ok`. Non-zero → status `warn`, capture stderr for the Handoff Issues section.

### Review

Cap: `--review-rounds N` (default `1`).

**Read `${CLAUDE_PLUGIN_ROOT}/skills/review-change/references/checklist.md` and execute it inline against `<change-name>`.** That file is the single source of truth for review behavior — it defines change selection, parallel artifact reads, the 10 high-yield verification checks, the context-brief table format, the size gate (small → in-context analysis; large → 3-agent dispatch), the agent prompts, parallelism analysis, and the report shape + verdict rubric.

Do NOT invoke `Skill(cla:review-change)` from Review — that adds a 1-2 turn skill-load round trip with no extra capability, because the checklist file already carries everything. The standalone `/cla:review-change` slash-command path uses the same checklist via the thin `SKILL.md` shell, so verdicts remain consistent regardless of entry point. To revise review behavior, edit `${CLAUDE_PLUGIN_ROOT}/skills/review-change/references/checklist.md`; do NOT add review logic to either the spec-to-pr orchestrator or the review-change `SKILL.md` shell.

**Cross-PR doc-staleness sweep.** When the proposal touches application source, Review MUST grep ALL repo docs — not just the directly-touched files — for references to retired concepts. Specifically: enumerate every word/symbol the proposal says it's retiring (deleted functions, removed props, replaced modules, renamed domain keys, retired mock-data constants), then dispatch this grep to the `doc-sweeper` agent (haiku, read-only — per `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md`): pass it the retired-symbol list PLUS this repo's application-scoped doc-path list (`doc-sweeper` has no built-in notion of "the repo's docs" — the caller always supplies the exact paths; see `cla.io/project-facts.md` ("Doc-sweep paths (five-path list)") for this repo's exact list, falling back to `cla.io/overlays/spec-to-pr.md` if that file is absent).

It returns the hit list `path:line — symbol` plus a mandatory `Scanned: N files` accounting footer. **Check the footer before trusting the result**: `Scanned: 0` for any supplied surface, or a non-empty `Unresolved` list, means the sweep searched less than you asked — fix the path list and re-dispatch (a real sweep once returned a silent false-negative over an entire skills tree this way). Surface every hit as an Important Review finding. This matters especially for this repo's own load-bearing conventions (see `cla.io/overlays/spec-to-pr.md`) where a stale doc reference can mask a broken key contract.

**Same sweep applies to `.claude/`-meta changes, not just application code — run it as an additional `doc-sweeper` dispatch in the SAME Review pass, not a separate later step.** When the proposal touches a `${CLAUDE_PLUGIN_ROOT}/skills/<name>/SKILL.md` or any `${CLAUDE_PLUGIN_ROOT}/skills/<name>/references/*.md` file, apply the identical grep discipline within that skill's own reference network: enumerate every mechanism/rule the change retires or alters (a dispatch mechanism, a demotion policy, a tool dependency), then dispatch `doc-sweeper` again with the retired-mechanism list PLUS a **different**, skill-directory-shaped doc-path list: `${CLAUDE_PLUGIN_ROOT}/skills/<name>/SKILL.md`, `${CLAUDE_PLUGIN_ROOT}/skills/<name>/references/*.md`. A `.claude/`-meta change is otherwise invisible to the application-scoped sweep above, which only knows the application-shaped globs.

**Thin-Review defaults (per `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/runtime-rules.md`).** On a **large** change (3-agent dispatch per the checklist size gate), the *mechanical* portion of the checklist's claim-verification (checks 0a–0h) defaults to a `fact-gatherer` dispatch that returns the context-brief rows as a structured pass/fail table, so the raw greps/reads stay out of the orchestrator context — you still adjudicate every ✗ row. This default is defined once in the shared `review-change/references/checklist.md` ("Cost offload for large changes"), which also drives standalone `/cla:review-change`; do NOT restate the review logic here. Both `fact-gatherer` and `doc-sweeper` return a schema'd object (the pass/fail table / the `path:line — symbol` hit list), not prose.

For each round:
1. Run the review (inline or via Agent per the size gate).
2. Parse the verdict line from the report (`READY` / `FIX FIRST` / `RETHINK`).
   - **Sub-Opus escalate-up.** If the session is below Opus AND the verdict sits at the FIX-FIRST/RETHINK boundary (a borderline call — not a clean READY, and not a clean RETHINK where every Critical/Important genuinely requires re-opening the design conversation, as opposed to several findings that are each single-edit fixes), second it with an `opus` `Agent` fed the same context brief before proceeding — see "Session-model routing & escalate-up" above. On an Opus session, or a verdict that isn't borderline, skip this step. Record whether it fired in `routing.escalate_up_fired`. (Judge "borderline" the same way `review-change/references/checklist.md`'s verdict rubric does — by the kind of fix needed, never by raw Critical/Important count alone; a change with several Criticals that are all contained single-edit fixes is a clean FIX FIRST, not something sitting at this boundary.)
3. If `READY` → status `ok`, exit loop.
4. If `FIX FIRST` or `RETHINK`:
   - Apply each Critical and Important finding via direct Edit/Write to the artifacts under `openspec/changes/<name>/`. When the edit is prose (not a structural fix), prefer this repo's canonical terms from `cla.io/terminology.md` if it exists and covers the concept (soft — proceed on your own judgement if absent or silent on the term).
   - **Re-validate (lightweight, not a re-dispatch).** For each Critical+Important finding just applied, perform a targeted check that the fix actually landed in the artifact: grep the artifact for the symbol/heading/clause the finding named, or re-read the section that should now reflect the change. If any fix appears incomplete (the named issue is still visible in the artifact), apply a follow-up edit in the same round before exiting the loop. Re-validation is NOT a re-dispatch (cost stays small) — it is a "did the edits land?" verification using the same tools that applied them.
   - Run `openspec validate <name> --strict` as the final correctness check after all fixes for the round. Exit 0 → fixes are at least structurally sound.
   - Decrement remaining round budget. If exhausted, status `warn`, exit loop with residue captured for the Handoff Issues section. If verdict was RETHINK and Critical-count > 0 after re-validation, mark `warn` even if budget remains — the next round is the user's call.

### Implement

**There is no `openspec apply` CLI subcommand** — `openspec.cmd` only ships `init / update / list / view / change / archive / spec / config / schema / validate / show / status / instructions / templates / schemas / new`. Apply is a Claude-Code skill, not a CLI flag.

1. **Pre-check (Python packaging gotcha).** Scan `tasks.md` for subtasks that promote a `.py` file to a package (e.g. "add `<name>/__init__.py`" or "rewrite imports as `from .X import Y`"). If any subtask renames or splits a module that has a sibling file with the same stem (e.g. `tests/fixtures.py` AND `tests/fixtures/` both exist or would coexist), flag it: `python3 -m <pkg>.<sibling>` will silently resolve to the file, not the directory. Resolve by collapsing the file into `<sibling>/__init__.py` before the package promotion. Capture the resolution as a one-line note for the Handoff report.

2. **Trust-but-verify the probe.** `probe_state.py`'s `implement` field reads `openspec status --json isComplete`, which only checks artifact-file presence (proposal.md, design.md, tasks.md, specs/) — NOT task-box state. A change with all four artifacts present but every `- [ ]` unticked still reports `implement: true`. Before skipping Implement on a resume, count unticked tasks: `grep -c '^- \[ \]' openspec/changes/<name>/tasks.md`. If > 0, treat `implement` as `false` and proceed with Implement regardless of the probe.

3. **Implement.** Default: invoke `Skill(openspec-apply-change, args="<change-name>")` (also surfaced as the `/opsx:apply` slash command — same skill, different entry point). The skill walks `tasks.md` subtask-by-subtask, edits the implementing modules and tests, and ticks each checkbox.

   **Inline-implementation escape hatch.** Use direct `Edit`/`Write` calls instead of the skill when you already hold the artifacts + source in context (skill hop would be pure indirection) or when the work needs repo-specific side knowledge the skill doesn't carry. See "When NOT to use `Skill()`" above.

   **Delegate-to-subagent escape hatch (context economy on a big change).** For a large multi-file implementation, dispatch ONE coding `Agent` at `model: sonnet` (per `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md`) to do the edits + tests. **Sized trigger:** delegate when `tasks.md` has **> ~15 subtasks OR the change touches > ~8 files**; below that, implement inline (a delegation brief costs more than it saves on a small change). Judgment, not a hard cutoff.

   Structure the brief per `references/subagent-brief.md` (scope / task / do-not-touch / report / done-when) — this delegate is where that file's "done when" slot came from. Its **do-not-touch** slot is the one this site has historically left implicit: name the paths the orchestrator is holding and any a sibling dispatch owns, since scope alone doesn't say what is *someone else's*.

   Three rules make the delegation safe:
   - **Full-task enumeration.** The brief MUST enumerate **every** task in `tasks.md` (or explicitly mark the ones you're deferring) — an agent implements exactly what the brief lists and will NOT invent an omitted task, so a task left out of the brief silently stays undone.
   - **Trimmed brief.** Inline `tasks.md` plus ONLY the `design.md` sections the tasks actually reference — not the full proposal/design/spec. The agent needs the task list and the design decisions those tasks implement, nothing more; a full-artifact dump is wasted input tokens.
   - **Evidence-based terminal contract.** Instruct the agent to end with an explicit `done` or `blocked` status. `done` is valid ONLY when accompanied by hard evidence: the test-run summary line (e.g. `npm run test` output, or the relevant suite's pass count) and the ticked-task count (`- [x]` count vs total). A return that claims done without that evidence is treated as **not done** — do not trust it.

   After the agent returns, run the Post-check task-box count **regardless of what the agent reported** and finish any task it skipped. The post-check is the deterministic backstop; the terminal contract just catches a hallucinated-completion one phase earlier.

   **Contract firings leave a trace.** When the contract fires — the delegate claimed `done` without evidence, OR the post-check finds unfinished tasks after a `done` — recovering inline is correct, but the event MUST be recorded as a Handoff Issue (e.g. `Implement delegate claimed done without evidence; 3 tasks finished inline`). Silently absorbing it would mask exactly the delegation-reliability signal the routing telemetry exists to collect. On a `blocked` return: finish the remaining tasks inline (or resolve the blocker and re-dispatch once), and record the blocker as a Handoff Issue either way.

4. **Post-check:** `openspec status --change <name> --json` returns `isComplete: true` AND every `- [ ]` in `tasks.md` is now `- [x]`. ✓ on both true. ⚠ otherwise; capture the unfinished tasks for the Handoff Issues section.

   **Live-run / experiment-verification tasks are NOT Implement misses.** A subtask that can only be completed by running the *built* tool (e.g. "record the `--walk-forward` stability verdict", "capture the live `--folds` output") or that is blocked on an external deploy / cache rebuild is structurally not completable in-build. Do NOT let it produce an Implement `warn`. Recognize this shape at **Propose** and record such tasks as explicit `deferred-to-TODO` items (TODO.md, surfaced in Handoff) from the start; at Post-check, treat a remaining live-run/deploy-blocked task as ✓-with-deferral, not ⚠.

### Test

Cap: `--test-rounds N` (default `3`).

The correctness gates are the root package's `build`/`lint`/`test` scripts. In a workspace/monorepo, these are typically themselves a fan-out (e.g. `pnpm -r --if-present run <script>`) across every app/package: `build` (the typecheck + bundle primary gate; fails on any type error anywhere in the workspace), `lint` (workspace-wide), and `test` (every app/package's own test suite, when a `test` script is present). So running these three at root already covers the whole workspace in one shot — there is no separate per-app/package suite to union in. Test runs whichever of these exist, in that order. See `cla.io/project-facts.md` ("Dev / build / test commands", "Workspace shape") for this repo's exact command set and app/package list (falls back to `cla.io/overlays/spec-to-pr.md` if that file is absent).

**Which gates to run.** Take the changed paths from `git diff --name-only <base-branch>...HEAD`, then read the command set out of `cla.io/project-facts.md` ("Dev / build / test commands") — that file is this repo's own record of them, whatever its stack, and `/cla:sync-context` keeps it current. Split into two tiers: **`smoke`** is the cheap fast-fail one (the lint command, typically milliseconds); **`full`** is the slow correctness tier (the build/typecheck command — the primary gate — then the test command). Whichever the repo doesn't have, it doesn't run.

**No gates to run means one of two different things, and they are NOT interchangeable.** No changed path is source-affecting → status `skip`; there is genuinely nothing to gate. Source-affecting means any path with a `src` component, or any file whose suffix belongs to the repo's own source or config — `.ts .tsx .js .jsx .mjs .cjs .py .go .rs .java .rb .php .sh .sql .vue .svelte .json .yaml .yml .toml .css .scss .html` and anything else this repo actually builds from. **The list is illustrative, not exhaustive: when a suffix is not on it, treat the path as source-affecting.** `.py` is called out because it was once missing, and in a Python repo a real source change then did not register as source-affecting at all — the run reported a clean docs-only skip having gated nothing. A closed list reproduces that defect for every language it omits. **The repo has source changes but names no commands → NOT a skip.** Treat it as **`warn`**, and say so plainly: either `project-facts.md` is stale (run `/cla:sync-context`) or the repo has no correctness gate at all. Reporting that case as a skip announces a source change as docs-only and silently runs no gate; the reason is plausible enough that nobody questions it, which is what makes it worse than a missing gate.

For each round — **smoke tier first, then full** (fail cheap before paying for the slow gate):
1. Run every `smoke` invocation. Any failure → diagnose (a lint violation, in whichever app/package it surfaced) via Edit and decrement budget; do NOT run the `full` tier this round — re-run from smoke next round. `smoke` is a pre-filter, not a correctness proof, so a smoke pass does NOT let you skip `full`.
2. Smoke clean (or empty) → run every `full` invocation, in order (the build script first — it is the primary gate — then the test script). These fan out across the whole workspace regardless of which package-manager wrapper invokes them.
3. Exit 0 across smoke AND full → status `ok`, exit loop.
4. Any `full` failure → diagnose (a typecheck error, a test failure) via Edit, decrement budget. If the budget is exhausted at any point, status `warn`, exit loop with the failing check(s) and the first error captured for the Handoff Issues section.

User can override via `--test-cmd "<cmd>"` to run a literal command instead of discovery.

**"Diagnose" in steps 1 and 4 means state a cause before editing.** The round budget bounds how many attempts you get, not how well-reasoned each one is — and an edit made without a stated cause spends a round either way. Per failing round: name the cause in one sentence specific enough that the fix follows from it (a restatement of the symptom is not a cause); read the actual failure output rather than inferring from the check's name, since a typecheck error or assertion diff *is* the diagnosis; and say what the re-run should do before running it, so a wrong hypothesis is eliminated rather than merely retried.

The failure mode this closes is the symptom fix: loosening an assertion, widening a type, or wrapping the failing call turns the gate green without touching the defect, and the gate cannot tell the difference. Unlike `/cla:lite-pr` — which HALTS on an unresolved failure — this phase is deliberately warn-and-continue, so a suppression here doesn't stop the run; it ships, and Revise never sees it because the gate reported clean. If the only account you can give for a fix is that it makes the check pass, record the round as `warn` with the real failure rather than banking the green.

**A repo-specific hard gate's own infra flakiness is transient, not a real failure — auto-retry before believing it.** When this repo has an extra hard-gate test suite that depends on locally-running infra (e.g. a database stack), a specific, recurring failure mode in that infra's own CLI can surface as a DIFFERENT test file failing on each run rather than a real assertion error — that's the signature of a startup/parallelism race in the infra tooling itself, not a code regression. Recognize it by: the failing FILE changes between otherwise-identical runs, and/or the stderr names the infra tool's own internal error, not an assertion. Remediation, in order, before ever recording a Test `warn` for this gate: (1) retry the gate once — a bare retry often clears it; (2) if it recurs, restart the local infra stack, then re-run; (3) confirm it's the race, not a real break, by running the specific failing file(s) in isolation — they pass standalone iff it was the parallelism race. Only after (1)-(3) still fail on the SAME file with a REAL assertion error is it a genuine regression worth a `warn`. Do NOT "fix" a known, pre-existing, deferred instance of this race inside an unrelated change's PR. See `cla.io/project-facts.md` ("Dev / build / test commands") for this repo's exact gate command, and `cla.io/overlays/spec-to-pr.md` for the specific CLI/error signature and its remediation commands.

**End-to-end UI smokes are OPTIONAL / manual, never a hard gate.** When this repo has a scripted browser-driven smoke test, it typically requires a dev server already running locally. Because the orchestrator does not stand up a dev server, do NOT run it as a blocking check and do NOT let its absence produce a Test `warn`. Mention in the Handoff report that the smoke is available for a manual pre-merge sanity pass, and flag it as recommended when the change touches the runtime flow it exercises. A repo may have more than one such smoke (e.g. one per app/product surface) — see `cla.io/project-facts.md` ("Test-file locations", "Ports") for this repo's exact smoke-script paths and dev-server commands/ports (falls back to `cla.io/overlays/spec-to-pr.md` if absent), and any additional local-infra prerequisites (e.g. a database stack) they need.

**External-API fetcher fixture (judgment note, not an automated gate).** When a change adds or extends code that calls an external HTTP API, check whether its test coverage includes at least one fixture captured against the real response shape, not stub-only mocks with an assumed shape. A stub built from a wrong field-name assumption can pass every test while the mismatch ships and only surfaces on the first live call post-merge (see `cla.io/overlays/spec-to-pr.md` "Incident history" for this repo's concrete adapter example). This is a Review/Revise judgment call, not a scripted diff-scan — flag it as an Important finding when spotted, rather than building a brittle automated detector for it.

### --- Autonomy gate ---

**Default behavior is continuous end-to-end execution. The orchestrator runs Propose → Handoff without stopping for ANY confirmation, including before push. This is non-negotiable in the default mode.**

Do NOT:
- ❌ Add model-side "confirm to proceed?" prompts at phase boundaries.
- ❌ Pause to summarize what's about to happen and wait for an "ok".
- ❌ Ask "ready to push?", "shall I continue to Revise?", "merge now?", or any variant.
- ❌ End a turn with a question and wait for user input between phases.

The user invoked `/cla:spec-to-pr` precisely to skip those interruptions. A phase-boundary confirmation prompt is a regression against the documented contract — past sessions have lost ~5 minutes per pause to model-side gating that the SKILL.md never authorized. Future invocations: if you find yourself drafting a "confirm to continue" sentence between phases, delete it and just run the next phase.

**No finality-suggesting headers between phases either.** A `## Implementation Complete` / `## Done` / `## Summary` Markdown header at the end of Implement (or any intermediate phase) reads as a *terminus* to the user even when the next tool call is queued. Likewise, between Ship (PR open) and Revise (agent dispatch), any narrative paragraph longer than one sentence reads as a stop. Rule: in `--auto`, phase transitions emit AT MOST one brief sentence per boundary (e.g. `**Revise:** dispatching 3 review agents.`). No headers, no bullet lists, no itemized summaries. The Handoff terminal report is the ONLY place a finality-shaped block is appropriate.

Three narrow exceptions:
- **Bootstrap permission decline** (already defined above) — halts before any phase runs.
- **`--gate-on-push` or `--interactive` flag explicitly passed in the invocation args** — pauses immediately before push + PR open. Decline → halt cleanly, mark Ship/Revise as `skip` with reason "user declined gate", proceed to terminal report.
- **Mid-flow scope-split ask** (Review authorized; same shape as the investigation-first detector). When Review audit finds the artifact is materially stale or its scope is materially inconsistent with the proposal — symptoms include missing-symbol claims against current code, wrong dict-keys in TypedDict definitions, Literal-value drift (e.g., a `Literal["fired","not_fired","unknown"]` shipped before suffixed statuses were added by a sibling change), a BREAKING semantic dependency on an un-shipped sibling, or task groups that span clearly separable concerns better shipped as multiple PRs — one `AskUserQuestion` with explicit-paths is allowed mid-flow to scope-down before Implement. This is NOT a "confirm to proceed" pause; it is a design-decision gate (same kind as investigation-first). The trigger is *content-based* (drift / inconsistency / separable-concerns), not size-based — a 30-task-group proposal that's internally coherent and matches current code does NOT need a scope-split ask. Phrase the ask as 3–4 explicit paths (tight scope / medium scope / full scope / halt) like the investigation-first detector.

In `--auto` mode (the default — applies whenever neither `--gate-on-push` nor `--interactive` is in the args), Ship (commit + push + PR) follows Test (tests) immediately. Revise (PR review) follows Ship immediately. Archive (archive) follows Revise immediately. Handoff (terminal report) follows Archive immediately. No turn boundary, no question, no wait.

User-driven mid-run interrupts (Ctrl-C, an explicit "stop" / "halt" / "wait" message) still halt — that's a hard interrupt, not a model-side pause. End-of-turn handoffs that wait for user input are NOT acceptable in `--auto`.

**Revise (PR review) is also in scope of "continuous".** The Revise Round 1 agent dispatch happens automatically after Ship's PR opens. Do NOT skip Revise when the user said "merge and clean" — that phrase is about post-Archive cleanup (merge + branch delete), not a directive to bypass review. If the user wants to skip review explicitly, they will say `--skip-review` or `no review`. (Past sessions have over-interpreted "merge and clean" as "skip review" — that was an error; review is part of the default flow.)

**Revise always runs the full agent dispatch per the agent-selection table** below. There is no "degraded" mode and no PR-count threshold that reduces agent count. The table is the source of truth: pick every row whose "Diff contains" condition matches the PR — `code-reviewer + silent-failure-hunter` for any logic / behavior code; `+ pr-test-analyzer` when tests are added; `+ type-design-analyzer` when new types are added; `+ comment-analyzer` when new comments / docs are added; `+ plugin-dev:skill-reviewer` when a `${CLAUDE_PLUGIN_ROOT}/skills/*/SKILL.md` frontmatter changes or a new skill is created. Sub-agents have their own context windows, so dispatching them consumes far less of the parent context than reading the diff inline would — the parent only sees each agent's final summary. If you find yourself drafting a "to save budget I'll only run 1 agent" rationale, delete it and dispatch every row the table says applies.

### Ship — commit, push, open PR (inline)

**Read `references/ship.md` first** — the full staging/commit/push/PR recipe, branch-name heuristic, and scratch-artifact-hygiene detail. Run inline (no `commit-push-pr` skill hop). Load-bearing invariants (hold these even if the reference isn't reloaded):

- **Branch preflight dispatches on the current branch** (`git rev-parse --abbrev-ref HEAD`): already on `<branch>` → SKIP collision-check + checkout, stage directly (the collision check false-positives on the branch you're on); on `<base-branch>` → check `git rev-parse --verify --quiet refs/heads/<branch>` and `git ls-remote --exit-code --heads origin <branch>` (branch exists either side, or `ls-remote` fails for any reason other than a clean "absent" → `warn` and **Ship + Revise + Archive all become `skip`**; both clean → `git pull` then `git checkout -b <branch>`); any other branch → fail loudly, **except** a `/cla:new-worktree`-created branch with zero commits ahead of `origin/<base-branch>` (post-fetch) AND no pre-existing remote `<branch>` — rename it in place (`git branch -m`) and proceed as if already on the feature branch (full check commands: `references/ship.md` §1).
- **Verify `git_state.py --expect-branch <branch>` before staging** (hoisted rule); exit 2/3 → halt and surface.
- **Scratch-artifact hygiene:** before staging, scan `git status --porcelain` untracked entries for a stray repo-root scratch artifact and delete it — never fold it into the commit (signature in `cla.io/overlays/spec-to-pr.md`).
- **Path-scoped `git add`, NEVER `-A`** (hoisted rule): enumerate the specific `apps/*/src/`/`packages/*/src/` (or, for a `.claude/`-meta change, the specific skill files) + the change dir; add any other legitimately-touched top-level file by name.
- **PR body is one line, no `\n#`** (parser bug); commit subjects are one line per the message-style table. **Post-check:** `gh pr view --json state` = OPEN → ✓; gh failure → ⚠ and Revise becomes `skip` (cannot review a PR that doesn't exist).

### Revise — PR-review loop

**Read `references/revise.md` first** — the agent-selection table, the round-1 `Workflow` fan-out snippet + diff-embedding discipline, the round-≥2 mechanics, the commit recipe, and the full prose behind each invariant. Cap: `--pr-rounds N` (default `2`). Load-bearing invariants (hold these even if the reference isn't reloaded):

- **Round 1 = ONE `Workflow` fan-out** (default regardless of diff size — describe the diff by file+symbol, never paste raw diff into the script string); **round N≥2 = direct `Agent`** scoped to the previous fix commit's diff. Never chain through `Skill(pr-review-toolkit:review-pr)`.
- **Dispatch EVERY agent-selection row the diff matches** — no budget-based reduction, no "degraded" mode. `code-reviewer` + `silent-failure-hunter` are the floor for any logic/behavior code.
- **`code-reviewer` and `silent-failure-hunter` are NEVER demoted — in ANY round** (the round-≥2 tier-down exempts them): a cheaper bug-hunter's phantom findings cost more to triage than the saving.
- **Completeness:** if a Workflow round's `reported < launched`, confirm via the run's `journal.jsonl` and re-dispatch the genuinely-missing agents via `Agent`; a crashed reviewer must never vanish silently (→ `warn` only if it still won't return). If the `Workflow` tool is **unavailable** (a capability gap), fall back to direct `Agent` dispatches → `ok` with a note (an absent capability isn't a run problem); if a **present** `Workflow` call **fails**, same fallback but → `warn`. An empty `findings` array is accepted at face value.
- **SEV-MAX:** the same finding rated differently by two agents is triaged at the HIGHER severity, always.
- **Triage every Critical/Important into Applied (fix lands this round) or Deferred-Known-Issue (with a one-line rationale, surfaced in Handoff + PR body).** A finding never exits "unaddressed"; Suggestions flow to the optional `docs: TODO.md` commit.
- **Fix-delegate default (thin-orchestrator, `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/runtime-rules.md`):** a fix-set past the existing sized-trigger (> ~15 subtasks-equivalent OR > ~8 files) delegates the mechanical EDIT APPLICATION to the existing generic coding `Agent(model: sonnet)` (NO new "fix-applier" agent) with the `done`/`blocked`+evidence contract — but the orchestrator RETAINS its own post-fix re-verification (INT-CAP/INT-SYC/SIR-TEST); that is never delegated. Below the trigger, apply inline.
- **SIR-TEST:** a subtle-implementation-risk finding ("letter-but-not-spirit") is Applied only when a dedicated regression test that would fail on the letter-but-not-spirit implementation lands and passes.
- **INT-CAP / INT-SYC:** a finding is Applied only when the defect is shown gone by a re-read of the corrected code — never because an edit was attempted, the budget is running out, or someone asserts "already handled." A finding never silently evaporates.
- **Verify before applying any Critical claiming internal control-flow / runtime / DB semantics** — read the actual flow first (1 Read); a runtime/DB scratch check MUST structurally mirror the real object or defer to the change's own implementation test.
- **Commit `fix: review round <N>`** (subject structurally drives `probe_state.py`) after a `git_state.py --expect-branch` check; inspect the `git push` exit code in-context (no `|| {…}`), `warn` on failure. **Exit gate:** 0 untriaged Critical/Important → `ok`; cap exhausted with residue → `warn` + capture for Handoff. Continue-on-everything: never halt.

### Archive

**Read `references/archive.md` first** — the full archive-and-commit recipe, the capability-enumeration step, the scope-assertion and push-post-check commands. Archive materializes the active `openspec/specs/<capability>/` and moves the change dir to `openspec/changes/archive/<YYYY-MM-DD>-<change-name>/`, committed to the same PR so it merges atomically. Load-bearing invariants (hold these even if the reference isn't reloaded):

- **Run `openspec archive <change-name> --yes` directly** (no `Skill(openspec-archive-change)` hop). Post-check: the dated archive dir's `proposal.md` exists AND the change dir's no longer does. First run the pre-archive main-spec heading-sanity checks + retired-path cleanup per **`references/archive-preflight.md`**, remediating in the same commit.
- **Commit the already-staged set; do NOT re-stage here.** `openspec archive` has moved the change dir off disk, so a `git add` naming a rename-source path fails with `did not match any files` and takes the commit with it. Once the two-sided scope assertion has passed, `git commit -m "chore: archive <change-name>"` (full detail: `references/archive.md`).
- **Enumerate EVERY capability the change modifies** (`ls openspec/changes/<change-name>/specs/`) — a change can materialize MORE THAN ONE; stage one `openspec/specs/<cap>/` group per capability.
- **Path-scoped staging, NEVER a broad `git add openspec/`** (it sweeps sibling untracked change dirs in a chain). Stage only the change dir (deletions) + the dated archive dir (additions) + each capability's `openspec/specs/<cap>/`.
- **Two-sided scope assertion on `git diff --name-only --cached`:** reject any staged path outside {change dir / dated archive dir / `openspec/specs/<cap>/spec.md` per capability} (over-staging → halt via `AskUserQuestion`), AND confirm every capability under `.../specs/` has its `openspec/specs/<cap>/spec.md` staged (under-staging → silent active-spec drift; stage it and re-diff).
- **Push post-check (required):** a 0-exit `git push` is NOT sufficient — verify HEAD branch = `<branch>`, `@{u}` == HEAD sha, and that sha appears in `gh pr view <#> --json commits` (each a separate Bash call, compared in-context). Any failure → Archive `⚠` + prominent Handoff warning "archive commit DID NOT REACH the PR". The archive commit is NOT re-reviewed. Rationale (archive-while-OPEN): `references/design-tradeoffs.md`.

### Handoff

**Read `references/handoff.md` first** — the exact terminal-report shape, the PR-body mirror, the TODO.md persistence format, and the run-log append. Load-bearing invariants (hold these even if the reference isn't reloaded):

- **Emit the terminal report inline** (rendered Markdown, not a file): header, PR/branch/mode/caps, per-phase glyph table, counts, Issues encountered, Deferred-Known-Issues (each with rationale), Deferred-to-TODO.md, and Next steps — sections in that order, "(none)" for empty ones.
- **Next-steps gating** (the load-bearing rule): **all ✓** → print `gh pr merge <#> --squash --delete-branch` — EXCEPT on a stacked child (`--pr-base` passed), where the PR lands parents-first via the chain's landing checklist; print "lands with its chain — see the multi-pr report" instead of a bare merge command; **any ⚠** → print "**Review warnings before merging.**" FIRST + the warned summaries, THEN name `gh pr merge`; **any ✗** → print "**This PR is NOT ready to merge.**" and do NOT name `gh pr merge`. Never name `openspec archive` (Archive did it). The skill is development-only — no merge/deploy.
- **Persist Deferred-Known-Issues + Suggestions to `TODO.md`** (`docs: TODO.md`, feature branch) when either list is non-empty; mirror the Issues list into the PR body.
- **Append the per-run JSONL line** via `lib/log_run.py` per `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/run-log-schema.md`, INCLUDING the `routing` object (per-agent `revise_findings_by_tier`, `implement_delegated`, `escalate_up_fired`). Failure is non-fatal (capture stderr, do not `warn` the run).
  **The Review record's `agents` field MUST agree with its `size_gate`, every time — this is the one field this checklist has been observed to drop in practice** (a downstream repo's `/cla:spec-to-pr-retro` run flagged multiple logged runs with `size_gate: "large"` and `agents: []`, caught by `aggregate.py`'s `review_gate_pair_mismatches` metric). Large mode: `agents` MUST be `["design", "task", "spec"]` (or whichever subset actually ran). Small mode: `agents` MUST be omitted or `[]`. Set this field from what Review actually dispatched, not from memory of "what large mode usually does" — assemble it at the same point you record `size_gate`, not as an afterthought when building the JSON object for `log_run.py`.
- **Commit the run-log line to the feature branch** (`chore: spec-to-pr run log`) so it ships with the PR and never dangles — **feature-branch-only guard:** SKIP this commit when Ship was `skip` (still on `<base-branch>`); skip when `CLAUDE_RETRO_DIR` is out-of-repo. It is the LAST commit of the run, not re-reviewed.
- **Say so in the report if the run-log line was not appended or not committed** — a loose end the user should see now, not one `/cla:spec-to-pr-retro` discovers later as a missing run. It does not `warn` the run.

## Per-loop caps and fix loops

| Loop | Default cap | Override flag | What "round" means |
|---|---|---|---|
| review-change | 1 | `--review-rounds N` | one full review → apply Critical+Important → cycle |
| tests | 3 | `--test-rounds N` | one full `npm run build` + `npm run lint` pass → fix failures → cycle |
| pr-review | 2 | `--pr-rounds N` | one full or scoped PR-review → apply C+I → push → cycle |

**Cap exhaustion behavior:** mark phase `warn`, capture unresolved findings for the Handoff Issues section, **continue to the next phase**. Never halt on cap exhaustion.

## Bash-style discipline

Follow the four hard rules in `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/bash-discipline.md`. One-line summary: no compound bash (`cd && cmd`), no heredoc subshells, no multi-line `--body`, no long `git add` lists. Use `--body-file`, single-line `-m` (or `-F file`), and absolute paths.

## Continue-on-everything escalation

Never halt on a sub-step failure — every failure becomes a `warn` phase + an entry in the Handoff Issues section. The only two halt points are already defined: Bootstrap permission decline (preceds all phases) and Autonomy-gate decline (subsequent phases marked `skip`). Trade-off rationale in `references/design-tradeoffs.md`.

## Development-only boundary

The skill MUST NOT perform any deployment action:

- ❌ `gh pr merge`
- ❌ `git push origin <base-branch>`
- ❌ `npm publish`, `pip upload`, `docker push`, `gh release create`

`openspec archive` IS in scope — it runs as Archive and is committed to the same PR so it merges atomically when the user merges.

The terminal report's "Next steps for you" section names `gh pr merge --squash --delete-branch` only when ALL phases are ✓ (stacked children instead point at their chain's landing checklist — see Handoff) (see the Handoff stub's next-steps-gating invariant, full detail in `references/handoff.md`). On any ⚠, the section prints a "Review warnings before merging" preamble first; on any ✗, the section explicitly does NOT endorse merging. Archive is no longer a follow-up — Archive handles it.

## Resume / dry-run

- **Implicit resume:** when re-invoked with the same change name, run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/scripts/probe_state.py <change-name>` and skip ahead to the first not-done phase per the JSON it emits (`{propose, implement, branch, pr, fix_rounds_applied, archived, base_branch, tools_missing?, environment_errors?}`). Each phase is idempotent. `base_branch` is the resolved default branch the `branch`/`fix_rounds_applied` ranges were computed against — check it before trusting a `false`/`0` there, since a wrongly-resolved base makes both read as legitimate negatives. `environment_errors` (unusable working directory, a timed-out child) is distinct from `tools_missing` (not on PATH).
- **`--dry-run`:** every probe and check runs; every write (commit, push, PR open, openspec apply, file edit) is suppressed. Useful for testing the orchestrator itself.

## References

- `references/workflow-diagram.md` — visual phase flow + glyphs + caps
- `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md` — per-dispatch model + effort routing table (single source of truth), the escalate-up rule, and the phantom-finding rationale; pointed at from the hoisted rules, Implement, Revise, and Handoff
- `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/runtime-rules.md` — the thin-orchestrator runtime disciplines (delegation, I/O hygiene, batching, structured output); pointed at from the hoisted rules and each phase that handles bulk raw material
- `references/progressive-disclosure.md` — the plugin-wide recipe for conforming a SKILL.md to the `cla-plugin` token-efficiency requirement (keep-inline/move boundary, the repeat-offender checklist, validation); read before progressive-disclosing any skill
- `references/ship.md` — the Ship phase's full staging/commit/push/PR recipe + branch preflight (mandatory-read from the Ship stub)
- `references/revise.md` — the Revise phase's agent-selection table, Workflow fan-out snippet, round-≥2 mechanics, and the full prose behind each triage invariant (mandatory-read from the Revise stub)
- `references/archive.md` — the Archive phase's archive-and-commit recipe, capability enumeration, scope assertion, and push post-check (mandatory-read from the Archive stub; distinct from `archive-preflight.md`)
- `references/handoff.md` — the Handoff phase's terminal-report shape, PR-body mirror, TODO.md persistence, run-log append, and discipline-audit finalize (mandatory-read from the Handoff stub)
- `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/bash-discipline.md` — hard rules for emitted bash shape
- `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/past-offenses.md` — generic enforcement-tier vocabulary behind the guardrails (read only when revising a rule)
- `cla.io/overlays/spec-to-pr.md` — this repo's project-context overlay: skill-specific worked examples, permission-set intent, and the dated incidents that justify individual guardrails (read only when revising a rule or reasoning about this repo specifically); repo-wide facts (commands, app/package paths, worktree convention, doc-sweep list) live in `cla.io/project-facts.md` instead
- `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/run-log-schema.md` — per-run JSONL schema + field obligations (Handoff step 5; the contract `/cla:spec-to-pr-retro` consumes)
- `references/archive-preflight.md` — main-spec heading-sanity checks + retired-path cleanup (Archive step 1)
- `references/design-tradeoffs.md` — design rationale for inline Ship, the Revise dispatch mechanisms (Workflow fan-out round 1 / direct-Agent round ≥2), Archive archive-while-OPEN, continue-on-everything, wildcard permissions, inline Handoff report (read once when revising the design; not per run). Review does NOT invoke `Skill(cla:review-change)` — it reads `${CLAUDE_PLUGIN_ROOT}/skills/review-change/references/checklist.md` directly and executes it inline (see the Review section); the checklist file is the single source of truth shared with the standalone `/cla:review-change` path.
- `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/required-permissions.json` — bootstrap pattern set (wildcard, default; read by the permissions check above)
- `references/required-permissions-narrow.json` — per-subcommand pattern set; opt in with `--narrow`. Useful when the user prefers stricter allowlisting.
