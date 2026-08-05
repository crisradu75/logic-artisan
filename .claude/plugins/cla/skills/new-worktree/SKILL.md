---
name: new-worktree
description: "Start a new isolated git worktree for this repo, with dependencies installed and any gitignored env files carried over. Triggers on /cla:new-worktree or natural language like 'new worktree', 'start a worktree for X', 'work on this in a worktree'."
---

# New worktree, fully set up

See `references/project-context.md` for this repo's own workspace shape, its gitignored env file(s), and why a bare `EnterWorktree` alone leaves the new worktree without a working dev setup (no installed dependencies, no env-derived secrets, so a dependent process silently degrades). This skill does the full setup in two tool round-trips total.

**The dominant cost here is round-trips, not the install's own execution time.** See `references/project-context.md` for this repo's own measured install timing. What actually makes a rerun feel slower is extra tool calls layered on top (a separate `git worktree list` lookup, ad hoc verification checks, status checks) — each one is a full model round-trip regardless of how fast the command inside it runs. So: keep this to the fewest possible tool calls, and don't add "just to be sure" verification steps — trust each command's own output/exit code.

## Path discipline once inside a worktree

Once `EnterWorktree` has run, every subsequent `Write`/`Edit`/`Read`/file-writing
`Bash` call for the rest of the task must use a path relative to the worktree cwd (or
its returned absolute path) — never a hardcoded primary-clone path. Two guard hooks
back this up — `guard-worktree-isolation.py` catches `git checkout`/`switch`/`commit`, and
`block-worktree-path-escape.py` blocks any `Write`/`Edit` whose target escapes the worktree
into the primary clone (escape hatch: `ALLOW_WORKTREE_PATH_ESCAPE=1`) — but treat them as a
backstop, not a licence to skip relative paths. If work still ends up in the wrong (shared) location, don't delete it to
fix the mistake until a verified copy exists elsewhere — copy first, confirm, then
clean up. If a commit ever goes missing after a shared branch gets switched/deleted
out from under it, check `git reflog` / `git fsck --unreachable` before assuming it's
lost — worktrees share one object store, so `git checkout <sha> -- <path>` recovers
files into a different worktree with no copy step needed. (Full incident writeup: see
memory `worktree-isolation-file-paths`.)

## Steps

1. **Enter the worktree.** Call `EnterWorktree`, passing `name` if the user gave one
   (from `$ARGUMENTS` when invoked as `/cla:new-worktree <name>`). If the session is
   already inside a worktree, the tool will refuse — tell the user and stop rather
   than working around it.

   If it refuses for a *different* reason — a "refusing to use ... as an isolation
   worktree" message naming two paths that look identical — see
   **When `EnterWorktree` refuses over path casing** below. Don't retry it; it will
   fail identically every time on that machine.

   **Know which base you land on, and say so in the report.** A harness-created
   worktree branches from the *remote's default branch*, not from whatever is checked
   out right now. That is usually what you want — a new worktree starts clean rather
   than inheriting half of an in-progress change — but it is the opposite of what
   someone expects when they deliberately branch off current work. A `worktree.baseRef`
   setting (value `"head"`) flips it repo-wide where the harness supports it. Don't set
   it unprompted: it is a repo-level default with a real trade, and the failure it
   prevents (unexpected clean base) is far cheaper than the one it introduces
   (unexpectedly inheriting uncommitted context into an isolated worktree). Surface the
   base branch in step 3 so the user can catch a mismatch immediately rather than after
   the first confusing diff.

2. **Fire off two independent steps in parallel — both in the same message, as
   separate tool calls (not chained with `&&`, not sequential turns). This is the
   only other round-trip; do not precede it with a separate `git worktree list` call
   to locate the main checkout — resolve it inline, in the copy command itself:**
   - This repo's own dependency-install command (offline-preferring where the package manager supports it) at the new worktree's root — see `references/project-context.md` for the exact command and why it's the **only** install needed (don't also run a separate install inside a sub-app whose own lockfile/install has been consolidated away); see `cla.io/project-facts.md` ("Workspace shape") for this repo's current workspace-member list (run `/cla:sync-context` to populate it; falls back to the overlay if absent).
   - Copy this repo's own gitignored env file(s) (see `cla.io/project-facts.md` ("Env files") for the exact path(s); falls back to `references/project-context.md` if absent) from the main checkout into the new worktree, resolving the main checkout path inline (don't spend a tool
     call discovering it first — but don't use `git rev-parse --show-toplevel` or
     `$CLAUDE_PROJECT_DIR` for this either: verified live, `CLAUDE_PROJECT_DIR` is
     unset in the Bash tool's shell, and `--show-toplevel` run from inside the new
     worktree resolves to the *worktree's own root*, not the main checkout —
     worktrees each have their own toplevel, that's the whole mechanism. `git
     rev-parse --git-common-dir` is the one that stays correct from inside a linked
     worktree: it always resolves to the shared `.git`, which lives in the main
     checkout, so its parent directory is the main checkout root regardless of which
     worktree you're currently in):
     ```bash
     cd <app-dir>
     MAIN="$(dirname "$(git rev-parse --git-common-dir)")"
     if [ -f "$MAIN/<env-file-path>" ]; then
       cp "$MAIN/<env-file-path>" ".env" && echo "copied .env"
     else
       echo "no <env-file-path> in main checkout — skipping"
     fi
     ```
     If it's missing, note that in the final report — don't fail the whole flow over it.

     **Worth checking once per repo: a `.worktreeinclude` may remove this step
     entirely.** Recent Claude Code versions read a `.worktreeinclude` file at the
     project root — `.gitignore` syntax, copying only paths that are both matched
     *and* gitignored — into every worktree the harness itself creates. Where that is
     supported, listing this repo's env file(s) there does declaratively what the `cp`
     above does imperatively, and deletes a command from the hot path this skill spends
     its whole design budget minimizing. Verify it actually populated the file before
     dropping the `cp`, and keep the `cp` if it didn't: this skill enters via
     `EnterWorktree`, and support is worth confirming rather than assuming.

     Two limits, so nobody over-reads this. It is harness machinery, **not** git — the
     worktrees that `/cla:multi-lite`, `/cla:multi-pr` and `/cla:spec-to-pr` create via
     raw `git worktree add` are unaffected and still need their own handling. And it
     copies only gitignored files, which is the point: a tracked file is already in the
     new checkout.

   An offline-preferring install flag is the default here, not an opt-in: it skips a registry
   network round-trip, which is a real (if modest) saving and never a regression.
   Don't oversell it as a big win — it isn't one once the store is warm, disk I/O
   dominates at that point (a content-addressable package store also means a warm
   rerun mostly hardlinks rather than re-downloads). If installs are still slow on
   Windows, see `references/project-context.md` for a machine-level mitigation worth
   mentioning — but don't change that setting without asking; it's machine-level, not
   project-level.

3. **Report back** using each step's own output — worktree path, branch name, and
   whether the install and the `.env` copy succeeded (or what was skipped and why).
   Do not add extra tool calls (`test -d node_modules`, `git status`, etc.) just to
   double-check success; the install command's own exit and the `cp && echo` output already
   confirm it. Only investigate further if an output actually looks wrong.

## When `EnterWorktree` refuses over path casing

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
python3 .claude/plugins/cla/skills/new-worktree/scripts/manual_worktree.py --diagnose
```

**Fallback: create the worktree with plain git.** One command, JSON on stdout,
including the main-checkout path so the rest of this skill's steps need no extra
lookup:

```bash
python3 .claude/plugins/cla/skills/new-worktree/scripts/manual_worktree.py --name <name>
```

It also clears the stale entry a failed `EnterWorktree` leaves behind — the tool
registers the worktree with git *before* its safety check refuses, so a locked
entry accumulates at that path on every attempt and blocks the next one. A
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

**The durable fix is upstream.** `EnterWorktree` should normalise both sides
(`os.path.realpath` and equivalents canonicalise to the filesystem's true casing)
before comparing. Worth reporting at `https://github.com/anthropics/claude-code/issues`
if not already tracked. Nothing inside a consuming repo can fix it.

## Non-goals

- Doesn't touch `.claude/settings.local.json` or any permission state.
- Doesn't run `ExitWorktree` — that's a separate, explicit user action later. (If a
  later `ExitWorktree --remove` fails with a file lock, that's normal on Windows right
  after an install — a process/AV scan may still hold a handle; leaving it "kept"
  is fine, no action needed from this skill.)
- Doesn't handle the "already inside a worktree" case beyond reporting it — `EnterWorktree`
  intentionally disallows nesting a new worktree creation inside an existing worktree session.
- Doesn't set up any heavier local backend stack this repo may have (e.g. Docker
  containers for a local database stack) — that's a heavier, explicit step the user
  can run themselves per this repo's own docs (see `references/project-context.md`)
  if they need that part of the workspace functional in this worktree, not something
  to do unprompted on every worktree creation.
