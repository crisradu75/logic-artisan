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

Measured in one session (2026-08-23) during a ~70-file tree move: `>= 55` against a
real 83 — a 34% collapse would have passed; `>= 6` against a real 15; and `>= 95`
against 96, which is the shape working as intended. State what you derived the number
from, in the assertion's own comment, so the next person moving the tree can re-derive
it rather than guess whether the margin is deliberate.

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

## Why these and not a longer list

Every rule above is the same failure mode seen from a different angle: the suite goes
green and the coverage is imaginary. A tautological assertion cannot fail; a floor far
below its population will not fail; a gate nobody planted a failure against has not
been shown to fail. All of them are the class a guard asserting over a collection it
never fills belongs to (the source repo's
`plugin-tests/tests/conformance/test_guards_are_not_vacuous.py`).

Rules about naming, length, or structure are style. These are about whether the test
can fail at all — which is the only property that makes a green run mean anything.
