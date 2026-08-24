## Why

A sub-agent brief has no notion of how much authority any line in it carries. The defect statement,
the fix the orchestrator happens to prefer, a field list the orchestrator recalled rather than read,
and a row a haiku delegate reported all arrive in the delegate's context as flat, equally-binding
prose. Four filed issues are four faces of that one gap:

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
- **#112** — nothing marks a fact row as agent-reported versus orchestrator-verified. The
  cost-offload default hands the mechanical claim checks to a haiku `fact-gatherer`; its rows land in
  a table headed `### Verified claims` with no tag distinguishing them from rows the orchestrator ran
  itself. A haiku dispatch was wrong on load-bearing rows twice in one dispatch.

These do not want four appended rules. They want one contract that says, of every line in a brief and
every row in a report, **what authority it carries and what evidence would overturn it.**

## What Changes

One contract — *the brief's authority contract* — with three authority levels and one provenance tag,
applied uniformly across the brief, the terminal contract, and the fact tables that feed a review:

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
- **Provenance is a column on the row, not a note about the dispatch.** Every row a delegate returns
  is `agent-reported` until the orchestrator re-runs its resolving command itself; the tag travels
  into the context brief, into `### Verified claims`, and into any finding derived from the row.
- **The adjudication rule widens, bounded.** The orchestrator adjudicates every ✗ row as it does
  today, **and** re-measures every row — ✓ or ✗ — that a Critical or Important finding depends on. A
  row supporting only a Suggestion, or supporting no finding, stays `agent-reported` and is reported
  as such. The cost is proportional to findings, not to rows.

No caps change. Nothing forces an additional Revise or Review round; this change deliberately leaves
the round-count question to its own decision item.

## Capabilities

### New Capabilities

(none — this change adds requirements to the existing capability below.)

### Modified Capabilities

- `cla-plugin`: four ADDED requirements covering the brief's authority contract — the binding
  defect / rejectable remedy split and its terminal contract, checkable factual sub-claims, review of
  an orchestrator-specified remedy, and fact-row provenance plus the bounded re-measurement rule. No
  existing requirement's text changes.

## Impact

Prose-only, in five shipped files. Measured with
`wc -l` and `grep -n '^### \|^## '` on 2026-08-25:

| File | lines | where the edit lands |
|---|---|---|
| `.claude/plugins/cla/skills/spec-to-pr/references/subagent-brief.md` | 115 | §2 (line 37) gains the fix-brief form; §5 (line 78) gains the defect-gone terminal contract |
| `.claude/plugins/cla/skills/spec-to-pr/SKILL.md` | 431 | Review (line 191) fix loop; Revise stub (line 327) invariant line |
| `.claude/plugins/cla/skills/spec-to-pr/references/revise.md` | 135 | the round-N≥2 scoping (line 68) and the INT-CAP re-read (line 101) |
| `.claude/plugins/cla/skills/review-change/references/checklist.md` | 316 | the cost-offload paragraph (line 64) and `### Verified claims` (line 262) |
| `.claude/plugins/cla/skills/_shared/references/run-log-schema.md` | 177 | the `Review` phase object (line ~26) gains `rows_remeasured` and `rows_remeasured_disagreed` |

**The fifth file is the one an implementer would miss.** Task 4.6 sits in a group otherwise scoped to `checklist.md`, and `checklist.md` defines no run record at all — so "where the review's run record is defined" resolves to `run-log-schema.md` and nowhere else. Naming it here is what stops the counts being added to a file nothing reads them from. **Sibling note:** `revise-round-two-question` also edits this file, adding `findings_by_round` to the **`Revise`** phase object. Different objects, so no textual conflict is expected — but the two changes must not both claim this file is theirs alone.

**Blast radius checked.** `grep -rn 'subagent-brief' .claude/plugins/cla/` returns exactly two
citing sites — `spec-to-pr/SKILL.md:234` and `lite-pr/SKILL.md:141` — and both cite the brief by its
five slot names (`scope / task / do-not-touch / report / done-when`). Because this change renames no
slot and adds no sixth, both citations stay correct and `lite-pr` needs no edit.

No script changes, no hook changes, no test-suite changes beyond the plugin's existing prose gates.
This is synced core, so every edit must stay portable: no repo token, no dev-tree path, no absolute
developer path.
