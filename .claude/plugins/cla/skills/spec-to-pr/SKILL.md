---
name: spec-to-pr
description: "Drive one OpenSpec change end-to-end, from idea, change name or /opsx:explore result, to an opened, archived PR with review fixes applied. No merge, no deploy. Triggers: /cla:spec-to-pr, 'take this change to a PR', 'spec-to-pr the X feature'."
argument-hint: "[change-name | description | (empty)]"
---

# /cla:spec-to-pr — full-workflow orchestrator

Drives one OpenSpec change from `/opsx:propose`-input to an opened PR with PR-review fixes applied. Composes existing skills only where they add real value. **Review reads `${CLAUDE_PLUGIN_ROOT}/skills/review-change/references/checklist.md` directly and executes it inline** — the checklist is the single source of truth for review behavior, shared with the standalone `/cla:review-change` slash-command path, so verdicts stay consistent across entry points without a skill-load round trip. Phases that previously delegated to skills which then bounced their workflow back to Claude (pr-review, commit-push-pr) now invoke `Agent`, run inline directly, or (Revise round 1 only) run a `Workflow` fan-out. See `references/workflow-diagram.md` for the phase order at a glance. The generic enforcement-tier vocabulary behind the guardrails throughout this skill lives in `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/past-offenses.md`; the dated, repo-specific incidents that justify individual rules live in `cla.io/overlays/spec-to-pr.md` — read either only when revising a rule; a normal run never needs them.

**Resolving `${CLAUDE_PLUGIN_ROOT}`.** This `SKILL.md` arrives with the placeholder substituted, but a
`references/` file opened with `Read` carries it literally, and it is not an environment variable in
Bash — an unset variable silently runs the command against `/skills/...`. Before running a command
that contains the literal text, replace it with the plugin root: the `Base directory for this skill`
path with `/skills/<name>` removed, or the absolute path of any plugin file you have read, cut
at `.../plugins/cla`. If neither works, say so and stop. Detail:
`${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/plugin-root.md`.

## Skill-level rules (hoisted — read first)

- **`<base-branch>` means THIS repo's default branch, resolved — never assumed.** Every command below that names it is a placeholder, not a literal: substitute the real name before running anything. Resolve it once, at the start of the run, with `git symbolic-ref --quiet refs/remotes/origin/HEAD` (take the segment after the last `/`); if that is unset, use whichever of `main` / `master` actually exists. The harness used to hardcode `master`, which silently broke every `main`-default repo — a `master..HEAD` range there fails outright with `unknown revision` rather than returning a wrong answer, and `git checkout master` cannot succeed at all.

**`<branch>`** — the feature branch this run creates and looks up. Resolved by `scripts/_git_common.branch_name()`: the `CLA_BRANCH_PREFIX` env var, else a `cla.io/overlays/branch-prefix.local.md` overlay (a `*.local.md`, so it is never synced), else `feature/`. `probe_state._resolve_branch` falls back to the one local branch whose final segment is the change name, announces which it adopted, and refuses to guess when several match (why: `references/branch-and-pr-base.md`). Never spell `feature/<change-name>` below — use `<branch>`.

**`<pr-base>`** — the branch THIS change is cut from and its PR opened against. Default `<base-branch>`; with no flag the two are identical everywhere. **`--pr-base <branch>`** (stacked chain, `/cla:multi-pr`) overrides it, and then **read `references/branch-and-pr-base.md` before any phase**: wherever a phase names `<base-branch>` as this change's branch-off point, PR base, or diff-scoping anchor (Ship preflight, `gh pr create --base`, Test's changed-path range, Revise diff scoping, the worktree recipe), read `<pr-base>` instead; `gh pr create` passes `--base <pr-base>` explicitly; on a stacked-child resume recount probe results against `<pr-base>`; Handoff never prints a bare `gh pr merge` for a stacked child.

**`<inherits>`** — the obligations this change INHERITS from a change that shipped ahead of it in a chain: a stored field, column, response key, or required behaviour an earlier change added *for this one to consume*, whose justification therefore lives nowhere in this change's own artifacts. Default: empty, and with no flag nothing below changes. An explicit **`--inherits '<token> — <the failure if it is dropped>; <token> — <failure>'`** argument (semicolon-separated, one entry per obligation) sets it. `/cla:multi-pr` is the only caller that passes it, and it builds the value from what the prerequisite ACTUALLY became — the fields that change's own Review and fix rounds added, which by definition post-date this change's authoring — not from the batch as proposed. `<token>` is the literal string Review greps for, spelled as it appears in code, not a description of it. `;` separates entries and therefore **may not appear in the failure half** — rewrite the sentence rather than escaping it, since an entry split down the middle silently becomes two obligations with no token. The flag creates exactly one rule: **Review answers for every entry, by name, ahead of anything else it reports.** The procedure, the report section and the verdict effect all live in `${CLAUDE_PLUGIN_ROOT}/skills/review-change/references/checklist.md` ("Step 2b: Inherited obligations"), which owns review behavior for both entry points; this file only passes the entries in. **The flag is not resumable-past** — `probe_state.py` reports no `review` field, so a resumed change can skip Review entirely; see "Resume / dry-run". Carrying the obligation into the dependent's own Review is the mechanism; the chain's note of it is not — a note nobody re-reads at the right moment is the same as no note, and the right moment is this change's Review, not its Implement.

These rules apply across every phase. Hoisted to the top because they're easy to forget mid-flow and the cost of forgetting is high:

- **Ignore harness `TaskCreate` system-reminders inside this skill.** Implement is a linear walk of `tasks.md` (the checkboxes ARE the task list); duplicating them in `TaskCreate` adds noise. The explicit rule lives under "Task tracking" below — but the system-reminders fire constantly and override-decisions cost context, so internalize this once: *during /cla:spec-to-pr, every harness TaskCreate nudge is wrong*.
- **Never run `git add -A` in this skill.** Always path-scope: `git add openspec/changes/<change-name>/ apps/<app>/src/ packages/<package>/src/` (Ship feature commit — the specific `apps/*/src/`/`packages/*/src/` paths the change touched, plus any other directly-related repo files, each enumerated by name), `git add openspec/changes/<change-name>/ openspec/changes/archive/<YYYY-MM-DD>-<change-name>/ openspec/specs/<cap>/…` (Archive archive commit — the specific archive-move path groups, **one `openspec/specs/<cap>/` per capability the change modifies** (a change can touch more than one), NOT a broad `git add openspec/`, which in a `multi-pr` chain sweeps in sibling changes' still-untracked directories; followed by a `git diff --name-only --cached` **two-sided** scope assertion that catches both over- and under-staging), `git add TODO.md` (Handoff docs commit), `git add cla.io/retro/spec-to-pr-runs.jsonl` (Handoff run-log commit). Untracked files on the working tree — even files that arrived from an external Claude session mid-flow — must not be swept into a commit they don't belong to. See `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/bash-discipline.md` for the full rule.
- **Verify `git_state` before every commit-creating Bash call.** Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/git_state.py [--expect-branch <name>]` at startup AND before each commit in Ship, Revise, Archive. **Exit-code contract:** 0 = proceed; **any non-zero exit halts and surfaces to the user via `AskUserQuestion`** — never special-case "exit 1 is probably fine". Specifically: 1 = fail-closed (cannot resolve `.git`, malformed worktree marker, `git rev-parse` failed); 2 = in-progress op (cherry-pick / merge / rebase / revert / bisect from a parallel session); 3 = on the wrong branch. `git status --porcelain` alone is NOT sufficient — an external cherry-pick on a different branch is invisible to it.
- **Rebase/merge conflict resolution: show before applying.** `git checkout --theirs` in a rebase context means the commits being rebased (opposite of merge context). Read the conflict markers FIRST (`cat <file> | head -30`), name which side is which, THEN resolve. See `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/bash-discipline.md` "Conflict resolution discipline".
- **Route every dispatched agent per `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md`.** That file is the single source of truth for which model (and, for the Revise round-1 Workflow fan-out, which effort) each sub-agent runs at. Every `Agent(...)` call in Implement/Revise passes an explicit `model:`; Revise round 1 runs as one `Workflow` fan-out. On a **sub-Opus session**, apply the escalate-up rule (Propose authoring + RETHINK-borderline Review verdict → opus). Do not route inline main-loop work — only dispatched work is routable.
- **Run thin — keep raw material out of the parent context (`${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/runtime-rules.md`).** Delegate bulk raw-material handling (large diffs, wide file sets, verbose output, big claim-verification sweeps) to a sub-agent so only conclusions return; read file slices not whole files; `tail`/`head` large command output; scratch-file-then-delegate large intermediate material; batch independent tool calls into one message; prefer terse schema'd agent output over prose. This is a standing discipline across every phase, not a per-trigger step. Full rules: `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/runtime-rules.md`.

## Mode detection

Bind the invocation argument once: **`<arg>` = `$ARGUMENTS`**. Every rule below refers to `<arg>`, never re-embeds the raw token — a long invocation would otherwise be interpolated into this body once per mention. Announce the mode in the **first line** of output before any other action.

- **explore-result mode** — `<arg>` is empty. Infer the change description from the current Claude Code conversation context (typically a just-finished `/opsx:explore`). Announce: `Mode: explore-result`.
- **existing-change mode** — `<arg>` matches a directory `openspec/changes/{name}/` containing a `proposal.md`. Skip the propose phase; resume from the next not-done phase. Announce: `Mode: existing-change ({name})`.
- **description mode** — any other non-empty value. Treat as a free-form description for `openspec-propose`. Announce: `Mode: description`.

Tie-break: directory existence wins. If both interpretations apply, use existing-change.

**Empty `<arg>` with no conversation context.** If `<arg>` is empty and there is no usable conversation context to infer a description from (e.g. a fresh session), but exactly one complete change directory exists under `openspec/changes/` (a `proposal.md` present — tracked or still untracked), resolve to **existing-change mode** for that change. Only fall back to prompting the user if zero or multiple such directories exist.

### Investigation-first changes are a poor fit for autonomous /cla:spec-to-pr

If a change's first task group produces *facts the rest of the change depends on* (e.g. reverse-engineering an unknown format), do not run it autonomously: in existing-change mode ask via `AskUserQuestion` with three explicit paths — pause and validate in `/opsx:explore` / proceed on current assumptions / user points at the artifact. Full shape: `references/scope-asks.md`.

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

**Read `references/precheck.md` first** — the full recipe: the `git_state.py` in-progress-op check
and its three resolution paths, how to classify each dirty path as in- or out-of-scope, and the
three explicit options an out-of-scope path is surfaced with. Load-bearing invariants:

- **Run it after the permissions check, before announcing the mode.** It exists so a run does not
  sweep another scope's uncommitted work into this change's first commit.
- **`git status --porcelain` alone is NOT sufficient** — an in-progress cherry-pick/rebase on
  another branch is invisible to it. `git_state.py` exit 2 is the check that sees it; resolving one
  is `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/conflict-resolution.md`.
- **An out-of-scope dirty path is an `AskUserQuestion` with three paths, never a silent decision** —
  commit to base first / include deliberately in this PR / stash. Do not proceed until answered.
- Skip the whole phase only with `--no-tree-check`.

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

**One exception to subject-only:** a commit whose change asserts a measurement carries one `Measured-by: <command> — <claim>` trailer per claim, in the same final `-m` paragraph as `Co-Authored-By:`/`Claude-Session:` with no blank line — git parses trailers from the last paragraph only. Recipe and the parse check: `references/ship.md` §2b. Use `git add -- <paths>`, `git commit -m`, and a one-line `gh pr create --body` (no newline followed by `#`).

**No per-phase logs.** The only run log is Handoff's one counts-only JSONL line (`references/handoff.md`); resume reads repo state via `probe_state.py`. A multi-line Issues list for the PR body goes in `temp/spec-to-pr-issues-<change-name>.md` and `gh pr edit --body-file`.

## Task tracking

No `TaskCreate` for phase progress or for a linear `tasks.md` walk (the checkboxes are the task list). Use it only for parallel, externally gated, or cross-session sub-work.

## When NOT to use `Skill()`

Do not hop through `Skill(pr-review-toolkit:review-pr)`, `Skill(commit-commands:commit-push-pr)` or `Skill(openspec-archive-change)` — dispatch the agents, run the git/gh commands, and run `openspec archive --yes` directly. Implement is the exception: `Skill(openspec-apply-change)` carries real workflow logic; inline `Edit`/`Write` instead when you already hold the artifacts and source in context. Rationale: `references/design-tradeoffs.md`.

## Concurrent runs (two sessions, and one session with its own delegate)

A single run needs no setup — it creates `<branch>` in place. To run two or more flows at once in
the same repo, each session needs its own `git worktree`: **read `references/concurrent-runs.md`**
for the setup commands, the base-branch trap, cleanup, and the orchestrator-vs-own-delegate rule.
Two rules worth holding without reloading it:

- Branch off `origin/<base-branch>` explicitly (or `origin/<pr-base>` for a stacked child) — a bare
  `git worktree add -b <branch>` takes whatever the primary clone's local ref happens to be, which
  goes stale the moment any sibling change merges.
- **While your own Implement or fix delegate is live, run no repository-state command and no test
  suite in that checkout** — no `checkout`/`switch`/`commit`/`push`/`branch`/`stash`, no verify run,
  no killing build processes. This one applies to a **single** run, which is why it is here and not
  only in the reference: a `git checkout` mid-suite manufactures failures that read as a real
  regression, and a delegate reporting interference is reporting you, not a third party.

## Session-model routing & escalate-up

Dispatched agents follow `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md`. Inline judgment runs at the session model; on a **sub-Opus session** escalate two moments to an `opus` `Agent`: **Propose authoring** (description / explore-result modes) and a **RETHINK-borderline Review verdict**. On Opus this is a no-op. Record it as `routing.escalate_up_fired`.

## Workflow phases

Order: Precheck → Propose → Review → Implement → Test → Ship → Revise → Archive → Handoff.

### Propose

| Mode | Action |
|---|---|
| description | `Skill(openspec-propose, args="<description>")`, then run the post-check below. |
| explore-result | Same as description, with description inferred from conversation context. |
| existing-change | Run the post-check inline (one `openspec validate <name> --strict` call). |

**Post-check:** `openspec validate <name> --strict`. Exit 0 → status `ok`. Non-zero → status `warn`, capture stderr for the Handoff Issues section.

**Read live specs overview-first, in every phase that needs them.** `openspec list --specs`, then `openspec show <id> --type spec --json --no-scenarios`; read in full only the capabilities the change touches. A MODIFIED block still carries its full live requirement. design.md is written only when a stock trigger applies, and a change with no behaviour change sets `skip_specs: true` instead of inventing a requirement.

### Review

Cap: `--review-rounds N` (default `1`).

**Read `${CLAUDE_PLUGIN_ROOT}/skills/review-change/references/checklist.md` and execute it inline against `<change-name>`.** That file is the single source of truth for review behavior — it defines change selection, parallel artifact reads, the 12 high-yield verification checks (`0a`–`0l`), the context-brief table format, the size gate (small → in-context analysis; large → 3-agent dispatch, whose agent prompts live in `${CLAUDE_PLUGIN_ROOT}/skills/review-change/references/dispatch.md` and load only then), the weight and proof checks, and the report shape + verdict rubric.

Do NOT invoke `Skill(cla:review-change)` — the checklist carries everything; review behavior is edited there, never here.

**Skip the checklist pass for a change `/cla:multi-spec` already reviewed and passed.** multi-spec's batch gate ran the same checklist before the proposals PR opened, and recorded each change's result in `openspec/changes/<change-name>/review.json` (shape: `${CLAUDE_PLUGIN_ROOT}/skills/multi-spec/references/review-gate.md`, Step 7). Skip only when all of these hold; anything else, including a missing or unreadable record, runs the full checklist:

1. `git status --porcelain -- openspec/changes/<change-name>/` is empty.
2. The record parses as JSON, its `verdict` is `READY` or `FIX FIRST`, `all_applied` is `true`, and `deferred` is empty.
3. `git ls-files -s -- openspec/changes/<change-name>/ ':(exclude)openspec/changes/<change-name>/review.json' | git hash-object --stdin` equals the record's `artifacts`, so no file in the change changed after the review, whether it was merged by squash, merge commit or rebase.

When a readable record lists `deferred` findings, the full checklist takes each one as a known issue: report it at its recorded severity unless the artifacts now resolve it. A record left in place after a full review is multi-spec's history, not this Review's result.

On a skip, still run the checklist's **Step 2b** (inherited obligations), the **MODIFIED-block retention comparison** against the live spec as it is now (`${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/modified-block-retention.md`), and the **doc-staleness sweeps** below; act on their findings as a review round would. Log Review as `status: "skip"` with `reason: "reviewed by multi-spec: <verdict>"`, the record's verdict (`${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/run-log-schema.md`). The skip trusts that the record came from multi-spec's gate. It does not re-check the artifacts' claims against code that changed after that review, and nobody independently re-reads the fixes that gate applied.

**Doc-staleness sweeps — read `references/review-sweeps.md` and run them in the same Review pass.** When the proposal retires a symbol, concept or mechanism, dispatch `doc-sweeper` (haiku) with the retired list plus the repo's doc-path list from `cla.io/project-facts.md`; for a `.claude/`-meta change, a second dispatch over that skill's own `SKILL.md` + `references/*.md`. Check the `Scanned:` footer, then **re-search every zero-count symbol yourself** — a non-zero footer has still hidden real hits. Every hit is an Important finding.

**Large change:** checks 0a–0h default to a `fact-gatherer` dispatch (the checklist's "Cost offload for large changes"); you still adjudicate every ✗ row.

**Inherited obligations — hand `<inherits>` (set by `--inherits`) to the checklist; do not restate its rules here.** When `<inherits>` is non-empty, split it on `;` and pass the entries into the checklist's **Step 2b**, which owns settling them, the `### Inherited obligations` report section, and the verdict carve-out that keeps a non-honoured entry out of a `READY`. This paragraph is the hand-off, not the procedure — review behavior lives in one file, and a copy here would be the copy that goes stale. Two orchestration duties stay on this side: pass the entries in, and **run Step 2b even when the probe skips Review** (see "Resume / dry-run" below).

For each round:
1. Run the review (inline or via Agent per the size gate).
2. Parse the verdict line from the report (`READY` / `FIX FIRST` / `RETHINK`).
   - **Sub-Opus escalate-up.** If the session is below Opus AND the verdict sits at the FIX-FIRST/RETHINK boundary (a borderline call — not a clean READY, and not a clean RETHINK where every Critical/Important genuinely requires re-opening the design conversation, as opposed to several findings that are each single-edit fixes), second it with an `opus` `Agent` fed the same context brief before proceeding — see "Session-model routing & escalate-up" above. On an Opus session, or a verdict that isn't borderline, skip this step. Record whether it fired in `routing.escalate_up_fired`. (Judge "borderline" the same way `review-change/references/checklist.md`'s verdict rubric does — by the kind of fix needed, never by raw Critical/Important count alone; a change with several Criticals that are all contained single-edit fixes is a clean FIX FIRST, not something sitting at this boundary.)
3. If `READY` → status `ok`, exit loop.
4. If `FIX FIRST` or `RETHINK`:
   - **Before the round's first fix, read `references/review-sweeps.md` "Applying a round's fixes" and capture the `design.md` rejected-alternatives snapshot** — the round's fixes routinely edit `design.md` itself.
   - Apply each Critical and Important finding by direct Edit/Write to `openspec/changes/<name>/`, then re-check that each fix landed (grep or re-read the named clause — not a re-dispatch).
   - **An applied remedy that reintroduces a rejected alternative is a Critical on the fix itself** — withdraw or re-specify it. No snapshot captured → the check did not run: Review `warn`, recorded under *Issues encountered*. No `design.md` → out of scope.
   - Run `openspec validate <name> --strict` as the final correctness check after all fixes for the round. Exit 0 → fixes are at least structurally sound.
   - Decrement remaining round budget. If exhausted, status `warn`, exit loop with residue captured for the Handoff Issues section. If verdict was RETHINK and Critical-count > 0 after re-validation, mark `warn` even if budget remains — the next round is the user's call.

### Implement

**There is no `openspec apply` CLI subcommand** — `openspec.cmd` only ships `init / update / list / view / change / archive / spec / config / schema / validate / show / status / instructions / templates / schemas / new`. Apply is a Claude-Code skill, not a CLI flag.

1. **Pre-check.** When `tasks.md` promotes a `.py` module to a package beside a same-stem file, read `references/implement-delegate.md` "Python packaging gotcha" first.

2. **Trust-but-verify the probe.** `probe_state.py`'s `implement` field reads `openspec status --json`: true when `isComplete` is, or when every artifact in a non-empty `applyRequires` is `done` (a change with no design.md never reports `isComplete`). Both only check artifact-file presence — NOT task-box state. A change whose artifacts are present but every `- [ ]` unticked still reports `implement: true`. Before skipping Implement on a resume, count unticked tasks: `grep -c '^- \[ \]' openspec/changes/<name>/tasks.md`. If > 0, treat `implement` as `false` and proceed with Implement regardless of the probe.

3. **Implement.** Tests written in this phase follow `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/test-quality.md` — the rules that decide whether a test can fail at all. It covers any test; read `test-quality-gates.md` beside it only when the test is a gate or you are proving one by planting a failure. Default: invoke `Skill(openspec-apply-change, args="<change-name>")` (also surfaced as the `/opsx:apply` slash command — same skill, different entry point). The skill walks `tasks.md` subtask-by-subtask, edits the implementing modules and tests, and ticks each checkbox.

   **Inline-implementation escape hatch.** Use direct `Edit`/`Write` calls instead of the skill when you already hold the artifacts + source in context (skill hop would be pure indirection) or when the work needs repo-specific side knowledge the skill doesn't carry. See "When NOT to use `Skill()`" above.

   **Delegate on a big change** (> ~15 subtasks or > ~8 files): ONE coding `Agent` at `model: sonnet`. **Read `references/implement-delegate.md` first** — the brief and the seven rules for reading what comes back. Invariants: the brief enumerates every task; `done` counts only with the test-summary line and ticked-task count; a return with no status token is `blocked`; on any miss, run `git status --porcelain` and `git log --oneline -1` (and check for a running gate) before re-dispatching or taking over; record every contract firing as a Handoff Issue. Run the Post-check regardless of what the agent reported.

4. **Post-check:** `openspec status --change <name> --json` reports the artifacts ready (`isComplete: true`, or every artifact in a non-empty `applyRequires` `done` — the probe's rule, step 2) AND every `- [ ]` in `tasks.md` is now `- [x]`. ✓ on both true. ⚠ otherwise; capture the unfinished tasks for the Handoff Issues section.

   **Neither reads the claim under the tick, so neither can catch a task that is ticked and untrue.** The box count is a presence check on the glyph; the artifact-ready flag is weaker still and does not read task state at all (see step 2 above). Three cheap additions close it:

   - **A ticked task that names a test is checked for that test.** A task names one when it quotes a test name, has a `Test:` clause, or names a test file. For each such ticked task, grep the tree for the named test (the `def test_…`, `it(`/`describe(` string, or the file). A miss is the contract firing exactly as a `done` without evidence: record a Handoff Issue and write the test inline before leaving Implement. Each scenario a change adds or rewrites has such a task, whose test carries a `scenario: <spec> / <heading>` comment line, or a tasks.md line `manual: <heading>: <reason>`, so this check is what ties a scenario to its proof. When you write the test, put that comment line above it.

   - **A task whose text asserts a MEASUREMENT records the measured value inline.** A confirmed value, a count, a mutation-test result — the tick is not the evidence, the number is: `- [x] 4.2 … measured: 1158 passed, 1 skipped`. A delegate that must produce a number produces a real one; a delegate that need only tick a box ticks it. The briefs that demanded numbers are the ones that came back with them.
   - **Re-measure a 2–3 task sample of the measurement- or test-bearing tasks yourself** (re-run the measurement, or the named test), rather than trusting the ticks wholesale. Sampling, not exhaustive re-verification — that would cost as much as the implementation.

   **The convention, stated because nothing enforces it: a task is `[ ]` until it is done, and the prose beneath it explains why it is still open.** Ticking a box and writing "NOT DONE — blocked on X" underneath is honest work filed dishonestly, and it makes every downstream count wrong.

   **Live-run / experiment-verification tasks are NOT Implement misses.** A subtask that can only be completed by running the *built* tool (e.g. "record the `--walk-forward` stability verdict", "capture the live `--folds` output") or that is blocked on an external deploy / cache rebuild is structurally not completable in-build. Do NOT let it produce an Implement `warn`. Recognize this shape at **Propose** and record such tasks as explicit `deferred-to-TODO` items (TODO.md, surfaced in Handoff) from the start; at Post-check, treat a remaining live-run/deploy-blocked task as ✓-with-deferral, not ⚠.

### Test

Cap: `--test-rounds N` (default `3`).

The correctness gates are the root package's `build`/`lint`/`test` scripts. In a workspace/monorepo, these are typically themselves a fan-out (e.g. `pnpm -r --if-present run <script>`) across every app/package: `build` (the typecheck + bundle primary gate; fails on any type error anywhere in the workspace), `lint` (workspace-wide), and `test` (every app/package's own test suite, when a `test` script is present). So running these three at root already covers the whole workspace in one shot — there is no separate per-app/package suite to union in. Test runs whichever of these exist, in that order. See `cla.io/project-facts.md` ("Dev / build / test commands", "Workspace shape") for this repo's exact command set and app/package list (falls back to `cla.io/overlays/spec-to-pr.md` if that file is absent).

**Which gates to run.** Take the changed paths from `git diff --name-only <base-branch>...HEAD`, then read the command set out of `cla.io/project-facts.md` ("Dev / build / test commands") — that file is this repo's own record of them, whatever its stack, and `/cla:sync-context` keeps it current. Split into two tiers: **`smoke`** is the cheap fast-fail one (the lint command, typically milliseconds); **`full`** is the slow correctness tier (the build/typecheck command — the primary gate — then the test command). Whichever the repo doesn't have, it doesn't run.

**No gates to run means one of two different things, and they are NOT interchangeable.** No changed path is source-affecting → status `skip`; there is genuinely nothing to gate. Source-affecting means any path with a `src` component, or any file whose suffix belongs to the repo's own source or config — `.ts .tsx .js .jsx .mjs .cjs .py .go .rs .java .rb .php .sh .sql .vue .svelte .json .yaml .yml .toml .css .scss .html` and anything else this repo actually builds from. **The list is illustrative, not exhaustive: when a suffix is not on it, treat the path as source-affecting.** **The repo has source changes but names no commands → NOT a skip.** Treat it as **`warn`**, and say so plainly: either `project-facts.md` is stale (run `/cla:sync-context`) or the repo has no correctness gate at all. Reporting that case as a skip announces a source change as docs-only and silently runs no gate; the reason is plausible enough that nobody questions it, which is what makes it worse than a missing gate.

For each round — **smoke tier first, then full** (fail cheap before paying for the slow gate):
1. Run every `smoke` invocation. Any failure → diagnose (a lint violation, in whichever app/package it surfaced) via Edit and decrement budget; do NOT run the `full` tier this round — re-run from smoke next round. `smoke` is a pre-filter, not a correctness proof, so a smoke pass does NOT let you skip `full`.
2. Smoke clean (or empty) → run every `full` invocation, in order (the build script first — it is the primary gate — then the test script). These fan out across the whole workspace regardless of which package-manager wrapper invokes them.
3. Exit 0 across smoke AND full → status `ok`, exit loop.
4. Any `full` failure → diagnose (a typecheck error, a test failure) via Edit, decrement budget. If the budget is exhausted at any point, status `warn`, exit loop with the failing check(s) and the first error captured for the Handoff Issues section.

User can override via `--test-cmd "<cmd>"` to run a literal command instead of discovery.

**"Diagnose" in steps 1 and 4 means state a cause before editing.** The round budget bounds how many attempts you get, not how well-reasoned each one is — and an edit made without a stated cause spends a round either way. Per failing round: name the cause in one sentence specific enough that the fix follows from it (a restatement of the symptom is not a cause); read the actual failure output rather than inferring from the check's name, since a typecheck error or assertion diff *is* the diagnosis; and say what the re-run should do before running it, so a wrong hypothesis is eliminated rather than merely retried.

**Two rounds on the SAME stated cause with the gate still red → escalate to `/cla:diagnose` via `Skill(cla:diagnose)`, before the budget exhausts.** The repetition is the signal the hypothesis is wrong, and a third edit against a wrong cause spends the last round to learn nothing. `diagnose` builds a deterministic pass/fail loop and ranks falsifiable hypotheses before touching anything — the step the round loop has no room for. Say in the invocation that it runs **unattended** — that is the declaration its mode block keys on, so it inherits this run's autonomy contract, does not stop to ask, and writes its ranked hypotheses into the report instead. Its outcome feeds back here — a confirmed cause resumes the loop with the remaining budget, and a "no buildable loop" or "no correct seam" finding is a `warn` carrying that finding, not a round to retry.

The failure mode this closes is the symptom fix: loosening an assertion, widening a type, or wrapping the failing call turns the gate green without touching the defect, and the gate cannot tell the difference. Unlike `/cla:lite-pr` — which HALTS on an unresolved failure — this phase is deliberately warn-and-continue, so a suppression here doesn't stop the run; it ships, and Revise never sees it because the gate reported clean. If the only account you can give for a fix is that it makes the check pass, record the round as `warn` with the real failure rather than banking the green.

**Test quality is an Implement-phase concern** — see `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/test-quality.md`. If a red gate here forces a test edit, the same rules apply to the edit.


**An infra-dependent hard gate failing is not yet a real failure — read `references/test-notes.md` before editing for it.** Signs of the infra race: the failing file changes between otherwise-identical runs, or stderr names the infra tool's own error rather than an assertion; retry, restart, and isolate before any `warn`. The same file covers the optional browser smoke (never a hard gate).

**External-API fetcher fixture (judgment note, not an automated gate).** When a change adds or extends code that calls an external HTTP API, check whether its test coverage includes at least one fixture captured against the real response shape, not stub-only mocks with an assumed shape. A stub built from a wrong field-name assumption can pass every test while the mismatch ships and only surfaces on the first live call post-merge (see `cla.io/overlays/spec-to-pr.md` "Incident history" for this repo's concrete adapter example). This is a Review/Revise judgment call, not a scripted diff-scan — flag it as an Important finding when spotted, rather than building a brittle automated detector for it.

### --- Autonomy gate ---

**Default behavior is continuous end-to-end execution. The orchestrator runs Propose → Handoff without stopping for ANY confirmation, including before push. This is non-negotiable in the default mode.**

Do NOT:
- ❌ Add model-side "confirm to proceed?" prompts at phase boundaries.
- ❌ Pause to summarize what's about to happen and wait for an "ok".
- ❌ Ask "ready to push?", "shall I continue to Revise?", "merge now?", or any variant.
- ❌ End a turn with a question and wait for user input between phases.

The user invoked `/cla:spec-to-pr` precisely to skip those interruptions.

**No finality-suggesting headers between phases either.** A `## Implementation Complete` / `## Done` / `## Summary` Markdown header at the end of Implement (or any intermediate phase) reads as a *terminus* to the user even when the next tool call is queued. Likewise, between Ship (PR open) and Revise (agent dispatch), any narrative paragraph longer than one sentence reads as a stop. Rule: in `--auto`, phase transitions emit AT MOST one brief sentence per boundary (e.g. `**Revise:** dispatching 3 review agents.`). No headers, no bullet lists, no itemized summaries. The Handoff terminal report is the ONLY place a finality-shaped block is appropriate.

**The mechanical form of that rule, because the prohibition above has lost in practice: status text and the next tool call go in the SAME message.** If you have no tool call to pair the text with, the phase is not over — start the next phase instead of narrating the last one. Ending a turn is legitimate in exactly two cases: a backgrounded `Agent`/`Workflow` dispatch is genuinely in flight (the completion notification re-invokes the session — that is the harness, not a pause), or the run is complete. Nothing else. The discriminator is whether a **pending event** will re-invoke this session — not whether you asked the user anything, because this failure asks nothing; **announcing the next step is not a mechanism**.

Three narrow exceptions:
- **Bootstrap permission decline** (already defined above) — halts before any phase runs.
- **`--gate-on-push` or `--interactive` flag explicitly passed in the invocation args** — pauses immediately before push + PR open. Decline → halt cleanly, mark Ship/Revise as `skip` with reason "user declined gate", proceed to terminal report.
- **Mid-flow scope-split ask** (Review authorized): when Review finds the artifacts materially stale or the scope separable into several PRs, one `AskUserQuestion` with 3–4 explicit paths (tight / medium / full scope / halt) before Implement. Content-based, never size-based. Under `/cla:multi-pr` only case (f) of its closed blocker list; otherwise a GitHub issue. Detail: `references/scope-asks.md`.

In `--auto` mode (the default — applies whenever neither `--gate-on-push` nor `--interactive` is in the args), Ship (commit + push + PR) follows Test (tests) immediately. Revise (PR review) follows Ship immediately. Archive (archive) follows Revise immediately. Handoff (terminal report) follows Archive immediately. No turn boundary, no question, no wait.

User-driven mid-run interrupts (Ctrl-C, an explicit "stop" / "halt" / "wait" message) still halt — that's a hard interrupt, not a model-side pause. End-of-turn handoffs that wait for user input are NOT acceptable in `--auto`.

**Revise is part of the continuous flow.** "merge and clean" is about post-Archive cleanup, not skipping review; only `--skip-review` / "no review" skips it. Revise dispatches every agent-selection row the diff matches (`references/revise.md`) — no budget-based reduction.

### Ship — commit, push, open PR (inline)

**Read `references/ship.md` first** — the full staging/commit/push/PR recipe, branch-name heuristic, and pre-staging hygiene detail (debug tags, then scratch artifacts). Run inline (no `commit-push-pr` skill hop). Load-bearing invariants (hold these even if the reference isn't reloaded):

- **Branch preflight dispatches on the current branch** (`git rev-parse --abbrev-ref HEAD`): already on `<branch>` → SKIP collision-check + checkout, stage directly (the collision check false-positives on the branch you're on); on `<base-branch>` → check `git rev-parse --verify --quiet refs/heads/<branch>` and `git ls-remote --exit-code --heads origin <branch>` (branch exists either side, or `ls-remote` fails for any reason other than a clean "absent" → `warn` and **Ship + Revise + Archive all become `skip`**; both clean → `git pull` then `git checkout -b <branch>`); any other branch → fail loudly, **except** a `/cla:new-worktree`-created branch with zero commits ahead of `origin/<base-branch>` (post-fetch) AND no pre-existing remote `<branch>` — rename it in place (`git branch -m`) and proceed as if already on the feature branch (full check commands: `references/ship.md` §1).
- **Verify `git_state.py --expect-branch <branch>` before staging** (hoisted rule); exit 2/3 → halt and surface.
- **Pre-staging hygiene, two scans, both before staging:** `grep -rn "\[DEBUG-" <paths about to be staged>` must return zero — a hit is `/cla:diagnose` instrumentation left by an interrupted run, and the tagged line comes out before staging (the tag pattern also lives in `${CLAUDE_PLUGIN_ROOT}/skills/diagnose/SKILL.md` Phase 6; a rename must touch both or this scan checks nothing). Then scan `git status --porcelain` untracked entries for a stray repo-root scratch artifact and delete it — never fold it into the commit (signature in `cla.io/overlays/spec-to-pr.md`).
- **Every measurement this change asserts names the command that produced it**, as one `Measured-by: <the exact command, runnable as written> — <the claim it produced>` trailer per claim at the end of the commit message. This stop is where the claims get assembled, which is why the obligation sits here and not at the keyboard. A claim you cannot pair with a runnable command has two exits and both are edits: **run the command now, or delete the claim** and restate it as the reasoning it is. A change asserting no measurement carries no trailer — never `Measured-by: none`, which certifies a check nobody ran while reading as evidence that one happened. **A measurement is evidence about the tree and conditions that produced it, and nothing else.** Three shapes break that, and each reads as settled fact. A pair asserting sameness — "unchanged", "same counts", "no regression" — must come from one tree, and the trailer must name it; measured on two, the pair asserts a third claim, that conditions matched, with no command behind it. A number measured earlier and restated as current is the same defect with one run missing. A number true under the conditions it ran on — one platform, one shell, one edition — is not true generally until someone runs the others. Three exits, all edits: run the comparison now, restate the numbers as two independent observations, or name the conditions. A before/after delta is the case this does not forbid — it is two trees by construction, so name both, and the claim is about the change rather than either number. The `Co-Authored-By:` and `Claude-Session:` lines go in that same block, with no blank line before them. Git parses trailers from the last paragraph only, and that paragraph must be `key: value` lines throughout. Anything else in it — a blank line, a line of prose, a bare `Closes #199` — drops every measurement out of the block. Check it parsed before pushing: what you wrote and what git's parser sees must agree, and nothing else reports a split block (full recipe, and the measured pair: `references/ship.md` §2b).
- **Path-scoped `git add`, NEVER `-A`** (hoisted rule): enumerate the specific `apps/*/src/`/`packages/*/src/` (or, for a `.claude/`-meta change, the specific skill files) + the change dir; add any other legitimately-touched top-level file by name.
- **PR body is one line, no `\n#`** (parser bug); commit subjects are one line per the message-style table. **Post-check:** `gh pr view --json state` = OPEN → ✓; gh failure → ⚠ and Revise becomes `skip` (cannot review a PR that doesn't exist).

### Revise — PR-review loop

**Read `references/revise.md` first** — the agent-selection table, the round-1 `Workflow` fan-out snippet + diff-embedding discipline, the round-≥2 mechanics, the commit recipe, and the full prose behind each invariant. Cap: `--pr-rounds N` (default `2`) — a ceiling, not a target. Load-bearing invariants (hold these even if the reference isn't reloaded):

- **Round 1 = ONE `Workflow` fan-out** (default regardless of diff size — describe the diff by file+symbol, never paste raw diff into the script string); **round N≥2 = direct `Agent`** scoped to the previous fix commit's diff. Never chain through `Skill(pr-review-toolkit:review-pr)`.
- **Dispatch EVERY agent-selection row the diff matches** — no budget-based reduction, no "degraded" mode. `code-reviewer` + `silent-failure-hunter` are the floor for any logic/behavior code.
- **`code-reviewer` and `silent-failure-hunter` are NEVER demoted — in ANY round** (the round-≥2 tier-down exempts them): a cheaper bug-hunter's phantom findings cost more to triage than the saving.
- **Completeness:** if a Workflow round's `reported < launched`, confirm via the run's `journal.jsonl` and re-dispatch the genuinely-missing agents via `Agent`; a crashed reviewer must never vanish silently (→ `warn` only if it still won't return). If the `Workflow` tool is **unavailable** (a capability gap), fall back to direct `Agent` dispatches → `ok` with a note (an absent capability isn't a run problem); if a **present** `Workflow` call **fails**, same fallback but → `warn`. An empty `findings` array is accepted at face value.
- **SEV-MAX:** the same finding rated differently by two agents is triaged at the HIGHER severity, always.
- **Triage every Critical/Important into Applied (fix lands this round), Deferred-Known-Issue (with a one-line rationale, surfaced in Handoff + PR body), or Remedy-Rejected (next bullet).** A finding never exits "unaddressed"; Suggestions flow to the optional `docs: TODO.md` commit.
- **Fix-delegate default (thin-orchestrator, `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/runtime-rules.md`):** a fix-set past the existing sized-trigger (> ~15 subtasks-equivalent OR > ~8 files) delegates the mechanical EDIT APPLICATION to the existing generic coding `Agent(model: sonnet)` (NO new "fix-applier" agent) — but the orchestrator RETAINS its own post-fix re-verification (INT-CAP/INT-SYC/SIR-TEST); that is never delegated. Below the trigger, apply inline. **This delegate is a FIX dispatch:** brief it in `references/subagent-brief.md`'s fix-brief form under the three-status contract, and route from the **per-finding outcome list**, not the overall status.
- **`remedy-rejected` is a SUCCESSFUL return with a third triage bucket, and it costs no round.** Route it by what it cites: **the remedy** → re-decide it, finding stays **open**; **a disproved defect** (a fact row was wrong and the defect does not survive its correction) → **close** the finding as closed-by-disproof, never as Applied. A rejection whose reason resolves against nothing in the brief is not a rejection — treat it as unaddressed.
- **Round ≥2 carries its own question, in each agent's prompt:** *"Does this fix introduce the defect it fixed, somewhere else? Enumerate every other instance of the resource or shape the fix concerns."* Three things make it answerable, and it is worth nothing without them: **you name the resource** (an agent holds a diff; you hold the finding and the remedy), **you grant repo search** (a sibling instance is outside the scoped diff the prompt inlines), and **the return cites the search it ran** — `enumerated: no other instance of <resource>; searched: <command>`. An enumeration with no search behind it is a missing result, not an empty one. Skip it on the two rounds it cannot fit — one entered on an empty `PREV_FIX_SHA`, and a rejection-only re-entry dispatched against open findings — and record that round's `sibling_instance` as `null`, which is the record's spelling for "no measurement", so the skip is not later read as a measured zero. `null` also covers an enumeration still uncited after its one re-dispatch. Raises no cap and makes no second round automatic; `references/revise.md` carries why.
- **Exit gate counts TWO things, and both must be zero:** *untriaged* (in no bucket) and *open* (in a bucket, not closed). A remedy-rejected-citing-the-remedy finding is triaged and OPEN. Open > 0 with budget → re-enter the loop. Counting only untriaged exits the loop `ok` with a live Critical, and Handoff then prints `gh pr merge` over it.
- **An orchestrator-specified remedy gets one extra read.** Its post-fix re-verification also checks the applied remedy against the change's `design.md` rejected-alternatives content, read as a **round-start snapshot** (never `git show HEAD:<path>` — it fails wherever the change dir is not yet committed). A hit is a **Critical on the fix itself**: withdraw or re-specify it; it does not stand on having resolved the original finding. Mark it `remedy: orchestrator-specified` on the finding's triage record. No change directory → no such document → out of scope, not a breach. Weaker than an independent reader, and raises no cap.
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
- **Validate the LIVE spec set before the commit — `openspec validate --specs --strict`.** Validating the *change* does not cover it: this step rewrites `openspec/specs/`, and a structurally broken live spec commits, pushes and merges with every other check green. `✗ spec/<cap>` → halt via `AskUserQuestion`, do not commit. Non-zero with no `✗` line is a **tooling fault** (missing binary, CLI without `--specs`), not a spec fault. `No items found to validate.` is **not a pass** — nothing was checked.
- **Two-sided scope assertion on `git diff --name-only --cached`:** reject any staged path outside {change dir / dated archive dir / `openspec/specs/<cap>/spec.md` per capability} (over-staging → halt via `AskUserQuestion`), AND confirm every capability under `.../specs/` has its `openspec/specs/<cap>/spec.md` staged (under-staging → silent active-spec drift; stage it and re-diff).
- **Push post-check (required):** a 0-exit `git push` is NOT sufficient — verify HEAD branch = `<branch>`, `@{u}` == HEAD sha, and that sha appears in `gh pr view <#> --json commits` (each a separate Bash call, compared in-context). Any failure → Archive `⚠` + prominent Handoff warning "archive commit DID NOT REACH the PR". The archive commit is NOT re-reviewed. Rationale (archive-while-OPEN): `references/design-tradeoffs.md`.

### Handoff

**Read `references/handoff.md` first** — the exact terminal-report shape, the PR-body mirror, the TODO.md persistence format, and the run-log append. Load-bearing invariants (hold these even if the reference isn't reloaded):

- **Emit the terminal report inline** (rendered Markdown, not a file): header, PR/branch/mode/caps, per-phase glyph table, counts, Issues encountered, Deferred-Known-Issues (each with rationale), **Rejected remedies still open**, Deferred-to-TODO.md, and Next steps — sections in that order, "(none)" for empty ones.
- **"Rejected remedies, still open" is its own section and its own gate.** Every Critical/Important finding a fix delegate rejected *citing the remedy* and the run did not close. It is neither a conscious deferral nor Suggestion residue — it is a live Critical with a reason the obvious fix was rejected. **A non-empty one withholds `gh pr merge` exactly as a ✗ phase does**, even when every phase glyph is ✓: the phase tally cannot see these findings, so gating on glyphs alone prints a merge command over an open Critical. Mirror it into the PR body and persist it to `TODO.md` alongside the Deferred-Known-Issues.
- **A "deferred / not applied" list is split into three NAMED subsections — `Blocked on a missing artifact`, `Trigger condition not yet fired`, `Skipped`** — never one bucket under a single alarming label. Under the full-severity policy the first two are legitimate and the third is a policy breach, and undifferentiated they read identically: the orchestrator's only options become waving the whole section through unread or re-reading every item, every change. Splitting them makes `Skipped` non-empty a grep rather than a judgement, so Handoff can fail on it automatically.
- **Next-steps gating** (the load-bearing rule): **all ✓ AND "Rejected remedies, still open" empty** → print `gh pr merge <#> --squash --delete-branch` — EXCEPT on a stacked child (`--pr-base` passed), where the PR lands parents-first via the chain's landing checklist; print "lands with its chain — see the multi-pr report" instead of a bare merge command; **any ⚠** → print "**Review warnings before merging.**" FIRST + the warned summaries, THEN name `gh pr merge` — **EXCEPT when "Rejected remedies, still open" is non-empty, which takes the ✗ branch instead and never names the command**, because that section is a live Critical and the ⚠ branch would hand the user a merge line under it; **any ✗** → print "**This PR is NOT ready to merge.**" and do NOT name `gh pr merge`. Never name `openspec archive` (Archive did it). The skill is development-only — no merge/deploy.
- **Mirror the inherited-obligation verdict lines into the terminal report when `<inherits>` was non-empty** — one line per supplied entry, `HONOURED` ones included, in the header block ahead of the phase table. The caller passed N entries and can count N lines; without them a chain cannot distinguish a run that answered every obligation from one that dropped the flag on the floor, which is the same "wrote it and fed it nowhere" failure one layer up. Print the lines even on a resumed run that skipped Review — the "Resume / dry-run" rule makes Step 2b unconditional precisely so this section is never empty when entries were supplied.
- **Persist Deferred-Known-Issues + rejected-remedies-still-open + Suggestions to `TODO.md`** (`docs: TODO.md`, feature branch) when ANY of the three is non-empty; mirror the Issues list AND the rejected-remedies list into the PR body. A run whose only residue is rejected-open findings still writes both — a two-list trigger skips exactly the case that carries a live Critical.
- **Append the per-run JSONL line** via `${CLAUDE_PLUGIN_ROOT}/lib/log_run.py` per `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/run-log-schema.md`, INCLUDING the `cost` object (wall-clock from the run's own start/end, the session model, the number of agents dispatched, and how many were escalate-ups — never a token estimate, which the orchestrator cannot observe) and the `routing` object (per-agent `revise_findings_by_tier`, `implement_delegated`, `escalate_up_fired`). Failure is non-fatal (capture stderr, do not `warn` the run). **Build Revise's `findings_by_round` at triage time, as each round closes** — not reconstructed here (`references/handoff.md`).
  **The Review record's `agents` MUST agree with its `size_gate`** — large: the agents that actually ran; small: omitted or `[]`. Set it when you record `size_gate`.
- **Commit the run-log line to the feature branch** (`chore: spec-to-pr run log`) so it ships with the PR and never dangles — **feature-branch-only guard:** SKIP this commit when Ship was `skip` (still on `<base-branch>`); skip when `CLAUDE_RETRO_DIR` is out-of-repo. It is the LAST commit of the run, not re-reviewed.
- **Say so in the report if the run-log line was not appended or not committed** — a loose end the user should see now, not one `/cla:spec-to-pr-retro` discovers later as a missing run. It does not `warn` the run.

## Per-loop caps and fix loops

| Loop | Default cap | Override flag | Phase | What "round" means |
|---|---|---|---|---|
| review-change | 1 | `--review-rounds N` | **Review — PRE-implementation**, before Implement; reviews the *artifacts* (proposal/design/tasks/specs) | one full review → apply Critical+Important → cycle |
| tests | 3 | `--test-rounds N` | Test | one full `npm run build` + `npm run lint` pass → fix failures → cycle |
| pr-review | 2 | `--pr-rounds N` | **Revise — POST-implementation**, after Ship; reviews the *code* on the open PR | one full or scoped PR-review → apply C+I → push → cycle |

**The two review flags read backwards from their names, so state the phase, not the flag.**
`--review-rounds` sounds like the PR review and is not; `--pr-rounds` is. A user reading the
flag names alone guessed the opposite in a real run, and the cost of guessing wrong is silent:
you disable the gate you meant to keep and keep the one you meant to drop, and nothing reports
a missing review. `--review-rounds 0` skips reviewing the change *before* it is built;
`--pr-rounds 0` skips reviewing the code *after* it is built.

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

Merge-command gating in the terminal report: Handoff's next-steps rule above.

## Resume / dry-run

- **Implicit resume:** when re-invoked with the same change name, run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/scripts/probe_state.py <change-name>` and skip ahead to the first not-done phase per the JSON it emits (`{propose, implement, branch, pr, fix_rounds_applied, archived, base_branch, tools_missing?, environment_errors?}`). Each phase is idempotent. `base_branch` is the resolved default branch the `branch`/`fix_rounds_applied` ranges were computed against — check it before trusting a `false`/`0` there, since a wrongly-resolved base makes both read as legitimate negatives. `environment_errors` (unusable working directory, a timed-out child) is distinct from `tools_missing` (not on PATH).
- **A non-empty `<inherits>` survives the probe — always run the checklist's Step 2b, whatever the probe says.** The JSON above has **no `review` field**: the probe reports `propose`, `implement`, `branch`, `pr`, `fix_rounds_applied`, `archived`, so a change resumed with `implement` true skips straight past Review and every inherited obligation goes unanswered, silently, on exactly the runs a long chain is most likely to be re-entered from. So when `<inherits>` is non-empty, run **Step 2b alone** — one `grep -rl` per token and one verdict line each — *before* the first phase the probe selects, and treat a non-`HONOURED` entry as a Critical to apply to the artifacts before continuing. This is not re-running Review: Step 2b needs no dispatch, no size gate and no context brief of its own, which is why it is cheap enough to be unconditional. Print the verdict lines even when every entry is `HONOURED` — Handoff mirrors them, and a chain that sees no lines cannot tell an answered run from one that ignored the flag.
- **`--dry-run`:** every probe and check runs; every write (commit, push, PR open, openspec apply, file edit) is suppressed. Useful for testing the orchestrator itself.

## References

Phase references (`precheck.md`, `ship.md`, `revise.md`, `archive.md`, `archive-preflight.md`, `handoff.md`) are mandatory reads from their phase stubs; branch-only ones (`branch-and-pr-base.md`, `scope-asks.md`, `review-sweeps.md`, `implement-delegate.md`, `test-notes.md`, `concurrent-runs.md`, `subagent-brief.md`) are read when their trigger fires. Also: `workflow-diagram.md` (phase flow at a glance), `design-tradeoffs.md` (rationale; read only when revising the design), `required-permissions-narrow.json` (`--narrow`); shared — `model-routing.md`, `runtime-rules.md`, `bash-discipline.md`, `run-log-schema.md`, `skill-authoring.md`, `past-offenses.md`, `required-permissions.json` under `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/`; this repo's dated incidents — `cla.io/overlays/spec-to-pr.md`.
