"""Guard the guards: a test whose assertion can never fail is worse than none.

MEASURED, not theoretical. Two guards shipped in this repo in a single day while
asserting nothing:

  - one greped for a function's NAME instead of calling it, so mutating that
    function to `return False` — which silently disables every scope it gates —
    changed nothing it could see;
  - one collected violations into a list and, after an edit, no longer appended
    to it, so the `assert not problems` at the end was `assert not []` forever.

Both passed cleanly. Both were caught by mutation, neither by reading. A green
suite says the assertions passed; it never says they could have failed.

WHAT THIS CHECKS. The second shape, statically, because it has a precise
signature: a function that builds a collection, asserts it is empty, and never
adds to it. That is not a heuristic — a `problems`/`offenders`/`missing` list
with no `.append`/`+=`/comprehension feeding it cannot report anything.

WHAT IT DOES NOT CHECK, deliberately. It cannot tell whether an assertion is
*meaningful*, only whether it is *reachable*. The first shape above (asserting
the wrong thing) is undecidable here and stays mutation's job — see
`skill-authoring.md`'s prove-it-adjacent rule and `mutate.py`. This closes one
concrete hole; it is not a substitute for killing a mutant.
"""

from __future__ import annotations

import ast
from pathlib import Path

_DEV_TREE = Path(__file__).resolve().parents[2]

# Names that, by this repo's own convention, hold "things that went wrong".
# An empty-assert over one of these is the plugin's standard guard shape.
#
# THIS LIST WAS EIGHT NAMES AND REACHED THREE OF THEM. Measured before the
# widening, over the two guard directories as they stood::
#
#     $ python - <<'PY'
#     import ast, sys
#     sys.path.insert(0, "plugin-tests/tests/conformance")
#     import test_guards_are_not_vacuous as G
#     names = {}
#     for p in G._guard_test_files():
#         for fn in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
#             if isinstance(fn, ast.FunctionDef) and fn.name.startswith("test_"):
#                 for n in G._empty_asserted_names(fn):
#                     names.setdefault(n, []).append(p.name)
#     print(len(names), sum(map(len, names.values())))
#     print("uncovered:", sorted(set(names) - G._COLLECTION_NAMES))
#     print("dead:", sorted(G._COLLECTION_NAMES - set(names)))
#     PY
#     21 39
#     uncovered: ['absent', 'blank', 'cached', 'collisions', 'drifted', 'empty',
#      'failures', 'gaps', 'overruns', 'thin', 'unaccounted', 'undeclared',
#      'undocumented', 'unknown', 'unpoliced', 'unresolved', 'vacuous', 'wrong']
#     dead: ['bad', 'errors', 'leaks', 'stray', 'violations']
#
# Nineteen of thirty-nine empty-assertions were invisible to this guard, and the
# guard reported nothing about the ones it was not looking at — the exact failure
# it exists to catch, in itself. `test_the_declared_names_match_the_tree` below
# closes the direction a hand-written list cannot close on its own.
#
# THE FIVE DEAD NAMES STAY. A declared name matching nothing today costs nothing:
# it cannot make any assertion pass vacuously, because the filter only ever
# ADDS names to the policed set. Deleting `violations` or `errors` because no
# guard currently spells it that way would re-open the blind spot for the next
# guard that does.
_COLLECTION_NAMES = frozenset(
    {
        # Declared before the measurement above; the last five match nothing in
        # the tree today.
        "problems", "offenders", "missing",
        "violations", "stray", "leaks", "errors", "bad",
        # Added by the measurement above: every name the guards actually use.
        "absent", "blank", "cached", "collisions", "drifted", "empty",
        "failures", "gaps", "overruns", "thin", "unaccounted", "undeclared",
        "undocumented", "unknown", "unpoliced", "unresolved", "vacuous", "wrong",
        # Added when discovery stopped being the two-directory literal and
        # started covering all of `tests/`. These nine are the names the OTHER
        # ten directories use — a second nine-name blind spot that existed for
        # exactly as long as the directory list was hand-written, which is the
        # argument for deriving it.
        "enforcing", "lost", "reanchored", "remote", "small", "stale",
        "unimported", "unrunnable", "warnings",
        # `unregistered` arrived with the ledger-dir membership check in
        # `test_check_script_drift.py`, and the test below caught it on the next
        # run of this area — the first live firing of the derived direction, on
        # a name written three commits after it.
        "unregistered",
    }
)

# Names a guard asserts empty that are NOT a findings collection, keyed to the
# reason they are not. The map is the documented escape hatch for the one case
# `_COLLECTION_NAMES` cannot absorb: an `assert not x` where `x` is a scalar or a
# loop variable rather than a list of problems, which this checker's `_feeds`
# heuristic could misread.
#
# It is EMPTY today, and an empty map is the honest state rather than a missing
# mechanism — every empty-asserted name in the tree is a findings collection.
# An entry here is a decision someone writes down; a name in neither map is the
# accident the test below converts into a failure.
_NOT_A_FINDING_COLLECTION: dict[str, str] = {}

# DERIVED, not declared. This was the two-tuple
# `("tests/conformance", "tests/consistency")` — the two `*-checks` scopes that
# predated the dev-tree move — and it reached 22 of the tree's 54 test files.
# The shape it excluded was never argued for, only inherited: a `problems` list
# nothing fills is exactly as vacuous in `tests/hooks/` or
# `tests/skills/annotate/` as it is here, and the two directories it named were
# the two that happened to exist when the line was written.
#
# THE FLOORS WERE DECORATIVE UNDER IT, measured with the declared pair patched
# down to one directory at a time::
#
#     $ python - <<'PY'
#     import ast, sys
#     sys.path.insert(0, "plugin-tests/tests/conformance")
#     import test_guards_are_not_vacuous as G
#     from pathlib import Path
#     for d in ("tests/conformance", "tests/consistency"):
#         files = sorted((G._DEV_TREE / d).glob("test_*.py"))
#         n = sum(len(G._empty_asserted_names(fn))
#                 for p in files
#                 for fn in ast.walk(ast.parse(p.read_text(encoding="utf-8")))
#                 if isinstance(fn, ast.FunctionDef) and fn.name.startswith("test_"))
#         print(d, len(files), "files", n, "empty-assertions")
#     PY
#     tests/conformance   6 files 11 empty-assertions
#     tests/consistency  16 files 28 empty-assertions
#
# Dropping EITHER declared directory left the survivor clearing both `>= 6`
# files and `>= 5` assertions — so half the population could vanish with the
# guard green. That is the decorative floor the sibling
# `test_guards_have_mutant_batches.py` records re-deriving four times before it
# gave up on a global count.
#
# Same derivation as that sibling's `_guard_areas()`: read the filesystem so a
# directory added later is DISCOVERED rather than requiring someone to remember
# a list edit. `rglob` rather than `glob`, because `tests/skills/<name>/` is one
# segment deeper — the same nesting `_area_test_dir` was fixed to stop assuming.
_TESTS_ROOT = _DEV_TREE / "tests"

# What discovery is REQUIRED to reach, written down independently of the
# derivation rather than read back out of it — the duplication is the point, and
# the reasoning is `REQUIRED_SUFFIXES`' in `test_no_hardcoded_plugin_paths.py`:
# an expectation read from the thing under test measures nothing. Deriving the
# directory list from `tests/` means comparing it against `tests/` is a
# tautology, so the floor has to be an independent statement. These four span
# the three nesting depths discovery has to handle plus the two original guard
# scopes; losing one is a deliberate deletion someone argues for, not a green run.
_REQUIRED_TEST_DIRS = frozenset(
    {"tests/conformance", "tests/consistency", "tests/hooks", "tests/skills/annotate"}
)


def _guard_test_files():
    return sorted(_TESTS_ROOT.rglob("test_*.py"))


def _discovered_dirs() -> set[str]:
    return {
        p.parent.relative_to(_DEV_TREE).as_posix() for p in _guard_test_files()
    }


def _bound_names(target: ast.expr):
    """Every `Name` this assignment target binds, unwrapping tuple/list unpacking
    and starred targets.

    `isinstance(t, ast.Name)` alone missed `checked, lost, problems, fatal =
    check_anchors(...)` entirely — the target is a `Tuple`, so no name in it was
    ever seen as rebound and all four read as never fed. That is a FALSE
    POSITIVE, the expensive direction for this checker: it accuses a guard that
    is fine, and an accusation nobody can act on is how a report gets ignored."""
    for sub in ast.walk(target):
        if isinstance(sub, ast.Name):
            yield sub.id


def _feeds(node: ast.AST, name: str) -> bool:
    """True if `name` is ever grown inside `node` — appended to, extended,
    augmented, rebound to something other than an empty literal, or handed to a
    call that could fill it."""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            # name.append(...) / name.extend(...) / name.update(...)
            if isinstance(sub.func, ast.Attribute):
                tgt = sub.func.value
                if isinstance(tgt, ast.Name) and tgt.id == name:
                    if sub.func.attr in {"append", "extend", "update", "add"}:
                        return True
            # f(..., name, ...) / f(..., problems=name) — the OUT-PARAMETER
            # shape, and the second false positive widening discovery exposed:
            # `store.read_all(path, problems=problems)` fills the list inside
            # the callee, which no amount of looking at this function can see.
            #
            # This is deliberately loose. A name merely READ by a call —
            # `print(problems)` — also reads as fed, so the checker gives up a
            # little strictness to stop accusing correct guards. That trade is
            # the module docstring's stated posture: it decides whether an
            # assertion is REACHABLE, never whether it is meaningful, and a
            # missed vacuous assertion stays mutation's job.
            for arg in [*sub.args, *(k.value for k in sub.keywords)]:
                if isinstance(arg, ast.Name) and arg.id == name:
                    return True
                if isinstance(arg, ast.Starred) and isinstance(arg.value, ast.Name):
                    if arg.value.id == name:
                        return True
        # name += ...
        if isinstance(sub, ast.AugAssign):
            if isinstance(sub.target, ast.Name) and sub.target.id == name:
                return True
        # name = <anything that is not an empty literal>
        if isinstance(sub, ast.Assign):
            for t in sub.targets:
                if name in _bound_names(t):
                    v = sub.value
                    empty_literal = (
                        isinstance(v, (ast.List, ast.Set, ast.Dict)) and not getattr(v, "elts", getattr(v, "keys", []))
                    )
                    # A tuple target never binds an empty literal to one of its
                    # names, so unpacking always counts as feeding.
                    if not isinstance(t, ast.Name) or not empty_literal:
                        return True
    return False


def _empty_asserted_names(fn: ast.FunctionDef):
    """Every NAME this function asserts to be empty — `assert not x` or
    `assert x == []`."""
    names = set()
    for sub in ast.walk(fn):
        if not isinstance(sub, ast.Assert):
            continue
        test = sub.test
        if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
            if isinstance(test.operand, ast.Name):
                names.add(test.operand.id)
        if isinstance(test, ast.Compare) and isinstance(test.left, ast.Name):
            for op, cmp in zip(test.ops, test.comparators):
                if isinstance(op, ast.Eq) and isinstance(cmp, (ast.List, ast.Set, ast.Dict)):
                    if not getattr(cmp, "elts", getattr(cmp, "keys", [])):
                        names.add(test.left.id)
    return names


def find_vacuous_asserts(paths):
    """`(file, function, name)` per assertion that cannot fail."""
    out = []
    for path in paths:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError):
            continue
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef) or not fn.name.startswith("test_"):
                continue
            for name in _empty_asserted_names(fn):
                if name in _COLLECTION_NAMES and not _feeds(fn, name):
                    out.append((path, fn.name, name))
    return out


def test_no_guard_asserts_over_a_collection_it_never_fills():
    files = _guard_test_files()
    vacuous = find_vacuous_asserts(files)
    detail = "\n".join(
        f"  {p.relative_to(_DEV_TREE).as_posix()}::{fn} — `{n}` is asserted "
        f"empty but nothing ever adds to it"
        for p, fn, n in vacuous
    )
    assert not vacuous, (
        "guard(s) asserting over a collection they never fill — these pass "
        "forever and check nothing:\n" + detail
    )


def _empty_asserted_names_in(paths) -> dict[str, list[str]]:
    """`{name: [where it is asserted empty]}` across `paths`.

    A parameter rather than a read of `_guard_test_files()` so a planted set can
    redden the test below — the rule `_stale_pending_entries` states in the
    sibling guard, and for the reason stated there."""
    out: dict[str, list[str]] = {}
    for path in paths:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError):
            continue
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef) or not fn.name.startswith("test_"):
                continue
            for name in _empty_asserted_names(fn):
                out.setdefault(name, []).append(f"{path.name}::{fn.name}")
    return out


def undeclared_names(asserted, declared, exempt) -> list[str]:
    """Names asserted empty that no map accounts for.

    All three inputs are parameters, so both the real-tree call and a planted one
    go through the same code."""
    return sorted(set(asserted) - set(declared) - set(exempt))


def test_the_declared_names_match_the_tree():
    """The direction a hand-written list cannot close on its own.

    `find_vacuous_asserts` only ever looks at names in `_COLLECTION_NAMES`, so a
    guard that collects its findings into a name nobody declared is not
    ASSERTED-ABOUT — it is INVISIBLE, and this file reports success either way.
    That is the same "still reports success, stopped looking" shape the whole
    module exists to catch, reached through the constant rather than the code.

    Measured at the widening: the list declared 8 names, matched 3, and left 19
    of the 39 empty-assertions in scope unreachable. The command is in the
    comment on `_COLLECTION_NAMES` above."""
    asserted = _empty_asserted_names_in(_guard_test_files())
    assert asserted, (
        "no guard asserts a collection empty any more — either the AST shapes "
        "this file recognises have stopped matching how guards are written, or "
        "discovery has collapsed. Either way nothing below is checking anything."
    )
    unaccounted = undeclared_names(asserted, _COLLECTION_NAMES, _NOT_A_FINDING_COLLECTION)
    detail = "\n".join(f"  {n} — {', '.join(asserted[n])}" for n in unaccounted)
    assert not unaccounted, (
        "name(s) asserted empty in a guard that are in neither _COLLECTION_NAMES "
        "nor _NOT_A_FINDING_COLLECTION, so nothing checks whether anything ever "
        "fills them:\n" + detail + "\n\nAdd it to _COLLECTION_NAMES if it holds "
        "findings; to _NOT_A_FINDING_COLLECTION, with a reason, if it does not."
    )


def test_every_exemption_still_earns_itself():
    """An exemption must not outlive its reason. A name nothing asserts empty any
    more is an entry excusing nothing, and an entry nobody can see excusing
    nothing is how the map becomes the pressure valve instead of the record."""
    asserted = _empty_asserted_names_in(_guard_test_files())
    for name, reason in _NOT_A_FINDING_COLLECTION.items():
        assert reason.strip(), f"{name} is exempt with no reason given"
        assert name in asserted, (
            f"{name!r} is exempted but no guard asserts it empty — delete the entry"
        )
        assert name not in _COLLECTION_NAMES, (
            f"{name!r} is both declared a findings collection and exempted from "
            "being one; the exemption would then never be reached"
        )


def test_an_undeclared_name_is_reported():
    """The planted half. `_NOT_A_FINDING_COLLECTION` is empty on the real tree, so
    without this nothing shows the check can distinguish its two maps at all."""
    assert undeclared_names({"problems": [], "surprise": []}, {"problems"}, {}) == [
        "surprise"
    ]
    assert undeclared_names({"problems": [], "surprise": []}, {"problems"},
                            {"surprise": "a stated reason"}) == []


def test_the_scan_is_not_vacuous():
    """This guard is itself the shape it polices, so it needs its own floor.

    Re-measured with this file's own `__main__`, which is why it has one::

        $ python plugin-tests/tests/conformance/test_guards_are_not_vacuous.py
        files 54  dirs 12  empty-assertions 68

    Both floors sit ONE BELOW the real count, the rule
    `test_no_hardcoded_plugin_paths.py` states for its own scan floor: move them
    to the new real count when something is deliberately added or deleted, never
    to a number chosen to be safe from future deletions. The next deliberate
    deletion is EXPECTED to trip them and get them lowered along with it.

    They were `>= 6` files and `>= 5` assertions against a real 22 and 39 — so
    dropping either of the two declared directories left the survivor clearing
    both, which is the measurement in the comment on `_TESTS_ROOT`."""
    files = _guard_test_files()
    assert len(files) >= 53, f"guard-test discovery collapsed to {len(files)} files"
    total_asserts = 0
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef) and fn.name.startswith("test_"):
                total_asserts += len(_empty_asserted_names(fn))
    assert total_asserts >= 67, (
        f"only {total_asserts} empty-collection assertions found across "
        f"{len(files)} guard files; the AST shapes this recognises have "
        "probably stopped matching how the guards are written"
    )


def test_discovery_still_reaches_every_required_directory():
    """A count cannot see a DIRECTORY dropping out — the failure the two-tuple
    made invisible, and the one a derived list re-opens from the other end.

    `rglob` over a directory that has been moved or renamed is empty rather than
    an error, so a whole area can stop contributing while the floor above absorbs
    it: `tests/skills/annotate/` is 8 of 54 files against a margin of one, and
    `tests/conformance/` is 6. Stated as an independent list for the reason
    `_REQUIRED_TEST_DIRS` gives — comparing the derivation against the filesystem
    it was derived from is a tautology."""
    found = _discovered_dirs()
    assert found, "discovery found no test directories at all"
    lost = sorted(_REQUIRED_TEST_DIRS - found)
    assert not lost, (
        f"directory(ies) discovery no longer reaches: {lost}. Either they were "
        "renamed or moved, or the rglob stopped descending. Removing one is a "
        "deliberate change: delete it from _REQUIRED_TEST_DIRS in the same "
        "commit, with a reason."
    )


# ---------- the checker's own behaviour, on seeded inputs ----------


def _seed(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "test_seeded.py"
    p.write_text(body, encoding="utf-8")
    return p


def test_it_flags_a_list_that_is_never_appended_to(tmp_path):
    p = _seed(
        tmp_path,
        "def test_x():\n"
        "    problems = []\n"
        "    for i in range(3):\n"
        "        pass\n"
        "    assert not problems\n",
    )
    assert [n for _, _, n in find_vacuous_asserts([p])] == ["problems"]


def test_it_accepts_a_list_that_is_appended_to(tmp_path):
    p = _seed(
        tmp_path,
        "def test_x():\n"
        "    problems = []\n"
        "    for i in range(3):\n"
        "        problems.append(i)\n"
        "    assert not problems\n",
    )
    assert find_vacuous_asserts([p]) == []


def test_it_accepts_a_list_built_by_a_comprehension(tmp_path):
    p = _seed(
        tmp_path,
        "def test_x():\n"
        "    problems = [i for i in range(3) if i]\n"
        "    assert not problems\n",
    )
    assert find_vacuous_asserts([p]) == []


def test_it_flags_the_equals_empty_list_spelling(tmp_path):
    p = _seed(
        tmp_path,
        "def test_x():\n    missing = []\n    assert missing == []\n",
    )
    assert [n for _, _, n in find_vacuous_asserts([p])] == ["missing"]


def test_it_accepts_a_name_bound_by_tuple_unpacking(tmp_path):
    """One of the two false positives widening discovery exposed. Real shape,
    from `tests/skills/annotate/test_render_doc.py`: `check_anchors` returns four
    values and `lost` is one of them, so nothing in the function assigns `lost`
    a `Name` target and the old `_feeds` called it never fed."""
    p = _seed(
        tmp_path,
        "def test_x():\n"
        "    checked, lost, problems, fatal = check_anchors(ctx, corpus)\n"
        "    assert lost == []\n",
    )
    assert find_vacuous_asserts([p]) == []


def test_it_accepts_a_collection_filled_by_the_callee(tmp_path):
    """The other one. Real shape, from
    `tests/skills/annotate/test_review_findings.py`: an empty list handed to a
    reader as an out-parameter, filled inside it."""
    p = _seed(
        tmp_path,
        "def test_x():\n"
        "    problems = []\n"
        "    rows = store.read_all(path, problems=problems)\n"
        "    assert problems == []\n",
    )
    assert find_vacuous_asserts([p]) == []


def test_it_still_flags_the_list_the_two_fixes_must_not_excuse(tmp_path):
    """Non-vacuity partner for the pair above: both widenings make `_feeds` say
    "fed" more often, so each one buys a false negative if it reaches too far.
    A list that is only ever COMPARED — never passed anywhere, never unpacked
    into — must still be reported."""
    p = _seed(
        tmp_path,
        "def test_x():\n"
        "    problems = []\n"
        "    other = [1, 2]\n"
        "    assert len(other) == 2\n"
        "    assert not problems\n",
    )
    assert [n for _, _, n in find_vacuous_asserts([p])] == ["problems"]


if __name__ == "__main__":
    # The command this file's floors cite. `pytest <this file>` prints a pass
    # count and nothing else, so a floor whose stated measuring command emits no
    # measurement cannot be re-derived — the decay this whole module exists to
    # stop, one level up. Same reason the two sibling conformance guards have one.
    _files = _guard_test_files()
    _n = sum(
        len(_empty_asserted_names(fn))
        for _p in _files
        for fn in ast.walk(ast.parse(_p.read_text(encoding="utf-8")))
        if isinstance(fn, ast.FunctionDef) and fn.name.startswith("test_")
    )
    print(f"files {len(_files)}  dirs {len(_discovered_dirs())}  empty-assertions {_n}")
