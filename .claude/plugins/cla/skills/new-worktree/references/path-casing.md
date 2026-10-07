# When `EnterWorktree` refuses over path casing

> Applies while `EnterWorktree` compares these paths as literal strings. That is
> a bug in an externally-owned tool, so re-check the symptom against the current
> version before following this — if the refusal no longer reproduces, this
> section is finished and should be deleted rather than worked around.

**Symptom.** Every `EnterWorktree` call on a given machine fails with a refusal
naming two paths that differ only in letter case — `C:\Code\<repo>\...` against
`C:/code/<repo>/...`, or similar.

**Cause.** Those name the same directory. On a case-insensitive filesystem
(Windows/NTFS, macOS APFS by default) a repo whose real on-disk name is
capitalised can be reached through a lowercase path, and the two spellings both
work. `EnterWorktree` compares the session's launch-time project path against
git's own resolution of it as literal strings, so it sees a mismatch and refuses.

Three things this is **not**, each worth ruling out explicitly so nobody spends
an afternoon on the wrong one:

- **Not a repo misconfiguration.** `core.ignorecase` is almost certainly already
  `true`, which is correct for such a filesystem. The comparison never asks git,
  so the setting cannot help.
- **Not a git problem.** Plain `git worktree add/list/remove` and `git -C <path>`
  all resolve these paths correctly. Only the tool's own check is affected.
- **Not caused by concurrent worktrees.** The mismatch is a property of the path,
  present on a completely idle repo. If it first appeared on a day with two
  sessions running, that was coincidence.

**Do not "fix" it by renaming the repo directory to lowercase.** That changes the
correct side of the mismatch to appease a tool that isn't honouring the
filesystem's own semantics, breaks any IDE workspace, shortcut, or concurrent
session pinned to the current name, and leaves the bug in place for the next repo.

Confirm the diagnosis (no side effects) with:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/new-worktree/scripts/manual_worktree.py --diagnose
```

On Windows — the platform this whole section exists for — `python3` is often
absent; use `py` or `python` instead. (`hooks.json` carries the same
`python3 || py || python` probe chain for exactly this reason.) It reports
`case_only` for the refusal described here, `path_indirection` when the repo
path resolves elsewhere through a symlink or junction (a different problem that
can look the same), and `null` when the path is clean.

**Fallback: create the worktree with plain git.** One command, JSON on stdout,
including the main-checkout path so the rest of this skill's steps need no extra
lookup:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/new-worktree/scripts/manual_worktree.py --name <name>
```

It also clears the stale entry a failed `EnterWorktree` leaves behind. Observed
behaviour, not documented contract: the tool appears to register the worktree
with git *before* its safety check refuses, so a locked entry accumulates at that
path on every attempt and blocks the next one. The cleanup is written to be
correct whether or not that ordering holds. A
non-empty directory git no longer tracks is never deleted; that is somebody's
work, and the add fails instead so a human can look.

Then continue with step 2 unchanged — the dependency install and env-file copy
are the same, run against the returned `worktree_path`.

**One thing genuinely changes, and it must go in the final report.** A session
that entered via `EnterWorktree` has its `Write`/`Edit`/file-writing `Bash` calls
redirected into the worktree automatically. A manually created worktree gets none
of that: the session is still rooted in the primary clone, so **every** subsequent
path must target the worktree explicitly. `block-worktree-path-escape.py` is no
backstop here either — it only fires for a session whose cwd *is* the worktree, so
in this mode the path discipline above is the only thing protecting the boundary.

**One detection limit worth knowing.** `--diagnose` compares the path as given
against its resolved form, and `os.path.realpath` folds letter case only on
Windows. On a case-insensitive POSIX filesystem (macOS APFS by default) the same
refusal can occur while `--diagnose` reports clean, so treat a `null` there as
inconclusive rather than as an all-clear.

**The durable fix is upstream.** `EnterWorktree` should normalise both sides
(`os.path.realpath` and equivalents canonicalise to the filesystem's true casing)
before comparing. Worth reporting at `https://github.com/anthropics/claude-code/issues`
if not already tracked. Nothing inside a consuming repo can fix it.
