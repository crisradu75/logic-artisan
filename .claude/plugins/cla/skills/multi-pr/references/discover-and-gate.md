# discover-and-gate — Phase 1 full mechanics (discover, sequence, pre-flight gate, chain-time estimate)

Phase 1's step-by-step procedure: how to discover and order the changes, the two edges `depends_on` cannot express (shared environment state, and a stale delta baseline), the full pre-flight-gate question wording + rationale (including the explicit-autonomy override, the bounded-window-autonomy mode, and infra self-remediation), and the chain-time-estimate recipe. `SKILL.md`'s Phase 1 stub carries the load-bearing invariants (batch-then-run-continuous, the recommended defaults, the cycle and unresolved-prerequisite exceptions, the caps pass-through); this file carries the recipes and reasoning.

## 1a. Discover and propose an order

List every non-archived directory under `openspec/changes/` that has at least one of `proposal.md`/`design.md`/`tasks.md` — a directory with none of the three isn't a real change yet:

```
ls openspec/changes
```

Then read each change's own `proposal.md`/`design.md`/`tasks.md` for what it says it depends on ("Depends on X being merged", "requires X", "after X"), and order the set so every change follows its prerequisites. Some changes open `tasks.md` with a task-0 / "Prerequisites" group listing the hard prerequisites outright — worth the one glance before reading prose, though nothing requires the group and plenty of changes have none. Dependency prose is written for a human, not a parser: the statement can sit in the design.md's "Context" section, name the prerequisite without any signal word at all, or mention another change only to contrast with it ("unlike add-foo, this ships independently"). Read for meaning; don't pattern-match.

- A **dependency cycle** (A needs B needs A) is not yours to break: do NOT guess an order — it goes into the Phase 1 gate as an explicit question (see below), naming the changes actually on the cycle, not every change the cycle happens to block.
- If a change's prerequisite lies outside the set you discovered, do NOT assume it merged. Check first: `gh pr list --state open --head <its branch>` (and, on a resume, the running notes). An OPEN unmerged PR for an archived change is a stacked parent in flight — discovery cannot see it under `openspec/changes/`, but its dependents still need its code. **Under the stacked policy** that means `--pr-base <its branch>`, or the resume silently un-stacks them onto a tree missing the parent's code. **Under any other policy nothing passes that flag** — change-loop's stacked clause is scoped to the stacked policy, and the chain never merges a PR it did not open — so the chain cannot supply the code at all, and it becomes a gate question below rather than a promise it cannot keep. Only a prerequisite that is genuinely merged is noted and not blocked on.
- **A `/cla:multi-spec` plan file's `depends_on` is a hint, never the dependency graph.** It is scoped to its own batch by construction (`multi-spec/references/plan-schema.md`: authoring order within the batch, "not a build/merge dependency in the `multi-pr` sense"), so a prerequisite proposed outside the batch cannot appear in it. Never use it as the sole source for ordering or prerequisite discovery.
- In explicit mode (change names given as arguments), skip this step's auto-ordering — use the given order, but still sanity-check it against each change's stated dependencies and flag a contradiction to the user rather than silently reordering or silently proceeding.
- **Unmerged-dependency check (cheap, do it once here).** A proposal can cite a doc section, roadmap entry, or scoping commit that was authored on a *local branch never merged to `<base-branch>`* — so it isn't actually present in the tree the chain builds on, and an Implement task like "confirm `docs/plan/X.md`'s entry still matches" then discovers the gap mid-run. Before Phase 2, grep the in-scope proposals for their load-bearing doc references (a `docs/plan/*.md` heading, a "committed runway" / "change #N" framing, a roadmap section) and confirm each cited section actually exists on `<base-branch>` (`git show <base-branch>:<path> | grep <heading>`, or just read the file). If a cited section is missing, it usually means an upstream docs commit is stranded on a local branch — surface it now (a one-line note is enough; a small docs-restoration branch+PR early is far cheaper than discovering it three changes deep). If this repo has hit this mid-chain before, `cla.io/overlays/multi-pr.md` ("Incident / offense history") is where the precedent is recorded — an empty section there means no such history, not that the check is optional.

  **Do the same for every change a proposal names as a prerequisite, not just every doc.** A prerequisite can exist as specs and tasks with no code written anywhere — an open, proposal-only PR — and nothing about the batch looks wrong until a dependent reads a store nobody wrote, hours in. For each name, ask where its code actually lives: archived on `<base-branch>`, in scope for this run, or on an open PR. Resolve an archive directory with the rule `spec-to-pr/scripts/probe_state.py`'s `_archived` already implements (it handles the `<YYYY-MM-DD>-` prefix and the suffix collisions a naive match hits) rather than restating it here, and use `gh pr diff --name-only` to see whether an open PR carries code at all. A prerequisite whose code exists nowhere — and that no in-scope change will write first — is a **Phase 1 gate question**, not a note.

### Capability overlap — the second thing to compute, before the gate

Ordering by dependency answers "does A need B's code". It does not answer "do A and
B write to the same capability spec", and two changes can be dependency-independent
while colliding on one.

The mechanism, and it is **not** parallel authoring — `/cla:multi-spec` dispatches
one call per change, awaited sequentially, never parallel (`multi-spec/SKILL.md`).
Sequential authoring collides identically, for a different reason: every change in
the batch is written against **one baseline**, because `multi-spec` writes only
under `openspec/changes/<name>/specs/` and never touches `openspec/specs/`, which is
updated at archive time. No delta is applied before the others are authored. Add
that a `## MODIFIED Requirements` block replaces its requirement **wholesale**
rather than patching it, and two in-scope changes modifying the same requirement
means the later one silently reverts or corrupts the earlier one's delta.

Nothing flags it: each change's artifacts are internally consistent, and the
collision is only visible across the batch.

Measured on one batch in a repo consuming this plugin, and reported here rather
than re-derived: change 4 hit this twice — its delta would have deleted an
exception clause a sibling had just merged into one capability, and two scenarios
plus an ownership record from another. It was caught because that change's own task
list happened to warn, which is luck, not a check.

So compute the matrix, once, right here:

```
ls openspec/changes/<name>/specs/          # per in-scope change → its capabilities
```

**A non-zero exit is a FAILED CHECK, not an empty result.** Run from the wrong cwd —
a dedicated worktree, or a repo that roots OpenSpec elsewhere — every call errors,
and an errors-are-empty reading turns that into a confident batch-wide "no overlap".
Report the denominator so the two cannot be confused: *N in-scope changes scanned, M
with a `specs/` directory, K distinct capabilities, J touched by more than one.* A
change with no `specs/` directory is a real, reportable answer; a change whose `ls`
errored is not.

**The re-base check triggers on `## MODIFIED Requirements`, not on overlap.** The
mechanism above is about *when the delta was authored*, and anything that reached
the live spec afterwards moves the text out from under it — an archived change from
a previous chain, a `/cla:lite-pr` landed in between, a hand edit. So **every**
in-scope change carrying a MODIFIED block earns the check: compare its delta against
the live spec **as of that moment**, not as the delta was authored, per
`${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/modified-block-retention.md` — which
defines what "compare" means here, in what order, and what the report line looks like.
The word on its own was the entire specification, and an undefined comparison run
without rename resolution reports every renamed requirement as missing. In-scope
overlap does not create the obligation; it raises the priority and names which sibling
to compare against.

A change that only ADDS a brand-new capability is genuinely clean, and that is worth
recording — on the batch above, changes 5, 6 and 7 each added exactly one new
capability and carried zero re-base risk. Report that too, per change, rather than
leaving it unstated.

**Then deliver it, because a record with no reader is not a mechanism.** This is the
same failure the `## Carried obligations` machinery exists to prevent (`SKILL.md`
Phase 3, from GitHub issues #98/#100/#102): the review this check gates happens
inside `Skill(cla:spec-to-pr, …)` hours later, in a different phase, from a
reference file that is closed by then. Write one row per affected change under
`## Capability re-base` in `cla.io/retro/multi-pr-run-notes-<date>.md` — change,
capability, the sibling or landed change to diff against, and the one-line failure
if dropped — and let change-loop step 2 turn the rows owed by a change into
`--inherits` entries the same way it does for carried obligations. A batch with
nothing to carry writes the counted denominator above, not a bare `none`.

## 1b. The pre-flight gate — ask everything now

**`AskUserQuestion` accepts at most 4 questions per call.** There are up to 5 candidate decisions below, but two of them (sequence confirmation, infra-unavailability policy) are *conditional* — they only need asking when the situation actually calls for a decision, not by default. In the common case that keeps everything to one call:

**Always ask, batched into one `AskUserQuestion` call:**

1. **Merge policy.** Three options, and the right default depends on whether merging is available to this session at all (see "When merging is unavailable" below):

   - **merge before dependents** — merge each PR before starting the next change that **needs it merged**: one that depends on its code, *or* one that follows a change which moved shared environment state (both edges, per the paragraph below). A later change's Implement phase may need the earlier change's code actually present in `<base-branch>`, not just an open PR. Best when it works: each PR is insulated from its siblings' review churn.
   - **stacked** — no merges at all. Each dependent change branches off its parent's feature branch instead of `<base-branch>`, so the parent's code is present without anything landing; mechanically, the child's `/cla:spec-to-pr` invocation carries `--pr-base <parent-branch>` — the branch the parent's run recorded in the running notes (change-loop steps 2 and 5-alt); the flag's semantics are spec-to-pr's `<pr-base>` rule, which also opens the child's PR against the parent so each diff shows only its own work. The chain ends as a stack of open PRs the user lands parents-first with the commands the final report provides. Use this whenever merging is blocked, and prefer it when the user wants the whole chain reviewable before anything reaches `<base-branch>`.
   - **open all, merge nothing** — every change branches off `<base-branch>` independently. Only valid when no change depends on another **and no change moves shared environment state** (see the edge below); with a real dependency, the dependent's Implement phase runs against a tree missing its parent's code.

   **`depends_on` is not the only edge, and the other one is invisible to it.** The
   vocabulary above — "merge before dependents", "independents stay open" — can only
   see edges the dependency graph records, and that graph records **source-level**
   dependencies: one change's code or spec needing another's. A change also creates
   an edge by moving **shared mutable environment state** that later changes will run
   against: applying a database migration, seeding shared fixture data, performing a
   provisioning step.

   When it does, **that change merges before the next one starts, whether or not
   anything depends on its code.** The shared state has already moved for every
   subsequent branch, and only merging its source makes the tree consistent with it
   again.

   **This is determined by the orchestrator from artifacts, not asked of the user** —
   it is a fact about each change, not a preference, and the gate's one call is
   already at its 4-question budget. Determine it in §1a, per change, from four named
   sources, because at Phase 1 the change is unimplemented and there is no diff to
   read:

   1. Files its `tasks.md` or proposal Impact section says it will ADD under a
      migrations directory, a seed/fixture script, or a provisioning manifest.
   2. `tasks.md` steps that RUN a migrate/seed/provision command during
      implementation — a change can move shared state without adding a file.
   3. Whether this repo's development environment is shared across branches at all
      (`cla.io/overlays/multi-pr.md` → *Infrastructure values*). A per-branch or
      ephemeral environment has no such edge and the whole determination is vacuous —
      say so once for the batch rather than per change.
   4. Whether the repo has a guard comparing environment state against the working
      tree — the thing that converts the edge into a failure. Same overlay section.

   **A NO carries its derivation, never the bare word.** "No migration directory
   entry in tasks.md, no migrate/seed step, dev environment per-branch" is an answer;
   "no" is a word, and a question whose default is NO and whose NO is never shown is
   an exemption with a question mark on it. Same rule, and same reason, as the
   counted `none` the carried-obligations record already requires.

   Record the per-change answer under `## Sequence` in
   `cla.io/retro/multi-pr-run-notes-<date>.md` — change, `depends_on`, moves-shared-
   state with its derivation — written when §1c step 4 creates that file, which is
   the first moment it exists.

   **Under the explicit-autonomy override and the bounded-window mode, this is still
   established.** It is not one of the gate's pre-answerable preferences, so applying
   a default to it is not available: the override's own required output ("state the
   applied defaults transparently as the first output") carries the per-change
   determination and its derivation. An unattended run is exactly where this edge was
   measured to cost the most, so skipping it there inverts the fix.

   Measured on a six-change chain in a repo consuming this plugin, and reported
   here rather than re-derived: change 1 was listed `depends_on: []` and no
   sibling named it, so the confirmed policy pointed at leaving its PR open. Its
   migration was already applied and checksummed on the shared development database,
   and a guard comparing database state against the working tree fails hard when the
   database has applied a migration whose file is absent from the branch — so the
   next five changes would each have failed a gate that had nothing to do with their
   own work. The orchestrator caught it by reasoning mid-chain. Nothing in Phase 1
   asked, and a run that took the confirmed policy at face value — which is what the
   policy is for — would have met it as five consecutive unexplained failures.

   The detection mechanism there is repo-specific; the shape is not. Any harness
   running changes serially against one shared development environment has this edge,
   and any guard that compares environment state against the working tree surfaces it
   as an unrelated failure in an innocent change.

   **Stacked cannot satisfy this edge, and must not silently absorb it.** Stacked
   performs no merges, so a change that moved shared state cannot merge before the
   next one starts — the state has moved and branching does not un-move it. So: a
   confirmed shared-state edge makes **stacked** and **open all, merge nothing**
   unavailable for the changes after it, and that is part of what question 1 is
   choosing between. It also binds the mid-run fallback below: when a `gh pr merge`
   refusal converts the chain to stacked, re-check whether any remaining change sits
   after a shared-state edge, and **surface that rather than proceeding** — the
   fallback silently turns a satisfied edge into an unsatisfiable one otherwise.

   **When merging is unavailable.** A host runtime may refuse `gh pr merge` outright — separately from, and in addition to, this plugin's own `ask-destructive-git` hook, which `ALLOW_PR_MERGE=1` already satisfies — and an allowlist entry covering `gh` does not necessarily clear it, with or without `--delete-branch`. (A dated instance lives in `cla.io/overlays/multi-pr.md` "Incident / offense history".) Do NOT hunt for a flag spelling that gets through — that is working around a safety gate, not configuring one. Treat the first refusal as the answer: switch to **stacked** for the rest of the chain, say so in the run report, and hand the user the ordered, parents-first landing commands at the end.

   Detecting it up front is not worth a probe merge (a probe that succeeds has merged something). Instead: if the user already knows merges are blocked in their setup, they pick **stacked** at this gate; otherwise start on the confirmed policy and fall back on the first refusal.
2. **No-unresolved-issues policy.** Recommended default: **every Revise finding gets fixed before a change counts as done — Critical, Important, AND Suggestion.** Nothing is left in `TODO.md`; a Deferred-Known-Issue or a Suggestion-level residue both trigger a follow-up fix round (Phase 3 step 4) rather than a deferred entry. This is the recommended default specifically because `/cla:multi-pr` runs unattended for hours — there's no natural point where the user comes back to triage a leftover list, unlike a single interactive `/cla:spec-to-pr` run. Offer two looser alternatives for a user who wants faster throughput over exhaustiveness: (a) Critical/Important only, Suggestions still deferred to `TODO.md` (this skill's own narrower prior default — a real run needed the full-severity fix mid-flight, requiring a retroactive follow-up PR against an already-merged change, which is exactly the friction this stricter default now avoids), or (b) accept `/cla:spec-to-pr`'s own default triage entirely (Deferred-Known-Issues allowed too). Ask this as an explicit 3-way choice, not just strict-vs-loose.
3. **`/cla:spec-to-pr` caps.** Confirm `--review-rounds`/`--pr-rounds`/`--test-rounds` to pass through to every change's `/cla:spec-to-pr` invocation. **Default to `/cla:spec-to-pr`'s own defaults (1/2/3) — including for large changes in any sub-app.** Where this repo's overlay records a measured run-history statistic of its own, prefer it over this default. Review firepower for a large change comes from its 3-agent *dispatch* (which the size gate already selects), not from a second *round*; and `/cla:spec-to-pr` now internally right-sizes the Revise fan-out by diff signal (the two bug-hunters + `pr-test-analyzer` always; `type-design-analyzer`/`comment-analyzer` only on a genuine type-invariant / load-bearing-comment signal), so a large-but-additive change gets appropriate coverage without a cap bump. Raising `--pr-rounds` to 3 is cheap optional insurance for an unattended run (no one's around to approve an extra fix round) but is not needed by default — offer it, don't impose it.
4. **Infra-unavailability policy** — include this 4th question in the same call ONLY if at least one discovered change's tasks touch this repo's own local-infra-dependent hard gate, if it has one (see `cla.io/overlays/multi-pr.md` for its exact command); omit it entirely otherwise, so the common case stays at 3 questions with headroom to spare. Ask whether an unavailable local stack should **hard-block the chain** (stop and wait — the recommended default, since silently skipping a coverage gate is a worse outcome than pausing) or **skip that gate for the affected change and note it** (only if the user explicitly prefers throughput).

**Ask separately, in a second `AskUserQuestion` call, ONLY when it's actually a decision.** If step 1a's sweep found a prerequisite the chain cannot supply, name it, say which in-scope changes depend on it (one commonly blocks several), and ask whether to **drop the blocked changes** and run the rest, or **stop the chain** and land the prerequisite first. Two cases qualify: its code exists nowhere, or its code sits only on an open PR **and** the confirmed merge policy is not stacked — in which case **switch to stacked** is a third option, since that policy can supply it with `--pr-base`. And if step 1a found a dependency cycle, the proposed order can't be trusted — ask "these changes have a dependency cycle (name the changes on it) that also blocks ordering the ones downstream of it — how should I sequence them?" as its own question, before or after the always-ask call (order between the two calls doesn't matter; both must land before Phase 2 starts). When there's no cycle and the order is unambiguous, this second call simply doesn't happen — showing the proposed order as context alongside the always-ask call is enough, it isn't a decision the user needs to make.

Do not proceed past this gate until every applicable question (3, or 4 if the infra question applies, plus the sequence question if a cycle exists) is answered. This is the **only** point in the whole run where a multi-question stop happens — everything after this point runs autonomously per the hoisted rule above, whether that took one call or two.

**Explicit-autonomy override.** If the user's own `/cla:multi-pr` invocation already states an autonomy directive — phrasing like "operate autonomously," "do not stop for questions or approvals," "don't ask, just run" — treat Phase 1b as pre-answered: apply the skill's own **recommended default** for every question above (merge-before-dependents, full-severity no-unresolved-issues, `/cla:spec-to-pr`'s own defaults `1/2/3` per the caps guidance above, infra hard-block) without calling `AskUserQuestion`. State the applied defaults transparently as the first output before Phase 2 begins, so the user can see and override any of them by replying before the chain proceeds too far. This does NOT extend to either question in the second call. A prerequisite whose code exists nowhere cannot be implemented under any policy, so there is no default to apply — and an unattended run is exactly where that goes undetected for hours. A genuine cycle is likewise still surfaced, since guessing past it risks shipping changes out of order, which no amount of "operate autonomously" phrasing can safely pre-authorize.

**Bounded-window autonomy (a third mode: interactive for a while, then autonomous).** A distinct real shape, seen on two separate chains: the user is *present at the start* — answers the Phase 1b gate live, maybe redirects the first change or two — but states up front they will then leave and expect the run to finish without them ("I'm about to leave and let you go by yourself", "answer what you need now, then run to done"). This is neither the fully-interactive default (which would keep asking mid-chain) nor the explicit-autonomy override (which skips the gate entirely). Handle it as: **run the Phase 1b gate normally in the interactive window** (the user is there — real answers beat guessed defaults), then, once they signal departure, **treat every subsequent decision point exactly as the explicit-autonomy override would** — apply the skill's recommended defaults, never emit a mid-chain `AskUserQuestion`, and carry on to the Final cleanup pass. The one carve-out is identical to the override's: a genuine dependency cycle discovered mid-chain is still a hard stop (it cannot be safely auto-resolved), surfaced for whenever the user returns rather than guessed past. When this mode is in effect, state it explicitly at the departure boundary ("proceeding autonomously from here; applying recommended defaults for any remaining decisions, stopping only on a structural failure or an unresolvable dependency cycle") so the transition from interactive to autonomous is on the record.

**Infra-unavailability self-remediation (before asking or hard-blocking).** When the infra-unavailability question would otherwise fire (or before enforcing an already-established hard-block policy), first attempt to bring the local stack up yourself: launch the local Docker Desktop / equivalent engine, then poll this repo's own local-stack status command (see `cla.io/overlays/multi-pr.md`) every ~15–20s for up to ~2–5 minutes. Only surface the question (or enforce the hard-block) if the stack is still unreachable after that. A "forgot to start Docker" condition is common and cheap to self-fix; don't spend a gate-stop or a chain-halt on it before trying.

## 1c. Upfront chain-time estimate

Once the Phase 1b gate is resolved (however it was resolved — explicit answers, autonomy override, or the bounded-window transition) and before Phase 2's `TaskCreate` call, produce one upfront wall-clock estimate for the whole chain and report it as part of Phase 1's output. This is a genuinely useful number for "I'm about to be away for a few hours," and it's also the baseline Phase 3 step 7 needs to report actual-vs-predicted per change as the chain runs.

1. **Predict each change's complexity bucket** — `small` / `large-extend` / `large-new-capability`, the same three buckets `per_change[].complexity` uses in the chain-log schema — reusing the proposal/tasks.md reads Phase 1a already did for sequencing, no extra reads needed. Use `review-change/references/checklist.md`'s own size-gate thresholds (subtask count, files-touched estimate) to call small vs. large; within large, call it `new-capability` if the proposal's Why/Impact introduces a capability, route, table, or UI surface that doesn't already exist, otherwise `extend`. This is a *prediction* made before Review actually runs its own size gate — say so, and don't be surprised if a change or two gets reclassified once Review runs for real.
2. **Look up historical timing per bucket.** Read the per-run running-notes files from this repo's prior chains (`cla.io/retro/multi-pr-run-notes-*.md`, written by Phase 3 step 6) and average the measured per-change times by complexity bucket. If a bucket has zero or one prior sample, say so plainly ("only 1 prior `large-new-capability` sample, ~150min — low confidence") instead of presenting a one-point mean as if it were solid.
3. **Sum to a chain total and present it as a range, not a false-precision point figure** — state the basis inline, e.g. "~4–5h across 4 changes: 2 large-extend @ ~85min avg (4 priors), 1 large-new-capability @ ~140min avg (3 priors), 1 small @ ~50min avg (2 priors)." If the ledger has fewer than ~3 total prior records (one of the first couple of chains ever run), say the estimate is a rough guess with essentially no historical basis rather than presenting a confident-looking number.
4. **Record each change's point estimate** (not just the chain total) in the per-run running-notes file (`cla.io/retro/multi-pr-run-notes-<date>.md` — same file Phase 3 step 6 writes measured actuals to) so it's available for the per-change actual-vs-predicted comparison as the chain runs.
