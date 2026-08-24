## Context

`openspec` applies a `## MODIFIED Requirements` block by **replacing** the named requirement in
`openspec/specs/<capability>/spec.md` with the block's contents. It is not a merge. A scenario
present on the live requirement and absent from the delta is therefore deleted, and no tool reports
it. GitHub issue #97 records the failure shipping once in a consuming repo — three live scenarios
dropped from one block, caught by hand — and one change in the 2026-08-20 chain carrying **six**
MODIFIED blocks across six capability specs, which is where hand-diffing stops happening in
practice.

**The fork this design has to settle first.** #97's own proposed fix is a refusal inside
`openspec archive`/`sync`. That is `openspec` tooling. This plugin does not own it, cannot ship into
it, and every repo running this workflow authors MODIFIED blocks the same way — so the argument for
"report upstream and add nothing here" is real and had to be answered rather than assumed away.

**The tree as it stands 2026-08-25** (measured; commands in `tasks.md` §1), after PRs #149 and #150
landed:

| file:line | what it establishes |
|---|---|
| `multi-pr/references/discover-and-gate.md:62–70` | Every in-scope change carrying a MODIFIED block earns a re-base check against the live spec "as of that moment". A **trigger with no procedure** — the instruction is the word "diff" |
| `review-change/references/checklist.md:223` | Spec-reviewer dispatch item 5: a MODIFIED entry "must include the full final requirement text plus its scenarios". States a completeness property the reviewer cannot falsify from the delta alone |
| `multi-spec/references/authoring-brief.md:30` | The author-side rule: read the active spec, copy every scenario. Correct, and it is a rule given to the writer, not a check |
| `spec-to-pr/references/archive-preflight.md:65–79` | Check (c): every delta MODIFIED **heading** exists verbatim in the active spec. Heading only, and it says so |
| `openspec/specs/cla-plugin/spec.md:519–529` | PR #150's live-set validation. Line 529 explicitly disclaims this concern: parse integrity after any edit vs. content dropped through a delta |
| `multi-pr/references/change-loop.md:93` | Repeats that disclaimer at the step 4b site |

Two of those are load-bearing for scoping. The requirement at :519 **names this change's problem and
excludes itself from it in its own text**, so there is no overlap to argue about — it was settled by
the author of #150, not by this proposal. And #149 already supplies the chain-path trigger, which
makes the surviving gap materially smaller than #97 describes.

## Goals / Non-Goals

**Goals:**

- Define the retention comparison once, executably, in a place more than one skill reads.
- Carry the two design notes #97 paid for: resolve `## RENAMED Requirements` **first**, and report
  **ADDED counts alongside missing ones**.
- Give the single-change path (`/cla:spec-to-pr` alone, `/cla:lite-pr`, a hand-authored change) a
  trigger, since it passes through `multi-pr` Phase 1 never and is checked nowhere today.
- Make the flag-and-adjudicate contract explicit, including its expected false positives.
- Record the upstream half as forwarded, not dropped.

**Non-Goals:**

- **No script.** See D2.
- **No enforcing gate inside `openspec archive`/`sync`.** That is #97's own fix and it is upstream.
  Nothing here refuses, blocks, or auto-corrects a delta.
- **No new numbered check (`0l`, `0m`, …) in `review-change/references/checklist.md`.** See D7.
- **Not parse integrity.** PR #150 owns that; this change does not touch `openspec validate --specs`
  or any of its call sites.
- **Not the capability-overlap matrix.** PR #149 owns when the chain-path check fires; this change
  supplies only what it does when it fires.
- **No detection of a scenario whose WHEN/THEN body was silently gutted while its heading survived.**
  Heading-set comparison cannot see it. Stated as a known blind spot rather than implied away.

## Decisions

### D1 — There is an in-scope half, and it is the procedure, not the enforcement

**Decision.** Reject "report upstream and add nothing here". Accept that the enforcement half is
upstream.

The plugin does not own the apply step, so it cannot refuse a lossy sync. It *does* own four places
where it already instructs a skill to perform this comparison, and it defines the comparison in none
of them. `discover-and-gate.md:66` says "diff its delta against the live spec"; that sentence is the
entire specification. An undefined diff is precisely what #97's evidence indicts — run without
rename resolution and without added counts, the only real execution of it produced 2 flags and 2
false positives.

**Alternative considered — report upstream, add nothing.** Rejected on three grounds. (i) It leaves
`discover-and-gate.md`'s existing obligation unexecutable, which is worse than absent: a stated check
that cannot be performed correctly reads as coverage. (ii) The upstream fix, if it lands, lands on a
version of `openspec` a consuming repo may not be running for a long time; the plugin's own
instructions are what its skills follow today. (iii) The two design notes are knowledge this repo
paid for and would lose — they are about how to *read* a delta, not about how `openspec` should
behave. **The upstream half is still reported** (`tasks.md` §6), so this is not a substitution.

**Alternative considered — `/cla:report-upstream`.** That skill files against *this* repo from a
consuming repo. #97 is already filed here. The remaining forward is to `openspec`'s own tracker,
which is a human action outside this plugin's tree and is carried as a task, not a requirement.

### D2 — A shared reference in prose, not a script

**Decision.** One markdown reference. No Python.

`CLAUDE.md` §"Every script, and why it exists": a script earns its place only by doing something a
direct command plus a sentence of prose cannot do reliably. The comparison is two heading
enumerations and a set difference; `archive-preflight.md` check (c) already performs the
heading-level version of it with two greps. Scoping `#### Scenario:` lines to their owning
`### Requirement:` block is the one awkward part, and it is awkward, not unreliable — the reference
pins a recipe for it.

**Alternative considered — port the ~60-line script from the consuming repo.** Rejected. It is the
strongest single argument against this decision: the script exists, works, and was written precisely
because the manual rule stopped being followed at six MODIFIED blocks. Three reasons it still loses.
(i) A parser of the delta format shipped from this plugin *is* the thing #97 says belongs in
`openspec` — building it here entrenches the duplication the issue asks to remove. (ii) A script that
flags and cannot adjudicate adds a run step without removing the human step, and the adjudication is
the expensive half (D5). (iii) It is the standing preference in this repo — prose over machinery,
and a guard's firing count is asked for before the guard is defended. This one's measured firing
count is 2, both false positives.

**Reversal condition, stated so this is falsifiable rather than a taste:** if a later chain records
the comparison being skipped or performed wrongly at three or more MODIFIED blocks, the prose has
failed and a script is the answer. `tasks.md` §6 records where that evidence accumulates.

### D3 — Home is `skills/_shared/references/`

**Decision.** `skills/_shared/references/modified-block-retention.md`.

Per `CLAUDE.md`'s layout note, `_shared/references/` holds "references two or more skills read as
authority". Four skills bind this one: `review-change`, `spec-to-pr`, `multi-pr`, `multi-spec`.

**Alternative considered — put it in `review-change/references/` and point the others at it.**
Rejected: a cross-skill reference living inside one skill's directory makes that skill's ownership
look like precedence, and `spec-to-pr`'s archive-time use is not a review.

**Alternative considered — restate it at each of the four sites.** Rejected outright; that is how
this repo produced three wrong copies of one correct rule before.

### D4 — Three binding sites, deliberately, because they close different windows

**Decision.** Bind at `review-change` (dispatch item 5), `archive-preflight` (check (c)), and
`multi-pr` (the existing re-base check).

They are not redundant placements of one check; each is the only cover for a distinct window:

| site | window it covers | what it costs |
|---|---|---|
| `review-change` item 5 | Authoring error in **any** path, caught pre-implementation, when the delta is still cheap to fix | One live-spec read per MODIFIED requirement, inside a dispatch already reading the delta |
| `archive-preflight` (c) | Everything after review — a Revise-round delta edit, a hand-resolved merge conflict in the delta — and the last moment before materialization deletes anything | One grep per MODIFIED heading, inside a loop that already runs |
| `multi-pr` re-base check | The **baseline moving**: a sibling, an archived change from a previous chain, a `/cla:lite-pr` landing in between. A correct delta going stale, which neither of the above is looking for | Already in the flow; this change replaces "diff" with the procedure |

**Alternative considered — review-time only.** Rejected: it cannot see a delta edited after review,
and the archive placement is one line inside an existing loop.

**Alternative considered — archive-time only.** Rejected: it fires when the PR is reviewed and about
to merge, so a real hit costs a re-review. Cheapest detection is not the last one.

### D5 — Flag and adjudicate; never refuse

**Decision.** Every hit is reported for adjudication with exactly three verdicts — `renamed`,
`intentionally removed`, `dropped` — and only `dropped` is a finding. Nothing in this change refuses
a delta, edits one, or halts on a hit alone.

The evidence is the sharp part, and it is sharper than the decision doc's summary of it. #97 records
2 flags, both benign renames. **Resolving `## RENAMED Requirements` first removes exactly one of
them:**

- `anaf-tax-debt-list` — a MODIFIED **requirement name** absent from the live spec because a sibling
  `## RENAMED Requirements` block in the same file renamed it. Requirement-level. Rename resolution
  removes this false positive entirely.
- `company-events` — a live **scenario heading** absent from the delta because the scenario was
  renamed in place to widen its scope. Scenario-level. `## RENAMED Requirements` maps requirement
  names, not scenario names, so **no amount of rename resolution catches this one.**

A scenario renamed in place and a scenario deleted are byte-identical to any heading comparison, and
exactly one destroys a live `SHALL`. That is a permanent property of the format, not a gap in the
procedure — so a residual false-positive rate is designed in, and a guard that refused on a hit would
refuse on a legitimate rename. The requirement is written so that flagging both and making a human
adjudicate is the *correct* behaviour, not a tolerated weakness.

**Task-list note carried from this:** the brief for D2 in `cla.io/decisions/open-issues-2026-08-24.md`
compresses this to rename resolution being "what produced both false positives". The source (#97,
design note 1) attributes it to `anaf-tax-debt-list` only. The source wins; `tasks.md` §1 re-derives
it rather than trusting either summary.

### D6 — Report both directions, in one line, always

**Decision.** Every compared requirement reports, whether or not anything is missing.

The pinned shape is below. The reason it is both directions is #97's design note 2: `live 2 → delta
4, +3` distinguishes a widening from a truncation instantly, and a missing-only report does not — a
reader seeing "1 scenario missing" cannot tell a deliberate restructuring from a deletion without
opening both files, which is the work the report exists to save.

The **always** half is this repo's own rule about denominators, already stated at
`discover-and-gate.md`'s capability matrix: a zero that does not carry what it scanned is
indistinguishable from a scan that did not run. A clean requirement reports `live 4 → delta 4 (+0
added, -0 missing)`, not silence.

### D7 — Edit dispatch item 5; add no numbered check

**Decision.** The `review-change` binding rewrites item 5 of the spec-reviewer dispatch prompt
(Step 4, line 223 of 316). It adds no `0l`/`0m` entry to the `0a–0k` orchestrator list.

Two reasons, and the second is the weaker one. (i) Item 5 **already states this rule** and is simply
unfalsifiable as written — a delta carrying 3 of 5 live scenarios satisfies "full final requirement
text plus its scenarios" on its face. Fixing the existing sentence is a smaller and truer edit than
adding a check beside it. (ii) The sibling change `grounding-contract-claim-shapes` claims `0l`;
adding a numbered check here would collide in a file both changes edit. Reason (i) would hold alone.

## Pinned implementation parameters

Every value below is a decision, not a placeholder. An implementer changing one is making a design
change.

**P1 — File path and budget.** `.claude/plugins/cla/skills/_shared/references/modified-block-retention.md`,
**80–110 lines**. Above 110 it is competing with the sites that bind it; below 80 it is restating the
obligation rather than defining the procedure.

**P2 — Trigger.** The presence of a `## MODIFIED Requirements` heading in
`openspec/changes/<name>/specs/<capability>/spec.md`. Not capability overlap, not chain membership,
not requirement count. One MODIFIED block is enough; zero MODIFIED blocks means the check does not
apply and that is reported as such, not as a pass.

**P3 — Comparison baseline.** `openspec/specs/<capability>/spec.md` **as it stands in the working
tree at the moment of the check**, never as the delta was authored and never a git revision. Stated
explicitly because `discover-and-gate.md:66` already uses this phrasing and the two must not drift.

**P4 — Order of operations, and it is an order.**

1. Parse `## RENAMED Requirements` in the **same delta file** and build the FROM→TO map.
2. For each `### Requirement: <Name>` under `## MODIFIED Requirements`, resolve `<Name>` through the
   map to the name it carries **in the live spec**, then locate that requirement there.
3. Enumerate `#### Scenario:` headings in the delta's block, and in the live requirement's block.
   Block boundaries: from the `### Requirement:` line to the next line beginning `### ` or `## `, or
   end of file.
4. Compare the two heading sets and report per P5.

Step 1 before step 2 is the whole point of note 1; an implementation that resolves renames anywhere
later reproduces the `anaf-tax-debt-list` false positive.

**P5 — Report line, verbatim shape.** One line per compared requirement:

```
<capability>/<requirement name>: live N -> delta M (+K added, -J missing)
```

followed, only when `K` or `J` is non-zero, by one line per differing scenario, heading text verbatim:

```
  - <live scenario heading absent from the delta>
  + <delta scenario heading absent from the live spec>
```

`N` and `M` are the two heading counts; `K` and `J` are the two set differences. `K` and `J` are both
printed even when zero. ASCII `->`, `+` and `-` — no typographic minus, so the line stays greppable.
#97's example `live 2 -> delta 4, +3` renders here as `live 2 -> delta 4 (+3 added, -1 missing)`.

**P6 — Adjudication verdicts.** Exactly three, per flagged scenario: `renamed` (the live scenario
appears in the delta under a different heading), `intentionally removed` (the change's own proposal
or design says the behaviour is going away), `dropped` (neither). **Only `dropped` is a finding.**
A hit left unadjudicated is treated as `dropped`, not waived.

**P7 — Severity floor.** In `review-change`'s vocabulary a `dropped` scenario is **Critical** — it
deletes a live `SHALL` from the specification set, silently, at archive. An `intentionally removed`
verdict with no supporting sentence in the change's own artifacts is **Important**, because the
verdict is then an assertion rather than a citation. `+K added` with `J = 0` is never a finding.

**P8 — Denominator, on every run including a clean one.** *R MODIFIED requirements compared across C
capabilities; F flagged, A adjudicated as renames or intentional removals, D dropped.* A non-zero
exit from any enumeration command is a **failed check, not an empty result** — the same rule
`discover-and-gate.md` states for its `ls` matrix, and for the same reason.

**P9 — Ordering against the siblings.** This change edits
`review-change/references/checklist.md` **after** both `fix-brief-binding-defect` and
`grounding-contract-claim-shapes`. Its edit is confined to Step 4's spec-reviewer dispatch prompt,
item 5.

## Risks / Trade-offs

**[The corpus is one chain]** — every parameter above traces to 1 chain, 2 flags, 1 consuming repo,
plus 1 previously shipped incident. → Nothing here is written as "measured" beyond what #97 and the
decision doc actually record, and P5's report shape is the mitigation: it makes each future firing
self-describing, so a second chain produces comparable evidence rather than another anecdote. D2
carries an explicit reversal condition.

**[Prose is not a mechanism]** — this repo's own Gotchas say a check's presence is not evidence it
runs, and #97 says the manual rule is exactly what stopped being followed at six MODIFIED blocks. →
Partially accepted, not solved. What changes is that the obligation now has an executable procedure
and a report shape whose absence is visible in the run notes; what does not change is that a skipped
step is still invisible. Named here rather than dressed up.

**[Three sites means three firings per change in a chain]** → Accepted. The comparison is two greps
per MODIFIED requirement and it is idempotent; D4's table shows each site is the sole cover for a
different window. The cost is bounded by MODIFIED-block count, which is 0 for most changes.

**[Residual false positives, permanently]** — a scenario renamed in place is indistinguishable from a
deletion. → Designed in, not mitigated: D5, and P6's `renamed` verdict exists for exactly this. The
alternative — suppressing the flag — is the one that loses a `SHALL`.

**[A gutted scenario body is invisible]** — heading-set comparison sees headings. A delta keeping
every heading while emptying a scenario's WHEN/THEN passes. → Out of scope and stated as a Non-Goal
so it is not mistaken for coverage.

**[The upstream half may never land]** → Accepted. If `openspec` never adds the check, the plugin's
procedure is the whole defence, which is the situation today anyway.

## Migration Plan

None. Prose additions to synced core; consuming repos pick them up on the next release via
`/plugin marketplace update`. No state, no data, no compatibility surface. Rollback is reverting the
commit.

## Open Questions

1. **Does the `archive-preflight` placement earn its line once review-time catches the same hit?**
   Resolvable only by a second chain reporting where hits actually fire. D4's table is the argument
   for keeping it; the run notes are where the answer comes from.
2. **Does `openspec` accept the upstream request, and in which version?** Outside this repo. Tracked
   as a task, not a dependency — nothing here waits on it.
