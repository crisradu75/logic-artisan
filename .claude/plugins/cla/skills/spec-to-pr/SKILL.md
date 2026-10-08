---
name: spec-to-pr
description: "Drive one OpenSpec change end-to-end, from idea, change name or /opsx:explore result, to an opened, archived PR with review fixes applied. No merge, no deploy. Triggers: /cla:spec-to-pr, 'take this change to a PR', 'spec-to-pr the X feature'."
argument-hint: "[change-name | description | (empty)]"
---

# /cla:spec-to-pr — full-workflow orchestrator

Drives one OpenSpec change from a description, a change name or an `/opsx:explore` result to an opened, archived PR with its review fixes applied. Order: Precheck → Propose → Review → Implement → Test → Ship → Revise → Archive → Handoff (`references/workflow-diagram.md`).

**Each phase that names a reference reads it first; its stub here carries only the rules that gate correctness.** Why a rule exists is in `references/design-tradeoffs.md`, `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/past-offenses.md` and this repo's `cla.io/lessons-learned/`. Read those only when revising the skill, never during a run.

**Resolving `${CLAUDE_PLUGIN_ROOT}`.** This `SKILL.md` arrives with the placeholder substituted, but a
`references/` file opened with `Read` carries it literally, and it is not an environment variable in
Bash — an unset variable silently runs the command against `/skills/...`. Before running a command
that contains the literal text, replace it with the plugin root: the `Base directory for this skill`
path with `/skills/<name>` removed, or the absolute path of any plugin file you have read, cut
at `.../plugins/cla`. If neither works, say so and stop. Detail:
`${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/plugin-root.md`.

## Placeholders

- **`<arg>`** = `$ARGUMENTS`, bound once. Every rule refers to `<arg>` and never re-embeds the raw token.
- **`<base-branch>`** — THIS repo's default branch, resolved once at the start of the run, never assumed: `git symbolic-ref --quiet refs/remotes/origin/HEAD` (the segment after the last `/`); if that is unset, whichever of `main` / `master` exists. Substitute it before running any command that names it.
- **`<branch>`** — the feature branch this run creates and looks up, from `scripts/_git_common.branch_name()`: the `CLA_BRANCH_PREFIX` env var, else `cla.io/overlays/branch-prefix.local.md`, else `feature/`. `probe_state._resolve_branch` falls back to the one local branch whose final segment is the change name, says which it adopted, and refuses to guess when several match (`references/branch-and-pr-base.md`). Never spell `feature/<change-name>`.
- **`<pr-base>`** — the branch this change is cut from and its PR opened against. Default `<base-branch>`, identical to it everywhere when no flag is passed. **`--pr-base <branch>`** (a stacked PR, built on a still-open parent) overrides it; then **read `references/branch-and-pr-base.md` before any phase**. Wherever a phase uses `<base-branch>` as the branch-off point, PR base or diff anchor (Ship preflight, `gh pr create --base`, Test's changed-path range, Revise diff scoping, the worktree recipe), read `<pr-base>`. `gh pr create` passes `--base <pr-base>` explicitly; a stacked-child resume recounts probe results against `<pr-base>`; Handoff never prints a bare `gh pr merge` for a stacked child.

**`<inherits>`** — obligations this change INHERITS from a change that shipped ahead of it in a chain: a stored field, column, response key or required behaviour an earlier change added *for this one to consume*, whose justification therefore lives nowhere in this change's own artifacts. Default: empty, and then nothing below changes. **`--inherits '<token> — <the failure if it is dropped>; <token> — <failure>'`** sets it, one `;`-separated entry per obligation. Only `/cla:multi-pr` passes it, built from what the prerequisite ACTUALLY became (the fields its own Review and fix rounds added), not from the batch as proposed. `<token>` is the literal string Review greps for, spelled as it appears in code. `;` separates entries, so it **may not appear in the failure half** — rewrite the sentence rather than escape it, or one entry silently becomes two. The flag creates one rule: **Review answers for every entry, by name, ahead of anything else it reports.** The procedure, the report section and the verdict effect live in the checklist's "Step 2b: Inherited obligations"; this file only passes the entries in. **The flag is not resumable-past** — see "Resume / dry-run".

## Skill-level rules (hoisted — read first)

These rules apply across every phase.

- **No `TaskCreate` for phases or for walking `tasks.md`** — the checkboxes are the task list, and every harness TaskCreate nudge during this skill is wrong. Use it only for parallel, externally gated or cross-session sub-work.
- **Never run `git add -A`. Stage named paths only:** Ship — the change dir plus each source path the change touched, by name; Archive — the change dir, its dated archive dir and one `openspec/specs/<cap>/` per capability the change modifies, never `openspec/` (in a chain it sweeps in sibling changes), then a two-sided `git diff --name-only --cached` scope check; Handoff — `TODO.md`, and `cla.io/retro/spec-to-pr-runs.jsonl`. An untracked file never rides into a commit it does not belong to (`${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/bash-discipline.md`).
- **Verify `git_state` before every commit-creating Bash call.** Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/git_state.py [--expect-branch <name>]` at startup AND before each commit in Ship, Revise, Archive and Handoff. **Exit-code contract:** 0 = proceed; **any non-zero exit halts and surfaces to the user via `AskUserQuestion`** — never special-case "exit 1 is probably fine". 1 = fail-closed (cannot resolve `.git`, malformed worktree marker, `git rev-parse` failed); 2 = in-progress op (cherry-pick / merge / rebase / revert / bisect); 3 = wrong branch. `git status --porcelain` alone is NOT sufficient — an external cherry-pick on another branch is invisible to it.
- **Conflict resolution: show before applying.** In a rebase, `--theirs` is the commits being rebased. Read the markers first, name which side is which, then resolve (`${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/bash-discipline.md` "Conflict resolution discipline").
- **Route every dispatched agent per `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md`**: every `Agent(...)` passes an explicit `model:`, and Revise round 1 is one `Workflow` fan-out. On a **sub-Opus session**, escalate two inline moments to an `opus` `Agent`: Propose authoring (description / explore-result modes) and a RETHINK-borderline Review verdict. Inline work is not routable.
- **No `Skill()` hops** to `pr-review-toolkit:review-pr`, `commit-commands:commit-push-pr` or `openspec-archive-change`: dispatch the agents, run git/gh, and run `openspec archive --yes` yourself. Implement's `Skill(openspec-apply-change)` is the exception.
- **Run thin** (`${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/runtime-rules.md`): delegate bulk diffs, wide file sets and verbose output to a sub-agent so only conclusions return; read slices, `head`/`tail` long output, batch independent tool calls.
- **While your own Implement or fix delegate is live, run no repository-state command and no test suite in that checkout** — no `checkout`/`switch`/`commit`/`push`/`branch`/`stash`, no verify run, no killing build processes. A `git checkout` mid-suite manufactures failures that read as a real regression, and a delegate reporting interference is reporting you.
- **Bash:** no compound commands (`cd && cmd`), no heredoc subshells, no multi-line `--body`, no long `git add` lists; use `--body-file`, single-line `-m`, absolute paths (`bash-discipline.md`).
- **Continue on everything.** A failed sub-step becomes a `warn` phase and a Handoff Issue; it never halts the run. Apart from the `AskUserQuestion` stops this file names, the only halts are a bootstrap permission decline and a declined push gate.
- **Development only.** Never `gh pr merge`, `git push origin <base-branch>`, `npm publish`, `pip upload`, `docker push` or `gh release create`. `openspec archive` is in scope: Archive commits it to the same PR, so it merges with the change.

## Flags

| Flag | Effect |
|---|---|
| `--review-rounds N` | Review — the change's **artifacts**, before Implement. Default 1. |
| `--test-rounds N` | Test fix rounds. Default 3. |
| `--pr-rounds N` | Revise — the **code** on the open PR, after Ship. Default 2; round 2 runs whenever round 1 committed fixes; `1` opts out; `0` skips Revise. |
| `--skip-review` | Skips Revise, as does the user saying "no review". |
| `--gate-on-push`, `--interactive` | Pause before push and PR open ("Autonomy gate"). |
| `--pr-base <branch>`, `--inherits '<entries>'` | See "Placeholders". |
| `--test-cmd "<cmd>"` | Test runs this literal command instead of discovery. |
| `--narrow`, `--check-permissions` | See "Bootstrap permissions". |
| `--no-tree-check` | Skips the working-tree precheck. |
| `--dry-run` | See "Resume / dry-run". |

**The two review flags read backwards from their names, so state the phase, not the flag.** `--review-rounds 0` skips reviewing the change *before* it is built; `--pr-rounds 0` skips reviewing the code *after*. A cap exhausted with findings unresolved marks the phase `warn`, carries them to the Handoff Issues section and continues to the next phase.

## Mode detection

Announce the mode in the **first line** of output before any other action.

- **explore-result** — `<arg>` is empty: infer the description from the conversation (typically a just-finished `/opsx:explore`). `Mode: explore-result`.
- **existing-change** — `<arg>` names a directory `openspec/changes/{name}/` with a `proposal.md`: skip Propose and resume from the next not-done phase. `Mode: existing-change ({name})`.
- **description** — any other non-empty value, a free-form description for `openspec-propose`. `Mode: description`.

Directory existence wins a tie. Empty `<arg>` with no usable conversation context but exactly one complete change directory under `openspec/changes/` (tracked or untracked) → existing-change for it; zero or several → ask.

**Investigation-first changes** — a first task group that produces facts the rest depends on (e.g. reverse-engineering an unknown format) — are not run autonomously: in existing-change mode, ask via `AskUserQuestion` with the three paths in `references/scope-asks.md`.

## Bootstrap permissions

Before any workflow step, compare `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/required-permissions.json` (`permissions.allow`) with the repo's `.claude/settings.local.json`. All present → proceed silently. Any missing → print them and ask **once**: "Add these N pattern(s) to `.claude/settings.local.json`? [Y/n]". On approval, `Edit` them into `permissions.allow` — **additive only**, never removing or rewriting another key; create the file as `{"permissions": {"allow": [...]}}` if absent. On decline, **halt** and print the missing patterns as a copy-paste block.

`--check-permissions` runs only this comparison and exits. `--narrow` compares against `references/required-permissions-narrow.json` instead; when switching to it, remove the wildcard-default entries in the same edit and say which, or the broader patterns stay in force and the tightening does nothing.

## Working-tree precheck

**Read `references/precheck.md` first.** It runs after permissions, before Propose, so a run does not sweep another scope's uncommitted work into its first commit. `git_state.py` exit 2 (an in-progress op `git status` cannot see) or any out-of-scope dirty path is an `AskUserQuestion` with three paths, never a silent decision; do not proceed until answered. `--no-tree-check` skips it.

## Commit + PR message style — minimal

| Artifact | Shape |
|---|---|
| Ship commit | `feat: <change-name>` |
| Revise commit | `fix: review round <N>` |
| Archive commit | `chore: archive <change-name>` |
| Handoff, optional | `docs: TODO.md` |
| Handoff, run log | `chore: spec-to-pr run log` (feature branch only) |
| PR body (Ship) | one line — `Closes openspec/changes/<name>/. Checks: <the checks that ran>.` |
| PR body update (Handoff, only when issues exist) | one line, or one short Markdown file via `--body-file` |

Subjects only; no commit bodies, Test-plan checklists or restated proposals. **One exception:** a commit asserting a measurement carries one `Measured-by: <command> — <claim>` trailer per claim in its last paragraph (`references/ship.md` §2b). No per-phase logs: the only run log is Handoff's record, and resume reads repo state.

## Concurrent runs

A single run needs no setup. To run two or more flows at once in one repo, each session needs its own `git worktree`: **read `references/concurrent-runs.md`**. Branch each off `origin/<base-branch>` explicitly (`origin/<pr-base>` for a stacked child), never off the primary clone's local ref, which goes stale when any sibling change merges.

## Workflow phases

### Propose

- description / explore-result → `Skill(openspec-propose, args="<description>")` (sub-Opus: an `opus` Agent authors), then the post-check.
- existing-change → the post-check only.

**Post-check:** `openspec validate <name> --strict`. Exit 0 → `ok`; non-zero → `warn`, stderr to the Handoff Issues section.

**Apply `openspec/config.yaml` `rules:` in every phase that reads specs or writes a change's artifacts.** A MODIFIED block still carries its full live requirement.

### Review

Cap: `--review-rounds N` (default `1`).

**Read `${CLAUDE_PLUGIN_ROOT}/skills/review-change/references/checklist.md` and execute it inline against `<change-name>`.** It is the single source of truth for review behaviour: change selection, the 12 high-yield verification checks (`0a`–`0l`), the size gate (a large change also reads `dispatch.md` beside it, and checks 0a–0h default to a `fact-gatherer` dispatch whose ✗ rows you still adjudicate), and the report and verdict rubric. Never `Skill(cla:review-change)`; never add review logic here.

**Doc-staleness sweeps — read `references/review-sweeps.md` and run them in the same pass** whenever the proposal retires a symbol, concept or mechanism. Re-search every zero-count symbol yourself; every hit is an Important finding.

**Inherited obligations — hand `<inherits>` (set by `--inherits`) to the checklist; do not restate its rules here.** When `<inherits>` is non-empty, split it on `;` and pass the entries into the checklist's **Step 2b**, which owns settling them, the `### Inherited obligations` report section and the verdict carve-out. Two duties stay here: pass the entries in, and **run Step 2b even when the probe skips Review** ("Resume / dry-run").

For each round:
1. Run the review and parse its verdict (`READY` / `FIX FIRST` / `RETHINK`). On a sub-Opus session, a verdict at the FIX FIRST / RETHINK boundary is seconded by an `opus` `Agent` fed the same context brief. Borderline is judged by the kind of fix needed, never by finding count.
2. `READY` → `ok`, exit the loop.
3. `FIX FIRST` / `RETHINK` → before the first fix, read `references/review-sweeps.md` "Applying a round's fixes" and capture the `design.md` rejected-alternatives snapshot. Apply every Critical and Important to `openspec/changes/<name>/` and re-check each landed. A remedy that reintroduces a rejected alternative is a Critical on the fix; no snapshot captured → Review `warn`. Then `openspec validate <name> --strict`.
4. Decrement the budget. Exhausted → `warn`, residue to Handoff. RETHINK with Critical > 0 after re-validation → `warn` even with budget left; the next round is the user's call.

### Implement

**There is no `openspec apply` CLI subcommand** — the CLI ships `init / update / list / view / change / archive / spec / config / schema / validate / show / status / instructions / templates / schemas / new`. Apply is a Claude Code skill.

1. **Pre-check.** When `tasks.md` promotes a `.py` module to a package beside a same-stem file, read `references/implement-delegate.md` "Python packaging gotcha" first.
2. **Trust-but-verify the probe.** `probe_state.py`'s `implement` reads artifact presence (`isComplete`, or every artifact in a non-empty `applyRequires` `done`), never task boxes. Before skipping Implement on a resume, run `grep -c '^- \[ \]' openspec/changes/<name>/tasks.md`; above 0 → implement regardless of the probe.
3. **Implement.** Tests written here follow `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/test-quality.md` (and `test-quality-gates.md` beside it only for a gate, or when proving one by planting a failure). Default: `Skill(openspec-apply-change, args="<change-name>")`, which walks `tasks.md`, edits and ticks each box. Use direct `Edit`/`Write` instead when you already hold the artifacts and source, or the work needs side knowledge the skill lacks. **Big change** (> ~15 subtasks or > ~8 files): ONE coding `Agent` at `model: sonnet` — **read `references/implement-delegate.md` first**. The brief enumerates every task; `done` counts only with the test-summary line and the ticked-task count; a return with no status token is `blocked`; on any miss, settle the tree (`git status --porcelain`, `git log --oneline -1`, a running gate) before re-dispatching or taking over; every contract firing is a Handoff Issue.
4. **Post-check:** the artifacts are ready (step 2's rule) AND every `- [ ]` is `- [x]` → ✓; otherwise ⚠ with the unfinished tasks for Handoff. Neither reads the claim under a tick, so also:
   - **A ticked task that names a test is checked for that test** — a quoted test name, a `Test:` clause or a test file. Grep the tree for it; a miss is a Handoff Issue, and the test is written inline before leaving Implement. Each requirement a change adds or modifies has such a task, whose test carries a `requirement: <spec> / <heading>` comment line, or a tasks.md line `manual: <heading>: <reason>` — this check is what ties a requirement to its proof. Put that comment line above any test you write.
   - **A task asserting a measurement records the value inline**: `- [x] 4.2 … measured: 1158 passed, 1 skipped`. The tick is not the evidence; the number is.
   - **Re-measure a 2–3 task sample** of the measurement- or test-bearing tasks yourself.

   A task is `[ ]` until it is done; prose under a ticked box saying "NOT DONE" makes every count wrong. A task completable only by running the *built* tool, or blocked on an external deploy, is not an Implement miss: record it as `deferred-to-TODO` at Propose and treat it as ✓-with-deferral here.

### Test

Cap: `--test-rounds N` (default `3`).

**The gates are this repo's lint, build/typecheck and test commands**, read from `cla.io/project-facts.md` ("Dev / build / test commands", "Workspace shape"; run `/cla:cla-setup` when it is missing or stale). `cla.io/overlays/spec-to-pr.md`, if present, adds rules specific to this skill in this repo. If `cla.io/project-facts.md` lacks a fact this skill needs and this skill's overlay exists, the overlay may still hold it from before the move: tell the user "run /cla:cla-setup to move it". Run at the workspace root they already fan out across every app and package. `--test-cmd` replaces discovery with a literal command.

**Which gates to run.** Take the changed paths from `git diff --name-only <base-branch>...HEAD`. **`smoke`** is the lint command (cheap, fails fast); **`full`** is build/typecheck (the primary gate), then tests. Run whichever exist.

**No gates to run means one of two things, and they are not interchangeable.** No changed path is source-affecting → `skip`. Source-affecting is any path with a `src` component, or a suffix the repo builds from — `.ts .tsx .js .jsx .mjs .cjs .py .go .rs .java .rb .php .sh .sql .vue .svelte .json .yaml .yml .toml .css .scss .html` and anything else this repo builds from; **the list is illustrative, so a suffix not on it counts as source-affecting.** **Source changes but no commands named → `warn`, never `skip`**, saying plainly that `project-facts.md` is stale (run `/cla:cla-setup`) or the repo has no gate.

Each round, smoke first: a smoke failure → diagnose and fix, decrement, re-run from smoke next round (a smoke pass never skips `full`). Smoke clean → every `full` command, build first. All exit 0 → `ok`. A `full` failure → diagnose and fix, decrement. Budget exhausted → `warn` with the failing checks and the first error.

**Diagnose means stating a cause before editing:** one sentence specific enough that the fix follows from it (not the symptom restated), read from the actual failure output, plus what the re-run should show, said before running it.

**Two rounds on the SAME stated cause with the gate still red → escalate to `/cla:diagnose` via `Skill(cla:diagnose)`, before the budget exhausts, and add one to the run's `escalated_to_diagnose` count now, so Handoff reads it rather than recalling it.** Say in the invocation that it runs **unattended**, the declaration its mode block keys on. A confirmed cause resumes the loop with the remaining budget; a "no buildable loop" or "no correct seam" finding is a `warn` carrying that finding.

**No symptom fixes.** Loosening an assertion, widening a type or wrapping the failing call turns the gate green without touching the defect, and this phase warns and continues, so a suppression ships. If the only account of a fix is that it makes the check pass, record the round `warn` with the real failure. A test edit forced here follows `test-quality.md`.

**Read `references/test-notes.md` before editing for an infra-dependent gate failure** (the failing file changes between identical runs, or stderr names the infra tool's own error). It also covers the optional browser smoke, never a hard gate.

**External-API fixtures (a judgment call, not a scripted gate):** a change that adds or extends a call to an external HTTP API, whose tests use only stub mocks with an assumed response shape and no fixture captured against the real response, is an Important finding in Review or Revise.

### Autonomy gate

**Default: run Propose → Handoff continuously, without any confirmation, including before push.** Never ask "ready to push?", "shall I continue to Revise?", "merge now?" or any variant; never pause to summarise and wait; never end a turn with a question between phases. No finality headers (`## Done`, `## Summary`) before Handoff: a phase boundary gets at most one brief sentence (`**Revise:** dispatching 3 review agents.`), and Handoff's report is the only finality-shaped block.

**Status text and the next tool call go in the SAME message.** If you have no tool call to pair the text with, the phase is not over — start the next phase instead of narrating the last one. Ending a turn is legitimate in exactly two cases: a backgrounded `Agent`/`Workflow` dispatch is genuinely in flight (its completion notification re-invokes the session — that is the harness, not a pause), or the run is complete. Nothing else. The discriminator is whether a **pending event** will re-invoke this session — not whether you asked the user anything, because this failure asks nothing; **announcing the next step is not a mechanism**.

The exceptions:
- **Bootstrap permission decline** — halts before any phase.
- **`--gate-on-push` / `--interactive`** — pause immediately before push and PR open. Decline → halt cleanly, Ship and Revise `skip` ("user declined gate"), then the terminal report.
- **Mid-flow scope-split ask** — Review finds the artifacts materially stale or the scope separable into several PRs: one `AskUserQuestion` with 3–4 paths (tight / medium / full scope / halt) before Implement. Content-based, never size-based. Under `/cla:multi-pr` only its blocker case (f); otherwise a GitHub issue. Detail: `references/scope-asks.md`.
- A user interrupt ("stop", "wait", Ctrl-C) halts.

**Revise is part of the flow.** "Merge and clean" is about cleanup after Archive, not a skip; only `--skip-review`, "no review" or `--pr-rounds 0` skips it. It dispatches every agent row the diff matches — no budget-based reduction.

### Ship — commit, push, open PR (inline)

**Read `references/ship.md` first** — branch preflight, the hygiene scans, the `Measured-by:` trailers, staging and the PR. Gate rules: `git_state.py --expect-branch <branch>` before staging (exit 2/3 → halt and surface); a branch that already exists, or a remote that cannot answer, → `warn`, and Ship, Revise and Archive become `skip`; the PR body is one line with no `\n#`; `gh pr view --json state` not `OPEN` → ⚠ and Revise `skip`.

### Revise — PR-review loop

Cap: `--pr-rounds N` (default `2`): round 2 runs whenever round 1 committed fixes, scoped to that fix diff. **Read `references/revise.md` first** — agent selection, the round-1 `Workflow` fan-out, round 2's sibling-instance question, triage, fix delegation, the mutation gate, the commit and the exit gate. Gate rules: dispatch every row the diff matches, and `code-reviewer` and `silent-failure-hunter` are never demoted in any round; every Critical and Important is triaged, and counts as Applied only when the defect is shown gone; **the loop exits clean only when untriaged and open are both zero** — a remedy-rejected finding citing the remedy is triaged and still open; `git_state.py --expect-branch <branch>` before each `fix: review round <N>` commit. A non-zero `git push` exit → Revise `warn`, and Handoff says prominently that round-N fixes are local-only. Round ≥2 asks each agent whether the fix introduces its defect elsewhere: you name the resource, grant repo search, and the return cites the search it ran — an uncited enumeration is missing, not empty.

### Archive

**Read `references/archive.md` first**; its first section runs before the archive. Gate rules: `openspec archive <change-name> --yes` directly; stage only the change dir, the dated archive dir and each touched `openspec/specs/<cap>/`, never `openspec/`; `openspec validate --specs` before committing (`✗ spec/<cap>` halts and asks); commit the staged set without re-staging; confirm the archive commit reached the PR, else Archive `⚠`, said prominently in Handoff.

### Handoff

**Read `references/handoff.md` first** — the report, the PR-body mirror, `TODO.md`, the run record and its commit. Gate rules:

- **Name `gh pr merge` only when every phase is ✓ AND "Rejected remedies, still open" is empty.** Any ⚠ → "**Review warnings before merging.**" first, then the command. Any ✗, or a non-empty rejected-remedies section → "**This PR is NOT ready to merge.**" and no merge command. A stacked child (`--pr-base`) gets "lands with its chain" instead. Never name `openspec archive`.
- With `<inherits>` non-empty, print one verdict line per supplied entry, `HONOURED` ones included, ahead of the phase table — on a resumed run too.
- Build the run record from the example in `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/run-log-schema.md`, with `flags` (every flag invoked), `escalated_to_diagnose`, and Revise's `findings_by_round` as built when each round closed, and pipe it to `${CLAUDE_PLUGIN_ROOT}/lib/log_run.py`. On a refusal, rebuild it from the example, fixing every field named, and retry **once**; a second refusal or any other failure goes in Issues and never `warn`s the run.
- Then print what `python3 ${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr-retro/scripts/spec_to_pr_aggregate.py --nudge` prints, verbatim. It never blocks.
- Commit the record on `<branch>` only, as the run's last commit; skipped when Ship was `skip` or `CLAUDE_RETRO_DIR` is outside the repo. A record not appended or not committed is said in the report.

## Resume / dry-run

- **Implicit resume:** re-invoked on the same change, run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/scripts/probe_state.py <change-name>` and skip to the first not-done phase in its JSON (`{propose, implement, branch, pr, fix_rounds_applied, archived, base_branch, tools_missing?, environment_errors?}`). Each phase is idempotent. Check `base_branch` before trusting a `false`/`0` in `branch`/`fix_rounds_applied`: a wrongly resolved base makes both read as legitimate negatives. `environment_errors` (unusable working directory, a timed-out child) is not `tools_missing` (not on PATH).
- **A non-empty `<inherits>` survives the probe — always run the checklist's Step 2b, whatever the probe says.** The JSON has **no `review` field**, so a change resumed with `implement` true skips Review and every inherited obligation goes unanswered. So run **Step 2b alone** — one `grep -rl` per token, one verdict line each — *before* the first phase the probe selects, and apply any non-`HONOURED` entry to the artifacts as a Critical before continuing. It needs no dispatch, size gate or context brief, which is why it is unconditional. Print the verdict lines even when all are `HONOURED`; Handoff mirrors them.
- **`--dry-run`:** every probe and check runs; every write (commit, push, PR open, apply, file edit) is suppressed.

## References

Read first by their phase: `precheck.md`, `ship.md`, `revise.md`, `archive.md`, `handoff.md`. Read when their trigger fires: `branch-and-pr-base.md`, `scope-asks.md`, `review-sweeps.md`, `implement-delegate.md`, `subagent-brief.md`, `test-notes.md`, `concurrent-runs.md`, `required-permissions-narrow.json`. Orientation: `workflow-diagram.md`. Only when revising the skill: `design-tradeoffs.md`. Shared, under `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/`: `model-routing.md`, `runtime-rules.md`, `bash-discipline.md`, `run-log-schema.md`, `skill-authoring.md`, `past-offenses.md`, `required-permissions.json`.
