# Test-quality rules

Read at the point tests are **authored** — the Implement phase — not when a gate
turns red. A rule that arrives after the assertion exists only bites on the
rewrite, which is the smaller half of the risk.

A green gate proves the assertion passed. It never proves the assertion was worth
making, and these are the two ways it is not.

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

## Prove a gate by planting what it is supposed to catch

The two rules above are about a test that cannot fail. A **gate** — a guard standing
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

## Three ways the planting itself goes wrong

Planting a failure only proves something if the plant reaches the value the assertion
reads. Each of these produced a confident, wrong conclusion in a real run.

**The plant must land on the tested value, not merely change the file.** Three shapes,
all of which report "caught" while testing nothing. A plant that is a *superstring* of
the asserted value — renaming an index to `<name>_MUTATED` still satisfies a
`toContain`, and the author concluded the *test* was broken. A plant that lands in a
comment or docstring beside the data rather than in the data. And a plant that leaves
the file malformed, so the guard exits non-zero because it is rejecting a broken file,
not because it detected the change. Before reading the result, confirm what actually
moved.

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
`OK` with the forbidden import sitting on line 2 of the file whose reachability was the
stated reason for widening the guard's scope.

## Where planting is worth the cost, and where it is not

**Plant when a passing assertion is uninformative on its own** — the test asserts
*absence* ("no violations", "nothing found", "exit 0", an empty list). A broken
implementation produces the identical green, so nothing in the output distinguishes
working from dead.

**Do not bother when the assertion pins a specific positive value** — a count, a
string, a returned shape. There the test already is the plant: break the code and the
value changes, so it goes red on its own.

**Planting is blind to an input space you never enumerated, and this is the expensive
one.** It tests the implementation you wrote, never the cases you failed to think of.
Measured: a guard reported every planted failure caught while missing five of the eight
spellings of the operation it existed to detect, because the plants were derived from
the code rather than from the tool's documented grammar. For anything parsing an
external contract — command-line flags, a file format, an API shape — **enumerate from
the primary source first, then plant.** Reversing that order buys confidence in the
half you already had right.

**A floor is unexercised while the thing it floors is healthy.** A minimum-count
assertion, or a cap that only bites on bad input, cannot be reached by planting against
a correct tree — the plant has nothing to change. Cover those structurally instead,
with a test that gives the check bad state and asserts it notices. That form keeps
holding after a later refactor turns the check into a no-op, which a one-time plant
does not.

## Why these and not a longer list

Every rule above is the same failure mode seen from a different angle: the suite goes
green and the coverage is imaginary. A tautological assertion cannot fail; a floor far
below its population will not fail; a gate nobody planted a failure against has not
been shown to fail; a plant that missed the value under test proves nothing while
reporting success; and a plant derived from the code cannot reach a case the code
never considered. All of them are the class a guard asserting over a collection it
never fills belongs to (the source repo's
`plugin-tests/tests/conformance/test_guards_are_not_vacuous.py`).

Note the shape of the last two. The earlier rules ask whether a test *can* fail. Those
two ask whether the evidence you gathered is about the thing you meant — which is why a
clean run is evidence about the plants you thought of and nothing else, and why it is
worth naming what you did not plant rather than letting an all-green report imply a
coverage it does not have.

Rules about naming, length, or structure are style. These are about whether the test
can fail at all — which is the only property that makes a green run mean anything.
