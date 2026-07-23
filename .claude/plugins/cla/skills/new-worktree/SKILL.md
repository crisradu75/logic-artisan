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
