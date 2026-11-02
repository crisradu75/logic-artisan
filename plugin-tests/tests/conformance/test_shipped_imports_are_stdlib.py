"""Conformance guard: every shipped Python import is standard library.

A repo installs the plugin, not a requirements file. A third-party import in a
shipped script works on the machine that wrote it and fails on the first one
that lacks the package. CLAUDE.md states the rule ("Shipped scripts are
stdlib-only Python"); until issue #441 no test held it.

A relative import (`from . import x`, `from .x import y`) is reported too: no
shipped directory is a package, so one would fail at runtime. For an absolute
import, a name passes when its top-level module is in `sys.stdlib_module_names`, is
`__future__`, or is the stem of a `.py` file in the importing file's own directory
(a script importing a sibling helper such as `_dispatch_lib`). Every own-module
import the plugin makes is a sibling, so a shipped `yaml.py` elsewhere cannot
excuse an `import yaml`.

Needs Python 3.10+ for `sys.stdlib_module_names`. This test runs on the
developer's Python, not the user's, so older versions skip rather than guess.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    not hasattr(sys, "stdlib_module_names"),
    reason="sys.stdlib_module_names needs Python 3.10+",
)

_PLUGIN = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
# 30 shipped `.py` files on main when this test was added. A lower count means
# the walk stopped finding them, which would turn the scan into a pass over nothing.
_FLOOR = 30


def _shipped() -> list[Path]:
    return sorted(_PLUGIN.rglob("*.py"))


def _siblings(path: Path) -> set[str]:
    """Stems of the other `.py` files beside `path`: the own modules it may import."""
    return {p.stem for p in path.parent.glob("*.py") if p != path}


def _foreign_imports(source: str, own: set[str]) -> list[str]:
    """Names `source` imports that are relative, or not stdlib, `__future__` or `own`."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level > 0:
            found.append("." * node.level + (node.module or ""))
            continue
        elif isinstance(node, ast.ImportFrom) and node.module:
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
    bad = {
        str(p.relative_to(_PLUGIN)): names
        for p in files
        if (names := _foreign_imports(p.read_text(encoding="utf-8"), _siblings(p)))
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
    # A relative import is a defect here, not an exemption: no shipped directory
    # is a package.
    assert _foreign_imports("from . import sibling\nfrom .x import y\n", set()) == [".", ".x"]
    assert _foreign_imports("import _dispatch_lib\n", {"_dispatch_lib"}) == []


def test_an_own_module_counts_only_beside_its_importer(tmp_path: Path) -> None:
    """A shipped `yaml.py` in another directory must not excuse `import yaml`."""
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    importer = tmp_path / "a" / "tool.py"
    importer.write_text("import yaml\nimport helper\n", encoding="utf-8")
    (tmp_path / "a" / "helper.py").write_text("", encoding="utf-8")
    (tmp_path / "b" / "yaml.py").write_text("", encoding="utf-8")
    own = _siblings(importer)
    assert own == {"helper"}
    assert _foreign_imports(importer.read_text(encoding="utf-8"), own) == ["yaml"]
