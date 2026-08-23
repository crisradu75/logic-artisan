"""A guard without a killed mutant is a guard nobody has proven.

The sibling `conformance-checks/tests/test_guards_are_not_vacuous.py` catches one
concrete shape statically — a collection asserted empty that nothing fills. It
cannot catch the other shape this repo has actually shipped: an assertion that is
reachable but checks the wrong thing (greping for a function's name rather than
calling it). Only a mutant catches that, and only if someone writes one.

`mutate.py` is invoked by hand, so "write a mutant" was advice, and advice is
what gets skipped at the end of a long session. This makes the pairing checkable:
every guard test file in a checks scope has a same-named batch beside it under
`mutants/`, and every batch names a target that exists.

It deliberately does NOT run the mutants — a mutation run edits real files and
takes minutes, which does not belong in the ordinary gate. It asserts only that
the evidence CAN be produced and points at the command that produces it.
"""

from __future__ import annotations

import ast
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"

_CHECK_SCOPES = ("conformance-checks", "consistency-checks")

# Guard files exempt from needing a batch, each for a stated reason. Keep this
# list short and justified — it is the pressure valve that could quietly empty
# this test if it grew without argument.
_EXEMPT = {
    # This file and its sibling ARE the meta-guards; a mutant batch for them
    # would assert that the pairing checker checks pairing, which is circular.
    "consistency-checks/tests/test_guards_have_mutant_batches.py":
        "meta-guard: mutating it only tests itself",
    "conformance-checks/tests/test_guards_are_not_vacuous.py":
        "meta-guard: carries seeded-input tests of its own checker instead",

    # GRANDFATHERED, not excused. These guards predate the convention and have
    # never had a mutant written for them, so nobody has shown they can fail.
    # They are listed individually — rather than the rule being softened to
    # "new files only" — so the debt is countable and shrinks visibly. Delete a
    # line here the moment its batch lands. Tracked in TODO.md.
    "conformance-checks/tests/test_no_hardcoded_plugin_paths.py": "grandfathered",
    "consistency-checks/tests/test_check_script_drift.py": "grandfathered",
    "consistency-checks/tests/test_ledger_names_agree.py": "grandfathered",
    "consistency-checks/tests/test_marketplace_manifest.py": "grandfathered",
    "consistency-checks/tests/test_overlays_are_reachable.py": "grandfathered",
    "consistency-checks/tests/test_pre_push_is_installed.py": "grandfathered",
    "consistency-checks/tests/test_subprocess_encoding.py": "grandfathered",
    "consistency-checks/tests/test_token_list_is_curated_here.py": "grandfathered",
    "consistency-checks/tests/test_mutate.py": "grandfathered",
    "consistency-checks/tests/test_runner_stream_encoding.py": "grandfathered",
}


def test_the_grandfather_list_only_shrinks():
    """The pressure valve, bounded. A grandfathered guard is unproven debt; the
    list may lose entries but must never gain one, or the convention becomes
    opt-in and the whole check evaporates."""
    grandfathered = sum(1 for v in _EXEMPT.values() if v == "grandfathered")
    assert grandfathered <= 12, (
        f"{grandfathered} grandfathered guards; the list was 12 when the "
        "convention landed and is only allowed to shrink. A NEW guard needs a "
        "mutant batch, not an exemption."
    )


def _guard_files():
    out = []
    for scope in _CHECK_SCOPES:
        out.extend(sorted((_PLUGIN_ROOT / scope / "tests").glob("test_*.py")))
    return out


def _rel(p: Path) -> str:
    return p.relative_to(_PLUGIN_ROOT).as_posix()


def test_every_guard_file_has_a_mutant_batch_beside_its_scope():
    missing = []
    for path in _guard_files():
        rel = _rel(path)
        if rel in _EXEMPT:
            continue
        batch = path.parents[1] / "mutants" / path.name
        if not batch.is_file():
            missing.append(f"  {rel} -> expected {_rel(batch)}")
    assert not missing, (
        "guard(s) with no mutant batch — nobody has shown these can fail:\n"
        + "\n".join(missing)
        + "\n\nWrite one, then prove it: "
        "python3 <plugin>/mutate.py <plugin>/<scope>/mutants/<name>.py"
    )


def test_every_batch_is_loadable_and_declares_real_targets():
    """A batch that cannot load, or that points at a file that no longer exists,
    reports every mutant as an anchor error — which reads like a tooling problem
    and gets ignored, so the guard it covers quietly stops being proven."""
    problems = []
    for scope in _CHECK_SCOPES:
        for batch in sorted((_PLUGIN_ROOT / scope / "mutants").glob("test_*.py")):
            rel = _rel(batch)
            try:
                tree = ast.parse(batch.read_text(encoding="utf-8"), filename=str(batch))
            except (OSError, SyntaxError) as exc:
                problems.append(f"  {rel}: does not parse ({exc.__class__.__name__})")
                continue
            names = {
                t.id
                for node in ast.walk(tree)
                if isinstance(node, ast.Assign)
                for t in node.targets
                if isinstance(t, ast.Name)
            }
            if "MUTANTS" not in names:
                problems.append(f"  {rel}: defines no MUTANTS list")
            guarded = batch.parents[1] / "tests" / batch.name
            if not guarded.is_file():
                problems.append(f"  {rel}: guards {_rel(guarded)}, which does not exist")
    assert not problems, "mutant batch problems:\n" + "\n".join(problems)


def test_no_batch_hardcodes_an_absolute_path():
    """A batch resolving from an absolute developer path works on one machine and
    leaks a repo name into a directory the marketplace ships."""
    offenders = []
    for scope in _CHECK_SCOPES:
        for batch in sorted((_PLUGIN_ROOT / scope / "mutants").glob("*.py")):
            for lineno, line in enumerate(
                batch.read_text(encoding="utf-8").splitlines(), 1
            ):
                if ":\\" in line or line.lstrip().startswith("/home/"):
                    offenders.append(f"  {_rel(batch)}:{lineno}  {line.strip()[:80]}")
    assert not offenders, (
        "mutant batch(es) with an absolute path — resolve from `Path(__file__)` "
        "instead:\n" + "\n".join(offenders)
    )


def test_the_scan_is_not_vacuous():
    files = _guard_files()
    assert len(files) >= 6, f"guard discovery collapsed to {len(files)} files"
    batches = [
        b
        for scope in _CHECK_SCOPES
        for b in (_PLUGIN_ROOT / scope / "mutants").glob("test_*.py")
    ]
    assert batches, "no mutant batches found at all; the convention has evaporated"
