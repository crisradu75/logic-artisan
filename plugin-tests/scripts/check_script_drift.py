"""Detect logic drift between sibling scripts that deliberately carry duplicate
copies of the same logic and so can't share a single importable module.

The ledger writer (`lib/log_run.py`) and both readers of what it writes (the
two retro aggregators) each carry their own copy of the resolver that
decides WHERE the ledger lives (`_git_toplevel`, `_runs_dir`), and the two
readers additionally share their record-loading helpers (`_load_records`,
`_coerce_int`). Each file's own docstring says to keep these byte-identical to
its siblings. That convention was never enforced: nothing failed if a fix
landed in one copy and not the others — and a writer/reader disagreement in
particular is silent, since the reader then finds no records and reports a
cold start.

This can't be fixed by extracting a shared module the way
`hooks/_dispatch_lib.py` or `spec-to-pr/scripts/_git_common.py` do — each of
those is imported by exactly one skill, whereas these siblings are shipped
inside three different skills that a consuming repo may install and invoke
independently, so none of them may import from another. So instead of sharing
code, this compares the actual LOGIC of each named function across its sibling
files.

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

_REPO_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = _REPO_ROOT / ".claude" / "plugins" / "cla"
DEV_TREE_ROOT = _REPO_ROOT / "plugin-tests"

# Each group: a set of function names expected to be logic-identical across a
# set of sibling files, plus the `root` its paths are relative to.
#
# The root is per-group and not global because `extract-dev-tree-from-plugin`
# split the siblings across two trees. Groups 1 and 2 name shipped scripts that
# stayed in the plugin; group 3 names test helpers that moved to the dev tree
# while their subjects stayed behind. One root cannot address both sets, and a
# single corrected depth would silently resolve half of them to nothing.
SIBLING_GROUPS = [
    # The pair that can actually fail silently: the ledger WRITER and the two
    # READERS of what it writes. An earlier version of this group compared the
    # two readers to each other and left the writer out — so both readers could
    # be identically wrong about where the ledger lives, the retro would report
    # zero runs, and that is indistinguishable from a cold start. The readers
    # each end `_default_log_path` by appending their own ledger filename to
    # `_runs_dir()`, which is why only the dir resolver is compared here.
    {
        "name": "retro ledger dir resolver (writer + both readers)",
        "root": PLUGIN_ROOT,
        "functions": ("_git_toplevel", "_runs_dir"),
        "files": (
            "lib/log_run.py",
            "skills/codify-retro/scripts/codify_aggregate.py",
            "skills/spec-to-pr-retro/scripts/spec_to_pr_aggregate.py",
        ),
    },
    {
        # `_load_ledgers` and `_window` are here because they are the two blocks
        # that ACTUALLY diverged. Both were copied verbatim into the two
        # aggregators and then fixed in only one: the window kept inverting in
        # codify after spec-to-pr learned to sort, and nothing flagged it but a
        # reviewer. Pinning only `_load_records`/`_coerce_int` left the newest
        # duplication — the fleet ledger loop — outside the one mechanism built to
        # catch exactly this.
        "name": "retro aggregator record loading",
        "root": PLUGIN_ROOT,
        # `_fleet_roots` joins them for the same reason, before it has a chance to
        # diverge: it decides which repos a fleet run reads, so two copies that
        # disagree would silently give the two loops different fleets from one
        # `fleet.local.md`, and each would look internally consistent.
        "functions": ("_load_records", "_coerce_int", "_load_ledgers", "_window",
                      "_fleet_roots"),
        "files": (
            "skills/codify-retro/scripts/codify_aggregate.py",
            "skills/spec-to-pr-retro/scripts/spec_to_pr_aggregate.py",
        ),
    },
    {
        # Duplicated rather than shared because each copy is a test-local
        # helper in a different area of the suite, with no importable home
        # between them. Registered here so the copies cannot drift instead.
        #
        # This helper is what makes three tests actually RUN on Windows. They
        # previously called `os.symlink(..., target_is_directory=True)` and
        # skipped when it raised — which it always does for an unprivileged
        # account (WinError 1314) — so they skipped on the one platform whose
        # path handling they exist to check, while the suite reported green. A
        # junction needs no elevation and `realpath` resolves it identically.
        "name": "make_dir_alias test helper",
        "root": DEV_TREE_ROOT,
        "functions": ("make_dir_alias",),
        "files": (
            "tests/hooks/test_block_worktree_path_escape.py",
            "tests/hooks/test_block_unsafe_recursive_delete.py",
            "tests/skills/new-worktree/test_manual_worktree.py",
        ),
    },
]


def _normalize_constants(node: ast.FunctionDef) -> ast.FunctionDef:
    """Blank the function's docstring, and NOTHING else.

    An earlier version blanked every string literal, which silently defeated the
    whole check: these functions ARE mostly string literals. `_git_toplevel` is a
    `subprocess.run(["git", "rev-parse", "--show-toplevel"], …)` call and
    `_runs_dir` builds `<root>/cla.io/retro`, so blanking strings meant a sibling
    drifting to `--git-dir`, or writing its ledger to a different directory,
    compared EQUAL. Both cases are now covered by tests; both were missed before.

    A second exemption used to normalize the per-skill ledger filename, back when
    `_default_log_path` (which ends by appending it) was itself compared. That
    function now just returns `_runs_dir() / "<its ledger>.jsonl"` and is no
    longer in any group, so the exemption could only ever have hidden a real
    difference. Do not reintroduce one without a guarded function that needs it.
    """
    if (
        node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    ):
        node.body[0].value.value = ""
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
        problems.extend(check_group(group, group["root"]))

    if problems:
        print("Sibling script drift detected:")
        for p in problems:
            print(f"  - {p}")
        return 1

    print(f"No drift across {len(SIBLING_GROUPS)} sibling script group(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
