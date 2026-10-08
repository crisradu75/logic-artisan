---
name: new-worktree
description: "Start an isolated git worktree for this repo with dependencies installed and gitignored env files carried over; inside an existing worktree it runs only the setup half. Triggers: /cla:new-worktree, 'new worktree', 'work on this in a worktree'."
---

# New worktree, fully set up

A bare `EnterWorktree` leaves the new worktree without a working dev setup — no installed dependencies, no env-derived secrets, so a dependent process silently degrades. This skill does the full setup in two tool round-trips total. This repo's install command, workspace shape and gitignored env file(s) come from `cla.io/project-facts.md` ("Dev / build / test commands", "Workspace shape", "Env files"; run `/cla:cla-setup` when it is missing or stale). `cla.io/overlays/new-worktree.md`, if present, adds rules specific to this skill in this repo.

**Resolving `${CLAUDE_PLUGIN_ROOT}`.** This `SKILL.md` arrives with the placeholder substituted, but a
`references/` file opened with `Read` carries it literally, and it is not an environment variable in
Bash — an unset variable silently runs the command against `/skills/...`. Before running a command
that contains the literal text, replace it with the plugin root: the `Base directory for this skill`
path with `/skills/<name>` removed, or the absolute path of any plugin file you have read, cut
at `.../plugins/cla`. If neither works, say so and stop. Detail:
`${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/plugin-root.md`.

**The dominant cost here is round-trips, not the install's own execution time.** What actually makes a rerun feel slower is extra tool calls layered on top (a separate `git worktree list` lookup, ad hoc verification checks, status checks) — each one is a full model round-trip regardless of how fast the command inside it runs. So: keep this to the fewest possible tool calls, and don't add "just to be sure" verification steps — trust each command's own output/exit code.

## Path discipline once inside a worktree

Once `EnterWorktree` has run, every subsequent `Write`/`Edit`/`Read`/file-writing
`Bash` call for the rest of the task must use a path relative to the worktree cwd (or
its returned absolute path) — never a hardcoded primary-clone path. One guard hook
backs this up — `block-worktree-path-escape.py` blocks any `Write`/`Edit` whose target
escapes the worktree into the primary clone (escape hatch:
`ALLOW_WORKTREE_PATH_ESCAPE=1`). It covers writes only; nothing intercepts a stray
`git checkout`/`switch`/`commit` any more, so treat it as a
backstop, not a licence to skip relative paths. If work still ends up in the wrong (shared) location, don't delete it to
fix the mistake until a verified copy exists elsewhere — copy first, confirm, then
clean up. If a commit ever goes missing after a shared branch gets switched/deleted
out from under it, check `git reflog` / `git fsck --unreachable` before assuming it's
lost — worktrees share one object store, so `git checkout <sha> -- <path>` recovers
files into a different worktree with no copy step needed. (Full incident writeup: see
memory `worktree-isolation-file-paths`.)

## Steps

1. **Enter the worktree.** Call `EnterWorktree`, passing `name` if the user gave one
   (from `$ARGUMENTS` when invoked as `/cla:new-worktree <name>`).

   **If it refuses because the session is ALREADY inside a worktree, that is the
   setup-only case — skip to step 2 rather than stopping.** The worktree exists and
   only needs its dependencies and env files. This is the normal state when a session
   was started *inside* a pre-made worktree rather than migrating into one — a repo may
   create the worktree with plain git before Claude starts. Do NOT try to create a second
   worktree, and do not treat the refusal as an error to report and halt on.

   Don't spend a tool call checking whether you are in a worktree first — the refusal
   IS the signal, and a pre-check would cost a round-trip on every ordinary run for a
   case that announces itself. Likewise don't check whether setup has already been
   done: step 2 is idempotent (the install is offline-preferring and mostly hardlinks
   on a rerun, the env copy is a guarded `cp`), so re-running it is cheaper than
   detecting it.

   In the setup-only case, say so in the step 3 report — "worktree already existed;
   ran setup only" — so nobody reads it as a fresh worktree on a fresh base.

   If it refuses for a *different* reason — a "refusing to use ... as an isolation
   worktree" message naming two paths that look identical — that is NOT this case; see
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
   - This repo's own dependency-install command (offline-preferring where the package manager supports it) at the new worktree's root, from `cla.io/project-facts.md` ("Dev / build / test commands"). Run only the root install the facts name — don't also run a separate install inside a sub-app whose own lockfile/install has been consolidated away (the "Workspace shape" section lists the members).
   - Copy this repo's own gitignored env file(s) (`cla.io/project-facts.md`, "Env files", for the exact path(s)) from the main checkout into the new worktree, resolving the main checkout path inline (don't spend a tool
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
   Windows, a machine-level mitigation (such as an antivirus exclusion for the package
   store) may be worth mentioning — but don't change that setting without asking; it's
   machine-level, not project-level.

3. **Report back** using each step's own output — worktree path, branch name, and
   whether the install and the `.env` copy succeeded (or what was skipped and why).
   Do not add extra tool calls (`test -d node_modules`, `git status`, etc.) just to
   double-check success; the install command's own exit and the `cp && echo` output already
   confirm it. Only investigate further if an output actually looks wrong.

## When `EnterWorktree` refuses over path casing

A refusal naming two paths that differ only in letter case: **read `references/path-casing.md`**
and follow it. Don't retry `EnterWorktree`; it will refuse the same way. Never "fix" it by renaming
the repo directory. The fallback is a manual worktree, which gets no write redirection: every
path must target the worktree explicitly, and the final report must say this mode was used.

## Non-goals

- Doesn't touch `.claude/settings.local.json` or any permission state.
- Doesn't run `ExitWorktree` — that's a separate, explicit user action later. (If a
  later `ExitWorktree --remove` fails with a file lock, that's normal on Windows right
  after an install — a process/AV scan may still hold a handle; leaving it "kept"
  is fine, no action needed from this skill.)
- Doesn't create a *second* worktree from inside one — `EnterWorktree` intentionally disallows
  nesting. That refusal is not an error here: step 1 treats it as the setup-only signal and runs
  step 2 against the worktree you are already in.
- Doesn't set up any heavier local backend stack this repo may have (e.g. Docker
  containers for a local database stack) — that's a heavier, explicit step the user
  can run themselves per this repo's own docs (`cla.io/project-facts.md`, "Infrastructure")
  if they need that part of the workspace functional in this worktree, not something
  to do unprompted on every worktree creation.
