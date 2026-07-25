# Lessons learned

<!-- Rolling log written by /cla:codify-learnings, which prepends each report. Newest entries at the top. -->

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
