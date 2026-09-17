"""Mutation batch for test_guards_are_not_vacuous.py.

**THIS FILE WAS EXEMPT FROM NEEDING A BATCH, AND THE EXEMPTION COST SOMETHING.**
The stated reason was "meta-guard: carries seeded-input tests of its own checker
instead", and it was wrong on its own terms: the checker (`_feeds`,
`_empty_asserted_names`, `find_vacuous_asserts`) lives INSIDE the guard file, so
a mutant edits the checker and the killing assertion comes from that same file's
seeded inputs. Nothing is circular — it is the same shape
`mutants/consistency/test_subprocess_encoding.py` already has, and the same
argument that took `test_mutate.py` off the exempt list.

What it cost: `_feeds` was widened to treat a collection passed to ANY call as
"fed", which swept in the collection's appearance in the assertion's own failure
message. `assert not problems, "\\n".join(problems)` — the standard guard shape
here — became unreportable, and 29 of the 68 policed empty-assertions were
immunised against the exact defect this module exists to find. A review caught
it; no gate did, because the one file that polices vacuousness was the one file
nothing mutated.

**So mutants 1 and 2 are the regression itself, re-broken from both ends.** The
rule is keyword-only AND skips calls inside an assertion; either half alone lets
the defect back, so each is mutated separately rather than together. Mutating
them as a pair would have died just as loudly while proving only that one of them
matters.

**Mutants 3 and 4 are the opposite direction**, and they are here because
CLAUDE.md's check 4 is explicit that correcting one return path of a function
commonly breaks another. `_feeds` has exactly that shape — several independent
ways to answer True — so narrowing the call rule could silently have taken the
tuple-unpack and out-parameter widenings with it. These two prove it did not.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/conformance/test_guards_are_not_vacuous.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]

GUARD = DEV / "tests" / "conformance" / "test_guards_are_not_vacuous.py"

# Scoped to the ONE guard file: everything this batch breaks is defined in it,
# and the killing assertions are its own seeded-input tests.
TARGETS = [GUARD]

MUTANTS = [
    (
        # THE REGRESSION, half one. Accepting a POSITIONAL argument sweeps up
        # every read of the collection — len(), print(), "\n".join() — and each
        # of those immunises it.
        "the out-parameter rule accepts positional arguments again, so any READ "
        "of a collection counts as filling it",
        GUARD,
        "                for kw in sub.keywords:",
        "                for kw in [*[type('K',(),{'value':a})() for a in sub.args], *sub.keywords]:",
        TARGETS,
    ),
    (
        # THE REGRESSION, half two. Even keyword-only, a call inside the
        # assertion's own message would immunise it — the assertion cannot be
        # its own evidence.
        "calls inside the assertion stop being skipped, so the failure message "
        "counts as evidence that something fills the collection",
        GUARD,
        "            if id(sub) not in in_assert:",
        "            if True:",
        TARGETS,
    ),
    (
        # The second branch, direction one: tuple unpacking.
        "tuple unpacking stops counting as a rebind, so every name returned by a "
        "multi-value call is accused of never being filled",
        GUARD,
        "                if name in _bound_names(t):",
        "                if isinstance(t, ast.Name) and t.id == name:",
        TARGETS,
    ),
    (
        # The second branch, direction two: the genuine out-parameter.
        "the out-parameter rule is removed entirely, so a collection the callee "
        "fills is accused of never being filled",
        GUARD,
        "                for kw in sub.keywords:",
        "                for kw in []:",
        TARGETS,
    ),
    (
        # Not `_feeds` at all — the DERIVED coverage check. Dropping a name the
        # tree actually uses must be reported, or the list silently narrows
        # again.
        "a name the guards actually use is dropped from the declared list, so its "
        "assertions stop being policed and nothing says so",
        GUARD,
        '        "unimported", "unrunnable", "warnings",',
        '        "unimported", "unrunnable",',
        TARGETS,
    ),
    (
        # And the directory derivation: `glob` instead of `rglob` silently drops
        # every `tests/skills/<name>/` area.
        "discovery stops descending, so every nested skill area drops out of the "
        "scan and the guard reports clean over a third of the tree",
        GUARD,
        '    return sorted(_TESTS_ROOT.rglob("test_*.py"))',
        '    return sorted(_TESTS_ROOT.glob("test_*.py"))',
        TARGETS,
    ),
]
