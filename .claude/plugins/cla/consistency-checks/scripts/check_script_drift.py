"""Detect logic drift between sibling scripts that live in different skills'
isolated pytest scopes and so can't share a single importable module.

Several skills each carry their own copy of a small git/ledger-resolution
helper (`_git_toplevel`, `_runs_dir`, `_default_log_path`, `_load_records`,
`_coerce_int`) — see each file's own docstring, which says to "keep the
resolvers byte-identical" to its siblings. That convention was never
enforced: nothing failed if a fix landed in one copy and not the others.

This can't be fixed by extracting a shared module the way
`hooks/_dispatch_lib.py` or `spec-to-pr/scripts/_git_common.py` do — those
live inside ONE pytest scope each; these siblings are deliberately spread
across scopes that CANNOT share a same-named top-level module (see
`run_tests.py`'s own docstring). So instead of sharing code, this compares
the actual LOGIC of each named function across its sibling files, once per
`run_tests.py` pass.

The comparison ignores string constants (docstrings, log filenames, error
messages) — each sibling legitimately customizes those per skill — but not
int/float/bool constants or control flow, which must still match. That is
the same bar the "byte-identical" docstrings were informally asking for,
minus the false positives a literal byte-diff would raise on the prose that
was always meant to differ.
"""

from __future__ import annotations

import ast
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]

# Each group: a set of function names expected to be logic-identical across a
# set of sibling files (paths relative to PLUGIN_ROOT).
SIBLING_GROUPS = [
    {
        "name": "log_run.py family",
        "functions": ("_git_toplevel", "_runs_dir"),
        "files": (
            "skills/codify-learnings/scripts/log_run.py",
            "skills/multi-lite/scripts/log_run.py",
            "skills/multi-spec/scripts/log_run.py",
            "skills/spec-to-pr/scripts/log_run.py",
            "skills/multi-pr/scripts/log_chain_run.py",
        ),
    },
    {
        "name": "retro aggregate.py family",
        "functions": ("_git_toplevel", "_default_log_path", "_load_records", "_coerce_int"),
        "files": (
            "skills/codify-retro/scripts/aggregate.py",
            "skills/spec-to-pr-retro/scripts/aggregate.py",
        ),
    },
]


def _blank_string_constants(node: ast.AST) -> ast.AST:
    """Zero out every string-literal constant (docstrings, filenames, messages)
    in place, leaving int/float/bool/None constants and all control flow
    untouched — those must still match exactly."""
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            n.value = ""
    return node


def _normalized_dump(node: ast.AST) -> str:
    return ast.dump(_blank_string_constants(node), annotate_fields=False)


def extract_functions(path: Path, names: set[str]) -> dict[str, str]:
    """Return {function_name: normalized_dump} for top-level defs in `path`
    matching `names`. Missing file or parse failure raises — a group naming a
    file that no longer exists or no longer parses is itself a drift the
    check must not silently swallow."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in names:
            found[node.name] = _normalized_dump(node)
    return found


def check_group(group: dict, root: Path) -> list[str]:
    names = set(group["functions"])
    per_file: dict[str, dict[str, str]] = {}
    for rel in group["files"]:
        path = root / rel
        if not path.is_file():
            return [f"{rel}: file not found (listed in {group['name']!r})"]
        per_file[rel] = extract_functions(path, names)

    problems: list[str] = []
    for fn in sorted(names):
        baseline_file: str | None = None
        baseline_src: str | None = None
        for rel in group["files"]:
            src = per_file[rel].get(fn)
            if src is None:
                problems.append(f"{rel}: missing `{fn}` (expected in {group['name']})")
                continue
            if baseline_src is None:
                baseline_file, baseline_src = rel, src
            elif src != baseline_src:
                problems.append(
                    f"`{fn}` in {rel} has drifted from {baseline_file} "
                    f"({group['name']}) — logic differs, not just prose"
                )
    return problems


def main() -> int:
    problems: list[str] = []
    for group in SIBLING_GROUPS:
        problems.extend(check_group(group, PLUGIN_ROOT))

    if problems:
        print("Sibling script drift detected:")
        for p in problems:
            print(f"  - {p}")
        return 1

    print(f"No drift across {len(SIBLING_GROUPS)} sibling script group(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
