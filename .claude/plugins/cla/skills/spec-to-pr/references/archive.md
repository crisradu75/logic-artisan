# archive — materialize spec + commit the archive to the PR (full mechanics)

The Archive phase's step-by-step procedure. `SKILL.md`'s Archive stub carries the load-bearing invariants (path-scoped staging, the two-sided scope assertion, the push post-check); this file carries the recipes. **Distinct from `archive-preflight.md`** — that file holds the pre-archive main-spec heading-sanity checks + retired-path cleanup; THIS file holds the archive-and-commit procedure that runs after those checks pass.

After the PR-review loop completes, archive the OpenSpec change so the active spec at `openspec/specs/<capability>/` is materialized and the change directory moves to `openspec/changes/archive/<YYYY-MM-DD>-<change-name>/`. The archive's file moves + spec sync are then committed and pushed to the same PR so they merge atomically.

## 1. Run the archive

Directly via the CLI (skipping `Skill(openspec-archive-change)` for the same indirection-avoidance reason as Review/Revise):
```
openspec archive <change-name> --yes
```
Post-check: `openspec/changes/archive/<YYYY-MM-DD>-<change-name>/proposal.md` exists AND `openspec/changes/<change-name>/proposal.md` no longer exists. ✓ on both true; ⚠ on either false (capture stderr for the Handoff Issues section).

**Pre-archive: main-spec heading sanity + retired-path cleanup.** Older main specs predating OpenSpec heading conventions block the archive's materialization step. Before invoking `openspec archive`, run the three heading-sanity checks — (a) `## Purpose` / `## Requirements` present; (b) legacy `### <Name>` rewritten to `### Requirement: <Name>`; (c) every delta MODIFIED-block heading exists *verbatim* in the active spec (rename the active heading first if the delta renamed it) — **and** the retired-path spec-grep cleanup (a retired script/file's cross-refs in traceability matrices or "Implementation" tables stay stale unless cleaned here). Grep recipes and past offenses: **`references/archive-preflight.md`**. Apply all remediations in the same archive commit so the fixes ship with it.

## 2. Commit the archive's file moves + spec sync

The archive command warns about unticked task boxes when run via `--yes`; that's expected and not blocking.

**First, enumerate the capabilities this change modifies** — a change can materialize MORE THAN ONE (see `cla.io/overlays/spec-to-pr.md` for a real named precedent in this repo). List the change's own spec deltas: `ls openspec/changes/<change-name>/specs/` — each subdirectory there is one capability whose active `openspec/specs/<cap>/` the archive materializes. Stage **one `openspec/specs/<cap>/` path group per capability in that list**, not a single hardcoded one.

**Pre-commit git-state + live-spec + archive-scope checks (all three required):**
```
python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/git_state.py --expect-branch <branch>
openspec validate --specs --strict
git add openspec/changes/<change-name>/ openspec/changes/archive/<YYYY-MM-DD>-<change-name>/ openspec/specs/<cap1>/ [openspec/specs/<cap2>/ ...]
git diff --name-only --cached
```

**Why `--specs` and not just the change.** `openspec validate <change> --strict` validates the CHANGE. Nothing here validated the **live spec set**, and this step is the one that rewrites it — so a materialization that lands a structurally broken `openspec/specs/<cap>/spec.md` was committed, pushed and merged with every check green. Non-zero exit → **halt and surface via `AskUserQuestion`**; do not commit. It needs no database and no build and takes seconds, which is why it belongs at every write site rather than at one.

The failure it catches is silent by construction and lands far from its cause: measured in a six-change chain in a repo consuming this plugin, two live specs each ended up with a **duplicated `## Requirements` heading** — the second one closes the section, so every requirement in both specs became invisible to `validate`, `list` and `archive`. Both merged broken. It surfaced one whole change later, as an aborted archive.
**Stage the specific archive-move path groups, NOT a broad `git add openspec/`.** `git add openspec/` stages *untracked* files too, so in a `multi-pr` chain — where every other not-yet-shipped change still sits as an untracked `openspec/changes/<sibling>/` directory in the same worktree — the broad form sweeps those siblings into this change's archive commit, tripping the scope-assertion halt below on *every* archive in the chain. The enumerated paths cover exactly what the archive produces (the change dir's deletions, the new dated archive dir's additions, and the materialized `openspec/specs/<cap>/` for **every** capability the change touched) and nothing else. (If a capability's materialization touched sibling spec assets beyond `spec.md`, add those specific files by name too — still never the bare `openspec/`.)

Inspect the `git diff --name-only --cached` output in Claude's context. Every staged path MUST match one of these shapes for the archive commit:
- `openspec/changes/<change-name>/...` (deletions — the change directory moves out)
- `openspec/changes/archive/YYYY-MM-DD-<change-name>/...` (additions — the new archive location)
- `openspec/specs/<cap>/spec.md` (modifications — materialization), for each capability
- `openspec/specs/<cap>/` other files (when the materialization touches related spec assets)

**Two-sided scope check — the assertion catches over-staging AND under-staging:**
- **Over-staged** — if any staged path falls outside the set above (e.g. `openspec/changes/<some-other-change>/...`, or anything outside `openspec/`) → halt and surface to the user via `AskUserQuestion`.
- **Under-staged** — confirm that for **every** capability directory listed under `openspec/changes/<change-name>/specs/`, a matching `openspec/specs/<cap>/spec.md` appears in the staged output. A capability the change modified whose active spec is NOT staged means the delta gets archived out of active changes but its active spec is never materialized → **silent active-spec drift** (the exact failure the archive step exists to prevent). The over-staging check alone cannot catch this — a missing path is invisible to a "reject outside paths" scan. If any capability's `spec.md` is missing from the staged set, stage it and re-run the diff before committing.

The staged set the assertion just validated is exactly what should land, so **commit it as it stands** — do not re-stage anything here. `openspec archive` has already moved the change directory off disk, so a `git add` naming a rename-source path fails with `did not match any files` and takes the whole commit with it. Subject is one line, passed inline:

```
git commit -m "chore: archive <change-name>"
git push
```

If you do find yourself needing to add a path you missed, add that one path (never `openspec/`, never `-A`) and re-run the two-sided scope assertion before committing — a bare `openspec/` re-sweeps the sibling untracked change dirs *after* the assertion passed, silently reintroducing the cross-change contamination the assertion exists to catch.

**Push post-check (required):** `git push` exit 0 alone is NOT sufficient — there are real scenarios where it succeeds but the archive commit never reaches the PR (a `pre-push` hook rewrote/skipped the commit and exited 0; the orchestrator drifted onto a leaked branch and pushed *that* branch instead of `<branch>`; a detached HEAD after a Revise rebase pushed to a non-PR ref). Verify all of (each as a separate Bash call — no shell pipes or `$(...)`):
```
git rev-parse --abbrev-ref HEAD       # must equal <branch>
git rev-parse HEAD                    # capture this sha
git rev-parse @{u}                    # must equal the captured HEAD sha
gh pr view <#> --json commits         # the captured HEAD sha must appear in the returned commits[]
```
Compare the values in Claude's context (do not pipe shell output through `grep`). If any check fails, mark Archive as `⚠ proceeded with issues`, capture the failure for the Handoff Issues section, and emit a prominent warning in the terminal report ("archive commit DID NOT REACH the PR — merging the PR will not include the archive"). Do NOT silently mark Archive as `✓` based only on the local file moves or a 0-exit push.

## 3. No re-review

The archive commit is NOT re-reviewed by the pr-review agents — the pr-review cap has already exhausted in Revise, and the archive is mechanical (file moves + delta-spec materialization).

Trade-off rationale (archive runs while PR is OPEN; staleness risk on PR rejection) is documented in `references/design-tradeoffs.md`.
