# Bash-style discipline (hard rules)

These shapes defeat the project's Bash permission allowlist matching. The skill MUST NOT emit them. The same rules also live in the project's root `CLAUDE.md`; this file is the orchestrator's local enforcement reference.

## Forbidden shapes

- ❌ **Compound bash:** `cd <path> && <cmd>`. Use absolute paths and call the command directly. The Bash tool's working directory does NOT reliably persist between calls; default to absolute paths or `git -C <abs-path>`.
- ❌ **Heredoc subshell:** `git commit -m "$(cat <<'EOF' ... EOF)"` for commit messages or PR bodies. Write the message/body to a file and use `commit.py` (or `git commit -F <file>`).
- ❌ **Multi-line `--body` argument:** `gh pr create --body "...\n## ..."`. Use `--body-file <path>` (via `gh pr edit --body-file <path>`) — never `Skill(commit-commands:commit-push-pr)`, which this skill deliberately doesn't use (see "When NOT to use `Skill()`" and `design-tradeoffs.md`).
- ❌ **Long `git add` file lists:** `git add file1 file2 ... file39`. Use a glob or directory: `git add openspec/changes/<name>/`.
- ❌ **`git add -A` (or `git add .`).** Always path-scope every staging call. Failure mode: an Archive-phase `git add -A` can sweep untracked files left by a parallel Claude session's in-progress cherry-pick into the archive commit, shipping unrelated content. Even when `git status --porcelain` shows nothing unrelated at the START of the run, an external session can mutate the working tree mid-flow; path-scoped staging makes this impossible.

## Mandated alternatives

- ✅ Single-line `-m "<message>"` for trivial commits, or `-F <message-file>` via `commit.py`.
- ✅ `--body-file <path>` for every PR body and PR edit.
- ✅ Absolute paths everywhere — never rely on a prior `cd`.
- ✅ Path-scoped staging: `git add openspec/changes/<name>/ apps/<app>/src/ packages/<package>/src/` (Ship — name the specific `apps/*/src/`/`packages/*/src/` paths the change touched; there is no repo-root `src/`), `git add openspec/` (Archive). Never `git add -A`. If you legitimately need to stage multiple top-level paths, enumerate them on the same `git add` line — never expand to `-A`.

## Conflict resolution discipline (rebase + merge)

Failure mode: running `git checkout --theirs <file>` during a rebase expecting it to take the base branch's version. In a rebase, `--theirs` means the commits BEING REBASED (the branch's side, opposite of merge context), so it silently commits the wrong content and requires a `git reset --hard HEAD~1` and redo.

When resolving a conflict from `git rebase`, `git merge`, or `git cherry-pick`:

1. **Read the conflict markers FIRST.** `cat <conflicted-file> | head -30` (or Read the file). Confirm which side is `<<<<<<< HEAD` and which is the merging branch — never trust positional intuition about which side is "ours".
2. **Name the desired keep side in your own context** before issuing the resolve command. ("I want main's polished version, which is on the HEAD side of the conflict markers.")
3. **Use file-write Edit (not `--ours`/`--theirs`)** when the resolved content is a custom mix or when you've identified the desired side from the markers. Direct edit is unambiguous.
4. **If you do use `--ours`/`--theirs`, name the context explicitly.** In a `git merge`: `--ours` = the current branch (the one you ran `git merge` on); `--theirs` = the branch being merged in. In a `git rebase`: the semantics INVERT — `--ours` = the upstream you're rebasing ONTO (often main); `--theirs` = the commits being replayed (the branch's side). In a `git cherry-pick`: `--ours` = the current branch; `--theirs` = the commit being applied. Refer to the git man page when uncertain. Never assume.
5. After staging the resolution, `git diff HEAD --cached -- <file>` and verify the diff matches your intent BEFORE `git rebase --continue` / `git merge --continue` / `git cherry-pick --continue`.

## Why these patterns matter

Claude Code's permission allowlist matches against the literal command shape. A pattern like `Bash(git commit *)` matches `git commit -m "feat: x"` but NOT `cd /repo && git commit -m "feat: x"` (the `cd` prefix changes the shape). A heredoc / subshell / newline in the command string similarly slips past the matcher and triggers a fresh permission prompt every time. The visible symptom is "Claude keeps asking for permissions despite the allowlist" — the root cause is almost always a shape that breaks matching, not a missing pattern.
