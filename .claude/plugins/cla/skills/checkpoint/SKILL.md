---
name: checkpoint
description: "Compact the current session into a briefing the next session can resume from: what was decided and why, what landed, what is in flight with its exact next action, and the open threads. Points at commits, PRs, and decision docs rather than restating them, and never copies secrets or file contents. Writes cla.io/checkpoints/<date>-<slug>.md. Triggers on /cla:checkpoint or natural language like 'checkpoint this session', 'write a handoff for the next session', 'I am running out of context', 'summarize where we are so I can resume tomorrow'."
argument-hint: "[optional slug for the checkpoint file]"
allowed-tools: Bash, Read, Grep, Glob, Write
---

# /cla:checkpoint — compact a session into a resumable briefing

A long session ends in one of two ways: deliberately, or by running out of room.
Both lose the same thing — not the code, which is committed, but the *reasoning*:
why an approach was abandoned, which claim turned out false, what the next action
was going to be. That context is what makes the next session re-derive work
instead of continuing it.

This writes it down. It is a capture skill, like `feedback`: it records state and
decides nothing.

## What a checkpoint is NOT

- **Not a summary of everything.** A transcript replay is as unusable as no notes.
- **Not a copy of artifacts.** Point at the commit, the PR number, the decision
  doc. A checkpoint that duplicates them goes stale the moment they move.
- **Not a place for secrets.** Never copy a token, key, connection string, or the
  contents of a `.env`. Name the file, not its value.

## The argument

Bind it once: **`<arg>` = `$ARGUMENTS`** — an optional slug for the checkpoint
filename. Empty is the common case; derive a slug from the session's dominant
topic then.

## Procedure

### 1. Gather the mechanical state first

Cheap commands, not memory — memory is exactly what is degrading by the time this
skill runs:

```bash
git status --porcelain
git log --oneline -15
git branch --show-current
```

```bash
gh pr list --state open --json number,title,baseRefName
```

Read `cla.io/decisions/` and `cla.io/feedback/` for anything dated today — those
are this session's own durable outputs and the next session should start from
them rather than rediscovering them.

### 2. Write the briefing

To `cla.io/checkpoints/<YYYY-MM-DD>-<slug>.md` (slug from `<arg>`, else derived
from the session's dominant topic). Create the directory if absent. Six sections,
in this order, each omitted entirely if genuinely empty:

1. **Where things stand** — one paragraph. The state a reader needs before any
   detail makes sense.
2. **Landed** — what merged, as PR numbers and one-line subjects. Not diffs.
3. **In flight** — the single most important section. For each open thread: the
   branch, the PR if any, and **the exact next action**, phrased so it can be
   executed without reconstructing the reasoning behind it.
4. **Decided** — decisions made this session and *why*, each pointing at its
   decision doc if one exists. Include decisions to NOT do something; those are
   the ones a next session most often re-litigates.
5. **Open questions** — genuinely unresolved, with what would settle each.
6. **Traps** — things that cost time this session and would cost it again: a
   claim that turned out false, a command that failed for a non-obvious reason, a
   tool that behaved unexpectedly. This is the section that pays for the skill.

### 3. Say it exists

Print the path and the one-line resume instruction. Do not summarise the
checkpoint back to the user — they were there; the file is for who comes next.

## Resuming from one

Read the checkpoint, then verify it against the tree before acting on it: a
checkpoint records what was true when written, and `git status`/`gh pr list` are
the current truth. Where they disagree, the tree wins and the checkpoint is
stale — say so rather than quietly following it.

## When NOT to use

- On a short session — the transcript is the checkpoint.
- As a status report for the user. That is the terminal report of whichever skill
  did the work.
- Instead of committing. A checkpoint is not a substitute for landing work; if
  something is finishable, finish it first and checkpoint the remainder.
