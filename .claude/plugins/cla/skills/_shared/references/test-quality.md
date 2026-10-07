# Test-quality rules

Read at the point tests are **authored** — the Implement phase — not when a gate
turns red. A rule that arrives after the assertion exists only bites on the
rewrite, which is the smaller half of the risk.

A green gate proves the assertion passed. It never proves the assertion was worth
making, and these are the ways it is not.

**Read what applies.** This reference is two files. This one holds the rules for
any test; writing an ordinary unit test, it is the whole reference for you. The
rules for a **gate** — a check whose feature is detecting something, where a green
run is the evidence everyone downstream relies on — are in `test-quality-gates.md`
beside it. Read that one too when the test you are writing is a gate, or when you
are proving one by planting what it should catch.

**Which tests a change owes** is set elsewhere: each scenario a change adds or rewrites gets a test task,
whose test carries a `scenario: <spec> / <heading>` comment line above it, or a tasks.md line
`manual: <heading>: <reason>` (`multi-spec/references/authoring-brief.md`, step 4), and spec-to-pr's
Implement post-check greps for every test a ticked task names.

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
