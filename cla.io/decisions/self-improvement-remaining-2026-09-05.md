# Self-improvement loop — what is left

Written 2026-09-05, after the analysis of CLA's self-improvement capability across
seven repos and the first slice shipping as PR #223.

**Note on where this lives.** CLAUDE.md says deferred work belongs in GitHub issues,
not a file — `TODO.md` was retired on 2026-08-28 for that reason. This doc is a plan
for one program of work, kept in `decisions/` alongside the other shaped-decision
docs. Anything here that becomes standalone deferred work should be filed as an
issue rather than left to rot in this file.

---

## The intent, restated

Build a self-improving capability at two levels: the whole Claude Code session, and
each frequently-used skill. Both halves already exist and neither is whole.

| level | mechanism | state |
|---|---|---|
| session | `codify-learnings` | runs; 48 entries across repos; produces real artifacts |
| per-skill | `codify-retro`, `spec-to-pr-retro` | cover 2 of the 4 skill groups actually used |
| — `lite-pr` | none | no ledger, no retro, used in all six repos |
| — `shape-decision`, `feedback` | none | no ledger, no retro |

A third mechanism nobody named: the 10 guard hooks. They are the only part that
improves anything without being invoked.

## The central finding, unaddressed by anything shipped so far

**Both loops measure whether they WROTE something, never whether the thing WORKED.**

- Re-offenses across nine `codify-learnings` runs: 1, 2, 5, 2, 3, 1, 3, 3, 2 — flat.
- One lesson failed at three separate escalation rungs, including a downgrade.
- Another defeated the hook built for it, six days after that hook shipped.
- Fleet-wide: **219 suggestions proposed, 219 applied, 0 rejected** across 52 runs in
  five repos. The apply gate has never once said no. The user's own account: waved
  through.

`apply_rate: 1.0` is therefore not a quality signal. It is the absence of a
measurement, reported as a perfect score.

---

## Status of the seven proposals

| # | proposal | status |
|---|---|---|
| 1 | Validate records at write time | **dropped at review** — see below |
| 2 | Aggregate across repos | **done** — PR #223 |
| 3 | Close on outcome, not output | not started |
| 4 | Make the apply gate real by shrinking it | not started |
| 5 | Delete heuristics that cannot fire, and unread fields | not started |
| 6 | Decide about `commit-provenance`: give it a reader or delete it | not started |
| 7 | Cover `lite-pr`, `shape-decision`, `feedback`; onboard the two empty repos | not started |

### 1 — why it was dropped, so nobody re-proposes it unchanged

A writer-side canonical-shape check was authored and killed at review on two counts:

- **No conforming record was producible.** Every producer is prose in a `SKILL.md`,
  and the change scoped those out, so the check would have quarantined 100% of
  records in every repo — permanently, not on day one.
- **It could not catch its own motivating defect.** The cited failure was `phases`
  written as an object instead of an array. A top-level key check sees the key
  present either way.

Any revival must include the producer recipes in the same change, and must check
value shape rather than key presence.

### 3 and 4 — the two that answer the original question

Neither depends on anything shipped.

**3 — close on outcome.** `codify-learnings` Step 2.5 already classifies every prior
artifact as prevented / re-offended / n-a, then discards the result. Recording it is
one field on the run record. That is the cheapest available fix for the thing this
whole analysis is about: it turns the loop from counting what it wrote into
measuring whether the writing worked.

**4 — shrink the gate.** More ceremony will not help a gate that is waved through at
the end of a long session. Fewer suggestions at a higher bar will. Cap the count and
make rejection the expected outcome for anything not tied to a concrete failure in
that session.

### 5 — the dead weight, measured

Of 31 interpretation heuristics across the two retro skills, **4 could fire on real
data**. Three read fields the aggregator has never emitted. The rest sit below their
own thresholds or are computed and never read.

### 6 — the biggest untapped signal, or the biggest exhaust pile

`commit-provenance.jsonl` holds 257 rows across four repos, written automatically by
a hook at zero cost in attention — roughly 15x the manual ledgers. **No skill reads
it.** By this repo's own rule an unread ledger is exhaust. It is either the best
signal available or the largest pile of waste, and it cannot be both.

### 7 — the coverage gap

`lite-pr`, `shape-decision` and `feedback` are all on the frequently-used list and
have no run data at all. Two of six repos have no self-improvement data: `verto-ai`
has no `cla.io/retro/` at all, `future-champs` was scaffolded and never written to.

---

## Residue from the shipped slice

- **PR #224 open** — the interpreter-probe cache. Unrelated to this program; came out
  of a `/doctor` run. Ready to merge.
- **Three git stashes**, oldest first:
  - `stash@{2}` 192-run ledger rows preserved before an archive
  - `stash@{1}` WIP on the junction fix
  - `stash@{0}` orphaned provenance rows after the PR #223 squash-merge
  Each needs a decision: apply, or drop.
- **The uncommitted `commit-provenance.jsonl` row** in the working tree, which the
  hook regenerates on every commit. Related to open issue #219.

## Findings raised in review and deliberately not fixed

None is a crash or silent data loss. Listed so they are not rediscovered:

- `found` / `phantom` coercion failures in `revise_findings_by_tier` reach no counter.
- `version_bumped`, `trimmed`, `process_issue` and `verified_claims_count` drop
  non-conforming values with no warning and no tally.
- `mutate.py`'s environment allowlist omits `PYTHONUTF8` / `PYTHONIOENCODING`;
  untested rather than proven safe.
- The `PYTHONWARNINGS` claim in `mutate.py`'s comment ships unmeasured beside three
  measured siblings.
- `codify-retro/SKILL.md` asserts the effectiveness heuristics are fleet-safe without
  arguing why pooled `re_offenses` counts mean anything across repos.

## Suggested order

1. **3 + 4 together.** They are the intent, they are small, and they need nothing else.
2. **6.** A decision, not a build. Answering it either unlocks 257 rows or deletes a
   liability.
3. **5.** Pure subtraction; makes the retro reports readable.
4. **7.** Widens the data once the readers are worth feeding.
5. **1**, only if 3 and 4 leave a real need, and only with the producers in scope.
