---
name: diagnose
description: "Find the cause of a failure instead of guessing at fixes. Builds a deterministic pass/fail loop first, reproduces the reported bug, ranks falsifiable hypotheses before touching anything, instruments one variable at a time with tagged [DEBUG-xxxx] logs, writes the regression test before the fix at a genuinely correct seam, then cleans up and states the confirmed cause in the commit message. Escalated from a Test phase when two rounds spend themselves on the same stated cause with the gate still red. Triggers on /cla:diagnose or natural language like 'diagnose this', 'why is this test failing', 'I keep guessing at this bug', 'find the root cause', 'this failure makes no sense', 'I have tried three fixes and it is still red'."
argument-hint: "[what is failing | (empty — infer from the conversation)]"
allowed-tools: Read, Grep, Glob, Edit, Write, Bash, AskUserQuestion, Agent
---

# /cla:diagnose — find the cause, then fix it

Debugging is the one job every other skill in this harness refuses. `feedback`
refuses it mechanically — no `Edit` and no `Bash` in its `allowed-tools`, so it
cannot investigate even when it wants to. `lite-pr` and `spec-to-pr` both bound
how *many* fixes a red gate gets, which limits volume and not reasoning. This
skill holds the method, and the two Test phases cite it rather than restating it.

The failure it exists to stop is the plausible edit: a change that makes the
check pass without touching the defect. A gate cannot tell the difference, so
nothing downstream catches it.

`Edit` and `Bash` are in `allowed-tools` deliberately. They are what `feedback`
withholds, and this is the skill that job hands off to.

## Mode: standalone or escalated

Detect which, first, because the hypothesis gate below branches on it.

- **Standalone** — invoked by the user directly (`/cla:diagnose`, or natural
  language). An invoker is present.
- **Escalated** — reached from a running `lite-pr` or `spec-to-pr` Test phase,
  after two rounds spent on the same stated cause with the gate still red.

**An escalation inherits the parent run's autonomy contract.** It does not stop
to ask. Invoker presence is the honest signal, and a mid-run halt to ask a
question nobody is there to answer is how an unattended run dies at 3am.

The discipline is identical in both modes: hypotheses ranked, falsifiable, and
written down before anything is touched. Only who prunes them changes.

## Phase 1 — a deterministic pass/fail loop, before anything else

Build a way to make the failure happen and un-happen on demand. Everything after
this depends on it: a hypothesis is only falsifiable against a loop that answers
the same way twice.

Pick the cheapest strategy that fits. The ranked list, with what each one is for
and when it stops being worth it, is in `references/strategies.md` — **read it
before choosing**, because the order encodes cost, and the common error is
reaching for a browser when a failing test would have done.

**Done when:** one command reproduces the failure and exits non-zero, and the
same command exits zero against a known-good state (an earlier commit, a
reverted file, a different input). Write the command down. It is the loop.

**No buildable loop is a stop, not a licence to proceed.** Say so plainly, say
what you tried, and hand back. Guessing without a loop is what this skill
replaces; doing it faster is not an improvement.

## Phase 2 — reproduce, and confirm it is the reported bug

A loop that fails is not yet evidence. Confirm the failure it produces is the
one that was reported, not a second defect standing next to it.

**Done when:** the loop's output matches the reported symptom in specifics — the
same assertion, the same error text, the same wrong value — and the report names
which. A near-miss here costs the whole run: every hypothesis below is about the
wrong failure, and every one of them gets falsified correctly.

## Phase 3 — rank falsifiable hypotheses, before touching anything

Write 3–5 hypotheses. Each one states a cause specific enough that a fix follows
from it, plus **what would prove it wrong**.

- ✅ "The comparison is case-sensitive but the column collation lower-cases the
  stored value. Falsified if the same query with an already-lower-cased literal
  also fails."
- ❌ "There's a mismatch in the auth check." — a restatement of the symptom, and
  nothing can falsify it.

Rank by likelihood times cheapness to test. The top one is rarely the most
interesting; it is the one that costs least to eliminate.

**The gate is mode-aware:**

- **Standalone** — show the ranked list and let the user prune it, via
  `AskUserQuestion`. They often know something that kills three of them at once.
- **Escalated** — proceed on the top hypothesis without asking. Write the full
  ranked list into the report regardless, so the reasoning survives the run.

**Done when:** the list exists in writing, each entry names its falsifier, and
one is selected. Not before an `Edit`. Not after.

## Phase 4 — instrument one variable at a time

Change one thing, run the loop, read the result. Then change it back.

Tag every temporary log, print, or probe with `[DEBUG-xxxx]`, where `xxxx` is
four hex characters chosen once for this run. The tag is what makes Phase 6's
cleanup a grep rather than a memory exercise.

```
console.log(`[DEBUG-a3f1] collation=${row.collation} literal=${literal}`)
```

**Two variables at once forfeits the round.** If both change and the result
moves, the run has learned nothing and spent a cycle. This is the same failure
as the four-fixes-at-once shape the Test phases bound, one level down.

**Done when:** the selected hypothesis is confirmed or falsified against the
loop, with the output that settles it captured. Falsified → return to Phase 3
and take the next one. Never edit past a falsified hypothesis on the grounds
that the fix "probably still helps".

## Phase 5 — the regression test comes before the fix

Write a test that fails for the confirmed cause, at a seam where the cause
actually lives. Run it, see it fail, and only then fix.

A test written after the fix passes immediately, which proves it runs and
nothing else. This ordering is the only cheap evidence that the test would have
caught the defect.

**"There is no correct seam" is a finding, not an obstacle.** When the cause
sits somewhere no test can reach without contorting the design — a private
closure, a module-level side effect, an object with no injectable boundary —
stop and write it down rather than forcing a test into the wrong place or
skipping the test.

Write it as a dated finding into `cla.io/feedback/`:

```markdown
## <date> — no correct seam for <the confirmed cause>

**Confirmed cause:** <one sentence, from Phase 4>
**Why no seam:** <what a correct test would need that the code cannot offer>
**What a fix would require:** <the structural change, stated plainly>

Next step: `/cla:shape-decision`.
```

`cla.io/feedback/` is the capture end of this repo's existing capture → shape
pipeline, and `shape-decision` is where an architectural change gets weighed.
Putting it there costs one file and loses nothing.

**Done when:** either a test fails for the right reason and then passes after
the fix, or a dated finding exists in `cla.io/feedback/` naming
`/cla:shape-decision`.

## Phase 6 — clean up, then state the cause in the commit

**Every `[DEBUG-xxxx]` tag is removed. Prove it with a grep that returns
nothing:**

```
grep -rn "\[DEBUG-" <the paths this run touched>
```

A non-zero hit count is a halt, not a warning. A leaked debug log ships noise
into production output and reads as deliberate to the next person.

**The tag pattern now lives in two files, and a rename must touch both.** This
skill is one; `${CLAUDE_PLUGIN_ROOT}/skills/spec-to-pr/references/ship.md` §2a
is the other, where the same grep runs at the commit choke point so a tag leaked
by an *interrupted* run is still caught. Changing the tag here without changing
it there leaves the Ship scan searching for a string nothing writes — it passes,
and it checks nothing.

**The commit message states the confirmed hypothesis**, not the symptom and not
the edit:

```
fix: lower-case the literal before the collation-sensitive comparison

The column collation lower-cases stored values, so an upper-case literal
never matched. Confirmed by [DEBUG-a3f1] logging both sides of the compare.
```

**Done when:** the grep returns nothing, the regression test passes, and the
commit message names the cause.

## References

- **`references/strategies.md`** — the ranked feedback-loop strategies for
  Phase 1, cheapest first, each with what it is for and when it stops paying.
  Read before choosing a strategy.
- **`${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/test-quality.md`** — the
  rules the Phase 5 regression test is held to, including how a test written
  from a wrong model passes and defends the defect.
- **`${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/bash-discipline.md`** — for
  the Phase 1 loop and the Phase 6 grep.
