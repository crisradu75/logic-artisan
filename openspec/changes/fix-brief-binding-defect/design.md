## Context

Every dispatch this plugin makes is a block of prose. The delegate reads it as one thing: an
instruction. Nothing in the brief format distinguishes the sentence the orchestrator measured from
the sentence it recalled, or the sentence that must not be waived from the one the delegate is free
to disagree with. The delegate has no way to ask — it gets one prompt, works in its own context
window, and returns once, which the brief reference already states as the reason the template exists
at all (`subagent-brief.md`, "Why a template at all", line 15).

Four issues record what that flatness costs. They are usually read as four gaps: a missing pushback
rule, a missing fact check, a missing reviewer, a missing tag. They are one gap seen four times —
**a brief line's authority is not written down, so every line inherits the maximum.** The design
question the decision poses is therefore the brief format itself, and the deliverable is one contract
rather than four appended rules.

Current state, measured 2026-08-25:

```
wc -l .claude/plugins/cla/skills/spec-to-pr/references/subagent-brief.md      → 116
grep -n '^### \|^## ' .../subagent-brief.md
    → :29 "The five slots", :37 "2. Task — one sentence, one deliverable",
      :78 "5. Done when — a condition you will check, with evidence",
      :93 "What the brief cannot do"
grep -n 'adjudicat' .../review-change/references/checklist.md
    → :64 "You still adjudicate every ✗ row yourself" (the cost-offload paragraph)
grep -n '^###' .../review-change/references/checklist.md
    → :262 "### Verified claims", :297 "### Verdict integrity — no capitulation, no sycophancy"
grep -n '^## \|^Cap' .../spec-to-pr/references/revise.md
    → :5 "Cap: --pr-rounds N (default 2).", :68 "Round N (N ≥ 2)"
grep -rn 'subagent-brief' .claude/plugins/cla/
    → spec-to-pr/SKILL.md:234, lite-pr/SKILL.md:141   (two citing sites, both by slot name)
```

Two constraints bound every option below. The brief file is **synced core** — it ships verbatim to
consuming repos, so nothing repo-specific and no dev-tree path may enter it. And it is cited by slot
name from two skills, so renaming or adding a slot is a three-file edit whose cost has to be earned.

## Goals / Non-Goals

**Goals:**

- One contract that closes #96, #121, #107 and #112, expressible in a few lines of brief prose and
  legible to a delegate reading it cold.
- Change what `done` *requires*, not merely what the delegate is *permitted* to do — a compliant
  delegate is the failure mode in #96, and permission does not reach a compliant delegate.
- Make every factual claim, in a brief or in a review table, carry its source and whether anyone has
  actually run that source.
- Price the adjudication widening and adopt a bounded form of it, rather than leaving it open.

**Non-Goals:**

- **Round counts stay as they are.** `--pr-rounds` defaults to 2 and `--review-rounds` to 1; neither
  moves here, and nothing in this design makes a second round unconditional. Whether Revise round 2
  becomes the default is a separate decision item with its own cost argument, and folding it in here
  would smuggle a per-run cost through a design about brief format.
- **No new agent type, no new script, no new hook.** Every mechanism below is prose in a file that is
  already read at the moment it binds.
- **No change to the size gate, the agent-selection table, or the cost-offload default itself.** The
  offload stays; what changes is what a row it returns is worth.
- **Not the review checklist's claim-shape enumeration.** That is a separate item; this change touches
  the checklist only at the cost-offload paragraph and the `### Verified claims` heading.

## Decisions

### The contract: three authority levels and one provenance tag

Every line a brief contains, and every row a report contains, is exactly one of:

| Level | What it means | Who may overturn it, and how |
|---|---|---|
| **Binding** | The defect. The observable wrong behaviour and why it is wrong. | Nobody in the dispatch. A delegate may not decide the defect is acceptable and stop. |
| **Rejectable** | The candidate remedy. The orchestrator's proposed fix. | The delegate, with reasons — and doing so is a *successful* return. |
| **Checkable** | Every factual sub-claim: a field list, a signature, a line number, a count. | Anyone, by re-running the source the claim names. Each carries a **provenance tag**. |

And one rule that binds them together: **the terminal contract asks for evidence against the binding
line only.** That single sentence is what makes the contract more than a taxonomy — it is the reason
a compliant delegate cannot ship #96's regression, because "I applied the remedy you named" no longer
satisfies `done`.

The four issues fall out of the three levels: #96 is the binding/rejectable split, #121 is the
checkable level, #107 is what happens when the rejectable level has nobody to exercise it, and #112
is the provenance tag on the checkable level.

**Rejected alternative — four appended rules.** Add a "the delegate may push back" sentence to slot 2,
a "check the facts you were given" sentence beside it, an "orchestrator fixes get reviewed too" rule
in `revise.md`, and a provenance note in `checklist.md`. Rejected on three grounds. First, an
appended permission does not change what `done` requires, so it does not reach the compliant delegate
that #96 describes — the delegate reads a permission next to an instruction with a deliverable
attached, and the instruction wins. Second, four rules cover four filed instances and leave the fifth
uncovered; a stated authority level covers a shape nobody has filed yet. Third, four prose blocks in
three files go stale independently, which is the exact failure the brief reference was created to fix
(`subagent-brief.md` lines 9–11: one dispatch site had three carefully-reasoned rules and another had
a single sentence).

### Decision 1 — Slot 2 gains a fix-brief form; the brief keeps five slots

A dispatch whose purpose is to remedy a defect writes slot 2 as three named fields:

```
**Defect (binding).** <what is true now, and why that is wrong>
**Facts this defect rests on (checkable).**
  - <claim> — source: <path:line | command> — [agent-reported | orchestrator-verified]
**Candidate remedy (rejectable).** <the fix the orchestrator proposes, and why>
```

A build-this dispatch keeps the existing one-sentence form. Slot 2's heading and the file's "five
slots" framing are unchanged, so the two citing sites (`spec-to-pr/SKILL.md:234`,
`lite-pr/SKILL.md:141`) stay correct without edits.

**Rejected alternative — a sixth slot.** Splitting `Defect` and `Candidate remedy` into slots 2 and 3
would renumber every slot after them and invalidate both citing sites, which spell the slot list out
by name. It would also force a defect field onto dispatches that have no defect — a doc-sweep, a
fact-gather, an implement-these-tasks brief — where the honest content is "n/a", and an "n/a" field
teaches every reader to skim the section. Two forms of one slot keeps the cost inside the one dispatch
kind that has a defect.

### Decision 2 — The terminal contract asks for defect-gone evidence

Slot 5's existing default asks for the test-run summary line and the ticked-task count. Those stay:
they are the evidence that the *work* happened. What is added is the evidence that the *defect* is
gone, and the explicit statement that remedy-application is not it.

A fix brief's `Done when` also names the **defect check** — the command or read that exhibits the
defect today — which the orchestrator must supply, because it is the orchestrator that observed the
defect. A fix brief that cannot name a defect check is a brief whose defect has not been grounded, and
that is a defect in the brief rather than a case to exempt.

The third status, `remedy-rejected`, exists because `blocked` and a reasoned rejection call for
opposite next moves: `blocked` means the delegate could not proceed, so the orchestrator resolves the
blocker and re-dispatches; `remedy-rejected` means the delegate did the understanding work and found
the remedy wrong, so the orchestrator must re-decide the remedy — which is Decision 3's subject. Cost:
one word in a contract line, zero per-run cost.

**Rejected alternative — reuse `blocked` for a rejection.** It collapses the two next moves into one
and, worse, makes a correct rejection read as a delegate failure in the run ledger, which is precisely
the incentive that keeps a delegate compliant.

### Decision 3 — A wrong factual sub-claim does not void a real defect

The delegate's first action on a fix brief is to re-resolve every `Facts this defect rests on` row
against its named source, resolving each to verbatim evidence or an explicit NOT-FOUND — the same
grounding contract the review checklist already binds reviewers to (`checklist.md` line 68). Three
outcomes:

1. Every row holds → proceed.
2. A row is wrong **and** the defect does not survive its correction → return `remedy-rejected` with
   the corrected row. Do not implement.
3. A row is wrong **but** the defect survives → correct the row, proceed, and report the correction.

Outcome 3 is #121 exactly: four asserted fields, three real, defect still real. The correction is
returned in a required field, `Fact corrections:`, which prints `(none)` when empty rather than being
omitted — an omitted field and "nobody looked" are indistinguishable, which is the same reasoning the
report format already applies to its own empty sections.

**Rejected alternative — check sub-claims only when something looks off.** That is the status quo, and
#121 is what the status quo produces: nothing was noticed because nothing asked. Cost of the rule is
two to four greps inside the delegate's own context — claims the orchestrator has already read once to
write the brief — and it never enters the orchestrator's context at all.

### Decision 4 — An orchestrator-specified remedy is reviewed as a decision

Two paths, because the plugin has two places a fix gets applied.

**(a) Delegated fix.** The `Candidate remedy` field is rejectable and a rejection is a success return.
That *is* the review, and it costs nothing extra.

**(b) Orchestrator-applied fix** — below the delegation trigger in Revise, or in the Review phase's
artifact-fix loop where there is no delegate at all. Here nobody can reject anything, so the control
attaches to the re-verification the orchestrator already performs: Review's lightweight "did the edits
land?" re-validation, and Revise's INT-CAP re-read of the corrected code. For a remedy the orchestrator
specified, that re-verification additionally reads the change's `design.md` rejected-alternatives /
explicitly-rejected-decisions section and confirms the applied remedy does not reintroduce one. This
is the named, sourced form of what #107 records: the Critical reintroduced a bias the change's own
`design.md` had explicitly rejected, so `design.md` is the document that would have caught it.

The remedy is additionally **marked** — `remedy: orchestrator-specified` on the round's finding row —
so the next reader knows this hunk had no independent author. Where a later round runs, that round's
dispatch is told which hunks carry the mark and to check each against the same rejected-alternatives
list. Where no later round runs, the mark surfaces in the terminal report so a human sees the list.

**Priced, and stated plainly: an orchestrator-specified remedy does NOT force an extra round.** The
stronger option — every orchestrator-specified remedy triggers one more review round — would buy an
independent reader at the price of a round on a large fraction of runs, and round-count economics are
a separate decision item that recommends against moving defaults on the evidence available. So the
control here is in-round: one extra read of one section of `design.md`, on rounds that actually
contain an orchestrator-specified remedy, plus a marker line. That is deliberately weaker than an
independent reader, and the design says so rather than implying parity.

**Rejected alternative — a dedicated reviewer agent for orchestrator-directed fixes.** It doubles a
fan-out to buy a focus question. Revise round N ≥ 2 already dispatches over exactly the previous fix
commit's diff (`revise.md` line 68), so the reviewer was never missing; what was missing was anything
telling that reviewer which hunks had nobody to argue with.

### Decision 5 — Provenance is a column on the row, and the adjudication rule widens, bounded

**The tag.** Two values, `agent-reported` and `orchestrator-verified`, on the row itself rather than
in a note about the dispatch. Notes about a dispatch do not survive the row being copied; the row is
what travels. Three rules:

- Every row a delegate returns arrives `agent-reported`. The orchestrator may not re-label a row
  without re-running that row's own resolving command or read. Re-running it is what "verified" means.
- The tag travels wherever the row goes — into the context brief, into `### Verified claims`, and into
  any finding derived from the row, which inherits the tag until the row is re-measured.
- `### Verified claims` may not carry an untagged row. That heading is where the distinction currently
  disappears: a haiku-reported row and an orchestrator-run row print identically under it today, which
  is #112's mechanism.

**The widening.** Current rule, `checklist.md` line 64: *"You still adjudicate every ✗ row yourself."*
New rule:

> Adjudicate every ✗ row yourself, as now, **and** re-measure — re-run the row's own resolving command
> or read — every row, ✓ or ✗, that a Critical or Important finding depends on. A row that supports
> only a Suggestion, or supports no finding, stays `agent-reported` and is reported as such.

**Why bounded there.** #112's failure is a *load-bearing* row that was wrong. A ✓ row nothing rests on
being wrong costs nothing; a ✓ row a Critical rests on being wrong costs a phantom Critical, a fix
round, and a "fix" commit against a defect that was never there. Severity is exactly the line where the
cost of a wrong row starts to exceed the cost of re-running one grep.

**The price, honestly.** The re-measurement set is bounded by (Critical + Important findings) × (rows
per finding), not by row count — a review that finds nothing pays nothing, and a review that finds a
lot pays in proportion to what it found. The offload only applies to **large** changes, where the
context brief carries many more rows than the report carries Critical/Important findings, and a finding
typically rests on one or two rows; each re-measurement is one grep or one file read in the
orchestrator's own context. So the widening is affordable for a structural reason, not a measured one,
and this design does not claim a per-review number it has not run. To make the next pass able to price
it for real, the run record gains two counts — rows re-measured, and rows whose re-measurement
disagreed with the delegate — so a retro can compute the actual cost and the actual catch rate instead
of re-arguing this paragraph.

**Rejected alternative — re-measure every row.** It deletes the cost offload. The offload exists
because a large change's mechanical claim-checking is the bulk of the review's raw material; re-running
all of it in the orchestrator's context restores exactly the context cost the dispatch was created to
avoid, and buys verification of rows that no finding, and therefore no decision, depends on.

**Rejected alternative — keep "adjudicate every ✗" unchanged and rely on the tag alone.** A tag with no
obligation attached is a label. #112's rows were wrong and load-bearing; labelling them
`agent-reported` and proceeding would have shipped the same findings with an accurate adjective on
them.

## Pinned implementation parameters

Nothing below is decided during implementation.

**Fix-brief slot-2 field names** (verbatim, including the parenthetical authority level):

- `**Defect (binding).**`
- `**Facts this defect rests on (checkable).**` — rows as
  `- <claim> — source: <path:line | command> — [agent-reported | orchestrator-verified]`
- `**Candidate remedy (rejectable).**`

**Terminal-contract wording for a fix brief** (verbatim; replaces the slot-5 default block for fix
dispatches, and is quoted as a block in `subagent-brief.md` §5):

> End with an explicit `done`, `blocked`, or `remedy-rejected` status.
>
> `done` is valid ONLY when accompanied by evidence that the DEFECT is gone: the defect check named in
> this brief, re-run, with its output showing the defect absent — plus the test-run summary line and
> the ticked-task count (`- [x]` count vs total). **Evidence that the candidate remedy was applied is
> NOT evidence that the defect is gone.** A return claiming `done` without defect-gone evidence is
> treated as **not done**.
>
> `remedy-rejected` is a SUCCESSFUL return, not a failure: use it when the candidate remedy is wrong,
> or when a fact this defect rests on is wrong and the defect does not survive its correction. Give
> the reason and, where you can see one, a better remedy.
>
> Report `Fact corrections:` in every return — one line per fact row that did not resolve as stated,
> or `(none)`. Never omit the field.

**Required return fields** (a fix brief's return, in this order): `status`, defect-check output,
test-run summary line, ticked-task count, `Fact corrections:`.

**Provenance tag values** (exactly two, lowercase, hyphenated): `agent-reported`,
`orchestrator-verified`.

**Orchestrator-specified-remedy marker** (verbatim, on the round's finding row):
`remedy: orchestrator-specified`.

**The rejected-alternatives check's source document:** the change's own `design.md`, its
rejected-alternatives / explicitly-rejected-decisions content. Not the proposal, not the tasks file.

**Adjudication rule's exact scope:** every ✗ row (unchanged), plus every row — ✓ or ✗ — that a
**Critical or Important** finding depends on. Suggestion-supporting rows and finding-free rows are
explicitly out of scope and stay `agent-reported`.

**Run-record counts added:** `rows_remeasured` and `rows_remeasured_disagreed`.

## Risks / Trade-offs

- **Two forms of slot 2 is a branch a reader can take wrongly** → the fix-brief form is triggered by a
  stated, checkable condition ("this dispatch's purpose is to remedy a defect"), and the build-this
  form remains the unmarked default, so the branch only has to be recognised in the direction that
  adds structure.
- **`remedy-rejected` can become an escape hatch** — a delegate that finds the work hard rejects the
  remedy instead → the status requires a *reason*, and a rejection without a reason resolving against
  the brief's own defect or fact rows is not a rejection. The orchestrator's next move on a rejection
  is to re-decide the remedy, which surfaces a bad rejection immediately.
- **The in-round `design.md` check is weaker than an independent reader** → stated as such in
  Decision 4 rather than implied to be equivalent, and the marker carries into the terminal report so
  the weakness is visible per run rather than silent.
- **The widening's cost is argued structurally, not measured** → this is why the two run-record counts
  are pinned. The claim made here is a bound on the shape of the cost, not a number; the number comes
  from the ledger.
- **`Fact corrections: (none)` invites a reflexive `(none)`** → the same risk every mandatory
  "(none)" field carries. It is accepted for the same reason those were: an omitted field and a
  checked-and-clean field are indistinguishable, and a reflexive `(none)` at least leaves a row the
  orchestrator's own re-measurement can contradict.
- **Synced-core portability** → every added line must be free of repo tokens, dev-tree paths and
  absolute developer paths, since these four files ship verbatim. The plugin's existing conformance
  scan over synced core is the check.
