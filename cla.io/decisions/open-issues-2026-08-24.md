# Decision: the remaining 20 open issues, grouped into eight work items

Built 2026-08-24 from `gh issue list --state open` (20 issues) after the Lane 1 batch of
`open-issues-p1-p3-2026-08-23.md` merged and closed 11 issues across PRs #134, #135, #136, #140
and #141. It supersedes `open-issues-p1-p3-2026-08-23.md`, whose "Out of scope — Lane 2" section
grouped 15 of these 20; the other five (#138, #139, #142, #143, #144) were filed after it was
written. **That doc was deleted 2026-08-24 in a decisions-directory cleanup and is not recoverable
— it was never committed.** Everything it held that is still live is restated here.

This is now the only decisions doc in the repo. The other eight were deleted in the same cleanup;
all but the one above are tracked and recoverable at `eaa579b`.

Fifteen of the twenty issues were filed from the consuming repo `interoga-ro` against release
`cla--v0.10.0` and carry an explicit single-incident caveat. Grouping is the main defence: a work
item with four instances of one mechanism is better evidence than four issues with one each. It
does not make any of them measured, and the caveat travels with each item below.

**Measured-by** (all run 2026-08-24 from the repo root):

```
gh issue list --state open --limit 50                                 → 20
wc -l .claude/plugins/cla/skills/review-change/references/checklist.md → 316
grep -n 'pr-rounds' .claude/plugins/cla/skills/spec-to-pr/references/revise.md
                                                                       → :5 "Cap: --pr-rounds N (default 2)."
wc -l .claude/plugins/cla/skills/spec-to-pr/references/concurrent-runs.md → 21
grep -n '^#' .claude/plugins/cla/skills/_shared/references/test-quality.md
      → :41 non-vacuity floor, :85 prove a gate, :104 how planting goes wrong
grep -n '^##' .claude/plugins/cla/skills/spec-to-pr/SKILL.md
      → :159 Concurrent runs, :343 Archive
grep -rn '_guard_areas\|hardcodes_an_absolute_path' plugin-tests/tests/
      → both in tests/consistency/test_guards_have_mutant_batches.py, :30 and :229
ls plugin-tests/mutants/                                              → conformance, consistency, release
```

## Lanes

**Lane 1 — direct edits (`/cla:multi-lite`, one PR per item).** The change is knowable from the
issue; the only work is making the edit correctly. Items **F, G, E, D1**.

**Lane 2 — proposals (`/cla:multi-spec` → review → `/cla:multi-pr`).** Each carries a design
question that wants a proposal and a pre-implementation review. Items **A, B, C, D2, H**.

## Sequencing constraint — read before running

Lane 1 runs to completion before Lane 2 starts. The two lanes are almost disjoint, with one
exception: **`spec-to-pr/SKILL.md`**. D1 may need a line in its §Archive (line 343), and A, B and H
each edit it elsewhere. Nothing else is shared. Lane 2's proposals are authored against the state
Lane 1 leaves, not against this document's description of it.

| item | lane | files it edits |
|---|---|---|
| F | 1 | `plugin-tests/tests/consistency/test_guards_have_mutant_batches.py` (both guards live in that one file), `plugin-tests/mutants/` — dev tree only |
| G | 1 | `_shared/references/test-quality.md` |
| E | 1 | `multi-pr/references/discover-and-gate.md` |
| D1 | 1 | `spec-to-pr/references/archive.md`, `multi-pr/references/change-loop.md`, possibly `spec-to-pr/SKILL.md` §Archive |
| A | 2 | `spec-to-pr/references/subagent-brief.md`, `spec-to-pr/SKILL.md` (Review/Revise scope) |
| B | 2 | `spec-to-pr/references/subagent-brief.md`, `spec-to-pr/SKILL.md` §Concurrent runs, `references/concurrent-runs.md` |
| C | 2 | `review-change/references/checklist.md` |
| D2 | 2 | scoping first — likely no file in this plugin |
| H | 2 | `spec-to-pr/references/revise.md`, `spec-to-pr/SKILL.md` |

**A and B both edit `subagent-brief.md` and must not run concurrently.** A runs first: it settles
what a brief's slots bind, and B adds a terminal-contract rule that sits inside that shape. Within
Lane 1 all four items touch disjoint files and may run in any order.

## Lane 1 candidates — ✅ SHIPPED 2026-08-24, do not re-propose

All four merged: **F** → PR #147 (closes #138, #139) · **G** → #148 (#143) ·
**E** → #149 (#142, #99) · **D1** → #150 (#144). Run record and review-findings
breakdown: `cla.io/retro/multi-lite-run-notes-2026-08-24.md`.

**The table below is history.** A skill extracting candidates from this document takes its work
from the Lane 2 section only.

**What the run said about this plan.** All four candidates needed an enforcement round and this
document predicted none. Candidate F needed a design rebuild rather than a patch: a mutant that
turned its mechanism into the blanket exemption its own comment denied being passed all five tests
written for it. The classification was wrong because issue #138 said "possible directions, not a
prescription" — a design question — and this plan read it as a specification. **The Lane 1/Lane 2
test is not "does the issue name a fix" but "does the issue name a fix, or a direction".** Apply
that when sorting the next batch.

| id | description | depends_on |
|---|---|---|
| `mutation-batch-adoption` (**F**, #138 #139) | Two defects in `plugin-tests/` that jointly make the mutation-batch convention unreachable for any area that does not already have a batch. **(a)** `test_guards_have_mutant_batches.py`'s `_guard_areas()` derives areas from the subdirectories present under `plugin-tests/mutants/`, so creating the FIRST batch in an area makes the whole area policed at once — measured at **12** other hook guards newly demanding batches, none exemptable because `test_the_grandfather_list_only_shrinks` caps `_EXEMPT` at 12 and permits only shrinkage. The rational response is to not write the batch, which is the opposite of the convention's intent; observed for real, where the batch proving `ask-destructive-git`'s new `git branch -D` detection was run from outside the repo tree and committed nowhere. Adopt an area incrementally — police only guards that already have a batch, or make the grandfather list per-area. **Keep the property the current design gets right: a guard that once had a batch must not silently lose it.** **(b)** `test_no_batch_hardcodes_an_absolute_path` treats `:\` anywhere in a line as a Windows drive path, so `(?:\s`, `(?:\S` and `(?:\d` are flagged — three of five mutants in one hook batch, every one a regex anchor. Narrow to a drive-letter shape (`[A-Za-z]:[\/]`) and pin both directions with a fixture: a real `C:\...` string still caught, a regex containing `(?:\s` not. The false positive lands hardest on hook batches, which are disproportionately regex-mutating and are exactly the batches most worth writing. Dev tree only — ships nothing to a consumer. Closes GitHub issues #138, #139. | — |
| `guard-operating-point` (**G**, #143) | A guard, alarm or threshold can be **logically correct and still never fire**, because the volume it sees in steady state sits outside the range where it does anything. Distinct from the vacuous-guard class and from both traps PR #140 just shipped: mutating the comparison changes nothing, because the comparison is right — what is wrong is the precondition or threshold gating when it runs. Three instances in one chain: a join-rate floor with a minimum sample of 200 against ~113–190 real candidates a night (enforcement path existed, never ran); a vocabulary alarm that saw only total collapse and would have false-fired about half the time on a two-item batch; and a zero-yield alert whose threshold of 70 was derived from a measured zero-TERM share while the code it guarded counted zero ACTS. Add a lens to `_shared/references/test-quality.md`: any new alarm, threshold or minimum-sample precondition must state the volume it will see in **ordinary steady-state operation**, not the backfill-sized sample in front of the author, and answer "at that volume, can this fire, and will it fire only when it should?" The natural home is beside the existing §"A non-vacuity floor must track its population" (line 41), which is the same idea from the population side; §"How planting goes wrong" (line 104) is the wrong home, because no plant surfaces this. Prose only — this file ships to consuming repos, so name no dev-tree tooling. Closes GitHub issue #143. | — |
| `phase1-non-source-edges` (**E**, #142 #99) | `multi-pr` Phase 1 orders and gates a chain using `depends_on`, which records **source-level** dependencies only. Two real edges it cannot express, both caught by luck rather than by the workflow. **(a)** #142 — **shared mutable environment state.** A change that applies a database migration, seeds shared fixture data, or performs a provisioning step creates a merge-before-next edge regardless of whether anything depends on its code: the shared state has already moved for every subsequent branch, and only merging its source makes the tree consistent again. Evidenced by change 1 of the 2026-08-23 six-change chain, listed `depends_on: []`, whose migration was applied and checksummed on the dev database; leaving its PR open per the confirmed policy would have failed `check:migrations-unedited` on the next five branches, for reasons unrelated to their own work. The orchestrator merged it anyway by reasoning mid-chain — nothing in Phase 1 asked. Ask it per change during sequencing (§1b, the merge-policy gate at line 29) and record the answer in the run's sequence table next to `depends_on`. **(b)** #99 — **capability overlap.** `/cla:multi-spec` authors a batch in parallel, so every delta is written against the pre-batch spec text, and `## MODIFIED Requirements` replaces wholesale. Two dependency-independent changes touching one capability spec means the later silently reverts the earlier. Change 4 of the 2026-08-20 batch hit this twice, caught only because its own task 0.3 happened to warn. After §1a orders by dependency, list `openspec/changes/<name>/specs/` per in-scope change, report every capability touched by more than one, and make each such change's delta a **mandatory re-base check** against the live spec as of that moment before its review. Running it manually after the fact produced real information: changes 5, 6 and 7 each added exactly one brand-new capability, so they carried zero re-base risk. Closes GitHub issues #142, #99. | — |
| `live-spec-validate` (**D1**, #144) | `openspec validate <change> --strict` validates a **change**. Nothing validates the **live spec set** after it has been edited, so an ordinary prose edit under `openspec/specs/` can silently corrupt the parsed document. Evidenced by the 2026-08-23 chain: filling two live specs' TBD `## Purpose` left a **duplicated `## Requirements` heading** in each, which closes the section — every requirement in both specs became invisible to `validate`, `list` and `archive`. Both merged broken and it surfaced one whole change later, as an aborted archive. `openspec validate --specs --strict` already exists, needs no database and no build, and takes seconds; nothing runs it. Run it where the live spec set has just been written or edited: `spec-to-pr`'s Archive phase after the sync/archive completes (`references/archive.md` §1–2, 63 lines), and `multi-pr`'s per-change close-out (`references/change-loop.md` §Per-change loop) so a chain cannot carry a broken live spec into the next change. Record the rule it encodes: an edit to a live spec's prose is an edit to a **parsed document**, not a comment, and any hand-edit under `openspec/specs/` is followed by that command before the commit. **Scope guard:** this is the live spec set's own parse integrity after ANY edit, including edits that never touch a delta. The MODIFIED-block content half is D2 and is deliberately not in scope here. Closes GitHub issue #144. | — |

## Lane 2 items — a design question each

- **`A` — fix-brief and orchestrator-artifact trust** (#96, #121, #107, #112). One artifact, four
  ways a claim in it carried more authority than its evidence. #96: the brief binds the remedy, not
  the defect, so a compliant delegate can ship a regression that looks like success — the register's
  proposed format separates **binding defect** from **rejectable candidate remedy**, and changes the
  terminal contract to ask for proof the *defect* is gone. #121: the defect statement's own factual
  sub-claims (a type's field list, a signature, a line number) ship as ground truth — one asserted
  four required fields on `DeliveryPopulation` where the type carries three. #107: a fix the
  orchestrator specified skips the design-review scrutiny a delegate's fix gets; change 4's third
  round found two Criticals and both were in an orchestrator-directed fix, one of which reintroduced
  a bias the change's own `design.md` had explicitly rejected. #112: nothing marks a sub-agent's fact
  row as agent-reported versus orchestrator-verified, and a haiku `fact-gatherer` was wrong on
  load-bearing rows twice in one dispatch. **Design question:** the brief format itself — what binds,
  what is rejectable, what is checkable, and how a fact row's provenance is carried — as one design
  rather than four appended rules. Also whether the adjudication rule widens from "the orchestrator
  checks every ✗ row" to "re-measure any row a finding will depend on", which costs more per review.

- **`B` — delegate liveness and orchestrator interference** (#113, #115, #125). A delegate that
  backgrounds a ~300s gate and then stops sends a completion-shaped notification indistinguishable
  from a finish — four times in one chain, two returning verbatim "Standing by for the `npm run
  verify` completion notification". The orchestrator's natural next move, taking over the tree, is
  what produced the ~40-minute incident in #115: it ran `npm run verify`, `git checkout` and
  `git commit` in the same checkout while its own delegate was live, and then investigated the
  failures it had manufactured as a possible real regression. `spec-to-pr`'s "Concurrent runs"
  section (SKILL.md:159, `references/concurrent-runs.md`, 21 lines) covers two sessions sharing a
  clone and says nothing about the orchestrator versus its own delegate. #125 is the same layer: no
  standard language legitimising "stop rather than invent data", so the right call in the one run
  that got it right depended on the orchestrator typing that sentence into that task's brief by
  hand. All three land in `subagent-brief.md` §5 ("Done when — a condition you will check, with
  evidence", line 78) or the section beside it. **Design question:** whether long gates run
  synchronously by default — a cost every run pays — and what a terminal contract's *absence* obliges
  the orchestrator to do.

- **`C` — claim shapes under the grounding contract** (#124, #126, #118, #119, #109). Four issues
  each ask for a new numbered check in `review-change/references/checklist.md`, which already carries
  0a–0k across 316 lines before the overlay adds more. All four are instances of a rule its
  §"Grounding contract" (line 68) already states — a claim resolves to evidence or NOT-FOUND — applied
  to a claim shape nobody enumerated. The shapes: a demo/fixture state must be producible by the real
  code path over the real corpus (#124 — three requirements specified shapes the code cannot produce,
  one structurally impossible); a requirement citing a shipped precedent must be checked against that
  precedent and not be silently stricter (#126 — an over-strict provision made a change unbuildable);
  a "prevents this hazard" explanation names whether the guarantee is a **code** property or a
  **deployment** property, and if the latter, the trigger that changes it (#118); a
  compensating-coverage claim is verified rather than accepted, and a route-level exclusion enumerates
  the components it silently takes with it (#119 — "component-level axe assertions" turned out to be
  hand-written ARIA, and missed a real `wcag21a` violation). #109 rides along as one merge rule, not a
  claim shape: on a finding both reviewers report at different severities, the reviewer who read the
  implementation wins. **Design question:** extend the Grounding contract with a named list of claim
  shapes, or add 0l–0o as filed. The first covers instances nobody has filed yet; the second is what
  each issue literally asks for.

- **`D2` — wholesale `## MODIFIED Requirements` replacement** (#97). A MODIFIED block replaces the
  named requirement wholesale at sync/archive, so a live scenario absent from the delta is silently
  deleted. The consuming repo shipped this once already, dropping three live scenarios, caught by
  hand. A ~60-line script written during the 2026-08-20 chain flagged 2 items across two changes,
  both benign renames — and still earned its place, because a rename and a deletion are byte-identical
  to a naive diff and exactly one destroys a live `SHALL`. Two design notes learned the hard way:
  resolve `## RENAMED Requirements` **first**, and report ADDED counts alongside missing ones, since
  "live 2 → delta 4, +3" distinguishes a widening from a truncation instantly. **Design question:**
  #97's own proposed fix belongs in `openspec` tooling rather than this plugin — every repo using the
  workflow authors MODIFIED blocks the same way. The in-scope half has to be scoped before it can be
  built, and the alternative is reporting it upstream to `openspec` and adding nothing here.

- **`H` — Revise round 2 as default** (#106). Every change that reached a second Revise round found
  something new — not a leftover from round 1, but a defect round 1's fix introduced, or a sibling
  instance of the same defect round 1's fix missed. Two of four were the second shape. The proposal
  is to bias toward a second round and give it a distinct question: "does this fix introduce the
  defect it fixed, somewhere else? Enumerate every other instance of the resource or shape the fix
  concerns" — the framing that surfaced the `MATCH_ROW_LIMIT` regression. **Design question, and the
  reason this is last:** `--pr-rounds` already **defaults to 2** (`references/revise.md:5`), so the
  cap is not what ends Revise early — the exit gate at zero untriaged Critical/Important findings is.
  Making round 2 unconditional is a cost decision for every run, and the evidence is n=1 chain with
  3–4 data points, one still in flight when logged. A 100% hit rate across four changes is suggestive,
  not a base rate. **Recommendation: do not change the default until a second chain provides a second
  data point.** Encode the round-2 question now if anything; leave the default alone.

## Suggested order

~~Lane 1 first~~ — **done, shipped as #147–#150.** Remaining: **A → B** (serial, shared
`subagent-brief.md`), then **C**, then **D2**. **H** last, and probably not at all this pass.

**One Lane 1 outcome changes a Lane 2 assumption.** PR #149 rewrote `multi-pr` Phase 1, and PR #150
edited `spec-to-pr/references/archive.md`, `archive-preflight.md`, `change-loop.md`, `lite-pr` and
both orchestrator `SKILL.md` files. Lane 2's proposals are authored against **the tree those left**,
not against this document's description of it — which is this plan's own sequencing rule, applied to
itself.

Both guards F touches sit in one file, so F is one edit, not two — `_guard_areas()` (line 30) and
`test_no_batch_hardcodes_an_absolute_path` (line 229) in
`plugin-tests/tests/consistency/test_guards_have_mutant_batches.py`. Per CLAUDE.md check 4, F is a
fix to a guard: mutate what the fix touches and confirm a test fails. `mutants/` currently holds
`conformance/`, `consistency/` and `release/` — `hooks/` is un-adopted, which is the state #138
describes.

## Next step

`/cla:multi-lite` on this doc's Lane 1 table, one PR per candidate. Then `/cla:multi-spec` for
Lane 2. No candidate merges another; each closes its own GitHub issues via `Closes #N` in the PR
body.
