## Context

`review-change/references/checklist.md` is the single source of truth for the review workflow — loaded
both by the standalone `/cla:review-change` entry point and directly by `/cla:spec-to-pr`'s Review
phase. It carries, in order: a numbered sweep list `0a–0k` (Step 2), a §"Grounding contract" stating
that every claim resolves to verbatim evidence or an explicit NOT-FOUND (line 68), the context-brief
format, the size gate, three dispatched agent prompts, and Step 6's aggregation.

**Measured 2026-08-25, from the repo root:**

```
wc -l .claude/plugins/cla/skills/review-change/references/checklist.md   → 316
grep -n 'Grounding contract' .../checklist.md                           → 68
grep -n 'Deduplicate' .../checklist.md                                  → 249
grep -n '^## Step 6' .../checklist.md                                   → 247
grep -c '^### Requirement:' openspec/specs/cla-plugin/spec.md          → 25
```

316 is the same count the decision document recorded on 2026-08-24, so PRs #147–#150 did not reach
this file; the proposal is authored against the tree those PRs left.

**The five issues.** #124, #126, #118 and #119 each propose a new numbered check. #109 proposes a
severity tie-break. All five carry an explicit single-incident caveat and all five come from one
consuming repo's 7-change chain.

**What the four actually have in common.** Read the four reports and the common element is not a
missing rule. In every case the reviewer had the Grounding contract, had the license to read source
(line 29: "Source files are authoritative; artifacts are claims"), and had the capability. What was
missing was recognising the sentence as a claim at all:

| issue | the sentence | why it did not read as a claim |
|---|---|---|
| #124 | "the demo page shows these three states" | reads as a *requirement* — a thing to build, not a thing to check |
| #126 | "this mirrors `demo-company.ts`" | reads as *context* — a pointer, not an assertion |
| #118 | "it is not a concurrency control — `batchSize: 1` is" | reads as an *explanation* — reasoning, not a fact |
| #119 | "replaced by component-level axe assertions" | reads as a *trade* — a decision, not a promise |

#119's reporter names the mechanism precisely: "the given-up half is visible in the diff, the
replacement is a promise." A promise phrased as a decision does not present as a claim, so the
contract that governs claims never engages.

This diagnosis was checked for counterexamples, per CLAUDE.md check 3. The counterexample to look for
is an issue in this set whose reviewer *did* recognise the claim and lacked a procedure. #124 is the
nearest: its reviewer **did** catch all three unproducible shapes. But the issue itself says why that
is not a counterexample — "an ad hoc catch from one reviewer's close reading, not from a structured
checklist prompt." The recognition happened by luck, which is the same defect the other three
exhibit, observed on its lucky branch.

## Goals / Non-Goals

**Goals:**

- Answer the decision document's design question explicitly and on the record.
- State the four claim shapes in a form a reviewer executes — trigger, what to read, what to resolve
  it against, what to record, and the severity floor — meeting the repo's own bar: *"Confirm what
  moved" is not a condition; "diff the file and confirm the change is in the data, re-parse it and
  confirm it is well-formed, and read the failure message for the value you planted" is three.*
- Give the shape list a run-time placement, so it is reached in the Step-2 sweep rather than only
  when someone reads the contract section.
- Place #109's tie-break where reviewer reports are actually reconciled, and state its evidence
  honestly.

**Non-Goals:**

- Renumbering, rewording, or re-scoping any existing check `0a–0k`.
- Adding a fifth claim shape that nobody has filed. The list is *stated* as open; it is not padded.
- Any script, hook, or test. This change is portable prose in synced core.
- The `### Verified claims` report block and the cost-offload paragraph's adjudication sentence, both
  of which the sibling change `fix-brief-binding-defect` edits. See "Batch coupling" below.
- Changing what `fact-gatherer` does. This change only states that `0l` is outside its reach.

## Decisions

### D1 — The design question: a named shape list inside the Grounding contract, plus one numbered check pointing at it

**Decision: the hybrid, and it is not "having both".**

The shapes are stated **once**, as a named list inside §"Grounding contract". **One** numbered check —
`0l` — is added to the Step-2 sweep, and its entire content is "walk the artifacts for the claim
shapes the Grounding contract names, and resolve each per that contract."

"Having both" would mean stating each shape twice: as prose in the contract *and* as four independent
numbered checks `0l–0o`. That is two statements of one rule, free to drift apart, and it leaves the
fifth shape with nowhere to go. What is proposed here is one statement of the rule with one citation
handle and one run-time placement. **The file already does exactly this**: `0f–0i` is a single line
that names four checks and delegates their content elsewhere (to the overlay). The shape is
precedented in the artifact being edited, which is why it is not an invention.

**Three arguments for the contract placement, in descending strength.**

1. **The defect is recognition, not procedure.** Every one of the four reviewers had the procedure. A
   numbered check at the end of a sweep list is more procedure — it answers a question nobody was
   failing. Naming the shapes beside the rule they instance is what addresses the actual failure:
   "here are four sentences that do not look like claims and are." That is a definition, and
   definitions belong with the term they define.

2. **The four shapes are not delegable, and the numbered list is where delegation lives.** Line 64's
   cost-offload paragraph defaults the *mechanical* portion of `0a–0h` to a read-only `fact-gatherer`
   dispatch (haiku, no `Bash`) returning a pass/fail table. `0l–0o` would sit outside that stated
   range but inside the same list, and inside a list whose default is delegation. None of the four
   shapes survives that treatment: "is this requirement stricter than the precedent it cites" requires
   reading a mechanism and judging comparative strictness; "is this a code property or a deployment
   property" is a classification; "is this compensating coverage real" requires judging one test's
   strength against another's. Each returns a judgement, not a row. This is a structural argument
   readable from the file, not a prediction.

3. **The numbered form closes an open rule.** The Grounding contract binds *every* claim. Four
   numbered checks convert that into four enumerated cases, and the fifth shape — the one nobody has
   filed — then reads as needing a sixth check before anyone may act on it. The contract form keeps
   the general rule primary and the list illustrative, which is what it actually is. As a side
   effect it is also **shorter**: four numbered checks each restate the resolve-to-evidence-or-NOT-FOUND
   discipline; one contract subsection states it once, because it is already stated three lines above.

**The rejected side, argued.** `0l–0o` as filed has three real advantages, and the third is the one
that forces the hybrid rather than the pure contract form.

- *It is what the issues asked for.* The reporters are downstream users of a marketplace install who
  will look for what they filed. #109 explicitly says "I don't have visibility into the plugin's
  internal file layout from a read-only marketplace install, so I'm proposing a location rather than
  reporting one" — these are proposals of *intent*, and honouring the intent while relocating the
  mechanism is legitimate. Mitigation: the PR body maps each issue number to the shape name that
  carries it, so a reporter can find their check.
- *Numbers are citable and countable.* A finding can say "0b" today. A shape with no handle cannot be
  cited in a finding or counted in the retro ledger. **This is answered by the hybrid**: findings cite
  `0l` plus the shape's name, and the shape names are the granular handle.
- *The numbered list has a run-time placement and the contract section does not.* This is the
  strongest objection and it is correct as stated. Step 2 says "run ALL verification checks
  simultaneously", and line 60 enumerates which checks the orchestrator runs. §"Grounding contract"
  is a rule about the *shape of an output*, cited by other sections but not itself a step anyone
  executes. A shape list living only there could plausibly never be read at review time. **This is
  precisely why `0l` exists** — the pure contract form was rejected on this objection, not the
  numbered form.

**What was NOT used as an argument.** "A checklist nobody finishes reading" is the obvious case
against a longer file, and it is not load-bearing here: no measurement of reviewers abandoning this
file exists, and asserting one would be exactly the failure CLAUDE.md check 3 names. The decision
rests on arguments 1–3 above, all of which are readable from the file's own structure.

### D2 — The four shapes, stated executably

Each shape is a **trigger** (when it fires), a **resolution** (numbered steps naming what to read and
what to resolve it against), a **failure mode** (what a non-resolution means), and a **severity
floor**. A shape stated as "check that the claim is grounded" would fail the repo's own bar and is not
what is written below.

**Shape 1 — Producible state (#124).** *Trigger:* an artifact specifies a fixed set of
example/demo/fixture/sample states a surface must show. *Resolution, per state:* (a) name the
production function or query that would produce it, and read it; (b) resolve the predicate that gates
the state against the **real corpus**, not the fixture's — the count or the condition; (c) record
`producible: <path:line of the producing path> + <the corpus figure>` or
`NOT PRODUCIBLE: <the line that forbids it>`. *Failure mode:* being unable to name a producing path is
`NOT PRODUCIBLE`, not `unresolved` — that asymmetry is the point, because the default here must be
negative. *Severity floor:* an unproducible state written as a requirement is **Critical**. Reason,
from the issue: a requirement the product cannot satisfy does not fail loudly, it gets satisfied
dishonestly — the available resolution under implementation pressure is always to invent the data.

**Shape 2 — Precedent strictness (#126).** *Trigger:* an artifact names an existing shipped
implementation as the precedent it mirrors, follows, or is modelled on. *Resolution:* (a) read the
named precedent's actual mechanism at its path; (b) for each provision the new requirement imposes,
record whether the precedent satisfies it, does not satisfy it, or does not have it; (c) for each
provision the precedent does not satisfy, state what the extra strictness buys and who pays for it.
*Failure mode:* a provision stricter than its own cited precedent whose benefit cannot be stated.
*Severity floor:* **Important**, rising to **Critical** when the provision blocks implementation.
Worth stating in the file, because it is why no existing check finds this: every other check asks
whether the artifact is strong *enough*; this one asks whether it is stronger than it needs to be, and
that direction has no other reader.

**Shape 3 — Guarantee class (#118).** *Trigger:* an artifact says a mechanism prevents, controls,
serialises, or makes impossible a hazard. *Resolution:* (a) classify the guarantee as a **CODE
property** (a constraint, a lock, a registration, a type, a test that goes red) or a **DEPLOYMENT
property** (true only because of how many processes, instances, workers, or regions run today); (b)
for CODE, quote the enforcing line; (c) for DEPLOYMENT, require the artifact to say so **and** to name
the trigger condition that changes it — the scaling change, the config flip, the phase that lifts the
limit. *Failure mode:* leaving it unclassified, because the two read identically in prose and the gap
only becomes visible once the deployment fact changes, at which point the hazard returns with no code
change and nothing red. *Severity floor:* a deployment property with no named trigger is
**Important**; a deployment property **described as** a code property is **Critical**, because that is
a false statement about what the code enforces.

**Shape 4 — Compensating coverage and exclusion reach (#119).** Two halves, one shape, because the
issue reports them as one event.

- *Trigger (a):* a change gives up automated coverage in exchange for a named alternative.
  *Resolution:* read the named replacement and confirm what kind of assertion it **actually runs** —
  grep the replacement file for the mechanism the claim names — then state the replacement's strength
  relative to what was given up. *Failure mode:* accepting the description. The given-up half is
  visible in the diff; the replacement is a promise, so the promise is the half to verify.
- *Trigger (b):* an exclusion entry is added to any route-, page-, or file-keyed allowlist or
  denylist. *Resolution:* enumerate the components or modules reachable **only** through the excluded
  surface, and for each, name where it is otherwise covered or state that it is not. *Failure mode:*
  the entry names a page file, so the exclusion reads as excluding a route while in practice it
  excludes every component that route uniquely renders.
- *Severity floor:* **Important** for an unverified compensating claim; **Critical** when the
  replacement is measurably weaker than what it replaced.

**The common signature, so a fifth shape is recognisable.** A sentence is a claim under this contract
when its truth depends on something outside the artifact — the code, the corpus, a shipped precedent,
the deployment, a test file — **even when its grammar is not assertive**. The four grammars that hide
one: an explanation ("because", "prevents", "is the control"), a comparison to something shipped
("mirrors", "same as", "following"), a specification of output shape ("the page shows"), and a trade
("replaced by", "compensated by", "covered instead by"). A sentence matching that signature is in
scope whether or not it appears in the list.

### D3 — `0l` is one check, and it states its own non-delegability

`0l` reads as one short numbered entry pointing at the contract's shape list, plus one clause: it is
**not** part of the mechanical portion that defaults to a `fact-gatherer` dispatch. The cost-offload
paragraph gets the matching sentence, so the exclusion is stated where the delegation decision is made
rather than only where the check is defined. Line 60's enumeration ("generic 0a–0e and 0j–0k here")
gains `0l`, because a stale enumeration is how a check goes quietly unrun.

*Alternative rejected:* leave the cost-offload paragraph alone and state non-delegability only at
`0l`. Rejected because the orchestrator decides delegation while reading line 64, not while reading
the check.

### D4 — #109 goes to Step 6's deduplication step, keyed on evidence rather than on agent role

**Decision:** at Step 6's "Deduplicate findings" line, add: when two dispatched reports carry the same
finding at different severities, the merged severity comes from the report whose evidence for that
severity is **implementation-level** — a source line, a schema, a migration, a query result — over the
report whose evidence is the spec delta or the artifact text alone. Where neither report's evidence is
implementation-level, or both are, keep the higher severity. Either way, record the tie-break on the
finding line so a reader can see one happened.

**Why keyed on evidence, not on which agent reported it.** The issue's wording is "the one who read
the implementation wins, not the one who read the spec." In this checklist all three Step-4 agents are
told "You MAY read source files to verify claims," so "the one who read the implementation" does not
pick out an agent. Keying on the evidence attached to the finding does, and it is decidable from the
report the orchestrator already has in front of it. This is also why the rule belongs in this change
rather than in a separate one: it is executable **only because** the Grounding contract makes every
finding carry its resolving evidence. Without that, there is nothing to compare.

**#109 is not a claim shape and is not forced into the list.** It is a merge rule about two reports,
not a rule about one sentence. It lands in the section that reconciles reports.

**Its evidence, stated honestly:** one overlapping finding out of 18, from one change in one chain in
one consuming repo. It is a reasonable heuristic with exactly one supporting data point, and the
observed instance was a **two-reviewer split (design + spec-delta) from a different workflow**, not
this checklist's three-agent dispatch — so it is being generalised across a dispatch shape it was not
observed in. Two consequences that must be written into the file rather than left implicit: the rule
will fire **rarely** (overlap was 1-in-18, and low overlap is the split working as designed), and its
cost is one sentence, which is the whole reason it is worth encoding at n=1. It must not be described
as measured.

*Alternative rejected:* "the higher severity always wins." Simpler, needs no evidence comparison, and
would have produced the right answer in the one observed instance. Rejected because it is right by
coincidence there — the design reviewer's grade was higher *and* better-evidenced — and it converts
every disagreement into an escalation, which inflates Critical counts and corrupts the `verdict`
field's meaning in `/cla:spec-to-pr-retro`'s telemetry. The file already records that exact corruption
happening once, at the verdict rubric's "Do not shortcut this to 'any Critical → RETHINK'". It is
retained as the *fallback* when evidence does not discriminate, which is where it is actually safe.

### D5 — Report budget

§"Report constraints" caps the report at roughly one screen and one line per finding. Nothing here
adds a report line: `0l`'s results land in existing context-brief rows, and the tie-break annotates an
existing finding line rather than adding one. Stated so a later reader does not have to re-derive it.

## Pinned implementation parameters

Every load-bearing name and location, fixed here so `tasks.md` does not re-decide them. **Anchors are
content, not line numbers** — line numbers are recorded as measured on 2026-08-25 and are re-derived
in task 1.1 before any edit.

**Target file (one file, no others):** `.claude/plugins/cla/skills/review-change/references/checklist.md`

**The subsection heading, verbatim:**

`#### Claim shapes — four sentences that are claims and do not look like claims`

Placed immediately after §"Grounding contract"'s existing paragraph (measured: heading at line 68,
paragraph ends line 70) and before `### Context brief — standard format` (measured: line 72). `####`
rather than `###` so the list is *inside* the contract rather than a sibling section, which is the
whole decision.

**The four shape names, verbatim** (these are the citation handles a finding uses):

| # | shape name | issue |
|---|---|---|
| 1 | **Producible state** | #124 |
| 2 | **Precedent strictness** | #126 |
| 3 | **Guarantee class** | #118 |
| 4 | **Compensating coverage and exclusion reach** | #119 |

**Per-shape structure, identical for all four:** a bolded name, then `*Trigger:*`, `*Resolution:*`
(lettered steps `(a)`/`(b)`/`(c)`), `*Failure mode:*`, `*Severity floor:*`. The content of each is
fixed in D2 above and is carried across verbatim.

**The openness clause:** one paragraph after the four, carrying the common signature and the four
hiding grammars from D2, ending with the statement that a sentence matching the signature is in scope
whether or not it is listed.

**The new numbered check, verbatim name:**

`0l. **Claim-shape sweep**`

Placed immediately after `0k` (measured: line 54) and before `### Applies when the change touches
allocation math, mock data, or i18n` (measured: line 56). Content: point at the contract's shape list,
and state that unlike `0a–0h` it is not delegable to `fact-gatherer` because each shape returns a
judgement rather than a pass/fail row.

**Line 60's enumeration** (`All checks above (generic 0a–0e and 0j–0k here, ...)`) becomes
`0a–0e and 0j–0l`. Anchor by content: `grep -n 'generic 0a–0e and 0j–0k' <file>`.

**Cost-offload paragraph** (measured: line 64): one added sentence naming `0l` as outside the
delegable set, appended to the paragraph. It **does not** touch the sentence beginning "You still
adjudicate every ✗ row yourself" — that sentence belongs to the sibling change.

**Step 6 tie-break** (measured: Step 6 at line 247, "Deduplicate findings" at line 249): one paragraph
after the existing deduplication sentence, carrying the evidence-keyed rule, the higher-severity
fallback, the record-it-on-the-finding-line requirement, and the honest-evidence sentence (1 of 18,
one chain, one repo, observed on a different dispatch shape, expected to fire rarely).

**Requirement names for the delta spec** (checked against all 25 live requirement names and both
siblings' deltas — no collision):

- `Grounding contract enumerates the claim shapes that do not look like claims`
- `Reviewer report severities are reconciled by the evidence behind them`

**Delta type:** `## ADDED Requirements` only. No live requirement's text or scenarios change, so no
MODIFIED block is written and nothing can be dropped at archive-sync.

## Batch coupling — `fix-brief-binding-defect` edits the same file

Both changes land in one PR and both edit `checklist.md`. The overlap and its resolution:

| region | this change | `fix-brief-binding-defect` | collision |
|---|---|---|---|
| cost-offload paragraph (line 64) | appends one sentence naming `0l` as non-delegable | tasks 4.1–4.3 add a provenance-field requirement and **replace the adjudication sentence** | **Yes — same paragraph.** Resolved by ordering: the sibling's 4.1–4.3 land first, this change appends after, and task 4.1 here re-greps the paragraph and confirms both edits are present |
| §Grounding contract (68–70) | adds a `####` subsection after the paragraph | its task 4.5 states that a provenance tag travels into the context brief and into derived findings, without naming a location — the contract is a plausible home | **Soft.** Same region, different sentences, no shared text. Whichever lands second reads the region first rather than assuming its shape |
| `### Verified claims` (262, 307) | **not touched, deliberately** | task 4.4 requires the provenance tag there | None |
| Step 6 dedup (249) | adds the tie-break paragraph | not touched | None |
| `0a–0k` list, line 60 | adds `0l`, updates the enumeration | not touched | None |

`delegate-liveness-contract` does not touch `checklist.md` at all; it is disjoint.

## Risks / Trade-offs

- **[The shape list is read as closed despite saying it is open.]** → The openness clause is not a
  disclaimer at the end but a *signature* — the four hiding grammars named explicitly, so a fifth
  shape is recognised by pattern rather than by permission. This is a mitigation, not a guarantee; if
  a fifth shape gets filed as a sixth numbered check anyway, that is the signal this framing failed.
- **[`0l` becomes a line nobody expands, because it points elsewhere.]** → It sits in the sweep the
  orchestrator runs and its results land as context-brief rows like every other check's, so an unrun
  `0l` shows up as absent rows. The same risk already applies to `0f–0i`, which points at the overlay;
  no incident of `0f–0i` being skipped is on record, which is weak evidence but is the only evidence
  there is. Not asserted as measured.
- **[Four shapes derived from four single incidents in one consuming repo.]** → Each shape's text
  carries the shape, not the incident's mechanism — no `batchSize`, no axe, no CAEN, no route
  allowlist name reaches synced core, because those are one repo's infrastructure. Note that
  `check_no_project_tokens.py` does **not** catch these unless they sit on this repo's curated token
  list, so `tasks.md` 5.2 makes it a read rather than leaning on the guard. The generalisation is the deployment-vs-code
  distinction, the precedent-strictness direction, the producibility question, and the
  promise-vs-diff asymmetry — none of which is tied to that repo's stack.
- **[The tie-break is encoded from n=1 and generalised across dispatch shapes.]** → Stated in the file
  as exactly that, with the count. Its cost is one sentence and it fires rarely; the failure mode of
  encoding it wrongly is one finding graded one level off, which the verdict rubric already judges by
  the fix's nature rather than by severity label.
- **[The file grows by roughly 45 lines on top of 316.]** → Accepted. The numbered-check alternative
  is not shorter — it restates the resolution discipline four times — and the growth is stated here
  rather than defended with a reading-abandonment figure nobody measured.
- **[Same-file collision with the sibling change in one PR.]** → Pinned above with an ordering rule
  and a re-grep confirmation task, rather than left to whichever edit runs second.

## Open Questions

None blocking. One deferred by choice: whether the shape list should eventually move to
`_shared/references/` so `/cla:spec-to-pr`'s Revise phase can cite it for post-implementation
findings. #119 was filed against `spec-to-pr`'s Review phase, which reads this file directly, so
placing it here already reaches that caller. Revisit only if a shape is needed by a skill that does
not load `checklist.md`.
