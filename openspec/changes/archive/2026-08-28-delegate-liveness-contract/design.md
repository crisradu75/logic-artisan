## Context

A brief's terminal contract is the only thing standing between a dispatch and a wrong belief about
what happened in it. The current contract (`subagent-brief.md` §5, line 78) is one paragraph and it
defines exactly one outcome:

> End with an explicit `done` or `blocked` status. `done` is valid ONLY when accompanied by hard
> evidence — the test-run summary line, and the ticked-task count (`- [x]` count vs total). A return
> claiming done without that evidence is treated as **not done**.

Read it as a classifier and the gap is visible. It classifies a return that *claims* `done`. It says
nothing about a return that claims nothing — and a return that claims nothing is what a delegate
produces when it starts a long gate in the background and ends its turn. The orchestrator, holding no
rule, falls back to reading the prose, and the prose is a status report about work in progress, which
in the position a return occupies reads as a finish.

Everything else follows from that one misclassification. The orchestrator believes the delegate is
done, so the checkout is free, so it takes over: runs the gate, checks out, commits. The delegate's
background job is still running in that same checkout. The failures that come out are then real
observations of a state the orchestrator itself created, and they were investigated as a possible
regression. ~40 minutes (#115).

Current state, measured 2026-08-25:

```
wc -l .claude/plugins/cla/skills/spec-to-pr/references/subagent-brief.md      → 115
wc -l .claude/plugins/cla/skills/spec-to-pr/references/concurrent-runs.md     → 21
wc -l .claude/plugins/cla/skills/spec-to-pr/SKILL.md                          → 431
grep -n '^### [0-9]\.' .../subagent-brief.md
    → :31 "1. Scope", :37 "2. Task", :45 "3. Do not touch", :68 "4. Report",
      :78 "5. Done when — a condition you will check, with evidence"
grep -n '^## ' .../spec-to-pr/SKILL.md
    → :159 "Concurrent runs (worktree-per-session)", :412 "References"
grep -rn 'subagent-brief' .claude/plugins/cla/
    → spec-to-pr/SKILL.md:234, lite-pr/SKILL.md:141    (two citing sites, both by slot name)
grep -rn 'concurrent-runs' .claude/plugins/cla/
    → spec-to-pr/SKILL.md:162, spec-to-pr/SKILL.md:415  (both by path)
grep -rn 'Never end a turn with nothing in flight' .claude/plugins/cla/skills/
    → multi-lite/SKILL.md:46, multi-pr/SKILL.md:25, multi-spec/SKILL.md:38
    (spec-to-pr/SKILL.md:301 states the same rule in its own words)
```

Two facts from that measurement bound every option below.

**First: the turn-liveness rule already exists, and it is addressed to the wrong actor for this
failure.** Four skills state it, and all four say the same thing — ending a turn is legitimate in
exactly two cases, *a backgrounded dispatch is genuinely in flight* or *the run is complete* — with
the first case justified by "its completion notification wakes the session". That is true of an
orchestrator session. It is not true of a dispatched agent, whose turn ending is its return: there is
no session left for a notification to wake. A delegate applying the rule it would most plausibly
infer from the plugin's own prose backgrounds the gate and stops, and is *following the documented
rule* while doing it. This change does not add a third case; it names the actor for whom the first
case does not exist.

**Second: half the brief-side prohibition is already written.** §3 already argues, at length, that a
read-only agent hears "make no edits" as being about file contents and will still run `git checkout`,
`switch`, `stash`, `branch` or `worktree add`, and it already gives the spelled-out forbidden-verb
form. What it lacks is `commit`, `push` and `reset` (it was written for read-only reviewers, and a
delegate that implements does commit), process cleanup, and build/cache directories. So the
brief-side work here is an extension of an existing block with an existing rationale, not a new rule
needing its own argument.

## Goals / Non-Goals

**Goals:**

- Close #113, #115 and #125 with rules a reader applies without judgement — the same standard the
  turn-liveness rule was forced to adopt after its judgement form lost in practice.
- Settle whether long gates run synchronously **by default**, take a position, and price it in terms
  of what every run pays rather than what the failing runs cost.
- Say what a terminal contract's *absence* obliges the orchestrator to do, including the case where
  the obvious move — take over the tree — is the one that caused the incident.
- Keep every rule inside the terminal-status vocabulary `fix-brief-binding-defect` establishes.

**Non-Goals:**

- **No fourth terminal status.** `done`, `blocked` and `remedy-rejected` are the whole set. An
  evidence-free return is `blocked`; giving it a status of its own would let a delegate reach for it,
  and a status the delegate chooses cannot classify a return the delegate did not think it was making.
- **No slot renumbering, no sixth slot.** Both citing sites spell the five slot names out.
- **No change to the orchestrator's own use of backgrounding.** The plugin depends on it — the
  turn-liveness rule's watchdog, the Revise fan-out. Only a dispatched agent's use is constrained.
- **No new script, hook, or agent type.** Every mechanism here is prose in a file already read at the
  moment it binds.
- **No cap changes.** No round cap, no test-round cap, no dispatch cap moves.
- **Not a general concurrency model.** Two orchestrators in one clone stays exactly what
  `concurrent-runs.md` already says it is: use a worktree.

## Decisions

### Decision 1 — Long gates run synchronously for a dispatched agent, and the rule keys on the runner

**The rule.** A dispatched agent runs every gate in the foreground and waits for it, however long it
takes. It does not background a command, and it does not end its turn while a command it started is
running.

**Why the runner and not the duration.** The obvious rule keys on time — "gates over N seconds run
synchronously", or its inverse. Both are wrong, and identically wrong: duration is not what makes
backgrounding unsafe. A 5-second command backgrounded by a delegate that then returns is lost in
exactly the same way a 300-second one is. What determines safety is whether the party that started the
command survives long enough to collect its result:

| Runner | Ends its turn with a job pending | Result |
|---|---|---|
| Orchestrator session | Notification re-invokes the session | Safe — and the turn-liveness rule *requires* this shape at a seam with nothing else in flight |
| Dispatched agent | Turn ending **is** the return | The job's result is unreachable; the return carries no evidence |

So the discriminator is the runner's own liveness, which is a property known at dispatch time and
needs no estimate of anything. It also explains, rather than merely prohibits, which is what makes it
survivable prose: a delegate told "don't background things" looks for the exception; a delegate told
"a backgrounded command does not survive your return" has nowhere to put one.

**Stated as a rule, not a preference.** The instruction is not "prefer synchronous". It is: a
dispatched agent's gates are foreground, always, and a gate that cannot run in the foreground is not
the delegate's to run.

**The ceiling, and what happens at it.** Foreground is not unbounded — a single foreground call has a
maximum duration in whatever harness the plugin is running under, and a gate exceeding it cannot be
run this way. This is the one place a threshold genuinely exists, and it is deliberately **not
pinned as a constant**: the number belongs to the harness, not to the plugin, and a constant written
into synced core is wrong in every harness whose limit differs and stale in the one it was measured
against. The orchestrator resolves it at dispatch time and the rule keys on the comparison, not the
number:

> If a gate's expected duration approaches or exceeds what one foreground call permits here, do not
> delegate that gate. Run it yourself after the dispatch returns, or dispatch the work without it and
> gate afterwards. A delegate that meets such a gate returns `blocked` naming it.

That branch is what stops the synchronous rule from producing the backgrounding it forbids. Without
it, a delegate facing a 45-minute end-to-end suite has a rule it cannot obey, and an unobeyable rule
is obeyed by exception.

**The cost, priced honestly — and it is smaller than it looks.** The framing in the decision
("a cost every run pays") assumes synchronous execution costs the gate's wall-clock time. It does
not: the gate takes its duration either way, and the delegate has nothing else queued. What is
actually surrendered is the delegate's ability to interleave work while a gate runs — and in every
observed instance that capability was not used, because the delegate stopped. So the per-run cost is:

- **Delegate side: effectively zero.** It waits instead of stopping. The four observed cases traded a
  wait for a lost result.
- **Orchestrator side: a genuine cost, and it already exists.** The orchestrator is blocked on the
  `Agent` call for the gate's duration. It is blocked for that duration today too — the difference is
  that today it is blocked, gets an early return, and *believes the gate finished*. The change buys a
  correct belief at the price of the same wait.
- **The real new cost is the ceiling branch:** a gate too long to delegate now runs in the
  orchestrator's own turn instead of a delegate's. That is one serialised gate per affected run, on
  the subset of runs that have a gate that long. Not zero, and not measured — this design does not
  claim a number it has not run.

**Rejected alternative — a duration threshold ("gates under 60s foreground, over 60s backgrounded
with a wait loop").** It requires the delegate to estimate a duration it has never run, and it makes
the *long* gates — the ones that matter — the backgrounded ones, which is exactly the failing case.
It also needs a wait loop, and a wait loop is a second mechanism whose own failure mode (the loop
exits early, the delegate returns anyway) is indistinguishable from the failure it replaces.

**Rejected alternative — let the delegate background it and require a wake mechanism.** There is no
wake mechanism available to a terminated agent. Any version of this reduces to "the delegate polls",
which is the wait loop above, or "the orchestrator polls", which is Decision 2's on-a-miss ladder
arriving by a worse route — it makes the evidence-free return normal rather than exceptional, and a
normal evidence-free return cannot also be the signal that something went wrong.

### Decision 2 — A return is read for its evidence before it is read for its words

**The mechanical test.** On every return from a dispatch, before acting on anything it says:

1. Does it carry a status token from the closed set the brief named — `done`, `blocked`, or (per
   `fix-brief-binding-defect`) `remedy-rejected`?
2. Does it carry every evidence field the brief's slot 5 required — for the standard contract, the
   test-run summary line and the ticked-task count?

Both present → classify as the token says. **Either missing → the return is `blocked`**, whatever its
prose says, including a return that reads as finished, reports a result, or says it is standing by
for something. This is a scan against a list the orchestrator itself wrote into the brief minutes
earlier; it needs no judgement, which is the property the turn-liveness rule had to be rewritten to
acquire and the property this rule is copying deliberately.

**Why `blocked` and not a new status.** `blocked` already means "the delegate could not proceed and
the orchestrator must resolve something before re-dispatching", and that is precisely the state. The
alternative — a distinct `incomplete-return` status — fails on ownership: `done`, `blocked` and
`remedy-rejected` are all statuses the *delegate* declares, and this classification is made by the
orchestrator about a delegate that declared nothing. A status the delegate can reach for is the wrong
mechanism for a return the delegate did not know it was making.

**What the absence obliges — the ladder.** On a miss, in this order:

1. **Classify `blocked` and record a contract firing.** The mechanism exists: `spec-to-pr` already
   requires a fired contract to be recorded as a Handoff Issue rather than absorbed silently,
   precisely so the delegation-reliability signal survives. An evidence-free return is a firing.
2. **Establish quiet before touching anything.** Read-only only: determine whether any command started
   under that dispatch is still running. Until that check comes back clean, the checkout is not the
   orchestrator's — no gate, no state-changing git command, nothing that writes into a build or cache
   directory. This step exists because it is the step that was skipped in #115.
3. **Re-dispatch once — this is the default move, not take-over.** Same brief, plus the evidence
   fields the previous return omitted, named explicitly, plus the liveness line. One re-dispatch,
   matching the cap `spec-to-pr`'s Implement phase already states for a `blocked` return ("resolve the
   blocker and re-dispatch once").
4. **Take over only after step 2 is clean, and only within the phase's existing budget.** Take-over is
   not forbidden — it is the correct move once the tree is quiet and a re-dispatch has not produced
   evidence. What is forbidden is take-over *before* step 2.

**The rule that would have ended #115 in one line.** Anything observed in a checkout the orchestrator
disturbed while a delegate's work was live is not evidence about the change:

> A failure observed in a checkout you touched while a dispatch of yours was live is not evidence of
> a regression. Re-derive it from a quiet tree before investigating it as one.

The incident was not that the orchestrator took over. It was that it took over, produced failures,
and then spent the time investigating them as a possible real regression — the manufactured evidence
was indistinguishable from the real thing precisely because it *was* real, just about a state the
orchestrator had created. A rule about not interfering does not cover this; the interference had
already happened. This is the second half, and it is the half that bounds the cost when the first
half fails.

**Rejected alternative — "on a miss, take over the tree".** It is the natural instruction and it
re-specifies #115. Take-over is the move the orchestrator was already making; writing it down as
policy makes the incident the documented behaviour.

**Rejected alternative — poll the delegate.** Nothing to poll. A returned agent has terminated.

### Decision 3 — Single-writer discipline, stated in both directions, in two places because it must be

The brief and the skill body reach different readers, and this rule has two readers.

**(a) Brief-side — an extension of §3's existing block, made standard.** §3 already spells out
forbidden verbs for a read-only agent. The extension: add `commit`, `push` and `reset` (§3 was
written for reviewers; an implementing delegate commits, and a delegate that "cleans up" with a reset
destroys the orchestrator's staged work), and add the two non-git shared resources — do not kill,
restart or clean up a process you did not start, and do not delete or regenerate a build, cache or
dependency directory you did not create.

**Should the ad-hoc sentence become boilerplate?** Yes — and the test for that is worth stating,
because the sibling change rejects a mandatory field on exactly the opposite reasoning (a field whose
honest content is "n/a" teaches every reader to skim the section). The two are consistent under one
test: **boilerplate is warranted when there is no dispatch kind for which it is inapplicable.** A fix
brief's defect field is inapplicable to a doc-sweep dispatch, so it is a second form of a slot rather
than a mandatory field. Every dispatch this plugin makes runs in the orchestrator's own checkout —
there is no dispatch kind that does not share it — so the prohibition is never "n/a", and a reader
never learns to skim it. It also costs two lines and is the cheapest line in the brief; the alternative
priced it at ~40 minutes once.

**(b) Orchestrator-side — a new case inside "Concurrent runs", not a new section and not a brief
line.** A brief cannot carry this half: a brief travels to the delegate, and the party that needs
binding is the one writing the brief. So it goes where the orchestrator reads.

The existing section is the right home rather than a new one, for a reason that generalises: its
subject is not worktrees, it is **what happens when two agents write to one checkout**. Two sessions
sharing a clone is one case of that; an orchestrator and its own delegate is another, with the same
mechanism (git's HEAD and the working tree are per-clone, shared, process-wide, and leave no diff to
notice a change by — §3 already makes this argument almost verbatim) and no worktree between them,
because a delegate runs in the session's own directory by construction. Splitting them puts one
invariant in two files that then go stale independently, which is the failure the brief reference was
created to fix and which this repo has already paid for once.

The consequence is a **retitle**: both the file's H1 and the SKILL.md section heading currently say
"worktree-per-session", which stops being the whole story. Cheap — `grep -rn 'concurrent-runs'` finds
two references, both in `spec-to-pr/SKILL.md`, both by path, neither by heading text.

**Rejected alternative — a new "Delegate interference" section.** Two sections, one invariant, drifting
apart. The worktree recipe would keep the search terms ("concurrent", "parallel", "same repo") an
orchestrator with this problem actually looks under, and the new section would be found by whoever
already knew it existed.

**Rejected alternative — brief-side only.** A brief cannot bind the orchestrator, and the orchestrator
is the party that caused #115.

### Decision 4 — Stop rather than invent data, attached to the requirement that creates the pressure

**Placement is the decision.** The clause could sit anywhere in the brief; it belongs in §5, adjacent
to the evidence requirement, because §5 is what creates the incentive it counteracts. A contract that
says `done` requires a test-run summary line puts a delegate that cannot run the tests in a position
where the cheapest compliant-looking output is a plausible summary line. Filed elsewhere the clause is
a virtue statement; filed there it is the exception branch of the rule directly above it.

**The content**, in three parts, because each closes a different route to a fabricated value:

- Every value the contract asks for is one the agent produced — not one it estimated, inferred, or
  carried over from an earlier run or another file.
- If it cannot produce one, the return is `blocked`, naming the field it could not fill and why. This
  is where the standard language legitimises the honest answer: a `blocked` return with a named gap is
  a **successful** return, on the same footing as `remedy-rejected` in the sibling change.
- A value the agent did not produce is a **reportable defect**, not a formatting slip — the
  orchestrator records it as a contract firing, the same as an evidence-free return.

**Interaction with `fix-brief-binding-defect`, checked for contradiction.** The two changes govern
opposite directions of travel and must resolve consistently. They do:

| What is wrong | Whose claim | Correct return | Which change owns it |
|---|---|---|---|
| A fact the brief asserted, defect survives its correction | Orchestrator's | `done`, plus a `Fact corrections:` row | sibling |
| A fact the brief asserted, defect does not survive | Orchestrator's | `remedy-rejected` | sibling |
| The candidate remedy is wrong | Orchestrator's | `remedy-rejected` | sibling |
| Evidence the contract requires cannot be produced | Delegate's | `blocked`, field named | **this change** |
| Evidence was produced but is not the agent's own measurement | Delegate's | reportable defect | **this change** |

No cell resolves to "proceed with a guess", and no cell is claimed by both changes. The
sibling makes a wrong factual row a reason to *reject a remedy*; this change makes an invented value a
*defect in the return*. The first is about input the orchestrator supplied; the second is about output
the delegate supplied. They meet only at the shared status set, which neither extends.

## Pinned implementation parameters

Nothing below is decided during implementation.

**Terminal statuses:** exactly three — `done`, `blocked`, `remedy-rejected` (the third from
`fix-brief-binding-defect`). This change adds none.

**The classification rule** (verbatim, orchestrator-side, in `spec-to-pr/SKILL.md` at the delegation
site and restated in `subagent-brief.md` §5 as what the contract means):

> Read a return for its evidence before you read it for its words. It is `done` only if it carries a
> status token from the set this brief named AND every evidence field slot 5 required. A return
> carrying neither — including one that reads as finished, reports a result, or says it is waiting on
> something — is `blocked`, whatever its prose says. This is a scan, not a judgement: name the fields,
> then look for them.

**The delegate liveness line** (verbatim, `subagent-brief.md` §5):

> Do not end your turn while a command you started is still running. Run every gate in the foreground
> and wait for it, however long it takes. A backgrounded command does not survive your return, and
> ending your turn is what produces your return — there is no notification that can reach you
> afterwards. If a gate cannot finish inside one foreground call, do not start it: return `blocked`
> naming the gate and what it needs.

**The no-invented-values line** (verbatim, `subagent-brief.md` §5, standard in every brief):

> Every value this contract asks for is one you produced. If you cannot produce one — the gate would
> not run, the command is unavailable, the file is not there — return `blocked` and say which field
> you could not fill and why. Do not construct, estimate, infer, or carry a value over from anywhere
> else. Stopping with an honest gap is a successful return; a value you did not measure is a defect,
> and it is reported as one.

**The brief-side prohibition** (verbatim, `subagent-brief.md` §3, extending the existing block rather
than replacing it — the existing `git diff <base>...<branch>` read-only guidance stays):

> Do NOT run `git checkout`, `switch`, `branch`, `stash`, `reset`, `commit`, `push`, or
> `worktree add`, or anything else that mutates repository state. Do NOT kill, restart, or clean up a
> process you did not start, and do not delete or regenerate a build, cache, or dependency directory
> you did not create — the orchestrator or a sibling agent may be using it.

**The orchestrator-side prohibition** (verbatim, `concurrent-runs.md`, new case):

> While a dispatch of yours has not returned, or a command started under it may still be running, the
> checkout is not yours. Run no `git checkout`, `switch`, `branch`, `stash`, `reset`, `commit` or
> `push` in it, start no gate in it, and delete or regenerate nothing it builds into. A failure
> observed in a checkout you touched while a dispatch of yours was live is not evidence of a
> regression — re-derive it from a quiet tree before investigating it as one.

**The synchronous-gate threshold:** there is **no duration constant**. The sync/async decision keys on
the runner (dispatched agent → always foreground; orchestrator → unchanged). The only threshold is the
delegability ceiling — *what one foreground call permits in the harness this is running in* — which the
orchestrator resolves at dispatch time and which is never written into the shipped prose as a number.

**The on-a-miss ladder:** classify `blocked` and record a contract firing → read-only quiet check →
**re-dispatch once** (matching the existing one-re-dispatch cap for a `blocked` return) → take over
only after the quiet check is clean. Take-over before the quiet check is prohibited.

**Section retitle:** `references/concurrent-runs.md`'s H1 and `spec-to-pr/SKILL.md`'s section heading
both drop "worktree-per-session" as the whole subject and name two cases: two sessions in one clone,
and an orchestrator and its own delegate in one checkout. The **file path does not change** — both
citing sites reference it by path.

**Slots:** five, unchanged. §3 and §5 are edited; no slot is renamed, renumbered, or added.

**Caps:** none move. No round cap, test-round cap, or dispatch cap is touched by this change.

## Risks / Trade-offs

- **A foreground gate could hit the harness's call limit and fail in a new way** → that is the case the
  ceiling branch exists for, and it fails *loudly* (a timed-out foreground call is visible) rather than
  silently (a backgrounded job whose result is never collected). The trade is a visible failure for an
  invisible one, which is the trade this whole change makes.
- **The delegability ceiling is unpinned, so an orchestrator must judge it** → accepted deliberately.
  Pinning a number into synced core makes it wrong in every harness whose limit differs. The judgement
  is a comparison against a limit the orchestrator can read, not an estimate of an unknown.
- **"Any command started under the dispatch" may not be checkable read-only in every environment** →
  where it is not, the quiet check cannot pass, and the ladder's own ordering then keeps the
  orchestrator out of the tree rather than letting it proceed on an unverified assumption. Failing
  closed here costs a re-dispatch; failing open costs #115.
- **Classifying an evidence-free return as `blocked` will sometimes be wrong** — a delegate that really
  did finish but formatted its return badly gets re-dispatched. Accepted: the cost is one duplicated
  dispatch, against a mode of failure that cost ~40 minutes and produced a false regression
  investigation. The asymmetry is the argument, and the contract-firing record makes a high rate of
  this visible rather than invisible.
- **Two prohibition blocks (brief-side and orchestrator-side) can drift apart** → they are deliberately
  *not* identical text — one is addressed to a delegate about a checkout it is borrowing, the other to
  an orchestrator about a checkout it is lending — and each is pinned verbatim above, so a later edit
  to one is visible as a divergence from a stated parameter rather than a stylistic difference.
- **The retitle touches a section two sites reference** → both reference it by path, not by heading,
  and the check is one grep, pinned as a task.
- **Synced-core portability** → all three edited files ship verbatim. No line may name the consuming
  repo's gate command (the observed incident's `npm run verify` must not appear in shipped prose), any
  dev-tree path, or an absolute developer path. The plugin's existing conformance scan over synced core
  is the check.
- **Overlap with `fix-brief-binding-defect` in §5** → both changes add to the same slot. This one runs
  second and composes: its three lines are properties of *every* contract block in the slot, including
  that change's fix-brief block, and are written to sit above or below the blocks rather than inside
  one. If the sibling's §5 edit has not landed when this is implemented, the classification line still
  reads correctly against the two-status set and gains the third status when that change lands.
