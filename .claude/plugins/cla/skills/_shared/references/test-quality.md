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

## Why these two and not a longer list

Both are failure modes where the suite goes green and the coverage is imaginary —
the same class as a guard that asserts over a collection it never fills
(`conformance-checks/tests/test_guards_are_not_vacuous.py`). Rules about naming,
length, or structure are style; these two are about whether the test can fail at
all.
