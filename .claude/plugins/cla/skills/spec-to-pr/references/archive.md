# archive — materialize the specs and commit the archive to the PR

The Archive phase's procedure. It moves the change to `openspec/changes/archive/<YYYY-MM-DD>-<change-name>/`, updates `openspec/specs/<capability>/`, and commits both to the same PR so they merge with it. Why it archives while the PR is still open: `design-tradeoffs.md` "Archive".

## 1. Before archiving

**List the capabilities this change modifies now**, while the change dir still exists: `ls openspec/changes/<change-name>/specs/`, held for §3 (on a resume past the archive, list `openspec/changes/archive/<YYYY-MM-DD>-<change-name>/specs/` instead).

Fix what these find in this PR, in the same archive commit:

1. Run `openspec validate <change-name> --strict` and fix what it reports. It fails a MODIFIED block that drops a live scenario and a malformed delta. A MODIFIED heading the live spec does not have only prints an `Archive would refuse this delta` line and exits 0: treat that line as a failure too.
2. If the change retired a script or file, grep `openspec/specs/<capability>/spec.md` for the retired path and fix stale references now.
3. After any hand edit under `openspec/specs/`, run `openspec validate --specs`. A stray second `## Requirements` heading hides every requirement below it while the file still reads fine.

## 2. Run the archive

Directly, not through `Skill(openspec-archive-change)`:
```
openspec archive <change-name> --yes
```
Post-check: `openspec/changes/archive/<YYYY-MM-DD>-<change-name>/proposal.md` exists AND `openspec/changes/<change-name>/proposal.md` does not. ✓ on both; ⚠ on either false, stderr to the Handoff Issues section. Its warning about unticked task boxes under `--yes` is expected and not blocking.

## 3. Commit the file moves and the spec sync

Stage **one `openspec/specs/<cap>/` per capability §1 listed** — a change can materialize more than one.

**Pre-commit git-state, live-spec and scope checks — all required:**
```
python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/git_state.py --expect-branch <branch>
openspec validate --specs
git add openspec/changes/<change-name>/ openspec/changes/archive/<YYYY-MM-DD>-<change-name>/ openspec/specs/<cap1>/ [openspec/specs/<cap2>/ ...]
git diff --name-only --cached
```

**`validate --specs`, not `--strict`:** archiving rewrites the live specs, which validating the change does not check; §1 already ran `--strict` on the change, and an older live requirement is rewritten only when a change touches it. Read the output, not only the exit code:

- **`✗ spec/<cap>`** → the live set is broken. Halt and ask via `AskUserQuestion`; do not commit. Read the line before blaming this change — an earlier one may have left it.
- **Non-zero with no `✗` line** (`command not found`, `unknown option`) → a tooling fault, not a spec fault. Say so.
- **`No items found to validate.`** → nothing was checked; not a pass. Where the repo does not use OpenSpec, say so once and skip.

**Stage the named path groups, NEVER a broad `git add openspec/`.** It stages untracked files too, so in a `multi-pr` chain it sweeps every sibling's still-untracked `openspec/changes/<sibling>/` into this commit. If a capability's materialization touched spec assets beyond `spec.md`, add those files by name.

Every staged path in `git diff --name-only --cached` must match one of:
- `openspec/changes/<change-name>/...` (deletions — the change dir moves out)
- `openspec/changes/archive/YYYY-MM-DD-<change-name>/...` (additions)
- `openspec/specs/<cap>/spec.md` (materialization), for each capability
- `openspec/specs/<cap>/` other files the materialization touched

**Two-sided scope check:**
- **Over-staged** — any staged path outside that set (another change's dir, anything outside `openspec/`) → halt and ask via `AskUserQuestion`.
- **Under-staged** — every capability under the change's `specs/` must have its `openspec/specs/<cap>/spec.md` staged. A missing one archives the delta while its live spec is never materialized — silent drift a reject-outside-paths scan cannot see. Stage it and re-run the diff before committing.

**Commit the validated staged set as it stands — do not re-stage.** `openspec archive` already moved the change dir, so a `git add` naming its old path fails with `did not match any files` and takes the commit with it:

```
git commit -m "chore: archive <change-name>"
git push
```

A path you missed is added alone (never `openspec/`, never `-A`), then the two-sided check runs again: a bare `openspec/` after the check re-sweeps the siblings it exists to catch.

**Push post-check (required).** A 0-exit push is not enough: a `pre-push` hook can skip the commit and exit 0, the run can drift onto another branch, a detached HEAD can push to a non-PR ref. Each as a separate Bash call (no pipes or `$(...)`):
```
git rev-parse --abbrev-ref HEAD       # must equal <branch>
git rev-parse HEAD                    # capture this sha
git rev-parse @{u}                    # must equal the captured HEAD sha
gh pr view <#> --json commits         # the captured HEAD sha must appear in the returned commits[]
```
Compare the values in your own context. Any failing → Archive `⚠ proceeded with issues`, captured for Handoff, and a prominent warning in the report: "archive commit DID NOT REACH the PR — merging the PR will not include the archive". Never mark Archive `✓` on the local file moves or a 0-exit push alone.

## 4. No re-review

The archive commit is not re-reviewed: Revise's cap is spent, and the archive is mechanical.
