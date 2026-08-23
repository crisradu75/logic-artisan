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
_COLLECTION_NAMES = frozenset(
    {"problems", "offenders", "violations", "missing", "stray", "leaks", "errors", "bad"}
)

# The dev-tree directories whose tests are guards over the repo itself. A
# skill's own unit tests are ordinary tests and are not held to this shape.
# These were the two `*-checks` scopes before the dev tree moved out of the
# plugin; the guards themselves did not change, only where they live.
_GUARD_TEST_DIRS = ("tests/conformance", "tests/consistency")


def _guard_test_files():
    out = []
    for rel in _GUARD_TEST_DIRS:
        out.extend(sorted((_DEV_TREE / rel).glob("test_*.py")))
    return out


def _feeds(node: ast.AST, name: str) -> bool:
    """True if `name` is ever grown inside `node` — appended to, extended,
    augmented, or rebound to something other than an empty literal."""
    for sub in ast.walk(node):
        # name.append(...) / name.extend(...) / name.update(...)
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
            tgt = sub.func.value
            if isinstance(tgt, ast.Name) and tgt.id == name:
                if sub.func.attr in {"append", "extend", "update", "add"}:
                    return True
        # name += ...
        if isinstance(sub, ast.AugAssign):
            if isinstance(sub.target, ast.Name) and sub.target.id == name:
                return True
        # name = <anything that is not an empty literal>
        if isinstance(sub, ast.Assign):
            for t in sub.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    v = sub.value
                    empty_literal = (
                        isinstance(v, (ast.List, ast.Set, ast.Dict)) and not getattr(v, "elts", getattr(v, "keys", []))
                    )
                    if not empty_literal:
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


def test_the_scan_is_not_vacuous():
    """This guard is itself the shape it polices, so it needs its own floor."""
    files = _guard_test_files()
    assert len(files) >= 6, f"guard-test discovery collapsed to {len(files)} files"
    total_asserts = 0
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef) and fn.name.startswith("test_"):
                total_asserts += len(_empty_asserted_names(fn))
    assert total_asserts >= 5, (
        f"only {total_asserts} empty-collection assertions found across "
        f"{len(files)} guard files; the AST shapes this recognises have "
        "probably stopped matching how the guards are written"
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
