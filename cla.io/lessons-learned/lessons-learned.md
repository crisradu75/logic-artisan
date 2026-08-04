# Lessons learned

<!-- Rolling log written by /cla:codify-learnings, which prepends each report. Newest entries at the top. -->

## Lessons learned — 2026-08-04 02:40 — scope: repo-wide (`.claude/plugins/cla/hooks/`, `skills/update-cla/`, `skills/spec-to-pr/`, `skills/multi-lite/`, `skills/multi-pr/` — cross-repo ledger port from claude-plugins)

*(memory dedup skipped — index not found; this project's memory dir had no `MEMORY.md` yet)*

### Session summary

Read `claude-plugins`' `cla-upstream.md` carry-back ledger, verified all 17 items against this
repo's own tree (not accepted on faith — 2 items dropped: #15 not applicable, #11 deliberately
deferred as a design change). Shaped the remaining 15 into a 4-candidate decisions doc and ran
`/cla:multi-lite` over it, dependency-first: `push-guard-bypasses` (PR #12), `hook-crash-and-
base-branch` (#13), `update-cla-apply-hardening` (#14) — all three merged as dependencies — and
`docs-accuracy-and-guard-determinism` (#15) — left open per the confirmed plan, later merged on
explicit request. Every candidate's PR review pass (code-reviewer + silent-failure-hunter +
pr-test-analyzer, one round each) found and fixed real regressions before merge, most notably an
inverted ratio threshold in #14 that would have silently broken this repo's own next sync. The
run-log commit hit a genuine collision — `multi-lite`'s documented direct-to-`main` recipe vs.
the very push guard hardened by #12 in this same run, with no metadata exception — surfaced to
the user rather than silently using the escape hatch; routed through PR #16 instead. User then
requested "merge all," landing #15 and #16.

### Suggested edits

**1. Add a fallback to multi-lite's and multi-pr's run-log commit recipe for when the base-branch push is blocked** (`.claude/plugins/cla/skills/multi-lite/references/phase4-and-log.md`, `.claude/plugins/cla/skills/multi-pr/references/cleanup.md`) — both recipes assumed a direct `git commit` + `git push` to `<base-branch>` for the run-log line always succeeds. Added: if the push is blocked by `block-direct-push-to-main.py` (or equivalent), fall back to a small branch + PR instead of stopping to ask, and don't reach for `ALLOW_PUSH_TO_MAIN=1` as a routine workaround. *Benefit: this exact collision happened this run — the guard hook this same run hardened (PR #12) now correctly has no metadata-only exception, and the run had to stop mid-flow and ask the user how to proceed. A future multi-lite/multi-pr run hits the identical wall with no documented way through.* — **APPLIED**

**2. Memory: verify a new content-scanning heuristic against real repo files during Implement, not just synthetic test cases** (type: feedback) — before shipping a new ratio/threshold/pattern-match that filters real repository content, run it against the actual files it will see, not only hand-built unit-test constructions. *Benefit: this run shipped two first-draft implementations with review-caught defects that empirical verification would have caught immediately — a ratio threshold that was literally inverted (would have silently broken this repo's own next sync) and a git-state query keyed off `HEAD` instead of the index (silently missed staged-but-uncommitted paths). Both were only caught by a dispatched reviewer's empirical scan, not by me before Ship.* — **APPLIED**

**3. Sharpen lite-pr's Review self-read instruction to name a concrete technique** (`.claude/plugins/cla/skills/lite-pr/SKILL.md`) — changed "check sibling instances aren't affected too" to grep the same file for other call sites consuming the same untrusted input the fix just guarded. *Benefit: this run's own self-read pass missed a second unguarded `.get()` in `warn-stacked-pr-merge.py`, 29 lines below a fix for the identical pattern — only the dispatched silent-failure-hunter agent caught it. A concrete grep technique is harder to satisfy loosely than the prior vague phrasing.* — **APPLIED**

**4. Memory: don't call ScheduleWakeup right after starting a Bash run_in_background command** (type: feedback) — the harness already notifies on completion; ScheduleWakeup is for delays the harness can't track. *Benefit: happened twice this run, both times requiring an immediate follow-up call to cancel the wakeup — pure wasted turns with no benefit.* — **APPLIED**

**5. failure-modes.md: add a bullet on surfacing prompt-injection-neutralization notices explicitly** (`.claude/plugins/cla/skills/codify-learnings/references/failure-modes.md`) — new bullet under "Agent behavior" on surfacing a subagent-output injection-pattern notice to the user explicitly, even when judged benign. *Benefit: this run had exactly this happen (one review agent's output tripped a "settings-json" pattern detector) and I judged it benign and continued without telling the user — inconsistent with my own stated instruction to flag suspected injection attempts visibly.* — **APPLIED**

### Memory candidates

Both listed above as suggestions #2 and #4 (numbered inline per this run's payoff order, not a separate section) — **APPLIED**, written to `feedback_verify_heuristics_empirically.md` and `feedback_no_schedulewakeup_after_background_bash.md`, indexed in a newly-created `MEMORY.md`.

### Lessons (meta)

- Three of four PRs this run had real, review-caught defects in their FIRST commit — not a sign the workflow is broken (the review-fix-round mechanism is exactly what caught and fixed all of them before merge), but a reminder that "the code compiles and the unit tests I wrote pass" is not the same bar as "this heuristic is correctly calibrated against real data" — see suggestion #2.
- The push-guard/run-log collision is a good example of a hardening effort's side effects reaching further than the file it touched — closing a guard bypass in one skill's hooks broke an assumption baked into two OTHER skills' own documented recipes. Worth a habit: after hardening any guard hook, grep sibling skills' reference docs for the exact command shape just tightened, not just the file that motivated the fix.

### Recurring patterns

- **prevented**: "User question 'why would X be relevant?' is often hypothesis-rejection evidence" — the user's "why push directly to main instead of a branch?" was treated as a request to re-examine and explain the trade-off, not defended as already-correct; the user then chose to redirect (branch+PR route), which was followed without pushback.
- **prevented**: "Did Claude commit, push, or merge without explicit user authorization?" — the run-log push-block was surfaced via `AskUserQuestion` rather than silently resolved with the escape hatch; every merge in this run followed an explicit user instruction ("merge all").
- **prevented**: "Did Claude make a compound shell command harder to read than necessary (`cd /x && cmd`)?" — one `cd`-containing Bash call was attempted and correctly blocked by `block-cd-in-bash.py` before it ran; confirms the existing hook is still doing its job, no further action needed.
- **re-offended (existing checklist bullet, never load-bearing)**: "Was a tolerance/threshold too tight or too loose for the real distribution of inputs?" already named this exact risk class in `failure-modes.md`, but as a retro-time-only checklist item it had no power to prevent the ratio-threshold bug this run — escalated via suggestion #2 to a load-bearing **memory** entry (checklist → memory).
- **re-offended (SKILL.md-rung rule, insufficiently followed)**: lite-pr's own "check sibling instances aren't affected too" Review-phase instruction already existed and was followed each of the four times this run, yet still missed the second unguarded `.get()` in `warn-stacked-pr-merge.py`. No clean hook exists for "did you actually grep for sibling instances" (a semantic-judgment rule, not a deterministic precondition), so escalated by sharpening the SAME rung's wording to name a concrete technique rather than moving to hook/script — see suggestion #3.

### Codify-process notes

Second-ever run of `/cla:codify-learnings` for this repo. No mis-routing or workflow snag in the
codify-learnings process itself this run; the Step 2.5 effectiveness check did produce real
classifications this time (the prior first-run log had none to check against). One process
observation: this repo's memory directory (`memory/`) existed but had no `MEMORY.md` index —
created it fresh this run rather than treating the absence as a scoping error.

---

## Lessons learned — 2026-07-25 15:00 — scope: repo-wide (`.claude/plugins/cla/hooks/`, cross-repo skill porting)

### Session summary

Extracted the `/right-model` skill from peer repo `interoga-ro`'s local CLA (found on its
`main` branch via `git show`, since the checked-out working tree there was on an unrelated
feature branch and the skill dir was empty on disk) into `logic-artisan` verbatim — it was
already written as a generic, project-agnostic skill. Added a `CLAUDE.md` skill-table row,
ran the full test suite, committed on `main`, then on explicit user request pushed directly
to `origin/main` with `git -C "<repo>" push origin main`. That push should have been blocked
by `block-direct-push-to-main.py` per this repo's own documented no-direct-push-to-main
convention, but the hook's regex didn't fire.

### Suggested edits

#### Hooks / settings
1. `[cost: high]` **`.claude/plugins/cla/hooks/block-direct-push-to-main.py`** — extend the push-detection regexes to allow git global flags (`-C <dir>`, `-c k=v`, etc.) between `git` and `push`, reusing the `_G`/`_GIT` pattern already implemented in `guard-worktree-isolation.py`. — *(why: this session ran `git -C "<repo>" push origin main` directly against `main` — the canonical CLA sync source — and the hook did not fire. Verified by direct regex test: none of the three detection patterns matched. The push succeeded and is live on `origin/main`.)* — **APPLIED**
2. `[cost: med]` **`.claude/plugins/cla/hooks/warn-branch-base.py`** — same gap: `_BRANCH_CREATE` required `git` and `checkout`/`switch` adjacent, so `git -C <dir> checkout -b <name>` silently skipped the stacked-branch-base warning. — *(why: same root cause as #1, found by grepping sibling hooks for the same regex shape.)* — **APPLIED**
3. `[cost: med]` **`.claude/plugins/cla/hooks/warn-stray-scratch-artifact.py`** — same gap: `_GIT_ADD_OR_COMMIT` required `git` and `add`/`commit` adjacent, so `git -C <dir> commit ...` skipped the scratch-artifact check. — *(why: same root cause, same sweep.)* — **APPLIED**

#### Docs
4. `[cost: low]` **`.claude/plugins/cla/skills/codify-learnings/references/failure-modes.md`** — added a bullet under "Tooling and codebase" about checking a peer repo's actual branch/`git log --all`/`git show` before concluding a path doesn't exist. — *(why: this session found `interoga-ro`'s `right-model` skill dir empty on disk because its working tree was on an unrelated feature branch; the content was on `main`.)* — **APPLIED**

### Memory candidates
5. `[cost: low]` type: reference — Peer repo `interoga-ro`'s local CLA lives at `/Users/cradu/Documents/Git Personal/interoga-ro/.claude/plugins/cla/`. — **Why:** useful when porting skills/hooks between `cris`'s CLA-adopting repos. **How to apply:** check this path first for future cross-repo skill ports. — **APPLIED**

### Lessons (meta)

- The regex fix pattern (`_G` = optional git global flags before the subcommand) already existed correctly in `guard-worktree-isolation.py` — the other git-matching hooks were just never updated to match. Worth grepping for this specific `\bgit\s+(?:add|commit|push|checkout|switch)\b`-without-`_G` shape again after any future new git-matching hook is added, since it's an easy pattern to forget to copy forward.
- A hook that block/warns on `git <subcommand>` is only as strong as its command-shape coverage — `-C <dir>` is a very common, legitimate way to target a repo without `cd` (this session's own convention, driven by the `cd`-avoidance guidance), so it was likely to be hit eventually regardless of what triggered it this time.

### Recurring patterns

- First `/cla:codify-learnings` run for this repo — `lessons-learned.md` was empty going in, so no prior-lesson re-offense checks were possible.
- **prevented**: "Did Claude commit, push, or merge without explicit user authorization?" — commit and push were each done only after an explicit, separate user instruction ("Yes, commit this" / "push it").
- **prevented**: "Was a change declared done without verification?" — ran the full aggregated test suite (`run_tests.py`) before declaring the skill-port task complete, and again after this run's hook fixes.
- **re-offended (new discovery, not a prior lesson)**: the no-direct-push-to-main convention itself was bypassed by a hook gap — see suggestion #1, escalated directly at the hook (already the top of the ladder; this is a correctness fix to existing enforcement, not a new rung).

### Codify-process notes

No codify-process issues this run — this is the first run, so there was no prior ledger or memory index to cross-check against beyond the (absent) `MEMORY.md`, which the run created.

---
