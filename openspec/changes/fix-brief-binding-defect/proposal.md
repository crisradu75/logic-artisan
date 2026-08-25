## Why

A sub-agent brief has no notion of how much authority any line in it carries. The defect statement,
the fix the orchestrator happens to prefer, and a field list the orchestrator recalled rather than
read all arrive in the delegate's context as flat, equally-binding prose. Three filed issues are
three faces of that one gap:

- **#96** — the brief binds the *remedy*, not the *defect*. A perfectly compliant delegate
  implements the named remedy, returns `done` with the evidence the terminal contract asks for
  (tests pass, boxes ticked), and ships a regression that looks exactly like success. Nothing in the
  contract asks whether the defect is gone.
- **#121** — a defect statement's own factual sub-claims ship as ground truth. One asserted four
  required fields on `DeliveryPopulation`; the type carries three. The defect was real, the field
  list was not, and no step existed at which the delegate was asked to resolve either.
- **#107** — a fix the orchestrator specified skips the scrutiny a delegate's fix gets, because the
  delegate that would push back is the one being told what to do, and the orchestrator that decided
  the remedy is also the one triaging the findings on it. Change 4's third round found two Criticals
  and both sat in an orchestrator-directed fix — one of which reintroduced a bias the change's own
  `design.md` had explicitly rejected.
These do not want three appended rules. They want one contract that says, of every line in a brief,
**what authority it carries and what evidence would overturn it.**

**Scope note — #112 is deliberately not here.** A fourth filed issue, #112 (nothing marks a fact row
as agent-reported versus orchestrator-verified), was proposed alongside these and cut from this
change at review. Its subject is a *review report's* fact table, not a brief: it has no dispatch, no
delegate, and no authority level, and carrying it dragged this change into a second skill, a fifth
file, and a run-record edit whose consumer was never in scope. It is tracked separately as
`fact-row-provenance`.

## What Changes

One contract — *the brief's authority contract* — with three authority levels, applied uniformly
across the brief, its terminal contract, and the sites that restate either:

- **Slot 2 of the brief gains a fix-brief form.** A dispatch whose purpose is to remedy a defect
  states three named fields instead of one task sentence: a **binding** `Defect`, a set of
  **checkable** `Facts this defect rests on` (each with its source and provenance tag), and a
  **rejectable** `Candidate remedy`. A build-this dispatch keeps the existing one-sentence form. The
  brief still has five slots and no slot is renamed.
- **The terminal contract asks for proof the defect is gone**, not proof the remedy landed. A fix
  brief's `done` requires the check that exhibits the defect, named and re-run, showing it absent —
  the remedy having been applied is explicitly *not* that evidence. A third terminal status,
  `remedy-rejected`, makes a reasoned rejection of the candidate remedy a successful return rather
  than a failure.
- **A defect's embedded factual claims are checkable, and checking them is the delegate's first
  action.** A wrong sub-claim does not void a defect that survives its correction: the delegate
  corrects the row, proceeds, and returns the correction in a required `Fact corrections:` field that
  prints `(none)` rather than being omitted.
- **An orchestrator-specified remedy is reviewed as a decision.** Where the fix is delegated, the
  rejectable field is that review. Where the orchestrator applies the fix itself — inline in Revise,
  in the Review phase's artifact-fix loop, or in `multi-spec`'s per-change review gate, none of which
  has a delegate — its own post-fix re-verification additionally checks the applied remedy against
  the change's `design.md` rejected alternatives, reading a **round-start snapshot** rather than the
  working tree. A hit is a Critical finding on the remedy itself, not a note: the remedy is withdrawn
  or re-specified. On the Revise path, where delegated and orchestrator-applied fixes mix, the remedy
  is marked so the next reader knows which hunks had no independent author.
- **Every site that restates the terminal contract for a FIX dispatch states the new one.** The
  contract is written in four places besides the brief, but only two of them brief a dispatch that
  remedies a defect — the Revise fix-delegate default and the Revise stub's invariant line. Both are
  edited here. Implement's coding delegate and `multi-spec`'s authoring brief are named as out of
  scope so neither is "fixed" by mistake.
- **`remedy-rejected` gets a receiving branch at every point that receives one.** Three, not one.
  The **triage** gains an explicit third outcome beside Applied and Deferred-Known-Issue. The **exit
  gate** splits its single counter in two — *untriaged* and *open* — because a rejected finding is
  the first that is triaged and still open, and a gate counting only untriaged would exit the loop
  clean while a Critical is live. The **terminal report** gains its own bucket for it, distinct from
  conscious deferrals and from Suggestions. And because Revise's fix-delegate has no return-handling
  prose of its own today, this change writes that branch too.
- **A set-level dispatch returns per-finding outcomes.** The fix-delegate is dispatched once over a
  whole fix-set while every branch receiving its result is per finding, so the return carries one
  overall status plus one row per finding — fourteen applied and one rejected has to be sayable.
- **A rejection citing a disproved defect closes the finding.** A rejection normally leaves the
  finding open for a re-decided remedy. Where the delegate has shown the defect itself does not
  exist, re-attempting it forever is the wrong move: that case closes, with the corrected fact row as
  the evidence.

No caps change. Nothing forces an additional Revise or Review round; this change deliberately leaves
the round-count question to its own decision item.

## Capabilities

### New Capabilities

(none — this change adds requirements to the existing capability below.)

### Modified Capabilities

- `cla-plugin`: three ADDED requirements covering the brief's authority contract — the binding
  defect / rejectable remedy split and its terminal contract, checkable factual sub-claims, and
  review of an orchestrator-specified remedy. No existing requirement's text changes.

## Impact

Prose-only, in five shipped files. Measured with
`wc -l` and `grep -n '^### \|^## '` on 2026-08-25:

| File | lines | where the edit lands |
|---|---|---|
| `.claude/plugins/cla/skills/spec-to-pr/references/subagent-brief.md` | 115 | §2 (line 37) gains the fix-brief form; §5 (line 78) gains the defect-gone terminal contract |
| `.claude/plugins/cla/skills/spec-to-pr/SKILL.md` | 431 | Review (line 191) fix loop; the Revise stub (line 327) invariant lines. **Implement (lines 239/243) is deliberately NOT edited** — see the site classification below |
| `.claude/plugins/cla/skills/spec-to-pr/references/revise.md` | 135 | the round-N≥2 scoping (line 68), the fix-delegate default (line 97), the triage buckets (line 82) and exit gate (line 134), the INT-CAP re-read (line 101), plus a new return-handling branch the fix-delegate currently lacks entirely |
| `.claude/plugins/cla/skills/spec-to-pr/references/handoff.md` | — | the terminal report's deferred buckets (lines 13, 24) gain a third for a rejected-but-open finding |
| `.claude/plugins/cla/skills/multi-spec/references/review-gate.md` | — | Step 7 (line 55) applies findings as direct Edit/Write to a change's artifacts with no delegate — a second site inside the orchestrator-specified-remedy rule |

**The restating sites are what an implementer would miss.** The `done`/`blocked` contract is written
in five places, not one. Measured 2026-08-25 with
``grep -rn 'explicit `done`\|`done`/`blocked`' .claude/plugins/cla/skills/`` — five hits:

| site | dispatch it briefs | in scope here |
|---|---|---|
| `spec-to-pr/references/subagent-brief.md:83` | the definition every other site cites | **yes** |
| `spec-to-pr/SKILL.md:337` | Revise's fix-delegate, stub line | **yes** |
| `spec-to-pr/references/revise.md:97` | Revise's fix-delegate, full recipe | **yes** |
| `spec-to-pr/SKILL.md:239` | Implement's coding delegate — implements enumerated tasks | **no** |
| `multi-spec/references/authoring-brief.md:46` | authors proposals; never remedies a defect | **no** |

**Two of the five are not fix dispatches, and both are named so they are not "fixed" by mistake.**
`multi-spec`'s authoring brief writes proposals. `SKILL.md:239` is Implement's coding delegate, and
excluding it is a correction: an earlier draft counted it in scope, which contradicts this change's
own rule that a site briefing a dispatch that never remedies a defect is left unchanged. Implement's
delegate implements the tasks it is handed, under a rule two lines above that same bullet requiring
full-task enumeration because the delegate "will NOT invent an omitted task" — a delegate with no
discretion to reject the plan cannot be given a contract whose third status is a reasoned rejection.

**Which relocates the real gap rather than removing it.** `SKILL.md:243` — the prose that receives a
delegate's return and branches on it — is the only delegate-return receiver in the skill, and it
lives in Implement. Revise's fix-delegate has no return-handling prose of its own at all. So
excluding Implement does not leave Revise covered; it shows that Revise's fix-delegate is dispatched
with nothing written to receive what it returns. This change writes that branch in `revise.md`,
where it belongs, and leaves `SKILL.md:239`/`:243` untouched.

Editing only the definition leaves two fix-dispatch sites briefing against the old two-status
contract, and `remedy-rejected` arriving at a triage (`revise.md:82`) that has no bucket for it, an
exit gate (`revise.md:134`) that lets it exit the loop while the finding is still open, and a
terminal report (`handoff.md`) with no bucket to print it in.

**Blast radius checked.** `grep -rn 'subagent-brief' .claude/plugins/cla/` returns exactly two
citing sites — `spec-to-pr/SKILL.md:234` and `lite-pr/SKILL.md:141` — and both cite the brief by its
five slot names (`scope / task / do-not-touch / report / done-when`). Because this change renames no
slot and adds no sixth, both citations stay correct and `lite-pr` needs no edit.

No script changes, no hook changes, no test-suite changes beyond the plugin's existing prose gates.
This is synced core, so every edit must stay portable: no repo token, no dev-tree path, no absolute
developer path.

## Sibling coupling

This change lands first in its batch, so the note is for whoever runs the others.

- **`delegate-liveness-contract` must carve out `remedy-rejected`.** That change classifies a return
  missing the evidence fields its brief's slot 5 named as `blocked`. A legitimate `remedy-rejected`
  return carries no defect-check output *by construction* — the delegate rejected the remedy rather
  than applying it — so the naive rule reclassifies a successful return as a failure, which is the
  exact ledger distortion this change rejected `blocked` to avoid. The carve-out belongs in that
  change, since this one ships before it and cannot reference a rule that does not yet exist.
  **Two additions from this change's review:** the carve-out must key on the **per-finding outcome
  list**, not the overall status — a set-level dispatch returning `remedy-rejected` overall may carry
  thirteen applied rows whose evidence fields are fully populated, so "missing evidence ⇒ blocked"
  applied at the dispatch level misreads a mostly-successful return. And a rejection citing a
  **disproved defect** carries no defect-check output for the same by-construction reason, yet closes
  its finding rather than leaving it open; classifying it `blocked` would reopen something this
  change closes.
- **`fact-row-provenance` inherits the cut scope, and gains the telemetry.** #112, the adjudication
  widening, and the `rows_remeasured` / `rows_remeasured_disagreed` run-record counts —
  **plus the rejection counts this change deliberately does not add.** `remedy-rejected` ships here
  with no ledger field, so `/cla:spec-to-pr-retro` cannot price the escape-hatch risk the design
  names; the field and its consumer in `spec_to_pr_aggregate.py` have to land together, which makes
  it that change's work rather than this one's. Two findings travel with it and
  are not this change's to fix: `agents/fact-gatherer.md` pins a four-column output table and
  "Do not add any text outside the table", so a provenance column needs that file edited; and
  `spec_to_pr_aggregate.py` reads no such counts, which `run-log-schema.md`'s own line 8 forbids
  ("adding fields the aggregator doesn't consume is dead weight").
- **`modified-block-diff-scope` verifies edits this change never makes.** Its task list checks that
  siblings' edits to `checklist.md` §Grounding-contract, `0l`, and Step 6 survived. This change makes
  no `checklist.md` edit at all — before and after the split — so that check will look for edits that
  never existed.
