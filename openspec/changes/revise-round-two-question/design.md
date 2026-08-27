## Context

Item **H** of `cla.io/decisions/open-issues-2026-08-24.md` (GitHub #106) proposes two things at once:
give a second Revise round its own question, and make a second round the default. They are bundled
because they came from the same observation — four changes reached a round 2 and all four found
something — but they are not the same kind of proposal. One is a paragraph of prose in a file that
round already reads. The other is a cost every run pays, forever, on an n=1 chain.

Current state, measured 2026-08-25 from the repo root:

```
grep -n 'pr-rounds' .claude/plugins/cla/skills/spec-to-pr/references/revise.md \
                    .claude/plugins/cla/skills/spec-to-pr/SKILL.md
    → revise.md:5   "Cap: `--pr-rounds N` (default `2`)."
      SKILL.md:329  same sentence in the Revise stub
      SKILL.md:375  per-loop caps table row: pr-review | 2 | --pr-rounds N
      SKILL.md:378,382  the --review-rounds/--pr-rounds disambiguation note

grep -n 'Exit gate\|un-triaged\|Round N (N' .../references/revise.md
    → :68  "## Round N (N ≥ 2)"
      :134 "4. **Exit gate.** Count *un-triaged* Critical and Important findings
            (Applied and Deferred-Known-Issue both count as triaged). If 0 untriaged
            → status `ok`, exit loop."

wc -l .../spec-to-pr/references/revise.md .../spec-to-pr/SKILL.md \
      .../_shared/references/run-log-schema.md
    → 135, 431, 177

python -c "import json; recs=[json.loads(l) for l in open('cla.io/retro/spec-to-pr-runs.jsonl')]; \
  print(len(recs), sum(1 for r in recs for p in r['phases'] \
  if p['name']=='Revise' and 'findings_by_round' in p))"
    → 3 0        (3 logged runs; 0 carry round-attributed findings)

Revise rounds_used / rounds_cap across those 3 records:
    remove-update-cla                1 / 2
    decouple-skills-from-dev-assets  2 / 2
    extract-dev-tree-from-plugin     2 / 2
```

Three constraints bound everything below.

**The cap is not the thing that ends Revise.** `--pr-rounds` defaults to `2`, so a run that stops
after one round did not hit a cap. Step 2 of §"For each round" requires every Critical and Important
finding to be triaged into Applied or Deferred-Known-Issue **in the round that surfaced it**; step 4
then counts *untriaged* findings and exits at zero. Step 5 says so outright — cap exhaustion is
"the only scenario where untriaged residue exists — step 2's rule otherwise prevents it". So as
literally written, the untriaged count is zero by construction at the end of round 1 and the loop
exits there; the default cap of `2` is a ceiling that ordinarily never binds. Anyone reasoning about
this item from the cap alone is reasoning about the wrong control.

**Practice already diverges from that text, and the divergence is data, not noise.** Two of the three
logged runs used two rounds. The §"Round N (N ≥ 2)" section exists and scopes a second round to the
previous fix commit's diff, which only makes sense if a second round is expected to happen. So the
skill contains both a gate that closes after round 1 and a section describing what round 2 does, and
nothing reconciles them. This change states the gate accurately and deliberately does not move it —
resolving the divergence in either direction is a default change, which is what the decision declines.

**The ledger cannot currently settle the question.** `routing.revise_findings_by_tier` counts
Critical+Important findings **per agent, summed across every round**, and the `Revise` phase object
records `rounds_used` but nothing about what any particular round found. Reading all three records
tells you a second round ran twice; it does not tell you whether either second round found anything.
The four data points behind item H exist only in a run-notes file and in the memory of the chain that
produced them.

## Goals / Non-Goals

**Goals:**

- Give round N ≥ 2 a framing question that differs from round 1's, in the file the round reads, with
  an enumeration obligation rather than a re-read suggestion.
- State what actually ends the Revise loop, at the two places that currently name only the cap, so
  `default 2` stops reading as a promise of two rounds.
- Leave the declined half of #106 with a reversal condition someone can check against the run ledger
  rather than re-argue, which means logging the number that would settle it.

**Non-Goals:**

- **The `--pr-rounds` default does not move**, and neither does the exit gate's threshold. Nothing
  here makes a second round more likely to run. `/cla:spec-to-pr` runs exactly as many Revise rounds
  after this change as before it; what changes is what a round ≥ 2 asks when one happens.
- **No reconciliation of the gate-versus-§Round-N divergence.** It is named in this design and stated
  in the skill, and left as it is. Closing it upward (round 2 always runs) is the default change;
  closing it downward (round 2 never runs) deletes a behaviour two of three logged runs performed.
- **Nothing consumes the new ledger field automatically.** No metric in
  `spec-to-pr-retro/scripts/spec_to_pr_aggregate.py`, no new report row. The field is written so a
  human can answer one question over a handful of records; building an aggregator metric for a
  question with three records behind it is the same over-build this change declines elsewhere.
- **No new agent, script, or hook.** Every mechanism here is prose in a file already read at the
  moment it binds, plus one documented JSON field.
- **Not the brief format.** `subagent-brief.md` and `review-change/references/checklist.md` belong to
  sibling changes in this batch and are not opened here.

## Decisions

### Decision 1 — Round N ≥ 2 asks a named, different question

Round 1 asks whether the diff is correct. Round 2 currently asks the same thing over a smaller diff,
which is why it is easy to read as a formality. The question that actually earned its rounds is
narrower and adversarial toward the previous round's own fix:

> Does this fix introduce the defect it fixed, somewhere else? Enumerate every other instance of the
> resource or shape the fix concerns.

The framing is placed in §"Round N (N ≥ 2)" of `revise.md`, where the round's dispatch is already
being assembled, and mirrored as one line in `SKILL.md`'s Revise stub — the stub is required to stay
self-sufficient when the reference is not reloaded, and the load-bearing half of this is the
enumeration, which a reader will not reconstruct from "review the fix diff".

**Enumeration, not re-reading, is the load-bearing part.** The precedent behind the framing is the
`MATCH_ROW_LIMIT` regression: round 1 fixed a count-vs-match divergence, round 1's own fix added a
safety cap, and the cap silently recreated the same divergence at a second site. No amount of
re-reading the fix hunk finds that; only listing every other place the same resource is counted or
matched does. So the round's dispatch prompt must carry a list of the other instances and a verdict
per instance, and an empty list is a stated result ("no other instance exists") rather than a
skipped step — the same reasoning the deferred-findings sections already use for their mandatory
`(none)`.

**That precedent is not re-derivable from this repo.** `git log -S'MATCH_ROW_LIMIT' --all --oneline`
returns only planning documents quoting the case second-hand — the fix itself lives in a consuming
repo's history. (Stated without a count on purpose: an earlier draft said "exactly two commits", and
the commit carrying that sentence quoted the token and made it three. A count of matches for a
string is falsified by writing it down.)

So the question was tried against a fix from **this** repo's record instead. **What follows is a
walk-through, not a test, and the difference matters enough to state before the result.** It was
written by someone who already knew which site the later round found, and who chose how to frame the
resource. A trial that cannot fail establishes less than its author wants it to.

**The case: `lint_profile`, recorded in `cla.io/lessons-learned/lessons-learned.md` and in
`CLAUDE.md`'s pre-ship checks.** A round-2 fix corrected the function's no-overlay return path,
which had returned `()` for args and made the hook a silent no-op in every JS repo. Round 3 then
found that the same fix had moved the identical no-op to the **overlay** path.

Applying the enumeration obligation as worded — *enumerate every other instance of the resource or
shape the fix concerns* — the resource is the return paths of `lint_profile` that yield the args
tuple. The site the later round found is among them, so the wording reaches the shape it was written
for.

**The walk-through's first draft got its own enumeration wrong, and that is the most useful thing it
produced.** It listed two paths, the no-overlay one and the overlay one. `git show
0a55138:.claude/plugins/cla/hooks/warn-lint-on-edit.py` shows **three**: no-overlay, the
half-configured-overlay fallback, and the valid overlay. An enumeration written by the author of the
enumeration rule, over a function whose whole point was a missed second path, missed a third. That
is a stronger argument for the rule than the tidy version was — and a direct argument for the
citation requirement, since a list nobody can see the search behind is a list nobody can check.

**What this does not establish.** The case is weaker as a precedent than it first looked. PR #41 is a
single squash commit, so the round-2 and round-3 intermediate states are not in this repo's history
either — the record is a lessons-learned narrative, the same second-hand status that disqualified
`MATCH_ROW_LIMIT` above. The function was later deleted from the tree entirely. So: the question's
wording has been walked against one real shape with a known answer, and nothing more. The evidence
that it works on an unknown answer can only come from a round that runs it.

**Rejected alternative — fold the question into the round-1 prompt.** Round 1 has no previous fix to
be adversarial about; the question is literally unanswerable there. Asking it anyway trains the
reader to skim it, which is how a mandatory field becomes decorative.

**Rejected alternative — make it a new checklist item in `review-change/references/checklist.md`.**
Wrong phase and wrong file. The checklist reviews artifacts before implementation; this question is
about a fix commit that exists only after Ship. The checklist is also a sibling change's territory
in this batch.

### Decision 2 — State the exit gate where the cap is named, and change neither

Both places that currently say `Cap: --pr-rounds N (default 2)` gain a clarifying half-sentence: the
loop ordinarily ends at the exit gate, not at the cap, because step 2 requires every Critical and
Important finding to be triaged in the round that surfaced it. Step 4's own text gains the same
observation, phrased as what the count means rather than as a new rule.

This is a documentation-accuracy change with no behavioural effect, and it is in scope because the
decision this change implements is *about* the cap and would be misread without it. It is also the
cheapest available protection against the specific error the decision warns of: reading `default 2`
as evidence that two rounds already happen, and concluding that item H is asking for nothing.

**Rejected alternative — change the gate so a fix commit's own diff always earns a round.** That is
the default change, wearing a different hat. It makes round 2 unconditional for every run that fixes
anything in round 1, which is nearly every run with findings, at exactly the per-run cost the
decision declines to pay on this evidence.

**Rejected alternative — say nothing and let the divergence stand.** The divergence is what makes
this item hard to reason about; leaving it undocumented guarantees the next pass re-derives it.

### Decision 3 — The default stays at 2, with a stated reversal condition

The decision's recommendation is adopted verbatim: **do not change the default until a second chain
provides a second data point.** The reasoning, restated so it survives without the decisions doc:
four changes reaching round 2 and all four finding something is a 100% rate on a denominator of four,
drawn from a single chain, with one of the four still in flight when it was logged. It is suggestive.
It is not a base rate, and a default is priced against a base rate.

The change therefore states the deferral in the requirement itself rather than leaving it as an
absence, and names what would end it.

**The reversal condition, and why it needs a field first.** The condition is: round-attributed Revise
findings exist in `cla.io/retro/spec-to-pr-runs.jsonl` for **at least two distinct chains** and **at
least eight changes** in which a round ≥ 2 ran, and across those, a round ≥ 2 surfaced at least one
Critical or Important finding on a **majority** of them. The two-chain floor comes straight from the
decision. The eight-change floor and the majority bar are **stated judgements, not measurements** —
they are the smallest denominator on which a per-run cost argument is worth re-opening, and they are
written down so the next pass argues with a number instead of inventing one.

That condition is **not checkable today, and that is itself a finding.** Measured 2026-08-25:

```
python -c "import json; recs=[json.loads(l) for l in open('cla.io/retro/spec-to-pr-runs.jsonl')]; \
  print(len(recs), sum(1 for r in recs for p in r['phases'] \
  if p['name']=='Revise' and 'findings_by_round' in p))"
    → 3 0
```

Three records, none round-attributed. `rounds_used` says a second round ran; nothing says what it
found. So the field is added here, in this change, rather than left to a follow-up — a deferral whose
evidence is not being collected is not a deferral, it is a decision made by default, and this change
would otherwise ship a reversal condition that can never be met.

**Rejected alternative — defer the field too, and reconstruct the numbers from run-notes files.**
The 2026-08-23 chain's numbers survive in `cla.io/retro/multi-pr-run-notes-2026-08-23.md` because
someone wrote prose that day. That is not a mechanism; it is a habit, and it is the habit that
produced "four data points, one still in flight" as the entire evidence base for this item.

**Rejected alternative — a new aggregator metric in `spec_to_pr_aggregate.py`.** The script earns its
place by counting over 40–130 records; this question has three. A `python -c` one-liner over the
ledger answers it, and the script would have to be maintained for a metric read once.

### Decision 4 — Field shape: per-round counts on the Revise phase object

```json
{"name": "Revise", "status": "ok", "rounds_used": 2, "rounds_cap": 2,
 "agents": ["code-reviewer", "silent-failure-hunter"],
 "findings_by_round": [{"round": 1, "found": 9, "sibling_instance": 0},
                       {"round": 2, "found": 2, "sibling_instance": 1}]}
```

One entry per round actually dispatched, in round order. `found` is that round's Critical+Important
count **after triage dedup** — the number of distinct findings the round put into Applied or
Deferred, matching what step 1 of §"For each round" already aggregates. `sibling_instance` is the
subset of `found` that answers the round-2 question affirmatively: a defect the previous round's fix
introduced, or a sibling instance the previous round's fix missed. It is `0` on round 1 by
construction, since round 1 has no previous fix.

**`found` here is deliberately NOT expected to equal the sum of `revise_findings_by_tier`'s per-agent
`found`.** The per-agent field credits the same underlying finding to every agent that surfaced it,
so its sum over-counts relative to a deduplicated round total. Stating a cross-field equality here
would plant an invariant that is false the moment two agents agree — which is the common case, and
which SEV-MAX exists to handle. The schema note must say this explicitly, because "these two fields
both say `found`" is exactly the kind of assumed identity a later reader will act on.

Additive and optional: `log_run.py` validates only the ledger filename shape, UTF-8 decoding, that
the top level is a JSON object, and the 4 KiB atomic-append ceiling — it has no field allowlist, so
no script changes. `spec_to_pr_aggregate.py` reads phase fields by name via `.get()`, so an unread
field is ignored rather than counted as producer drift. Records written before this change stay
valid with the field absent, and absent is distinguishable from "a round found nothing" (which is an
entry with `found: 0`).

**Rejected alternative — a flat pair of scalars (`later_round_found`, `later_round_sibling`).**
Cheaper to write and it loses the round index, so a three-round run collapses into one bucket and the
question "did round 3 still find things" cannot be asked without a schema change. The array costs a
few dozen bytes against a 4 KiB ceiling that a counts-only record is nowhere near.

**Rejected alternative — attribute findings by round inside `revise_findings_by_tier`.** That field
is pinned per-agent by a dated schema pin (2026-07-18) precisely because it has already been through
two incompatible shapes, and the aggregator now bucket-counts anything that is neither the per-agent
shape nor a recognised legacy shape as malformed drift. Adding a round dimension to it would trip its
own drift detector on every record.

## Pinned implementation parameters

Nothing below is decided during implementation.

**The round-2 question, verbatim.** This exact sentence pair, as a quoted block in
`revise.md` §"Round N (N ≥ 2)", and the same two sentences in the `SKILL.md` Revise stub line:

> Does this fix introduce the defect it fixed, somewhere else? Enumerate every other instance of the
> resource or shape the fix concerns.

**The enumeration obligation, verbatim** (the sentence that follows the question in `revise.md`):

> The enumeration is the deliverable, not the re-read: the round's dispatch names every other
> instance of that resource or shape and states, per instance, whether the defect is present there.
> An empty enumeration is a stated result — "no other instance exists" — never a skipped step.

**Where each edit lands** (located by content at implementation time, not by these line numbers):

| File | Site | Edit |
|---|---|---|
| `spec-to-pr/references/revise.md` | §`## Round N (N ≥ 2)` | the question + the enumeration obligation |
| `spec-to-pr/references/revise.md` | the `Cap:` line | the exit-gate clarification |
| `spec-to-pr/references/revise.md` | §`For each round` step 4, `**Exit gate.**` | what the untriaged count means at the end of round 1 |
| `spec-to-pr/SKILL.md` | Revise stub, the `Cap:` sentence | the same clarification |
| `spec-to-pr/SKILL.md` | Revise stub, invariant bullets | one bullet carrying the question + enumeration |
| `_shared/references/run-log-schema.md` | `Revise` phase object + its field notes | `findings_by_round` |

**Round-cap values that MUST be unchanged after implementation:** `--pr-rounds` default `2`,
`--review-rounds` default `1`, `--test-rounds` default `3`. The per-loop caps table in `SKILL.md`
keeps its numbers exactly.

**Ledger field name and shape:** `findings_by_round`, on the `Revise` phase object, an array of
`{"round": N, "found": N, "sibling_instance": N}` in round order, one entry per dispatched round.
Optional; absent on records written before this change.

**`sibling_instance`'s definition, verbatim** (for the schema note):

> Of that round's `found`, how many were the shape the round-≥2 question targets: a defect the
> previous round's fix introduced, or a sibling instance of the defect the previous round's fix
> missed. `0` on round 1, which has no previous fix.

**The reversal condition, verbatim** (for the requirement and the schema note):

> Revisit the `--pr-rounds` default when `findings_by_round` covers at least eight changes across at
> least two distinct chains in which a round ≥ 2 ran, and a round ≥ 2 surfaced at least one Critical
> or Important finding on a majority of them.

**The stated non-equality** (for the schema note): `findings_by_round[*].found` is a deduplicated
per-round total and is NOT expected to equal the sum of `routing.revise_findings_by_tier[*].found`,
which credits one finding to every agent that surfaced it.

**Consistency with the sibling change.** `fix-brief-binding-defect`'s design states that an
orchestrator-specified remedy does **not** force an extra round and that "round counts stay as they
are… whether Revise round 2 becomes the default is a separate decision item with its own cost
argument". This change is that item, and it reaches the same conclusion: the default does not move.
A reader of both sees one position. The implementation must not let either change's edits imply the
other raised a cap.

## Risks / Trade-offs

- **A question nobody reads is worth nothing, and round 2 may rarely run under the current gate** →
  accepted knowingly. Two of the three logged runs did run a round 2, so the framing lands on real
  rounds today; and if the ledger later shows round 2 almost never running, that is itself the answer
  to item H, arrived at by measurement instead of by a default change. This is the honest form of the
  trade: the cheap half ships now, the expensive half waits for the number that prices it.
- **`sibling_instance` is a judgement call made by the same orchestrator that wrote the fix** → true,
  and it is the same producer-honesty assumption `revise_findings_by_tier`'s `phantom` count already
  runs on. Mitigated only by the definition being pinned narrowly enough to be arguable: "introduced
  by the previous fix, or a sibling the previous fix missed" is checkable against the fix diff by
  anyone re-reading the round.
- **The eight-change / majority threshold is a judgement, not a measurement** → said so, in the design
  and in the requirement, rather than dressed as derived. The two-chain floor is the decision's own
  and carries its authority; the rest is a starting number for the next argument.
- **Adding a ledger field that nothing aggregates can rot** → the field is small, optional, and its
  one consumer is a documented one-liner. If the reversal condition is met and the default moves, the
  field's purpose is discharged and it can be retired with the same edit.
- **Two changes in this batch edit §"Round N (N ≥ 2)"** → both add paragraphs; neither rewrites the
  section. This change edits last and its implementation re-locates the section by content, so it
  appends after whatever the sibling left rather than against a remembered line number.
- **Synced-core portability** → all three files ship verbatim to consuming repos. No repo token, no
  dev-tree path, no absolute developer path may enter the added prose; the ledger path is named as
  `cla.io/retro/spec-to-pr-runs.jsonl`, which is the portable per-repo location the schema already
  documents. The existing conformance scan over synced core is the check.

## Open Questions

- **Should the exit gate itself distinguish "no untriaged findings" from "no unreviewed diff"?** The
  divergence in Context is real and this change does not close it. Closing it is a default change,
  which is deferred with the rest of item H; the `findings_by_round` data is what would inform it.
- **Does the round-≥2 question generalise to `/cla:lite-pr`'s single fix round?** Not investigated.
  `lite-pr` runs one review pass with a single fix round and has no round 2 to ask a different
  question in, so there is nothing to attach it to today; if the default ever moves, this is the
  second place to look.
