# A-diff: proposed edits, part A (never applied)

Paths are relative to `C:\Code\logic-artisan\.claude\plugins\cla\`. One finding per hunk, high and
medium confidence only. Finding ids match `A-report.md`. Nothing here edits a file outside the
plugin. No hunk touches request code (there is none), so there is no history-editing caveat.

---

## A1 (High) new-worktree/SKILL.md: the env-file snippet starts with `cd`, which the plugin's own guard blocks

```diff
--- a/skills/new-worktree/SKILL.md
+++ b/skills/new-worktree/SKILL.md
@@ -90,10 +90,9 @@
      worktree you're currently in):
      ```bash
-     cd <app-dir>
-     MAIN="$(dirname "$(git rev-parse --git-common-dir)")"
+     MAIN="$(dirname "$(git -C <app-dir> rev-parse --git-common-dir)")"
      if [ -f "$MAIN/<env-file-path>" ]; then
-       cp "$MAIN/<env-file-path>" ".env" && echo "copied .env"
+       cp "$MAIN/<env-file-path>" "<app-dir>/.env" && echo "copied .env"
      else
        echo "no <env-file-path> in main checkout — skipping"
      fi
```

## A2 (High) new-worktree/SKILL.md: pointer to a memory entry that no repo has

```diff
--- a/skills/new-worktree/SKILL.md
+++ b/skills/new-worktree/SKILL.md
@@ -32,6 +32,5 @@
 clean up. If a commit ever goes missing after a shared branch gets switched/deleted
 out from under it, check `git reflog` / `git fsck --unreachable` before assuming it's
 lost — worktrees share one object store, so `git checkout <sha> -- <path>` recovers
-files into a different worktree with no copy step needed. (Full incident writeup: see
-a per-user note.)
+files into a different worktree with no copy step needed.
 
```

## A3 (High) _shared/references/skill-authoring.md: `ship.md` no longer sits under `spec-to-pr/references/`

```diff
--- a/skills/_shared/references/skill-authoring.md
+++ b/skills/_shared/references/skill-authoring.md
@@ -1,4 +1,4 @@
 # Skill-authoring doctrine (plugin-wide)
 
-This is plugin-wide doctrine: it lives in `_shared/` because every skill is held to it, not because any one skill owns it. `spec-to-pr` is the largest worked example — its `references/{ship,revise,archive,handoff}.md` show the split in practice.
+This is plugin-wide doctrine: it lives in `_shared/` because every skill is held to it, not because any one skill owns it. `spec-to-pr` is the largest worked example — its `references/{revise,archive,handoff}.md` and `_shared/references/ship.md` show the split in practice.
```

## A4 (High) _shared/references/model-routing.md: the two agent files carry no effort instruction

```diff
--- a/skills/_shared/references/model-routing.md
+++ b/skills/_shared/references/model-routing.md
@@ -48,4 +48,4 @@
-| Review Step-2 fact-gathering offload (large changes) | haiku | low (body-instructed) | `${CLAUDE_PLUGIN_ROOT}/agents/fact-gatherer.md` |
-| Cross-PR / `.claude/`-meta doc-staleness sweep | haiku | low (body-instructed) | `${CLAUDE_PLUGIN_ROOT}/agents/doc-sweeper.md` |
+| Review Step-2 fact-gathering offload (large changes) | haiku | inherited | `${CLAUDE_PLUGIN_ROOT}/agents/fact-gatherer.md` |
+| Cross-PR / `.claude/`-meta doc-staleness sweep | haiku | inherited | `${CLAUDE_PLUGIN_ROOT}/agents/doc-sweeper.md` |
```

## A5 (High) annotate/SKILL.md: bare `$CLAUDE_PLUGIN_ROOT` in a Bash block

```diff
--- a/skills/annotate/SKILL.md
+++ b/skills/annotate/SKILL.md
@@ -103,9 +103,9 @@
 # one document — Markdown, plain text or HTML. `render_doc.py` dispatches on the
 # extension, so this is the same command for all three and the CLI and the server
 # cannot disagree about what a file renders as.
-python3 "$CLAUDE_PLUGIN_ROOT/skills/annotate/scripts/render_doc.py" <path>
-python3 "$CLAUDE_PLUGIN_ROOT/skills/annotate/scripts/annotate_server.py" <path>
+python3 "${CLAUDE_PLUGIN_ROOT}/skills/annotate/scripts/render_doc.py" <path>
+python3 "${CLAUDE_PLUGIN_ROOT}/skills/annotate/scripts/annotate_server.py" <path>
 
 # a whole change — the server takes the same target and works out which it is
-python3 "$CLAUDE_PLUGIN_ROOT/skills/annotate/scripts/render_change.py" <change>
-python3 "$CLAUDE_PLUGIN_ROOT/skills/annotate/scripts/annotate_server.py" <change>
+python3 "${CLAUDE_PLUGIN_ROOT}/skills/annotate/scripts/render_change.py" <change>
+python3 "${CLAUDE_PLUGIN_ROOT}/skills/annotate/scripts/annotate_server.py" <change>
```

## A6 (Medium) _shared/references/bash-discipline.md: the root `CLAUDE.md` does not carry these rules

```diff
--- a/skills/_shared/references/bash-discipline.md
+++ b/skills/_shared/references/bash-discipline.md
@@ -1,4 +1,4 @@
 # Bash-style discipline (hard rules)
 
-These shapes defeat the project's Bash permission allowlist matching, or write where the skill must not. The skill MUST NOT emit them. The same rules also live in the project's root `CLAUDE.md`; this file is the orchestrator's local enforcement reference.
+These shapes defeat the project's Bash permission allowlist matching, or write where the skill must not. The skill must not emit them.
```

## A7 (Medium) _shared/references/model-routing.md: `Agent` has an optional `effort` parameter

```diff
--- a/skills/_shared/references/model-routing.md
+++ b/skills/_shared/references/model-routing.md
@@ -24,6 +24,6 @@
 | Mechanism | Model knob | Effort knob | Used for |
 |---|---|---|---|
-| `Agent(subagent_type, model:)` | yes (per call) | **no** (inherits session) | Implement delegate, Revise round 1 (default) and round ≥2, escalate-up dispatches, `fact-gatherer`/`doc-sweeper` dispatches |
+| `Agent(subagent_type, model:)` | yes (per call) | optional `effort:` per call; the tool says to set it only when the user or a skill explicitly asks, so this plugin leaves it inherited | Implement delegate, Revise round 1 (default) and round ≥2, escalate-up dispatches, `fact-gatherer`/`doc-sweeper` dispatches |
 | `Workflow` `agent(prompt, {model, effort, agentType, schema})` | yes | **yes** (per call) | Revise round 1 fan-out ONLY, and only when the user has opted into workflows |
-| `${CLAUDE_PLUGIN_ROOT}/agents/*.md` frontmatter | yes (`model:`) | **no** (no effort key exists) | our own agents: `fact-gatherer`, `doc-sweeper` |
+| `${CLAUDE_PLUGIN_ROOT}/agents/*.md` frontmatter | yes (`model:`) | yes (`effort:`); unused by our two agents | our own agents: `fact-gatherer`, `doc-sweeper` |
```
Follow-on, outside this audit's scope: `model-routing.md:146-147`, `right-model/SKILL.md:78-80` and
`project-review/SKILL.md:42` repeat "effort is not dialable". Check the current Claude Code subagent
frontmatter docs before taking this hunk, then edit those three lines the same way.

## A8 (Medium) _shared/references/runtime-rules.md: scratch location disagrees with bash-discipline

```diff
--- a/skills/_shared/references/runtime-rules.md
+++ b/skills/_shared/references/runtime-rules.md
@@ -18,3 +18,3 @@
-- **Scratch-file-then-delegate large intermediate material.** When a step produces a large intermediate artifact another step consumes, write it to `temp/` and hand the path to a delegate, rather than carrying the whole artifact inline. (The happy path needs no scratch file: the only one spec-to-pr writes is Handoff's multi-line PR body.)
+- **Scratch-file-then-delegate large intermediate material.** When a step produces a large intermediate artifact another step consumes, write it to the session scratchpad (or a gitignored `temp/`, per `${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/bash-discipline.md`) and hand the path to a delegate, rather than carrying the whole artifact inline. (The happy path needs no scratch file: the only one spec-to-pr writes is Handoff's multi-line PR body.)
```

## A9 (Medium) _shared/references/retiring-specs.md: a version pin from before the OpenSpec 2.0 upgrade

```diff
--- a/skills/_shared/references/retiring-specs.md
+++ b/skills/_shared/references/retiring-specs.md
@@ -25,3 +25,3 @@
 ## Before archiving: format traps
 
-These were reproduced on OpenSpec 1.14.1. Each one makes the old spec text survive or blocks the retirement, and old specs written by hand often have them.
+These were reproduced on OpenSpec 1.14.1. Re-check the one you hit with `openspec validate` under the installed version before working around it. Each one makes the old spec text survive or blocks the retirement, and old specs written by hand often have them.
```

## A10 (Medium) new-worktree/references/path-casing.md: the probe chain moved out of `hooks.json`

```diff
--- a/skills/new-worktree/references/path-casing.md
+++ b/skills/new-worktree/references/path-casing.md
@@ -40,5 +40,5 @@
 On Windows — the platform this whole section exists for — `python3` is often
-absent; use `py` or `python` instead. (`hooks.json` carries the same
-`python3 || py || python` probe chain for exactly this reason.) It reports
+absent; use `py` or `python` instead. (`hooks/probe-python.sh` tries `python3`,
+then `py`, then `python` for exactly this reason.) It reports
 `case_only` for the refusal described here, `path_indirection` when the repo
```

## A11 (Medium) _shared/references/test-quality-gates.md: dated measurement block

```diff
--- a/skills/_shared/references/test-quality-gates.md
+++ b/skills/_shared/references/test-quality-gates.md
@@ -19,13 +19,8 @@
 green is standing where the check used to be.
 
-Measured in one session (2026-08-23) during a ~70-file tree move, three floors found
-stale in the source repo and each raised in the same edit that found it: one sat at
-`>= 55` against a real 83 (a 34% collapse would have passed) and is now `>= 80`;
-another at `>= 6` against a real 17 and is now `>= 15`; a third at `>= 95` against 96,
-which is the shape working as intended and was left alone. Quote the *current* value
-when citing one — a floor named here after being raised is a number a reader will
-grep for and not find.
+Illustration: a floor of `>= 55` over 83 real files lets a 34% collapse pass, while a
+floor of `>= 95` over 96 is the shape working as intended. Never quote a repo's current
+floor from memory; read it from the assertion.
 
 State what you derived the number from, in the assertion's own comment, so the next
```

## A12 (Medium) _shared/references/test-quality-gates.md: commit SHAs and a commit-message anecdote

```diff
--- a/skills/_shared/references/test-quality-gates.md
+++ b/skills/_shared/references/test-quality-gates.md
@@ -273,15 +273,9 @@
-Measured, in the source repo (`f0e8dd7`): a guard file whose rules are written by hand
-per command went through three review rounds finding 5, 5 and 4 real bypasses, every
-round after the first the same displacement shape — a construct handled for one rule and
-never carried to the others. A fourth round, after the matrix replaced the case list,
-came back clean of that class.
-
-A caution earned in the same commit. Its message claimed three planted displacements
-were killed "BY THE MATRIX, not by a bug-specific test", and that second half was false:
-the batch pointed each mutant at the matrix test and ran only that test, so it could
-never have observed a hand-written test dying too — and at least one had, since
-`test_branch_delete_fires_on_every_executable_spelling` had covered that exact spelling
-since `865d366`. What the run showed is that the matrix catches these; the exclusivity
-was inferred from evidence that could not carry it. Note the shape, because it is this
-file's own subject: a green targeted run is evidence about the target and nothing else.
+A guard whose rules were written by hand per command went through three review rounds
+finding 5, 5 and 4 real bypasses, each after the first the same displacement shape, and
+came back clean of that class once a matrix replaced the case list. A matrix run shows
+the matrix catches a planted bug; it does not show the matrix was the only test that did.
+Run the whole file and say only what it showed.
```

## A13 (Medium) _shared/references/base-branch-resolution.md: migration-relative phrasing

```diff
--- a/skills/_shared/references/base-branch-resolution.md
+++ b/skills/_shared/references/base-branch-resolution.md
@@ -4,11 +4,8 @@
 names it is a placeholder, not a literal: substitute the real name before running anything.
 Resolve it once, at the start of the run, with `git symbolic-ref --quiet refs/remotes/origin/HEAD`
 (take the segment after the last `/`); if that is unset, use whichever of `main` / `master`
-actually exists. The harness used to hardcode `master`, which silently broke every `main`-default
-repo — a `master..HEAD` range there fails outright with `unknown revision` rather than returning a
-wrong answer, and `git checkout master` cannot succeed at all.
+actually exists. Never hardcode `master`: in a `main`-default repo a `master..HEAD` range fails
+with `unknown revision`, and `git checkout master` cannot succeed.
 
-Shared verbatim by `multi-lite`, `multi-pr`, and `multi-spec` (all three chain per-change work
-against `<base-branch>` in the primary clone) — previously copy-pasted identically into each
-SKILL.md, so a fix to the resolution logic (like the master→main bug above) had to be
-hand-reapplied to all three. Edit this file once; it's the single source of truth for all three.
+Shared by `multi-lite`, `multi-pr`, and `multi-spec`, which all chain per-change work against
+`<base-branch>` in the primary clone. Edit this file once; it is the single source of truth.
```

## A14 (Medium) _shared/references/conflict-resolution.md: migration-relative phrasing

```diff
--- a/skills/_shared/references/conflict-resolution.md
+++ b/skills/_shared/references/conflict-resolution.md
@@ -3,6 +3,5 @@
 `git_state.py` exits 2 when one of these is mid-flight. That exit is a detection,
 not a verdict — this file is the procedure it hands you. Four skills check that
-exit at every commit boundary (`spec-to-pr`, `lite-pr`, `multi-pr`, `multi-spec`)
-and, until this file existed, all four stopped at "halt and surface" with nothing
-to surface but the halt.
+exit at every commit boundary (`spec-to-pr`, `lite-pr`, `multi-pr`, `multi-spec`),
+and each follows this file instead of stopping at "halt and surface".
```

## A15 (Medium) _shared/references/model-routing.md: "Shared, and now filed as such"

```diff
--- a/skills/_shared/references/model-routing.md
+++ b/skills/_shared/references/model-routing.md
@@ -8,8 +8,6 @@
-**Shared, and now filed as such.** This is the repo's single routing source for *all* dispatched
-review work. It lived under `spec-to-pr/references/` until the skills that depend on it outnumbered
-its nominal owner; it now sits in `skills/_shared/references/`, which is what it always was:
-`review-change/references/dispatch.md` (the checklist's Step 4 3-agent dispatch) and `project-review/SKILL.md`
+**Shared.** This is the repo's single routing source for *all* dispatched
+review work: `review-change/references/dispatch.md` (the checklist's Step 4 3-agent dispatch) and `project-review/SKILL.md`
 (Step 2 5-agent dispatch) both route by the "Review-agent dispatch" section below. Keeping one table
 means the "reviewer runs at the top tier, structured-rubric work runs a tier down" posture is
 consistent wherever agents review code — see that section for why each review dimension gets the tier
 it does.
```

## A16 (Medium) _shared/README.md: "previously under"

```diff
--- a/skills/_shared/README.md
+++ b/skills/_shared/README.md
@@ -8,8 +8,7 @@
 ## Why it exists
 
-These files were previously under `skills/spec-to-pr/references/`, where up to
-nine other skills reached for them. That made one skill's directory the plugin's
-de-facto common library: `spec-to-pr` could not be reorganised, renamed, or
-version-bumped without moving files half the plugin depends on, and a reader had
-no way to tell which of its references were its own and which were everyone's.
+Up to nine skills read these files. Kept in one skill's directory they would make
+that directory the plugin's de-facto common library: that skill could not be
+reorganised, renamed, or version-bumped without moving files half the plugin
+depends on, and a reader could not tell which references were its own.
```

## A17 (Medium) report-upstream/SKILL.md: two history asides

```diff
--- a/skills/report-upstream/SKILL.md
+++ b/skills/report-upstream/SKILL.md
@@ -10,9 +10,7 @@
 The plugin is installed read-only from a marketplace, so a repo that finds a defect in
 portable core cannot fix it where it lives. Without a channel back, the observation dies
-with the session and the same defect is rediagnosed independently in every repo running
-the plugin — which is exactly what happened before this existed: one launcher bug was
-diagnosed and fixed separately in three repos, and none of those fixes reached the others.
+with the session and every repo running the plugin rediagnoses the same defect
+independently, and none of those fixes reaches the others.
@@ -37,5 +35,4 @@
-State a claim about the current core only if you verified it **this run**. The recurring
-failure in the file-based predecessor of this channel was an item asserting "unfixed
-upstream" that had been fixed long before.
+State a claim about the current core only if you verified it **this run**; an issue
+asserting "unfixed upstream" about a defect already fixed costs a maintainer's triage.
```

## A18 (Medium) save-permissions/SKILL.md: incident dates, absolute rule without its scope

```diff
--- a/skills/save-permissions/SKILL.md
+++ b/skills/save-permissions/SKILL.md
@@ -69,3 +69,3 @@
-   Do NOT pause for user confirmation before running the script — just run it. **This applies only to exact, non-wildcard entries** (a literal tool name, a literal skill name, an exact path scope actually exercised this session — nothing containing `*`). For **any** wildcard or broad pattern at all — `Bash(*)`, `Bash(rm *)`, `Bash(cp *)`, `Bash(docker *)`, `Bash(sed *)`, or any other `Bash(<command> *)`-shaped entry, regardless of whether the command "looks" destructive — present it as a question and get explicit confirmation before writing it, even if that exact command family was used and worked fine this session. **Do not self-classify a wildcard as "narrow enough to skip asking" — there is no such exemption.** A wildcard is a wildcard; the confirm-before-write rule does not have a destructiveness threshold. (Recurred once already on 2026-07-11 with `Bash(rm *)`/`Bash(cp *)`; recurred again on 2026-07-16 when several non-destructive-looking wildcards — `Bash(docker *)`, `Bash(sed *)`, `Bash(grep *)`, `Bash(head *)`, `Bash(wc *)`, `Bash(find *)` — were judged "narrow" and nearly written unprompted, caught only by the harness's auto-mode classifier.) The harness's auto-mode classifier will independently block broad grants regardless of this skill's instructions, and retrying different wildcard phrasings after a block is itself a bad pattern — ask instead of retrying.
+   Run the script without pausing when every new entry is exact: a literal tool name, a literal skill name, or an exact path scope actually exercised this session, with no `*`. Present any wildcard or broad pattern (`Bash(*)`, `Bash(rm *)`, `Bash(docker *)`, any `Bash(<command> *)` entry) as a question and write it only after explicit confirmation, even when that command family worked fine this session. A wildcard grants every future command of that shape, and "narrow enough to skip asking" has no stable boundary, so a destructive-looking test does not decide it. The harness's auto-mode classifier also blocks broad grants independently; after a block, ask instead of retrying other wildcard spellings.
```

## A19 (Medium) feedback/SKILL.md: incident id and a self-referential history note

```diff
--- a/skills/feedback/SKILL.md
+++ b/skills/feedback/SKILL.md
@@ -56 +56 @@
-- **Committing the deliverable is the user's call too.** The during-loop incremental write (Phase 0 step 3) protects against a crash *within the session*, but the file stays uncommitted — and the very incident this durability design guards against (an incident id) destroys *uncommitted* files. State that the dated doc is written but uncommitted, and leave committing/pushing it to the user (same non-ownership posture applied to `notes.md`); this skill does not run git, and its frontmatter grants no `Bash` to run it with.
+- **Committing the deliverable is the user's call too.** The during-loop incremental write (Phase 0 step 3) protects against a crash *within the session*, but the file stays uncommitted, and the loss this durability design guards against destroys *uncommitted* files. State that the dated doc is written but uncommitted, and leave committing/pushing it to the user (same non-ownership posture applied to `notes.md`); this skill does not run git, and its frontmatter grants no `Bash` to run it with.
@@ -61 +61 @@
-- Does **not** edit source, run the app, or do a full root-cause investigation. Grounding is a few read-only greps producing a labeled hypothesis, not a confirmed diagnosis — it's a capture skill, not a debugging one. This is mechanically backed by the frontmatter `allowed-tools`, which withholds `Edit` — so the read-only promise does not rest on prose discipline alone. Read the frontmatter for the current list rather than trusting a copy here: a copy of it in this sentence once went stale in the commit that changed the list.
+- Does **not** edit source, run the app, or do a full root-cause investigation. Grounding is a few read-only greps producing a labeled hypothesis, not a confirmed diagnosis — it's a capture skill, not a debugging one. This is mechanically backed by the frontmatter `allowed-tools`, which withholds `Edit` — so the read-only promise does not rest on prose discipline alone. Read the frontmatter for the current list.
```

## A20 (Medium) new-worktree/SKILL.md: tool-call minimisation read literally by Sonnet

```diff
--- a/skills/new-worktree/SKILL.md
+++ b/skills/new-worktree/SKILL.md
@@ -18 +18 @@
-**The dominant cost here is round-trips, not the install's own execution time.** What actually makes a rerun feel slower is extra tool calls layered on top (a separate `git worktree list` lookup, ad hoc verification checks, status checks) — each one is a full model round-trip regardless of how fast the command inside it runs. So: keep this to the fewest possible tool calls, and don't add "just to be sure" verification steps — trust each command's own output/exit code.
+**The dominant cost here is round-trips, not the install's own execution time.** What actually makes a rerun feel slower is extra tool calls layered on top (a separate `git worktree list` lookup, ad hoc verification checks, status checks) — each one is a full model round-trip regardless of how fast the command inside it runs. So run the steps below as written, and add a check only when a command's own output or exit code looks wrong; those already confirm each step.
```

## A21 (Medium) output-styles/CLA.md: routine-narration ban, read literally by an under-narrating model

```diff
--- a/output-styles/CLA.md
+++ b/output-styles/CLA.md
@@ -33 +33 @@
-- **Play-by-play narration.** A plan posted once before a long task is not narration.
+- **Narration of routine steps.** Before a long task, say in a line what you are about to do. During it, speak when a finding changes the plan or the answer, and close with a recap that stands on its own. Do not narrate each tool call.
```

## A22 (Medium) output-styles/CLA.md: numeric sentence and paragraph ceilings

```diff
--- a/output-styles/CLA.md
+++ b/output-styles/CLA.md
@@ -85,6 +85,6 @@
-- Instructions: 20 words or fewer per sentence, one instruction each. Explanations: 25 or fewer.
+- One instruction per sentence. A sentence a reader must re-read to follow gets split.
 - **A dash, colon, or parenthetical does not end a sentence.** Split welded ideas at the joints.
-  Before sending, find the longest sentence; over the ceiling → split it.
-- One topic per paragraph, six sentences or fewer. Prefer bullets to a paragraph.
+  Before sending, find the longest sentence and split it if it holds two ideas.
+- One topic per paragraph. Prefer bullets to a paragraph.
```

## A23 (Medium) annotate/SKILL.md: "four lines"

```diff
--- a/skills/annotate/SKILL.md
+++ b/skills/annotate/SKILL.md
@@ -143,3 +143,3 @@
-The whole report is four lines: what was built (blocks and words), the URL, where
-annotations land, and how to stop the server. **Then stop talking and let them
-read.**
+The report holds what was built (blocks and words), the URL, where annotations
+land, and how to stop the server, and nothing else. **Then stop talking and let
+them read.**
```
