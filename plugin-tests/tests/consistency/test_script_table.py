"""Drift guard: DEVELOPER-GUIDE.md's script table must list the repo's scripts.

Section 11 ("Every script, and why it exists") has one row per command script.
Nothing tied it to the scripts themselves, so a new script could ship with no
row, and a deleted or renamed one could leave a row naming a file that is gone.
This test checks both directions:

1. Every tracked script under the roots the table covers has a row.
2. Every row names a tracked file.

The roots are `skills/*/scripts/*.py` and `lib/*.py` under the plugin,
`plugin-tests/mutate.py`, `plugin-tests/scripts/*.py` and
`.claude/skills/release/scripts/*.py`. A hook is not a script here; section 8
covers hooks. A module that a command imports (`spec_proof_*.py` and the like)
is not a command, and the guide says so; `_IMPORTED_MODULES` mirrors that
sentence, and a test fails if the sentence stops naming them.

Row paths come in two styles, which `_row_path_to_repo_path` resolves: a path
starting `plugin-tests/` or `.claude/` is repo-relative, and any other is
relative to `.claude/plugins/cla/` (`lib/...` as it stands, `<skill>/scripts/...`
under `skills/`).
"""

from __future__ import annotations

import fnmatch
import re
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PLUGIN_PREFIX = ".claude/plugins/cla/"
_GUIDE = _REPO_ROOT / "DEVELOPER-GUIDE.md"
_HEADING = "### Every script, and why it exists"

# Directories whose direct `*.py` children the table covers, repo-relative,
# plus single files. `skills/<skill>/scripts/` is handled in `_in_root`.
_FLAT_ROOTS = (
    _PLUGIN_PREFIX + "lib/",
    "plugin-tests/scripts/",
    ".claude/skills/release/scripts/",
)
_SKILLS_PREFIX = _PLUGIN_PREFIX + "skills/"
_SINGLE_FILES = ("plugin-tests/mutate.py",)

# Modules a command imports. The guide's sentence names these four patterns.
_IMPORTED_MODULES = (
    "spec_proof_*.py",
    "render_doc_*.py",
    "render_change_*.py",
    "openspec_change_*.py",
)


def _in_root(path: str) -> bool:
    if path in _SINGLE_FILES:
        return True
    if not path.endswith(".py"):
        return False
    for root in _FLAT_ROOTS:
        if path.startswith(root) and "/" not in path[len(root):]:
            return True
    if path.startswith(_SKILLS_PREFIX):
        parts = path[len(_SKILLS_PREFIX):].split("/")
        return len(parts) == 3 and parts[1] == "scripts"
    return False


def _is_imported_module(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatchcase(name, pat) for pat in _IMPORTED_MODULES)


def _row_path_to_repo_path(row_path: str) -> str:
    if row_path.startswith(("plugin-tests/", ".claude/")):
        return row_path
    if row_path.startswith("lib/"):
        return _PLUGIN_PREFIX + row_path
    return _PLUGIN_PREFIX + "skills/" + row_path


def _table_rows(guide_text: str) -> list[str]:
    """Repo-relative paths of the scripts the table's rows name, in order."""
    start = guide_text.find(_HEADING)
    assert start != -1, f"DEVELOPER-GUIDE.md no longer has the heading {_HEADING!r}"
    section = guide_text[start + len(_HEADING):]
    end = re.search(r"^#{1,3} ", section, re.MULTILINE)
    if end:
        section = section[: end.start()]
    rows = []
    for line in section.splitlines():
        match = re.match(r"\|\s*`([^`]+)`", line)
        if match:
            rows.append(_row_path_to_repo_path(match.group(1)))
    return rows


def script_table_problems(
    guide_text: str, tracked_files: list[str]
) -> tuple[list[str], list[str]]:
    """Return (scripts with no row, rows naming no tracked file)."""
    rows = _table_rows(guide_text)
    tracked = set(tracked_files)
    scripts = sorted(
        p for p in tracked if _in_root(p) and not _is_imported_module(p)
    )
    missing = [p for p in scripts if p not in rows]
    dangling = [p for p in rows if p not in tracked]
    return missing, dangling


def _git_tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(_REPO_ROOT), "ls-files", "-z"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=30, check=True,
    )
    return [p for p in out.stdout.split("\0") if p]


def test_every_script_has_a_row_and_every_row_names_a_script():
    guide_text = _GUIDE.read_text(encoding="utf-8")
    assert _table_rows(guide_text), "no rows parsed from the script table"
    missing, dangling = script_table_problems(guide_text, _git_tracked_files())
    problems = [
        f"no row in DEVELOPER-GUIDE.md section 11 for the script {p}" for p in missing
    ] + [
        f"the row for {p} names a file that is not tracked (renamed or deleted?)"
        for p in dangling
    ]
    assert not problems, "\n".join(problems)


def test_the_guide_still_names_the_imported_module_patterns():
    """The exemption in `_IMPORTED_MODULES` is the guide's own sentence. If the
    guide stops naming a pattern, the test would exempt files nothing says to."""
    guide_text = _GUIDE.read_text(encoding="utf-8")
    absent = [pat for pat in _IMPORTED_MODULES if f"`{pat}`" not in guide_text]
    assert not absent, (
        f"DEVELOPER-GUIDE.md no longer names {absent} as imported modules; "
        "update _IMPORTED_MODULES to match"
    )
