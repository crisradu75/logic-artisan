## Context

`openspec` applies a `## MODIFIED Requirements` block by **replacing** the named requirement in
`openspec/specs/<capability>/spec.md` with the block's contents. It is not a merge. A scenario
present on the live requirement and absent from the delta is therefore deleted. `openspec` refuses
that apply from 1.11.0 — the guard is `findMissingCurrentScenarios`, and since their #1482
`openspec validate` runs the same check — so the loss is caught at apply time by a tool this plugin
does not own, on a version a consuming repo may not be running. GitHub issue #97 records the failure shipping once in a consuming repo — three live scenarios
dropped from one block, caught by hand — and one change in the 2026-08-20 chain carrying **six**
MODIFIED blocks across six capability specs, which is where hand-diffing stops happening in
practice.

**The fork this design has to settle first.** #97's own proposed fix is a refusal inside
`openspec archive`/`sync`. That is `openspec` tooling. This plugin does not own it, cannot ship into
it, and every repo running this workflow authors MODIFIED blocks the same way — so the argument for
"report upstream and add nothing here" is real and had to be answered rather than assumed away.

**The tree as it stands 2026-08-29**, after this change's own edits (measured; commands in
`tasks.md` §1), and after PRs #149 and #150 landed:

| file:line | what it establishes |
|---|---|
| `multi-pr/references/discover-and-gate.md:62` | Every in-scope change carrying a MODIFIED block earns a re-base check against the live spec "as of that moment". A **trigger with no procedure** — the instruction is the word "diff" |
| `multi-pr/SKILL.md:64` | **The same obligation, hoisted, in the same undefined words** — "earns a re-base check of its delta against the live spec as of that moment". A sixth site, found by review; see the note under this table |
| `review-change/references/checklist.md:305` | Spec-reviewer dispatch item 5: a MODIFIED entry "must include the full final requirement text plus its scenarios". States a completeness property the reviewer cannot falsify from the delta alone |
| `multi-spec/references/authoring-brief.md:30` | The author-side rule: read the active spec, copy every scenario. Correct, and it is a rule given to the writer, not a check. **It sits inside a fenced prompt template** (lines 11–38) — see D8 |
| `spec-to-pr/references/archive-preflight.md:65` | Check (c): every delta MODIFIED **heading** exists verbatim in the active spec. Heading only, and it says so |
| `openspec/specs/cla-plugin/spec.md:521–531` | PR #150's live-set validation. Line 531 explicitly disclaims this concern: parse integrity after any edit vs. content dropped through a delta |
| `multi-pr/references/change-loop.md:95` | Repeats that disclaimer at the step 4b site |

**Every line number above was re-measured AFTER this change's own edits landed**, which is the
part that matters and the part an earlier version got wrong twice. First: the table carried
2026-08-25 figures asserted under a heading reading "(measured)" — `checklist.md` had since grown
316 → 424 lines and item 5 moved 223 → 304, `spec.md` 529 → 531, `change-loop.md` 93 → 95. Review
caught that. Then the refreshed numbers were themselves invalidated by this change's edits to the
same files, and PR review caught *that* — item 5 moved 304 → 305, the injection rule 212 → 213,
"Modal case" 179 → 180. **A measurement taken before the last edit to the thing it measures is not
a measurement**, and this table needed telling twice. Locate by content regardless; `tasks.md` §1
re-derives these at implementation time, because a sibling change will move them again.

**`multi-pr/SKILL.md:64` is a sixth site and was missed by the original four-site framing.** It
hoists the same obligation in the same undefined terms, so after this change the hoisted rule and
the reference it points at would describe the check differently — the divergence D3 exists to
prevent, one level up. Whether it gains a pointer is contingent on D8; `tasks.md` carries the task
to settle it either way.

Two of those are load-bearing for scoping. The PR #150 requirement **names this change's problem and
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
of them. `discover-and-gate.md`'s re-base check said "diff its delta against the live spec"; that sentence is the
entire specification. An undefined diff is precisely what #97's evidence indicts — run without
rename resolution and without added counts, the only real execution of it produced 2 flags and 2
false positives.

**Alternative considered — report upstream, add nothing.** Rejected on three grounds. (i) It leaves
`discover-and-gate.md`'s existing obligation unexecutable, which is worse than absent: a stated check
that cannot be performed correctly reads as coverage. (ii) The upstream fix, if it lands, lands on a
version of `openspec` a consuming repo may not be running for a long time; the plugin's own
instructions are what its skills follow today. **That prediction was tested and held.** The
enforcing check had already landed upstream when this was written — and this repo, along with the
seven others on the machine, ran between four and eight minor versions behind it until 2026-08-27.
An upstream fix that exists is not an upstream fix that runs. What the landing does cost D1 is the
never-lands half of this ground: the reason to build the in-scope half is now (i) and (iii), plus
the version lag, not the possibility that nothing ever ships upstream. (iii) The two design notes are knowledge this repo
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

### D4 — Five binding sites, deliberately, because they close different windows

**Decision.** Bind at **five** sites: `review-change` dispatch item 5, `review-change`'s size gate
(Step 3, the small-change branch),
`archive-preflight` check (c), `multi-pr`'s existing re-base check, and `multi-spec`'s
authoring rule.

**The count is stated once, here, and every other artifact defers to this sentence.** An earlier
draft of this section said "Five" in its heading, "three" in this Decision, "Three sites" in the
Risks header and "Two placements" in the proposal, while `tasks.md` §3 implemented five — five
statements, no two alike, in a change whose whole subject is a comparison nobody performs
consistently. Review caught it; the heading's number was the correct one.

They are not redundant placements of one check; each is the only cover for a distinct window:

| site | window it covers | what it costs |
|---|---|---|
| `review-change` item 5 | Authoring error on the **large** path, caught pre-implementation, when the delta is still cheap to fix | One live-spec read per MODIFIED requirement, inside a dispatch already reading the delta |
| `review-change` size gate (Step 3, small-change branch) | The same authoring error on the **small** path, which skips the dispatch entirely and is the modal case here | One live-spec read, inline, on a path already reading the delta |
| `archive-preflight` (c) | Everything after review — a Revise-round delta edit, a hand-resolved merge conflict in the delta — and the last moment before materialization deletes anything | One grep per MODIFIED heading, inside a loop that already runs |
| `multi-pr` re-base check | The **baseline moving**: a sibling, an archived change from a previous chain, a `/cla:lite-pr` landing in between. A correct delta going stale, which neither of the above is looking for | Already in the flow; this change replaces "diff" with the procedure |
| `multi-spec` authoring rule | The author's own hand, before a delta exists to compare — the only site upstream of the defect rather than downstream of it | A pointer; the rule is already written |

**The small path is not covered by item 5, and this is the batch's honest gap.** `checklist.md:165`
sends a small change past the 3-agent dispatch — "Skip the 3-agent dispatch… Go straight to Step 5" —
and `:179` records "Modal case in this repo: small." So a binding that lives only in Step 4's
dispatch item reaches the minority of reviews. The change closes this at the size gate's own small-change
branch — where that path is defined, and where "the orchestrator IS the reviewer" is already
stated — with a single sentence rather than a numbered check. **Not at Step 5**, which is
`## Step 5: Analyze task parallelism`: a spec-retention instruction there would sit inside a section
about dependency lanes, and an earlier draft of this design said Step 5 for exactly that reason —
nobody had opened the file to see what Step 5 is. A numbered entry would also compete for `0l`
with the sibling `grounding-contract-claim-shapes`, and D7's reason for adding none still holds.
`archive-preflight` remains the backstop, but it is deliberately not the answer here — D4 already
rejects last-detection as the design, and accepting it for the modal path would be that rejection
reversed by omission.

**What `multi-pr`'s row does NOT cover, stated because the row's own wording overclaims it.**
`discover-and-gate.md` computes the capability matrix **once, at Phase 1**, and hands rows forward
via `--inherits`. A comparison taken there reads the live spec before any sibling in the chain
merges — so the "baseline moving" window it is credited with is precisely the one a Phase-1 snapshot
cannot see. The row is still the only cover for a baseline that moved **before** the chain started
(an earlier chain's archive, a `/cla:lite-pr` landing in between), which is what it actually buys.
Covering movement *during* the chain requires the comparison to re-run per change at change-loop
time; this change does not add that, and says so rather than implying the window is closed.

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

A scenario renamed in place and a scenario deleted both flag, and exactly one destroys a live
`SHALL`. So a residual false-positive rate is designed in, and a guard that refused on a hit would
refuse on a legitimate rename. The requirement is written so that flagging both and making a human
adjudicate is the *correct* behaviour, not a tolerated weakness.

**Corrected by this change's own dry-run (`tasks.md` §5.6), which is what §5 exists for.** This
paragraph said the two cases are "byte-identical to any heading comparison". They are not, once the
report states both directions as D6 requires: deleting a scenario reported
`live 4 -> delta 2 (+0 added, -2 missing)` and renaming one in place reported
`live 4 -> delta 3 (+1 added, -2 missing)`, because the new heading arrives as an addition. Measured
by executing P4 against a real archived block.

**The decision does not change, and the reason is worth stating precisely.** A non-zero `K` beside a
non-zero `J` is a *hint*, not a distinction: a change may legitimately delete one scenario and add an
unrelated one, producing the identical pair, and `K` says nothing about which addition corresponds to
which absence. So the procedure still must not claim to separate them mechanically, and nothing may
refuse on a flag. What changes is only the honesty of the claim — the reference now says a non-zero
`K` is a reason to read the two headings side by side before adjudicating. An earlier wording would
have had a reader dismiss a real signal because the design told them none existed.

**The upstream guard took the opposite decision, and that is now the sharpest argument for this
one.** `openspec` ≥1.11.0 refuses a MODIFIED block whose scenario set does not cover the live one,
which means a scenario renamed in place — the `company-events` case above, the one rename
resolution provably cannot catch — is not a false positive there but a hard block. Their open issue
#1697 is exactly that complaint, and the corpus replay in its thread measures the cost: across 75
archived changes carrying a MODIFIED block, **29 (39%) would be blocked**, every detection correct,
and of the 26 findings hand-classified for intent, **16 (62%) were intended omissions** —
supersessions, deliberate deletions, and a stale base. Roughly three intended omissions blocked for
every two losses stopped. **The 39% and the 62% are computed over different denominators** — 29
blocked, 26 classified, 3 unaccounted for in the thread — so they do not compose into a single rate
and are not presented as one. Both figures were checked against the #1697 thread verbatim during
this change's review.

Two things follow for this design. First, D5's "never refuse" is no longer only a preference: it is
the behaviour a measured corpus says a refusal gets wrong at a 62% rate on the cases it fires over,
and this procedure runs *before* implementation, where a false block costs a change rather than a
line of adjudication. Second, the rename-resolution ordering (P4) gains a second audience. It was
written for a reader catching a loss; it now also serves an author who must satisfy an upstream
guard that reads their rename as one — the ordering is what tells them which of their flags are
renames before `openspec` refuses the apply over them.

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
(Step 4; locate by content — it is the item headed "MODIFIED requirements are complete"). It adds no
`0l`/`0m` entry to the `0a–0k` orchestrator list.

**Reason (i) is now the only reason, and it was always sufficient.** Item 5 **already states this
rule** and is simply unfalsifiable as written — a delta carrying 3 of 5 live scenarios satisfies
"full final requirement text plus its scenarios" on its face. Fixing the existing sentence is a
smaller and truer edit than adding a check beside it.

Reason (ii) was that the sibling `grounding-contract-claim-shapes` claimed `0l`, so a numbered check
would collide. **That sibling has since landed** — `0l` is in the file, `0m` is free, and the
collision no longer exists. The decision is unchanged because it never rested on (ii); recorded so a
later reader does not re-open it on the strength of a resolved conflict.

### D8 — The reference is written in two halves; the recipe half is injectable, the rest is pointed at

**Decision.** `modified-block-retention.md` opens with a **Procedure** section — the four steps, the
report line, the three verdicts — written to be pasted verbatim into a prompt, and capped at ~25
lines. Everything else (why the order is the order, the honest limits, the worked example, the
denominator rule) follows it and is only ever pointed at.

**A site that hands its text to a dispatched agent pastes the Procedure section. Every other site
points at the file.** Two sites paste: `checklist.md` item 5 and `authoring-brief.md`'s MODIFIED
rule. Three point: `checklist.md`'s size gate, `archive-preflight` check (c), `multi-pr`'s re-base check.

**Why this and not the three alternatives.** It dissolves the collision below instead of paying for
one side of it. There is still exactly one statement of the steps — the Procedure section — and a
prompt that pastes it is quoting that statement, not authoring a second one. D3's objection is to
three *independently maintained* copies that drift; a verbatim paste of a section that exists once
has no independent copy to drift from.

**What it costs, stated because every option here costs something.** P1's line budget has to be cut
in two rather than as one number, and the file needs an explicit rule about which half is injectable
— a reader who pastes the whole file has not broken anything, but a reader who pastes only half the
Procedure has. The section therefore carries its own boundary marker, and `tasks.md` §2 verifies the
Procedure section stands alone: readable, followable, and containing no forward reference to the
rationale half.

**Alternative considered — a short summary at the two prompt sites plus a pointer.** Rejected: the
summary is a second description of the rule, maintained separately, which is exactly D3's
three-wrong-copies failure at a smaller scale.

**Alternative considered — paste the whole 80–110 line file into both prompts.** Rejected: it roughly
doubles one already-long prompt, and every future edit to the reference has to be mirrored into two
prompts by hand.

**Alternative considered — drop the two prompt sites.** Rejected: one of them is the large-path
review binding the proposal names first, and the other is the only site upstream of the defect
rather than downstream of it.

**The collision this resolves.** D3 rejects restating the procedure at each site — "that is how this
repo produced three wrong copies of one correct rule before" — so every binding was a pointer. Two
of the five bindings are not ordinary prose:

- `checklist.md` item 5 lives inside the **Agent 3 dispatch prompt**. That same file, at line 212,
  states the opposing rule in its own words: a dispatched agent "never loads the skill or resolves
  `cla.io/overlays/review-change.md` itself, so a placeholder left un-filled, or replaced with a
  bare 'see the overlay' pointer, leaves that agent reviewing blind."
- `authoring-brief.md:30` lives inside a **fenced prompt template** (lines 11–38) handed verbatim to
  a dispatched authoring agent. Every other path in that template is repo-relative; a
  `${CLAUDE_PLUGIN_ROOT}`-spelled pointer is a form the template has never used.

So D3 forbids restating and `checklist.md:212` forbids pointing, at exactly the two sites where the
reader is an agent rather than a person. Neither the proposal nor this design noticed.

**What settling it requires.** A decision on how a shared reference binds at a dispatch site, with
its cost stated: a short injectable summary at the two prompt sites plus a pointer for the full
procedure (duplicates a little, and D3's three-wrong-copies risk applies to the summary); or
injecting the whole 80–110-line reference into two prompts (no duplication, meaningful prompt
weight); or dropping the two prompt sites and binding only where a pointer resolves (smaller change,
gives up the large-path review binding the proposal names first).

**Settled 2026-08-29, by the split above.** `tasks.md` §3.1, §3.2 and §3.8 paste the Procedure
section; §3.3b, §3.4 and §3.6 point at the file.

## Pinned implementation parameters

Every value below is a decision, not a placeholder. An implementer changing one is making a design
change.

**P1 — File path and budget, in two halves per D8.**
`.claude/plugins/cla/skills/_shared/references/modified-block-retention.md`, **80–110 lines total**,
split as:

- **`## Procedure` — the injectable half, 25 lines or fewer.** The four steps of P4, the report line
  of P5, and the three verdicts of P6 with their severity floors. Nothing else. It opens with a
  one-line marker saying it is pasted verbatim into a dispatch prompt and must stay self-contained,
  and it closes with an end marker so a paster can see the boundary. **It carries no forward
  reference** — no "see below", no "as the limits section explains" — because half of a sentence
  arriving in a prompt is worse than none.
- **The rest, 55–85 lines.** Why the order is the order, the honest limits, the worked example, the
  denominator rule, the scope boundary. Pointed at, never pasted.

Above 110 total it competes with the sites that bind it; below 80 it is restating the obligation
rather than defining the procedure; a Procedure section over 25 lines stops being injectable, which
is the number that actually binds.

**P2 — Trigger.** The presence of a `## MODIFIED Requirements` heading in
`openspec/changes/<name>/specs/<capability>/spec.md`. Not capability overlap, not chain membership,
not requirement count. One MODIFIED block is enough; zero MODIFIED blocks means the check does not
apply and that is reported as such, not as a pass.

**P3 — Comparison baseline.** `openspec/specs/<capability>/spec.md` **as it stands in the working
tree at the moment of the check**, never as the delta was authored and never a git revision. Stated
explicitly because `discover-and-gate.md`'s re-base check already uses this phrasing and the two must
not drift.

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

**Why the unadjudicated default is a Critical, when D5 spends a page arguing a 62% wrong-block rate
condemns the upstream refusal.** The two are not the same act, and an earlier draft left that
unreconciled. Upstream's refusal is **terminal** — it blocks the apply, and the 62% of intended
omissions pay for it by losing the change until someone edits the delta. P6's default is a
**finding**, and a finding's cost is one line of adjudication by a reader who is already reading the
report. The base rate is the same; the price of being wrong differs by two orders of magnitude. What
would be inconsistent is a refusal here, which is exactly what D5 forbids.

**What the archive-time consumer does with a hit, since it is the one non-blocking entry in a
blocking checklist.** Every other item in `archive-preflight.md` is remediate-before-archive — "apply
all remediations in the same PR". This one is not, per D5, so it must say what it does instead: a
`dropped` verdict at archive time is raised as a **Critical against the change**, the archive
proceeds, and the finding goes to the run's Issues so the PR carries it. It is deliberately not a
halt: a halt at materialization time is the last-detection design D4 already rejected, and a
scenario renamed in place would halt on a legitimate rename. The check's value here is that the loss
is *recorded before it happens*, not that it is prevented.

**P8 — Denominator, on every run including a clean one.** *R MODIFIED requirements compared across C
capabilities; F flagged, A adjudicated as renames or intentional removals, D dropped.* A non-zero
exit from any enumeration command is a **failed check, not an empty result** — the same rule
`discover-and-gate.md` states for its `ls` matrix, and for the same reason.

**P9 — Ordering against the sibling.** This change edits
`review-change/references/checklist.md` **after `grounding-contract-claim-shapes`**, which is the
only sibling that touches that file. `fix-brief-binding-defect` was named here too and does not edit
it at all — measured 2026-08-29 against its archived proposal, which states as much itself. Both are
archived, so the ordering is satisfied. It touches **two** regions of that file: Step 4's spec-reviewer
dispatch prompt (item 5) and the size gate's small-change branch in Step 3.

**The second region is not optional, and an earlier draft of this parameter lost it.** P9 read
"confined to Step 4's spec-reviewer dispatch prompt, item 5", and the proposal's Impact said the
same — while D4's body and `tasks.md` §3.3b bind the small path as well. An implementer following P9 and
Impact would have shipped nothing for the small path, which `checklist.md:179` records as the modal
case here and D4 calls "the batch's honest gap": the change's own headline gap would have survived
its implementation. Neither sibling touches the size gate, so the disjoint-by-region claim still holds.

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

**[Five sites means repeated firings per change in a chain]** → Accepted. The comparison is two greps
per MODIFIED requirement and it is idempotent; D4's table shows each site is the sole cover for a
different window. The cost is bounded by MODIFIED-block count, which is 0 for most changes. No
single change reaches all five: the `multi-spec` site is author-time, `multi-pr`'s is batch-only,
and the two `review-change` sites are mutually exclusive (a review is small **or** large, never
both), so a batched change fires at most four and a solo change at most three.

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
