# Resolving an in-progress rebase, cherry-pick, or merge

`git_state.py` exits 2 when one of these is mid-flight. That exit is a detection,
not a verdict — this file is the procedure it hands you. Four skills check that
exit at every commit boundary (`spec-to-pr`, `lite-pr`, `multi-pr`, `multi-spec`)
and, until this file existed, all four stopped at "halt and surface" with nothing
to surface but the halt.

**The rule the exit code implies: never `--abort` reflexively.** An abort throws
away work someone was in the middle of — possibly another session's, possibly
conflict resolutions already made by hand. Aborting is a legitimate ENDING, but
only after you know what you are discarding.

## 1. Identify what is running, and whose it is

```
python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/git_state.py
```

The `in_progress_op` field names it. Then read the state:

```
git status
git log --oneline -3
```

An operation this run did not start belongs to a parallel session. Do not
resolve it — surface it to the user with the branch name and the operation, and
stop. Concurrent runs are supposed to be worktree-isolated; an in-progress op
from elsewhere means that isolation broke, and continuing compounds it.

## 2. Recover each side's intent before touching a hunk

**Which side is which depends on the operation, and reading it backwards is the
classic way to delete the change you meant to keep.**

| Operation | `--ours` / `HEAD` | `--theirs` |
|---|---|---|
| merge | the branch you are on | the branch being merged in |
| rebase / cherry-pick | the branch being replayed **onto** (the base) | **your own commits** being replayed |

Rebase inverts the intuition: during a rebase, `--theirs` is *your* work. Confirm
which is which from the table before you resolve anything, not after.

Then get the intent, not just the text:

```
git log --oneline --left-right HEAD...MERGE_HEAD      # merge: what each side added
git show <sha>                                        # the commit a conflicted hunk came from
```

Read the conflict markers before editing — `cat <file>` and name, out loud, what
each side was trying to do. A hunk where both sides changed the same line for
*different reasons* usually needs both intents preserved, not one side chosen.

## 3. Resolve hunk by hunk, preserving both intents where possible

- Prefer a resolution that keeps both changes when they are compatible. Choosing
  a whole side wholesale is right only when the sides are genuinely alternatives.
- `git checkout --ours/--theirs <file>` takes an ENTIRE file. Use it only when the
  whole file is genuinely one side's — never as a shortcut past a two-line hunk.
- Leave no conflict markers: `git grep -n '^<<<<<<<\|^=======\|^>>>>>>>'` must
  return nothing before you continue.

## 4. Validate before continuing the operation

Run the repo's own gate — the build/lint/test commands from
`cla.io/project-facts.md` — on the resolved tree. A resolution that compiles is
not a resolution that is correct, and mid-rebase is the cheapest moment to find
out: the alternative is discovering it three commits later with the fix buried.

## 5. Continue, and re-check

```
git add -- <the specific resolved paths>          # never `git add -A`
git rebase --continue                             # or: git cherry-pick --continue / git merge --continue
python3 ${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/git_state.py
```

A rebase can stop again on the next commit — the exit-2 check is a loop, not a
one-shot. Re-run it until it exits 0, resolving each stop the same way.

## When aborting IS right

- The operation is not yours and the user says to clear it.
- The conflict reveals the branch was cut from the wrong base — abort, re-cut,
  and replay cleanly rather than hand-resolving a mess that should not exist.
- You cannot recover one side's intent (the commit is a squashed import, the
  history was rewritten). Say so plainly and abort rather than guessing.

`git rebase --abort` / `git cherry-pick --abort` / `git merge --abort` all restore
the pre-operation state. Say which you ran and why in the run's report — an abort
is a decision worth recording, not a cleanup detail.
