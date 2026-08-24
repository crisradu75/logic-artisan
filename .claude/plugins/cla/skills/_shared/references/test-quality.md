# Test-quality rules

Read at the point tests are **authored** — the Implement phase — not when a gate
turns red. A rule that arrives after the assertion exists only bites on the
rewrite, which is the smaller half of the risk.

A green gate proves the assertion passed. It never proves the assertion was worth
making, and these are the ways it is not.

**Read what applies.** Everything above "A non-vacuity floor" is about any test at
all. From that section onward the subject is a **gate** — a check whose feature is
detecting something, where a green run is the evidence everyone downstream relies
on. Writing an ordinary unit test, the opening sections are the whole file for you.

## No tautological assertion

An assertion that recomputes its expected value the way the code does passes for
any implementation, including a wrong one:

```python
# tautological — mirrors the implementation, so it cannot fail
assert slugify(name) == name.lower().replace(" ", "-")

# real — the expected value is stated, so a wrong implementation fails
assert slugify("My Thing") == "my-thing"
```

Pin the literal expected value, or derive it by a genuinely different route
(a fixture, a hand-checked table, an independent implementation).

## No implementation-detail testing

Assert observable behaviour at a real seam — a return value, a written file, an
exit code, a rendered string. Not a private helper's internals, not a call count
that no caller depends on.

A test coupled to structure fails on every refactor and catches no defect, which
inverts what a test is for: it makes the safe change expensive and lets the
dangerous one through.

## A non-vacuity floor must track its population

A guard that scans a set of files often carries a floor — `assert len(files) >= N` —
so that a discovery collapse fails loudly instead of passing over nothing. The floor
only does that job while `N` sits *near* the real count. Left far below it, the floor
becomes decorative: it still passes, so it still reads as protection, while a large
collapse sails through.

So: **whenever the population changes, re-derive the floor from the new real count in
the same edit** — a move, a rename, a scope split, a deletion. And **never lower a
floor to survive a change**; a floor relaxed to go green certifies exactly what it
stopped checking, which is worse than never having written it, because now something
green is standing where the check used to be.

Measured in one session (2026-08-23) during a ~70-file tree move, three floors found
stale in the source repo and each raised in the same edit that found it: one sat at
`>= 55` against a real 83 (a 34% collapse would have passed) and is now `>= 80`;
another at `>= 6` against a real 17 and is now `>= 15`; a third at `>= 95` against 96,
which is the shape working as intended and was left alone. Quote the *current* value
when citing one — a floor named here after being raised is a number a reader will
grep for and not find.

State what you derived the number from, in the assertion's own comment, so the next
person moving the tree can re-derive it rather than guess whether the margin is
deliberate.

## An alarm must be able to fire at the volume it will really see

The floor above is *decorative* when its number drifts below its population: the
comparison still runs and only its failing branch is dead. Here the number sits
**above** the population, and the enforcement path does not run at all — the guard
is correct, and the volume it meets on an ordinary day is outside the range where
it does anything.

**The boundary between the two sections is what you can count.** The floor rule
above assumes a population you can enumerate in the tree — files on disk, entries
in a manifest — so its instruction is to re-derive the number from the real count
in the same edit. Where the population is **runtime traffic** — a nightly batch, a
live rate, an incoming corpus — there is nothing in the tree to re-derive from,
and that is the case this section owns.

Three shapes, one cause. The instances below were measured in one six-change run
in a repo consuming this plugin, and are reported here rather than re-derived:

- **A minimum-sample precondition larger than any real batch.** The enforcement
  path exists and never runs. A rate floor required 200 samples, in a job seeing
  113–190 a night.
- **A threshold tuned on the wrong run, or against the wrong statistic.** Pinned
  to a backfill or a full-corpus measurement, it false-fires on the small batches
  that are the steady state. One was derived from a measured share of items
  missing a *term* while the code it guarded counted missing *records* — the same
  defect reached from the calibration end rather than the volume end.
- **An alarm too coarse to see the failure it is for.** One watching a combined
  counter sees only total collapse: retire three of four terms and one whole
  category stops permanently while the total stays in the thousands, well clear
  of anything. *The same alarm* would also have fired on roughly half of all
  two-item batches, because only 30% of real items carried the thing it counted —
  one alarm, unreachable in one direction and trigger-happy in the other.

**So state the volume, and where the volume came from.** Any new alarm, threshold
or minimum-sample precondition carries, in a comment beside itself:

1. **The volume it will see in ordinary steady-state operation, and the source of
   that figure** — the query, log window or run it came from, named so the next
   person can re-run it rather than guess. This is the condition that bites: the
   defect happens because the author is holding a backfill-sized or full-corpus
   sample at the moment the number is chosen, and requiring the *number* without
   its provenance leaves that exact mistake available.
2. **The guard's outcome at both ends of that range**, not at one point — which is
   what separates "cannot fire" from "fires constantly".
3. **Confirmation that whatever sample it was calibrated against sits inside that
   range** — and if it does not, which run it came from.

The third shape needs one more, because stating a volume does not fix it: an alarm
over an **aggregate** also names the sub-population it can no longer see.

**What this shares with the sections below, and what it does not.** Two of them
come close, and both reach this only under a condition they do not state — which
is what this section adds rather than replaces.

- **"A check planting cannot reach still has to be proven, structurally"** is the
  nearest, and it names a minimum-count floor outright. Its remedy — hand the
  check bad state and assert it notices — does catch this, *if the bad state is
  sized to the real operating point.* Supply a batch of 150 against a
  200-precondition and it goes red immediately; supply a comfortable 500 and it
  passes, having proven the guard works at a volume it will never see.
- **"A mirror that greps the guard's own source"** has the same conditional
  remedy: extract the comparison as a pure function and feed it synthetic inputs
  *in every direction the guard claims to check*. Sizes below the precondition are
  one of those directions, and are the one nobody thinks to supply.

What reaches it nowhere is a plant against the live tree. The guard fires
correctly, because the comparison was never the broken part — what goes
unexamined is the **precondition gating when the comparison runs**. Mutating that
constant does surface it, but as a *surviving* mutant rather than a red run, which
is the signal most easily read as noise.

So the distinguishing question is neither "can this assertion fail" nor "does this
test check the logic", but **"at the volume this will meet on an ordinary day, is
this reachable at all?"**

## Which gates are worth planting against

Not a rule about how a test fails — a routing question, answered before the gate
sections below are worth reading.

**Plant when a passing assertion is uninformative on its own** — the test asserts
*absence*: "no violations", "nothing found", "exit 0", an empty list. A broken
implementation produces the identical green, so nothing in the output distinguishes
working from dead.

**Skip it when the assertion pins a specific positive value** — a count, a string, a
returned shape. There the test already is the plant: break the code and the value
changes, so it goes red unaided. This narrows nothing else; a fix for a review finding
still earns its evidence, and this only says which technique supplies it.

Those two are the whole of the routing. What to do about a check planting cannot
reach is a rule, and lives with the other rules below.

## Prove a gate by planting what it is supposed to catch

The first rules in this file are about a test that cannot fail. A **gate** — a guard standing
between a defect and a release — has a sharper version of the same problem, because
its green run is the evidence everyone downstream relies on.

Reading a gate does not establish that it works. Planting the thing it exists to catch
does. Break it deliberately, watch it go red, restore exactly, watch it go green —
and report both halves, because a gate nobody watched fail is indistinguishable from
a gate that never looked.

This is `CLAUDE.md`'s "break the fix and confirm a test fails" pointed at a guard
rather than at a fix, and in one session it was decisive three times: a conformance
gate that had silently stopped running at all (planted a real project token — the
suite stayed green), an allowlist that accepted the very shape it replaced a denylist
to reject (planted a dev asset — the scan reported clean), and a non-vacuity check
whose assertion was tautological (hardcoded the value it derived — every assertion
still passed). None was found by reading. Each took ~60 seconds to plant.

## How planting goes wrong

Planting a failure only proves something if the plant reaches the value the assertion
reads. Each of these produced a confident, wrong conclusion in a real run.

**The plant must land on the tested value, not merely change the file.** Three shapes,
all of which report "caught" while testing nothing. A plant that is a *superstring* of
the asserted value — renaming an index to `<name>_MUTATED` still satisfies a
string-containment `toContain`, and the author concluded the *test* was broken (against
an array, the same plant correctly fails to match). A plant that lands in a comment or
docstring beside the data rather than in the data. And a plant that leaves the file
malformed, so the guard exits non-zero because it is rejecting a broken file, not
because it detected the change.

Three checkable conditions, before you read the result. Diff the planted file and
confirm the change sits in the data, not in a comment. Re-parse or re-load it and
confirm it is still well-formed. And read the failure message — it must name the value
you planted. A non-zero exit that names nothing, or a diff touching only a comment,
means the plant did not land: restore and re-plant rather than recording a kill.

**A plant reported by someone else is a claim, not a result.** When a delegate says it
mutation-tested its own guard, re-run one of the plants yourself before believing the
guard is sound in both directions. This is the step most worth never skipping, because
its cost is one command and its failure mode is a guard everyone believes in.

**A mirror that greps the guard's own source proves only that a word was written.**
When a guard needs live or external data the test suite cannot supply, the tempting
substitute is a test asserting the guard's *source text* contains certain strings.
`expect(script).toContain("declared AVAILABLE")` cannot distinguish a guard sound in
both directions from one sound in only one, because both produce the same source.
Extract the comparison as a pure function and feed it synthetic inputs in every
direction the guard claims to check. Doing exactly that once immediately surfaced a
real bug in the extraction — a loop reading a module-level constant instead of its own
parameter, so the function silently ignored its first argument.

**A guard scoped to more than one tree needs a plant in EACH tree.** A pattern copied
from a sibling guard carries the sibling's path assumptions, and the failure mode is
"matches nothing, exits 0" — indistinguishable from passing. One real instance printed
`OK` with the forbidden import sitting on line 2 of a file in the very tree whose
reachability was the stated reason for widening the guard's scope. "I modelled this on
the existing guard X" is itself the trigger for this one — it is the sentence that
should make you plant in every tree rather than trust the pattern, and the fix there
was to match the import specifier's path tail rather than a prefix that only held for
the original's tree.

**A check planting cannot reach still has to be proven, structurally.** A minimum-count
floor, or a cap that only bites on malformed input, has nothing to change when you
plant against a correct tree — the tree is already the good case, so the plant is a
no-op and reports nothing. Two ways out, and the second is better: mutate the *check*
rather than the asset, or write a test that hands the check bad state and asserts it
notices. A planted failure is evidence at one moment; a test that supplies bad state
keeps holding after a later refactor turns the check into a no-op. Left uncovered,
these are the pure form of this file's subject — a check that passes, reads as
protection, and has never once been shown able to fail.

**Planting is blind to an input space you never enumerated, and this is the expensive
one.** It exercises the implementation you wrote, never the cases you failed to think
of — so a guard can report every plant caught while missing most of what it exists to
detect. Measured on this plugin's own destructive-git hook: every plant was reported
caught, and the hook matched three of the eight ways the operation can be spelled,
because the plants were derived from the regex that existed rather than from the
command's documented grammar. One line of the tool's manual page named the other five.

So for anything parsing an external contract — command-line flags, a file format, an
API shape — **enumerate from the primary source first, then plant.** Reversing that
order buys confidence in the half you already had right, and buys it loudly.

## Why these and not a longer list

Every *rule* here is the same failure mode seen from a different angle: the suite goes
green and the coverage is imaginary. A tautological assertion cannot fail; a floor far
below its population will not fail; an alarm whose precondition sits above the volume
it will really see never runs at all; a gate nobody planted a failure against has not
been shown to fail; a plant that missed the value under test proves nothing while
reporting success; and a plant derived from the code cannot reach a case the code
never considered. All of them are the class a guard asserting over a collection it
never fills belongs to (the source repo's
`plugin-tests/tests/conformance/test_guards_are_not_vacuous.py` is the worked
example; a consuming repo has no such file, which is why it is named as the source
repo's rather than as something to go and run).

(Two sections are not in that list. "Which gates are worth planting against" is
routing, not a rule — it answers whether the gate sections after it apply to you at
all, which is why it sits before them rather than claiming membership here. "No
implementation-detail testing" is a rule, but its failure mode is the opposite one:
the test fails too easily rather than not at all, so it does not belong to the shared
shape this list is drawn around.)

Note the shape of the last two entries. The earlier ones ask whether a test *can* fail.
Those ask whether the evidence you gathered is about the thing you meant — which is why
a clean run is evidence about the plants you thought of and nothing else, and why it is
worth naming what you did not plant rather than letting an all-green report imply a
coverage it does not have.

Rules about naming, length, or structure are style. These are about whether the test
can fail at all — which is the only property that makes a green run mean anything.
