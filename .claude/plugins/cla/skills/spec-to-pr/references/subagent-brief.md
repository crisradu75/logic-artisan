# The sub-agent brief: five slots

The shared shape for every `Agent` dispatch in this plugin. Owned here because
`spec-to-pr` has the most dispatch sites, but **not** specific to it — `/cla:lite-pr`
cites this file rather than restating it, the same way
`review-change/references/checklist.md` is read by more than its own skill. Any skill
that dispatches an agent should cite it; the list of citing skills is not closed.

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

That one-sentence form is the default, and it is the right one for a **build-this**
dispatch. A dispatch whose purpose is to **remedy a defect** writes this slot
differently, because a defect and the fix proposed for it do not carry the same
authority and must not arrive as one instruction.

#### The fix-brief form

```
**Defect (binding).** <what is true now, and why that is wrong>
**Facts this defect rests on (checkable).**
  - <claim> — source: <path:line | command> — [agent-reported | orchestrator-verified]
**Candidate remedy (rejectable).** <the fix you propose, and why>
```

Three levels, and the difference between them is who may overturn each:

| Level | The field | Who may overturn it, and how |
|---|---|---|
| **Binding** | the defect | Nobody in this dispatch. You may not decide the defect is acceptable and stop. |
| **Rejectable** | the candidate remedy | You, with reasons — and doing so is a *successful* return, not a failure. |
| **Checkable** | each fact row | Anyone, by re-running the source the row names. |

**The provenance tag says whether anyone has actually run the source.**
`orchestrator-verified` means the party writing this brief resolved the claim against
that source. `agent-reported` means it was relayed from some earlier report and nobody
re-ran it. Without the tag a row's source says only where the claim *could* be checked,
so the rows most worth re-running look exactly like the rows already settled. The tag is
a field on a brief's fact row and nothing else — it does not travel into a review
report's claim table.

**Re-resolving the fact rows is your FIRST action, before any edit.** Each row resolves
to **verbatim evidence** (the actual line, the real signature, trimmed) or to an explicit
**NOT-FOUND** (`not found: <what you searched, where>`). "Looks right" and "the brief says
so" are not evidence. Where a row genuinely cannot be resolved either way, say
`unresolved: <why>` rather than guessing — an honest gap can be adjudicated, a fabricated
verdict cannot.

Then, by what you found:

1. **Every row holds** → the defect's factual base is sound. Now judge the *remedy*, which
   is a separate question — see below. Rows holding does not mean the proposed fix is right.
2. **A row is wrong AND the defect does not survive its correction** → return
   `remedy-rejected` with the corrected row. Do not implement. The defect itself was the
   casualty; there is nothing left to remedy.
3. **A row is wrong BUT the defect survives its correction** → correct the row, and treat it
   as case 1: the defect stands, so judge the remedy. Report the correction either way. A
   wrong sub-claim does not void a real defect.
4. **A row cannot be resolved either way** → say `unresolved: <why>` for that row and judge
   the defect on the rows that did resolve. An unresolved row is not a pass and not a
   failure; guessing it either way is worse than naming the gap.

**Then, in every case where the defect stands, judge the candidate remedy — this is the
step the whole form exists for.** The remedy is *rejectable*, and checking the facts is not
the same as agreeing with the fix. If the proposed remedy is wrong — it does not remove the
defect, it removes a symptom, it reintroduces something worse, it is aimed at the wrong
layer — return `remedy-rejected` with your reason and, where you can see one, a better
remedy. **Do not implement a remedy you believe is wrong merely because the facts checked
out.** A compliant delegate that implements a wrong remedy and returns genuine work evidence
is the exact failure this contract was written to stop.

### 3. Do not touch — the files another agent owns, named

Name the paths, not the principle. Include any file the orchestrator itself is holding
open, and any file a sibling agent in the same fan-out owns. Also name the *decisions*
that are not the agent's to make — "do not change the public signature", "do not add a
dependency" — since scope alone does not constrain those.

**Say "no repository-state changes", not "no edits".** A read-only agent reads "make no
edits" as being about file contents and will still run `git checkout`, `switch`, `stash`,
`branch`, or `worktree add` if that looks like the easiest way to see the code. Those are
shared, process-wide state: git's HEAD is per-clone, so one agent switching branches moves
the ground under the orchestrator and every sibling in the same fan-out — and it leaves no
diff to notice it by. Nor does a well-behaved agent undo it: it *restores* to the branch it
assumes was the baseline, usually `main` rather than the branch the session was on. Spell
out the forbidden verbs, and for a diff review name the read-only way to get it:

> Read the diff with `git diff <base>...<branch>`. Do NOT run `git checkout`, `switch`,
> `stash`, `branch`, or `worktree add`, or anything else that mutates repository state.

Where the agent is read-only, prefer the mechanical form: per "What the brief cannot do"
below, a `tools:` allowlist or `permissionMode: plan` makes these commands impossible
rather than merely forbidden.

### 4. Report — what to write, and where

An agent that returns only to the conversation has produced nothing that survives its
own termination. Where the output is durable, name the path. Where it is a finding
list, name the shape you will consume.

Keep briefs trimmed: pass the sections the task actually references, not the whole
document. For a diff review, describe the diff by **file + symbol + focus question**
and let the agent read the hunks itself rather than pasting raw diff text inline.

### 5. Done when — a condition you will check, with evidence

Not "when it looks right". The strongest form for a **non-fix** dispatch — anything that
edits code without being aimed at a specific defect:

> End with an explicit `done` or `blocked` status. `done` is valid ONLY when
> accompanied by hard evidence — the test-run summary line, and the ticked-task count
> (`- [x]` count vs total). A return claiming done without that evidence is treated as
> **not done**.

The evidence requirement is doing the real work. A status field alone is the agent's
opinion of its own output; a summary line and a count are checkable facts.

#### The fix-brief terminal contract

A dispatch using slot 2's fix-brief form uses this instead. The difference is what the
evidence is *of*: the block above proves the work happened, this one proves the defect is
gone.

> End with an explicit `done`, `blocked`, or `remedy-rejected` status.
>
> `done` is valid ONLY when accompanied by evidence that the DEFECT is gone: the defect
> check named in this brief, re-run, with its output showing the defect absent — plus the
> test-run summary line and the ticked-task count (`- [x]` count vs total). **Evidence
> that the candidate remedy was applied is NOT evidence that the defect is gone.** A
> return claiming `done` without defect-gone evidence is treated as **not done**.
>
> `remedy-rejected` is a SUCCESSFUL return, not a failure: use it when the candidate
> remedy is wrong, or when a fact this defect rests on is wrong and the defect does not
> survive its correction. Give the reason and, where you can see one, a better remedy.
>
> Report `Fact corrections:` in every return — one line per fact row that did not resolve
> as stated, or `(none)`. Never omit the field.

**Return these fields, in this order:** `status`, defect-check output, test-run summary
line, ticked-task count, `Fact corrections:`. A fixed order is what lets the orchestrator
notice a *missing* field instead of scanning prose for it.

**A dispatch briefed over more than one finding returns a per-finding outcome list** as
well as the overall status — one row per finding the brief enumerated, each carrying that
finding's own outcome and, for a rejection, its reason. Fourteen findings remedied and one
remedy rejected is an ordinary result and has to be sayable; a single status would either
discard the fourteen or hide the one. The overall status is `remedy-rejected` when any row
is. A single-finding dispatch returns a one-row list under the same contract.

**Why the third status exists.** `blocked` and a reasoned rejection call for opposite next
moves. `blocked` means you could not proceed, so the orchestrator resolves the blocker and
re-dispatches. `remedy-rejected` means you did the understanding work and found the
proposed fix wrong, so the orchestrator must re-decide the remedy. Collapsing them would
also make being right look like a delegate failure in the run record, which is precisely
the incentive that keeps a delegate compliant with a bad remedy.

**Naming the defect check is the orchestrator's job, not yours** — it observed the defect,
so it supplies the command or read that exhibits it. A fix brief that cannot name one is a
brief whose defect has not been grounded. That is a defect in the brief, to be fixed before
dispatch; it is not a dispatch exempt from this contract.

**And the orchestrator must have RUN it and seen it exhibit the defect, before dispatching.**
A check written from memory — a grep whose pattern never matched, a command that reports
nothing on a healthy *and* a broken tree — returns empty output, the delegate truthfully
reports the defect absent, and `done` passes with the defect fully intact. This is the same
"confirm it fails first" discipline the plugin already applies to a mutation test, and for
the same reason: a check that has never been seen to fail proves nothing when it passes.
So the brief states the check **together with the output it produced when the orchestrator
ran it**, which is what the delegate's re-run is compared against. A check nobody has run is
in the same position as a defect nobody grounded — fix it before dispatch.

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
