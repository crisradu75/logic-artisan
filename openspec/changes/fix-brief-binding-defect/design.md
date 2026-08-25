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
wc -l .claude/plugins/cla/skills/spec-to-pr/references/subagent-brief.md      → 115
grep -n '^### \|^## ' .../subagent-brief.md
    → :29 "The five slots", :37 "2. Task — one sentence, one deliverable",
      :78 "5. Done when — a condition you will check, with evidence",
      :93 "What the brief cannot do"
grep -n '^## \|^Cap' .../spec-to-pr/references/revise.md
    → :5 "Cap: `--pr-rounds N` (default `2`).", :68 "Round N (N ≥ 2)"
grep -n 'Applied\|Deferred-Known-Issue\|Exit gate' .../spec-to-pr/references/revise.md
    → :82 "Applied", :83 "Deferred-Known-Issue", :134 "Exit gate"  (two buckets, no third)
grep -rn 'explicit `done`|`done`/`blocked`' .claude/plugins/cla/skills/
    → subagent-brief.md:83, SKILL.md:239, SKILL.md:337, revise.md:97,
      multi-spec/references/authoring-brief.md:46
      (five sites; TWO are not fix dispatches — see the classification below)
grep -rn 'subagent-brief' .claude/plugins/cla/
    → spec-to-pr/SKILL.md:234, lite-pr/SKILL.md:141   (two citing sites, both by slot name)
```

**The census's two literals do not find every site this change binds, and a second census is
therefore required.** The grep above finds sites that *restate a terminal contract*. Decision 4
binds a different population — sites where an **orchestrator applies a fix to an OpenSpec change's
own artifacts with no delegate present** — and those say nothing about `done`/`blocked`, so the
first census cannot see them. Measured 2026-08-25:

```
grep -rn 'finding via direct\|finding as a direct\|deferred Critical/Important findings' \
    .claude/plugins/cla/skills/
    → spec-to-pr/SKILL.md:215            (Review's fix loop)
      multi-spec/references/review-gate.md:55  (Step 7, per change, design.md present)
      multi-lite/references/candidate-loop.md:22,23 (enforcement round over lite-pr candidates)
```

The three sites word the same action three different ways — "via direct Edit/Write", "as a direct
`Edit`/`Write` fix", "deferred Critical/Important findings" — which is why one literal does not find
them and why the pattern above is an alternation. That is also the general lesson: a census whose
pattern was written from one site's phrasing finds one site.

`multi-spec/references/review-gate.md:55` is squarely inside Decision 4(b): it applies findings as
direct `Edit`/`Write` to a change's artifacts, the change has a `design.md`, and there is no
delegate. It is in scope and this change edits it. `multi-lite/references/candidate-loop.md:23`
enforces `lite-pr`'s deferred findings, and `lite-pr` has no change directory by construction, so
it is exempt under Decision 4's stated condition rather than in breach of it.

Two constraints bound every option below. The brief file is **synced core** — it ships verbatim to
consuming repos, so nothing repo-specific and no dev-tree path may enter it. And it is cited by slot
name from two skills, so renaming or adding a slot is a three-file edit whose cost has to be earned.

## Goals / Non-Goals

**Goals:**

- One contract that closes #96, #121 and #107, expressible in a few lines of brief prose and
  legible to a delegate reading it cold.
- Change what `done` *requires*, not merely what the delegate is *permitted* to do — a compliant
  delegate is the failure mode in #96, and permission does not reach a compliant delegate.
- Make every factual claim **in a brief** carry its source and whether anyone has actually run that
  source.
- Land each new rule at every site that restates it, so no dispatch briefs against the old contract.

**Non-Goals:**

- **Round counts stay as they are.** `--pr-rounds` defaults to 2 and `--review-rounds` to 1; neither
  moves here, and nothing in this design makes a second round unconditional. Whether Revise round 2
  becomes the default is a separate decision item with its own cost argument, and folding it in here
  would smuggle a per-run cost through a design about brief format.
- **No new agent type, no new script, no new hook.** Every mechanism below is prose in a file that is
  already read at the moment it binds.
- **No change to the size gate, the agent-selection table, or the cost-offload default.** This change
  does not touch `review-change/references/checklist.md` at all.
- **Not fact-row provenance in a review report, and not the adjudication widening.** Issue #112 was
  proposed alongside these three and cut at review. It is about a *report's* fact table rather than a
  brief — no dispatch, no delegate, no authority level — and carrying it pulled in a second skill, a
  run-record edit whose consumer (`spec_to_pr_aggregate.py`) was never in scope, and a rule binding
  the standalone `/cla:review-change` path, which has no run record to carry a count in. Tracked as
  `fact-row-provenance`.
- **Not the review checklist's claim-shape enumeration.** That is a separate item too.

## Decisions

### The contract: three authority levels and one provenance tag

Every line a **brief** contains is exactly one of. (A review *report*'s rows are out of scope here
— that widening is `fact-row-provenance`; see Non-Goals.)

| Level | What it means | Who may overturn it, and how |
|---|---|---|
| **Binding** | The defect. The observable wrong behaviour and why it is wrong. | Nobody in the dispatch. A delegate may not decide the defect is acceptable and stop. |
| **Rejectable** | The candidate remedy. The orchestrator's proposed fix. | The delegate, with reasons — and doing so is a *successful* return. |
| **Checkable** | Every factual sub-claim: a field list, a signature, a line number, a count. | Anyone, by re-running the source the claim names. Each carries a **provenance tag**. |

And one rule that binds them together: **the terminal contract asks for evidence against the binding
line only.** That single sentence is what makes the contract more than a taxonomy — it is the reason
a compliant delegate cannot ship #96's regression, because "I applied the remedy you named" no longer
satisfies `done`.

The three issues fall out of the three levels: #96 is the binding/rejectable split, #121 is the
checkable level, and #107 is what happens when the rejectable level has nobody to exercise it. (A
fourth, #112, was proposed alongside them and cut at review — it is the provenance tag on a *review
report's* rows rather than on a brief's, and the three levels do not reach it. See Non-Goals.)

**The unification is honest for two of the three, and stated as such rather than claimed for all.**
#96 and #121 are brief-format issues: the binding/rejectable split and the checkable level are both
fields in slot 2, and both change what `done` requires. #107 is not. Its closure (Decision 4(b))
attaches a cross-check to the orchestrator's own re-verification *precisely because* the rejectable
level has nobody to exercise it on that path — the authority contract diagnoses #107 but does not
close it, and the mechanism that does close it carries no authority level. The contract is still the
right frame, because it is what makes the gap on that path nameable; but "one contract closes three
issues" would be overclaiming, and this design says two-and-a-diagnosis instead.

**Rejected alternative — three appended rules.** Add a "the delegate may push back" sentence to slot 2,
a "check the facts you were given" sentence beside it, and an "orchestrator fixes get reviewed too"
rule in `revise.md`. Rejected on three grounds. First, an
appended permission does not change what `done` requires, so it does not reach the compliant delegate
that #96 describes — the delegate reads a permission next to an instruction with a deliverable
attached, and the instruction wins. Second, three rules cover exactly the three filed instances; a
stated authority level covers a shape nobody has filed yet. (An earlier draft argued this ground by
counting #112 as the uncovered fourth. That does not hold: #112 is cut from this change too, so it
is uncovered either way and refutes nothing. The ground survives only in its general form — that a
rule enumerating instances stops at the instances enumerated — which is weaker than the count made
it look.) Third, three prose blocks in
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

**Outcome 2 and a rejected remedy are the same status with opposite next moves, and the difference
is what the rejection cites.** Decision 5 makes a rejection discharge the round's attempt at a
finding *without closing the finding*, because the normal case is "your remedy is wrong, re-decide
it" and the finding is still real. Outcome 2 is not that case: the delegate has shown the defect
itself does not exist. Left under Decision 5's rule, a finding proven false could never close — it
would be re-attempted with a re-decided remedy for a defect that is not there, every round, until
the cap ran out.

So the orchestrator's move on a rejection is chosen by reading the rejection's reason, and the two
branches are named:

- **The rejection cites the remedy** (the defect stands, the proposed fix is wrong) → re-decide the
  remedy; the finding stays open, per Decision 5.
- **The rejection cites a disproved defect** (outcome 2 — a fact row was wrong and the defect does
  not survive its correction) → **close the finding**, with the corrected row as the evidence of
  closure. Record it as closed-by-disproof rather than as applied, so the ledger does not claim a
  fix that never happened.

A fourth terminal status was considered and rejected: the two cases are already distinguishable from
the reason the delegate must supply anyway, and a fourth status would need a fourth arm on every
receiving branch this change is adding — the triage, the exit gate, the terminal report, and the
delegate-return receiver — for information the third status already carries.

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

**Two scope conditions, because the naive form of this check does not hold.** First, on the Review
path the remedy is frequently *an edit to that very `design.md`* — Review's fix loop applies findings
to the change's own artifacts. Reading the working tree would then have the remedy adjudicate itself.
So the check reads the rejected-alternatives content **as it stood at the start of the fix round**,
captured before any of that round's edits, and the design says so rather than leaving an implementer
to notice. Second, the check needs a rejected-alternatives document to exist, and a skill that
applies orchestrator fixes without operating on an OpenSpec change has none — the lightweight PR
workflow has no change directory by construction. The check is therefore conditioned on a change
directory being present, not asserted universally; a skill with no such document is out of its scope
rather than in breach of it.

**Why a round-start snapshot and not `git show HEAD:<path>`.** An earlier draft pinned the git
command, and it does not work on the path it was written for. The phase order is
Precheck → Propose → **Review** → Implement → Test → **Ship**, so on a freshly-proposed change the
change directory is still untracked when Review's fix loop runs, and
`git show HEAD:openspec/changes/<name>/design.md` fails with a path-does-not-exist error on the
common case. The requirement was never "the committed version" — it is "a version this remedy has
not touched", and a snapshot taken at round start satisfies that on both paths with no dependence on
whether the file is tracked yet.

**A hit is a Critical finding on the fix, not a note.** Where the check finds the applied remedy
reintroduces something the design rejected, that is a Critical finding against the remedy itself.
The remedy is withdrawn or re-specified; it does not stand on having resolved the original finding,
because resolving one finding by reintroducing a rejected decision is exactly the failure the check
exists to catch and is indistinguishable from success on the original finding's own evidence. Where
the rejection is what is now judged wrong, the `design.md` is amended explicitly — "the fix brief
said so" is not an amendment. Stating the response matters as much as stating the check: a check
whose only defined outcome is a note gets read as a note.

The remedy is additionally **marked** — `remedy: orchestrator-specified` — so the next reader knows
this hunk had no independent author. Where a later round runs, that round's dispatch is told which
hunks carry the mark and to check each against the same rejected-alternatives content. Where no
later round runs, the mark surfaces in the terminal report so a human sees the list.

**Where the mark actually lives, and where it carries signal.** Two corrections to the naive form.
First, Revise's round-1 findings are a schema'd object (`revise.md`'s fan-out returns
`{severity, file, line, summary}`); there is no "finding row" table anywhere in Revise for a marker
to sit on. The mark is therefore a field the orchestrator carries **on its own triage record** for
the finding — the same record that already holds Applied / Deferred-Known-Issue — and it is that
record the terminal report reads. Second, on the **Review** path there is no delegate at all, so
*every* remedy is orchestrator-specified and a per-remedy mark there discriminates nothing. The mark
is therefore load-bearing on the **Revise** path, where delegated and orchestrator-applied fixes mix
in one round; on the Review path the fact is a property of the phase and is stated once per run
rather than once per finding. The check itself still runs on both paths — it is the *marking* that
is Revise-specific, not the adjudication.

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

### Decision 5 — `remedy-rejected` needs a receiving branch, not just a name

Adding a third terminal status is half a change. `revise.md` triages every Critical and Important
finding into **Applied** or **Deferred-Known-Issue**, and its exit gate counts anything in neither
bucket as untriaged residue that turns the round `warn`. A `remedy-rejected` return fits neither: the
delegate did the work, understood the defect, and reported that the proposed fix is wrong. Landing
the status without the branch converts a *successful* return into a warned round, which is precisely
the ledger distortion Decision 2 rejected `blocked` to avoid.

So the triage gains an explicit third outcome, with one asymmetry that has to be stated rather than
inferred: a rejection discharges **the round's attempt** at the finding, not the finding. The
orchestrator re-decides the remedy; the finding stays open and is re-attempted. The round cap does
not move — a rejection is information, and charging a round for it would teach the orchestrator to
avoid asking.

**"Triaged" and "may exit the loop" are two different predicates, and conflating them is how the
third status silently ships a Critical.** `revise.md`'s exit gate reads: *count un-triaged Critical
and Important findings; if 0 untriaged → status `ok`, exit loop.* Applied and Deferred-Known-Issue
are both triaged **and** both closed, so on the two-bucket triage the two predicates coincided and
one counter served for both. A rejected finding is the first that is triaged and **open**. Told only
"stop counting it as residue", the gate sees zero untriaged, returns `ok`, and exits — with a live
Critical on the change and Handoff's all-✓ next-steps then printing `gh pr merge`. Nothing warns,
because every phase really did report `ok`.

The gate therefore splits into two counts, and both must be zero to exit clean:

- **Untriaged** — Critical/Important findings in no bucket at all. Unchanged; a rejection is not one
  of these.
- **Open** — findings triaged but not closed. A rejected-and-re-attemptable finding is exactly this.
  Non-zero open with budget remaining → **re-loop** (this is the branch the naive rule made
  unreachable). Non-zero open at cap exhaustion → status `warn`, and the open findings are captured
  as residue for the report, not dropped.

A finding closed by disproof (Decision 3's outcome 2) is closed and counts in neither.

**And a triage outcome with no bucket in the terminal report is a triage outcome nobody reads.**
Handoff's report has exactly two deferred buckets: *Deferred Known Issues* (Revise's
Deferred-Known-Issue, each with rationale) and *Deferred to TODO.md* (Suggestions plus
cap-exhausted untriaged residue). A rejected-but-open finding is neither — it is not a conscious
deferral and it is not a Suggestion. It needs its own named bucket in the report, for the same
reason the report already splits its "not applied" list by cause rather than pooling it: an
undifferentiated list is one nobody can act on. Landing the status without the bucket repeats, one
layer up, the exact half-a-change this decision exists to prevent.

**Rejected alternative — let a rejection close the finding.** It makes rejection the cheapest exit
from any hard finding, which is the escape hatch the Risks section already names. A rejection that
closes nothing costs the orchestrator one decision and cannot be gamed.

**Rejected alternative — spend a round on a rejection.** A delegate that rejects a remedy has done
*more* work than one that applies it, and the round budget exists to bound fix attempts, not
understanding. Charging for it makes the contract more expensive exactly where it is working.

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
test-run summary line, ticked-task count, `Fact corrections:`. The order is part of the pin, not a
presentation preference — a fixed order is what lets the orchestrator check for a missing field
rather than scanning prose for it.

**A set-level dispatch returns one status PLUS a per-finding outcome list.** Revise's fix-delegate
fires past the sized trigger (`> ~15 subtasks-equivalent OR > ~8 files`) and is dispatched **once
over a whole fix-set**, while every branch receiving its result — the triage, the exit gate, the
report — is **per finding**. A single `status` cannot express the ordinary case of fourteen findings
applied and one remedy rejected, and forcing it to would either discard the fourteen or bury the
one. So a fix-set dispatch returns:

- one overall `status` for the dispatch (`done` / `blocked` / `remedy-rejected`), plus
- a per-finding outcome list, one row per finding the brief enumerated, each row carrying that
  finding's own outcome and — for a rejection — its reason.

The overall status is `remedy-rejected` when any finding's row is; the orchestrator then reads the
list rather than the status to decide what to re-attempt. A single-finding dispatch degenerates to a
one-row list, so there is one contract, not two. Dispatching per finding instead was considered and
rejected: it would change the delegation trigger, which Non-Goals holds fixed.

**Where the orchestrator-specified marker lives:** on the orchestrator's own triage record for the
finding — the record that already carries Applied / Deferred-Known-Issue — not on a "finding row",
which does not exist as a structure in Revise. Revise's round-1 findings arrive as a schema'd
`{severity, file, line, summary}` object.

**Provenance tag values** (exactly two, lowercase, hyphenated): `agent-reported`,
`orchestrator-verified`.

**Orchestrator-specified-remedy marker** (verbatim, on the round's finding row):
`remedy: orchestrator-specified`.

**The rejected-alternatives check's source document:** the change's own `design.md`, its
rejected-alternatives / explicitly-rejected-decisions content. Not the proposal, not the tasks file.

**Provenance tag scope:** the tag is a field on a **brief's** fact row and nothing else. It tells the
delegate which facts someone has actually run and which the orchestrator recalled — which is what
makes the row checkable. It does **not** travel into `### Verified claims`, the context brief, or any
review report, and no adjudication rule changes here. That widening is `fact-row-provenance`.

**Terminal-status set (exactly three, and the triage has a branch for each):** `done`, `blocked`,
`remedy-rejected`. A rejection discharges the round's attempt at a finding, not the finding, and
consumes no round.

**Rejected-alternatives check reads a ROUND-START SNAPSHOT.** The check reads the change's
rejected-alternatives content as it stood at the start of the fix round, captured before any of that
round's edits. A document the remedy just edited cannot adjudicate the remedy. It is explicitly NOT
`git show HEAD:<path>`: Review runs before Ship, so a freshly-proposed change directory is untracked
at that point and the git form errors on the common case.

**Terminal-report bucket (Handoff):** a rejected-but-open finding gets its own named bucket, distinct
from *Deferred Known Issues* (conscious deferrals) and *Deferred to TODO.md* (Suggestions plus
cap-exhausted residue).

**Exit-gate counters (exactly two, both must be zero to exit clean):** *untriaged* (in no bucket) and
*open* (triaged, not closed). A rejected finding is triaged-and-open. A finding closed by disproof is
closed and counts in neither.

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
- **`remedy-rejected` ships with no telemetry, so its own escape-hatch risk is unobservable** → the
  run-record counts that would have measured it went with `fact-row-provenance`, and
  `spec_to_pr_aggregate.py` reads nothing about rejections, so `/cla:spec-to-pr-retro` cannot price
  the risk above across runs. Accepted deliberately rather than closed here: adding a field the
  aggregator does not consume is dead weight by `run-log-schema.md`'s own rule, so the field and its
  consumer have to land together, and that is a change about the ledger rather than about the brief.
  The consequence is stated plainly — the first evidence that a rejection is being used as an escape
  hatch will come from a human reading a terminal report, not from the ledger. Tracked with the
  sibling change.
- **`Fact corrections: (none)` invites a reflexive `(none)`** → the same risk every mandatory
  "(none)" field carries. It is accepted for the same reason those were: an omitted field and a
  checked-and-clean field are indistinguishable, and a reflexive `(none)` at least leaves a row the
  orchestrator's own re-measurement can contradict.
- **Synced-core portability** → every added line must be free of repo tokens, dev-tree paths and
  absolute developer paths, since these four files ship verbatim. The plugin's existing conformance
  scan over synced core is the check.
