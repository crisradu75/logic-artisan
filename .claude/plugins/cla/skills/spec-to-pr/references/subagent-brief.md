# The sub-agent brief: five slots

The shared shape for every `Agent` dispatch in this plugin. Owned here because
`spec-to-pr` has the most dispatch sites, but **not** specific to it — `/cla:lite-pr`,
`/cla:multi-lite` and `/cla:multi-spec` cite this file rather than restating it, the
same way `review-change/references/checklist.md` is read by more than its own skill.

Cite it; don't paraphrase it. A brief shape re-derived per call site is how the
quality gradient appeared that this file exists to remove: one dispatch site had three
carefully-reasoned rules and another had a single sentence.

---

## Why a template at all

An agent without a stated boundary infers one, and the boundary it infers is wider
than yours. It also cannot ask — it gets one prompt, works in its own context window,
and returns once. Everything it needs to not go wrong has to be in the brief, because
there is no second round to correct it in.

The slot people skip is **Do not touch**, and it is the one that matters most here:
this plugin dispatches agents *in parallel* (`lite-pr`'s Review fan-out,
`spec-to-pr`'s Revise fan-out). Two agents editing the same file overwrite each other
with no merge and no warning.

---

## The five slots

### 1. Scope — exact paths, not a description

`src/auth/` and `tests/auth/`, not "the auth module". A directory is checkable; a
description is a matter of interpretation, and two agents can each believe a shared
file is theirs.

### 2. Task — one sentence, one deliverable

If the sentence needs an "and", consider whether it is two agents. Where the task is
an enumeration (a task list, a set of findings), **enumerate every item explicitly**:
an agent implements exactly what the brief lists and will not invent an omitted one,
so an item left out silently stays undone. Mark anything deliberately deferred as
deferred rather than dropping it.

### 3. Do not touch — the files another agent owns, named

Name the paths, not the principle. Include any file the orchestrator itself is holding
open, and any file a sibling agent in the same fan-out owns. Also name the *decisions*
that are not the agent's to make — "do not change the public signature", "do not add a
dependency" — since scope alone does not constrain those.

### 4. Report — what to write, and where

An agent that returns only to the conversation has produced nothing that survives its
own termination. Where the output is durable, name the path. Where it is a finding
list, name the shape you will consume.

Keep briefs trimmed: pass the sections the task actually references, not the whole
document. For a diff review, describe the diff by **file + symbol + focus question**
and let the agent read the hunks itself rather than pasting raw diff text inline.

### 5. Done when — a condition you will check, with evidence

Not "when it looks right". The strongest form, and the default for anything that
edits code:

> End with an explicit `done` or `blocked` status. `done` is valid ONLY when
> accompanied by hard evidence — the test-run summary line, and the ticked-task count
> (`- [x]` count vs total). A return claiming done without that evidence is treated as
> **not done**.

The evidence requirement is doing the real work. A status field alone is the agent's
opinion of its own output; a summary line and a count are checkable facts.

---

## What the brief cannot do

**A brief is a request; frontmatter is a constraint.** When the same kind of worker is
briefed a third time, write it into `.claude/agents/` and move whatever can be
mechanically enforced out of the prose:

- `tools:` is an allowlist. A reviewer given `Read, Grep, Glob` *cannot* edit a file,
  regardless of what its prompt says or how far it has drifted. This is strictly
  stronger than "do not edit" in the brief.
- `disallowedTools:` denies against the inherited set, when the allowlist is the wrong
  shape.
- `model:` keeps mechanical delegated work off the expensive model.
- `permissionMode: plan` makes an agent read-only by construction. Note that tightening
  works and loosening does not: an agent cannot widen the parent session's mode.

Slots 1, 3 and 5 have no frontmatter equivalent and stay in the brief permanently.

**Verify the output; do not trust the report.** An agent that reports success has
reported its own opinion of its work. Whatever the brief's "done when" said, the
orchestrator still runs its own check — see `revise.md`'s no-capitulation and
no-sycophancy rules (`INT-CAP` / `INT-SYC`), and the Implement post-check that recounts
task boxes regardless of what the delegate claimed. The terminal contract catches a
hallucinated completion one phase earlier; it does not replace the check.
