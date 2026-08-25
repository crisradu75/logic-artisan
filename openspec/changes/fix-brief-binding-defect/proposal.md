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
  or in the Review phase's artifact-fix loop, where there is no delegate at all — its own post-fix
  re-verification additionally checks the applied remedy against the change's `design.md` rejected
  alternatives, and the remedy is marked so the next reader knows it had no independent author.
- **Every site that restates the terminal contract states the new one.** The contract is written in
  three places besides the brief — the Implement delegation step, the Revise fix-delegate default,
  and the Revise stub's invariant line — and a rule added only to the brief leaves a dispatch
  launched from any of those three briefing against the old two-status contract. All three are
  edited in the same change as the brief itself.
- **`remedy-rejected` gets a receiving branch.** Revise triages every Critical and Important finding
  into Applied or Deferred-Known-Issue, and its exit gate counts anything in neither as untriaged
  residue. A rejection is a *successful* return and belongs in neither bucket, so the triage gains an
  explicit third outcome and the exit gate is told to stop counting it against the round.

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

Prose-only, in three shipped files. Measured with
`wc -l` and `grep -n '^### \|^## '` on 2026-08-25:

| File | lines | where the edit lands |
|---|---|---|
| `.claude/plugins/cla/skills/spec-to-pr/references/subagent-brief.md` | 115 | §2 (line 37) gains the fix-brief form; §5 (line 78) gains the defect-gone terminal contract |
| `.claude/plugins/cla/skills/spec-to-pr/SKILL.md` | 431 | Review (line 191) fix loop; Implement's delegation contract (line 239); the Revise stub (line 327) invariant lines |
| `.claude/plugins/cla/skills/spec-to-pr/references/revise.md` | 135 | the round-N≥2 scoping (line 68), the fix-delegate default (line 97), the triage buckets (line 82) and exit gate (line 134), and the INT-CAP re-read (line 101) |

**The restating sites are what an implementer would miss.** The `done`/`blocked` contract is written
in five places, not one. Measured 2026-08-25 with
``grep -rn 'explicit `done`\|`done`/`blocked`' .claude/plugins/cla/skills/`` — five hits:

| site | dispatch it briefs | in scope here |
|---|---|---|
| `spec-to-pr/references/subagent-brief.md:83` | the definition every other site cites | **yes** |
| `spec-to-pr/SKILL.md:239` | Implement's coding delegate | **yes** |
| `spec-to-pr/SKILL.md:337` | Revise's fix-delegate, stub line | **yes** |
| `spec-to-pr/references/revise.md:97` | Revise's fix-delegate, full recipe | **yes** |
| `multi-spec/references/authoring-brief.md:46` | authors proposals; never remedies a defect | **no** — named so it is not "fixed" by mistake |

Editing only the definition leaves three fix-dispatch sites briefing against the old two-status
contract, and `remedy-rejected` arriving at a triage (`revise.md:82`) that has no bucket for it and
an exit gate (`revise.md:134`) that counts it as untriaged residue.

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
- **`fact-row-provenance` inherits the cut scope.** #112, the adjudication widening, and the
  `rows_remeasured` / `rows_remeasured_disagreed` run-record counts. Two findings travel with it and
  are not this change's to fix: `agents/fact-gatherer.md` pins a four-column output table and
  "Do not add any text outside the table", so a provenance column needs that file edited; and
  `spec_to_pr_aggregate.py` reads no such counts, which `run-log-schema.md`'s own line 8 forbids
  ("adding fields the aggregator doesn't consume is dead weight").
- **`modified-block-diff-scope` verifies edits this change never makes.** Its task list checks that
  siblings' edits to `checklist.md` §Grounding-contract, `0l`, and Step 6 survived. This change makes
  no `checklist.md` edit at all — before and after the split — so that check will look for edits that
  never existed.
