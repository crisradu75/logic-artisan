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

> Read the diff with `git diff <base>...<branch>`, and a committed file with
> `git show <ref>:<path>`. Do NOT run `git checkout`, `switch`, `stash`, `branch`, or
> `worktree add`, or anything else that mutates repository state. Do NOT run
> `git checkout -- <path>`, `git restore`, or `git reset`, or edit or revert a file
> directly — the tree may hold uncommitted work in the very files you are reading.
> Do NOT run `git commit` or `git push` unless this brief asks you to: the
> orchestrator may have staged work of its own, and a commit sweeps it in.
> Two non-git resources are shared the same way. Do NOT kill, restart or clean up a
> process you did not start. Do NOT delete or regenerate a build, cache or dependency
> directory you did not create.

**This block is standard in every dispatch, not written per brief.** Every dispatch runs in the
orchestrator's own checkout, so no dispatch kind is exempt. That is the test for making something
standard rather than a per-brief field: a field whose honest content is sometimes "not applicable"
teaches readers to skim.

**Where an exception goes.** Three of these prohibitions carry an "unless this brief asks you to",
and a standard block is the wrong place to write the grant. Put it in **slot 2, with the task that
needs it** — `commit the migration once the suite is green`, `regenerate the build directory before
measuring` — so the reader finds the exception attached to the work, not buried in a block they are
told is boilerplate. A grant nowhere in slot 2 does not exist, whatever the agent infers.

**A blocked gate is a `blocked` return, not a licence.** A stale cache or a stuck watcher the agent
did not start is an ordinary obstacle, and clearing it is exactly what these two prohibitions
forbid. Say so and stop: `blocked`, naming what is in the way. Where the check genuinely needs
mutation, the scratchpad route below applies — copy, mutate the copy, and report that the result
was not verified against the live tree.

**Two different losses, and the second verb list is the one that gets left out.** The **git**
verbs above split into moving HEAD (`checkout`, `switch`, `branch`, `worktree add`) and
overwriting or recording over tracked files (`checkout -- <path>`, `restore`, `reset`,
`commit`, `push`, a direct edit or revert); `stash` does both. The two non-git prohibitions —
a process you did not start, a directory you did not create — are a third kind, and are about a
resource the orchestrator is using rather than one git can restore. A HEAD move is recoverable — the orchestrator switches back. An
overwrite of an uncommitted file is not: there is no reflog for content that was never
committed, and the agent cannot see whether the file it is about to restore held an hour of
someone's work. A real incident had a review agent run `git checkout --` over three files
carrying ~344 uncommitted insertions and report success; the work survived on timing alone.
So name both lists, not the first one because it is the one about git's own state.

**Where a check genuinely needs the code mutated** — mutation-testing a guard, reproducing a
failure — say so and give the agent the safe route: copy the file to the session scratchpad,
mutate the copy there, and report that the result was NOT verified against the live tree. The
instinct to mutate is usually a good one; it is the target that is wrong.

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
> as stated **or that you could not resolve at all**, or `(none)`. An `unresolved:` row belongs
> here: it is a gap in the defect's factual base, and reporting `(none)` while holding one hides
> exactly what the field exists to surface. Never omit the field.
>
> If this brief names a defect check but does not record the output the dispatcher got when it
> ran the check, return `blocked` and say so. An unrun check cannot tell you whether the defect
> is gone, so no evidence you could produce would satisfy `done`.

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

#### A gate that outlives your turn

Both contracts above are satisfied by a status plus evidence, and both are defeated by a
return carrying neither. A delegate that backgrounds a long gate — a multi-minute verify, a
full suite — and then ends its turn sends a return shaped exactly like a finish. Measured in
one chain: **four delegates stalled this way, and only one of the four ever returned again.**
Two of them returned a sentence saying they were standing by for a completion notification.
It could not reach them: their turn ending *was* their return.

Put it in the brief in these words:

> Run the gates this brief names in the **foreground** and report their real output. Do not
> start a command and then end your turn — your turn ending is your return, and no
> notification reaches you afterwards.
>
> If a gate cannot finish inside one foreground call, do not background it. Return `blocked`,
> name the gate, and say what you did produce.

**The rule keys on the runner, not on the duration.** The orchestrator's own backgrounding is
unchanged, because a completion notification *does* re-invoke a session. Only the dispatched
agent has a turn that ends for good.

**This rule has no detector, and saying so is part of stating it.** Nothing the orchestrator
observes distinguishes a gate run in the foreground from one backgrounded and summarised
plausibly. What catches the latter is the contract above: a `done` needs the gate's real output,
and a delegate that never saw the gate finish has none to give. So the enforcement is the evidence
requirement, and this section is the instruction that keeps an honest delegate out of the trap.

**Expect the trap to be baited.** When a long gate hits the tool's own timeout, the error text
recommends re-running in the background — the forbidden route, offered by the platform, at the
moment this brief is furthest from attention. That is the case all four recorded stalls came from.
Returning `blocked` naming the gate is the sanctioned answer to exactly that prompt.

**And one rule the orchestrator applies, because a delegate cannot enforce its own liveness:
a return carrying no status token is `blocked`, never `done`.**

The test is one question, and only one: **does the return carry a token from the closed set —
`done`, `blocked`, or `remedy-rejected`?** No token means `blocked`, whatever the prose says.
That covers a return reading as finished, and one announcing that it is waiting on something.

**Do not fold the evidence requirement into this test.** A missing evidence field is already
handled, above, by each contract's own "`done` is valid ONLY when accompanied by…" rule. Testing
for both here would misfire on the one return that is *supposed* to arrive without work evidence:
`remedy-rejected` carries no defect-check output, no test-run summary and no ticked-task count,
by design. Classifying it `blocked` would collapse the two statuses that "Why the third status
exists" keeps apart, and would send a delegate that was right back to redo it.

**Scope: dispatches under a declared status contract**, which is what slot 5 gives a dispatch
that edits code. A read-only dispatch briefed to return findings and nothing else has no token to
carry, so this rule does not reach it — an empty findings list from such an agent is a result, not
a stall.

No status is added for any of this; the set stays `done` / `blocked` / `remedy-rejected`. What
changes is who classifies a tokenless return: the orchestrator, by scanning, rather than the agent,
by asserting.

#### When the evidence cannot honestly be produced

Both contracts above ask for evidence, and both leave one move that satisfies the contract
while destroying the thing it exists for: authoring the evidence instead of recording it.
An assertion whose data does not exist — a state the real corpus does not contain, an
outcome only a credentialed live run could produce, a fixture no run has ever emitted —
presents a delegate under implementation pressure with two visible options, fail the task
or make it pass. Everything else here rewards the second: `done` wants a green summary
line, the Post-check reads a ticked-task count, and invented data produces both. Put the
third option in the brief, in these words:

> If producing the evidence this task needs would mean **authoring** the data rather than
> recording it — inventing values, hand-writing an outcome no real run produced, filling a
> fixture from what the spec imagines — that is the defect, and reporting it is the task.
> Return `blocked`, name what could not be produced and why, and list the options you can
> see. Do NOT author it.

State it rather than trusting it to be inferred: nothing else in the brief implies it, and
a delegate that stops here has to be able to point at the sentence that sanctioned
stopping. **A stop of this kind is a successful return, and the run record must show it as
one** — the same reason `remedy-rejected` exists separately from `blocked`. A ticked task
resting on invented data is worse than an unticked one, because the tick is the only signal
anything downstream reads, and the two are indistinguishable in it.

Where the unproducible state was written as a *requirement*, the defect is older than this
dispatch and belongs upstream: `review-change`'s Shape 1
(`${CLAUDE_PLUGIN_ROOT}/skills/review-change/references/checklist.md`, "Producible state")
grades a state recorded `NOT PRODUCIBLE` and written as a requirement as
a **Critical** before implementation ever starts. A delegate hitting it here means that
check did not run or did not fire — worth saying in the `blocked` return, because the fix is
to the requirement, not to the task.

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
