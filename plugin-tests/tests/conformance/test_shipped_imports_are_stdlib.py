"""Conformance guard: every shipped Python import is standard library.

A repo installs the plugin, not a requirements file. A third-party import in a
shipped script works on the machine that wrote it and fails on the first one
that lacks the package. CLAUDE.md states the rule ("Shipped scripts are
stdlib-only Python"); until issue #441 no test held it.

Absolute imports only: `import x` and `from x import y` with no leading dots. A
name passes when its top-level module is in `sys.stdlib_module_names`, is
`__future__`, or is the stem of a `.py` file the plugin ships itself (a script
importing a sibling helper such as `_dispatch_lib`).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

_PLUGIN = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
# 30 shipped `.py` files on main when this test was added. A lower count means
# the walk stopped finding them, which would turn the scan into a pass over nothing.
_FLOOR = 30


def _shipped() -> list[Path]:
    return sorted(_PLUGIN.rglob("*.py"))


def _foreign_imports(source: str, own: set[str]) -> list[str]:
    """Top-level names `source` imports that are not stdlib, `__future__` or `own`."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module]
        else:
            continue
        for name in names:
            top = name.split(".")[0]
            if top in sys.stdlib_module_names or top == "__future__" or top in own:
                continue
            found.append(name)
    return found


def test_every_shipped_import_is_standard_library() -> None:
    files = _shipped()
    assert len(files) >= _FLOOR, f"found {len(files)} shipped .py files, expected at least {_FLOOR}"
    own = {p.stem for p in files}
    bad = {
        str(p.relative_to(_PLUGIN)): names
        for p in files
        if (names := _foreign_imports(p.read_text(encoding="utf-8"), own))
    }
    assert not bad, f"shipped files import outside the standard library: {bad}"


def test_the_scanner_is_not_vacuous() -> None:
    """The scanner must flag what the guard exists to catch, in every import form."""
    assert _foreign_imports("import requests\n", set()) == ["requests"]
    assert _foreign_imports("from yaml import safe_load\n", set()) == ["yaml"]
    assert _foreign_imports("import os, requests.adapters\n", set()) == ["requests.adapters"]
    assert _foreign_imports("def f():\n    import attr\n", set()) == ["attr"]
    # Allowed forms stay quiet.
    assert _foreign_imports("import os.path\nfrom __future__ import annotations\n", set()) == []
    assert _foreign_imports("from . import sibling\nfrom .x import y\n", set()) == []
    assert _foreign_imports("import _dispatch_lib\n", {"_dispatch_lib"}) == []
