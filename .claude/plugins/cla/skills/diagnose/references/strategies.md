# Phase 1 strategies — building a deterministic pass/fail loop

Ranked cheapest first. Take the first one that can actually reproduce the
failure; do not skip down the list for a more interesting instrument.

**The order encodes cost, and cost here means the whole run.** A browser session
that takes 40 seconds per cycle turns a ten-hypothesis diagnosis into seven
minutes of waiting. A failing test that runs in 200ms turns the same diagnosis
into a conversation. The common error is reaching for the powerful tool because
the bug feels complicated — the bug's complexity has no bearing on which loop
observes it.

## 1. A failing test

The best loop, and the one that survives the run: it becomes the Phase 5
regression test.

Use when the failure is reachable from code the test suite already imports.

Stops paying when the failure needs state the suite cannot build — a live
session, an external service, a specific clock.

## 2. A curl / HTTP script

One request, one assertion on the response. Cheap, scriptable, and it isolates
the server from every client concern.

Use when the failure is in a request/response boundary and you can name the
request that provokes it.

Stops paying when the failure needs several ordered requests carrying state
between them — write it as a script and it becomes strategy 6.

## 3. A CLI diff

Run the command two ways and diff the output. The difference is the evidence.

Use when there is a known-good invocation to compare against: an earlier commit,
a different flag, another input file.

Stops paying when the output is nondeterministic — timestamps, ordering, ids. A
diff of noise reads as a finding and is not one. Normalise first or move on.

## 4. A headless browser

Drive the real page. Expensive per cycle, and the first strategy that can
observe layout, stacking, and what a breakpoint does to the flow.

Use when the failure is genuinely visual or genuinely in the browser runtime —
geometry, an event that only fires on a real element, a state a round trip
leaves behind.

Stops paying — in fact never starts — when the question could be answered by
reading generated source. That is a grep, and it is free.

## 5. Trace replay

Replay a captured trace, log, or request recording against the current code.

Use when the failure happened somewhere you cannot reach: production, a user's
machine, a CI run that has since been recycled.

Stops paying when the trace lacks the field you need. A trace answers only what
it captured, and no amount of replay adds a column.

## 6. A throwaway harness

A small script that sets up the exact state and calls the exact function. Not
committed, not a test — deleted when the run ends.

Use when the failure needs a state the test suite cannot express, but which you
can build in twenty lines.

Stops paying when the setup grows past a page. At that size the harness has its
own bugs, and a bug in the instrument reads exactly like a bug in the subject.

## 7. Fuzzing

Generate inputs until one fails. Cheap to write, unbounded to run.

Use when the failure is input-dependent and the failing input is unknown — a
parser, a validator, an encoder.

Stops paying when the input space is small enough to enumerate. Enumerate it.

## 8. Bisection

`git bisect`, or a manual halving over commits, flags, or dependency versions.

Use when the failure is new and something that used to work no longer does.
Needs a reliable test command, so it composes with strategies 1–3 rather than
replacing them.

Stops paying when the "good" end is not actually good, which is common and
silent. Verify both ends before starting, or bisect converges confidently on
nothing.

## 9. Differential testing

Run two implementations against the same inputs and compare. The old path
against the new one, one library against another, two environments.

Use when a rewrite or migration broke something and both sides still exist.

Stops paying once one side is deleted. Do this before the cleanup commit, not
after.

## 10. An ad-hoc human-in-the-loop driver

Ask the user to perform the steps while the run observes. The slowest loop
available, and the last resort.

Use when reproduction needs credentials, hardware, or a judgement no script can
make.

Stops paying immediately once any strategy above becomes possible. A human loop
costs the user's attention, which is the most expensive input this harness
spends.

## When none of these is buildable

**Stop and say so.** Name the strategies tried and why each failed, and hand the
failure back.

This is a real outcome, not a failure of effort. A diagnosis without a loop is a
sequence of guesses with better formatting — the exact thing this skill exists
to replace. Proceeding anyway spends the same budget and produces a fix nobody
can verify.
