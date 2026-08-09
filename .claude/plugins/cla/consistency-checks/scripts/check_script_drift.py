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
import re
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]

# Each group: a set of function names expected to be logic-identical across a
# set of sibling files (paths relative to PLUGIN_ROOT).
SIBLING_GROUPS = [
    # The `log_run.py family` group used to sit here, covering five copies of
    # one writer. It is gone because the duplication is: three of those ledgers
    # had no reader and were deleted, and the surviving two now share a single
    # `lib/log_run.py` invoked with the ledger name as an argument. A shared
    # module was always the better answer than a drift check over copies — the
    # copies existed only because same-named modules collide inside one pytest
    # process, which living at the plugin root avoids.
    {
        "name": "retro aggregate.py family",
        "functions": ("_git_toplevel", "_default_log_path", "_load_records", "_coerce_int"),
        "files": (
            "skills/codify-retro/scripts/aggregate.py",
            "skills/spec-to-pr-retro/scripts/aggregate.py",
        ),
    },
    {
        # Duplicated rather than shared for the same reason as the families
        # above: `run_tests.py` runs each scope as its own pytest process
        # precisely because same-named modules collide, so a shared import
        # would break that isolation. Registered here so the copies cannot
        # drift instead.
        #
        # This helper is what makes three tests actually RUN on Windows. They
        # previously called `os.symlink(..., target_is_directory=True)` and
        # skipped when it raised — which it always does for an unprivileged
        # account (WinError 1314) — so they skipped on the one platform whose
        # path handling they exist to check, while the suite reported green. A
        # junction needs no elevation and `realpath` resolves it identically.
        "name": "make_dir_alias test helper",
        "functions": ("make_dir_alias",),
        "files": (
            "hooks/tests/test_block_worktree_path_escape.py",
            "hooks/tests/test_block_unsafe_recursive_delete.py",
            "skills/new-worktree/tests/test_manual_worktree.py",
        ),
    },
]


# The per-skill ledger filename (`codify-runs.jsonl`, `spec-to-pr-runs.jsonl`,
# …). This is the ONE string inside a guarded function that legitimately differs
# between siblings — `_default_log_path` builds the same path the same way and
# only names its own skill's ledger at the end. Normalizing it keeps every other
# string compared, which is the point: those functions' docstrings say they must
# stay byte-identical to the matching producer or "runs vanish silently", and
# what makes that true is `cla.io`/`retro`/`rev-parse`/`--show-toplevel`, not
# the filename.
_LEDGER_NAME = re.compile(r"^[a-z0-9-]+-runs\.jsonl$")


def _normalize_constants(node: ast.FunctionDef) -> ast.FunctionDef:
    """Blank the function's docstring and its per-skill ledger filename, and
    NOTHING else.

    An earlier version blanked every string literal, which silently defeated the
    whole check: these functions ARE mostly string literals. `_git_toplevel` is a
    `subprocess.run(["git", "rev-parse", "--show-toplevel"], …)` call and
    `_runs_dir` builds `<root>/cla.io/retro`, so blanking strings meant a sibling
    drifting to `--git-dir`, or writing its ledger to a different directory,
    compared EQUAL. Both cases are now covered by tests; both were missed before.
    """
    if (
        node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    ):
        node.body[0].value.value = ""
    for n in ast.walk(node):
        if (
            isinstance(n, ast.Constant)
            and isinstance(n.value, str)
            and _LEDGER_NAME.match(n.value)
        ):
            n.value = "<ledger>"
    return node


def _normalized_dump(node: ast.FunctionDef) -> str:
    return ast.dump(_normalize_constants(node), annotate_fields=False)


def extract_functions(path: Path, names: set[str]) -> dict[str, str]:
    """Return {function_name: normalized_dump} for TOP-LEVEL defs in `path`
    matching `names`. Missing file or parse failure raises — a group naming a
    file that no longer exists or no longer parses is itself a drift the
    check must not silently swallow.

    Iterates `tree.body` rather than `ast.walk`: a nested or method def sharing
    a guarded name would otherwise overwrite the real top-level one and the
    comparison would silently run against the wrong function.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            found[node.name] = _normalized_dump(node)
    return found


def check_group(group: dict, root: Path) -> list[str]:
    names = set(group["functions"])
    per_file: dict[str, dict[str, str]] = {}
    problems: list[str] = []
    for rel in group["files"]:
        path = root / rel
        if not path.is_file():
            # Collect and keep going rather than returning here: an early return
            # reported the first missing file and hid every other problem in the
            # group, so a run that renamed two siblings looked like one issue.
            problems.append(f"{rel}: file not found (listed in {group['name']!r})")
            continue
        per_file[rel] = extract_functions(path, names)

    present = [rel for rel in group["files"] if rel in per_file]
    for fn in sorted(names):
        baseline_file: str | None = None
        baseline_src: str | None = None
        for rel in present:
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
