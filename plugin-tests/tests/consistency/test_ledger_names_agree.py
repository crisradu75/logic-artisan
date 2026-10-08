"""The ledger name a skill WRITES must be the one its retro skill READS.

When `log_run.py` was consolidated into one shared writer, the ledger filename
moved out of Python and into markdown: each skill now names its own ledger as an
argument, in prose. The readers still hardcode it, as a constant in their
own aggregator script.

So the two halves of a single contract now live in different languages, in
different files, with nothing comparing them. `log_run.py` now refuses any name
but the one in its `SHAPES`, so a typo on the writer side fails at write time —
but only at write time, at the end of a long run, where a refused write is
non-fatal and easy to miss. The reader of a misspelled name finds nothing and
reports a cold start: `runs_analyzed: 0`. So this checks the prose names before
any run does: the writer's against the reader's, every skill's against the
writer's `SHAPES`, and cla-setup's seeded ledgers against the same.

`test_ledger_dir_agrees.py` checks the DIRECTORY half of this same contract
behaviourally. This guards the FILENAME half.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import log_run

_PLUGIN_ROOT = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"

# (skill that writes, the prose file carrying the invocation, the reader's aggregator)
_LEDGER_CONTRACTS = [
    (
        "spec-to-pr",
        _PLUGIN_ROOT / "skills" / "_shared" / "references" / "run-log-schema.md",
        _PLUGIN_ROOT / "skills" / "spec-to-pr-retro" / "scripts" / "spec_to_pr_aggregate.py",
    ),
]

# `log_run.py <name>.jsonl`, however the invocation is spelled around it.
_WRITER_RE = re.compile(r"log_run\.py\s+([A-Za-z0-9][A-Za-z0-9._-]*\.jsonl)")


def _reader_ledger_name(aggregate_py: Path) -> str:
    """The `.jsonl` literal inside the reader's `_default_log_path`.

    Parsed rather than regexed over the whole file so an unrelated mention in a
    docstring or comment cannot answer for the real constant.
    """
    tree = ast.parse(aggregate_py.read_text(encoding="utf-8"), filename=str(aggregate_py))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_default_log_path":
            names = [
                n.value for n in ast.walk(node)
                if isinstance(n, ast.Constant)
                and isinstance(n.value, str)
                and n.value.endswith(".jsonl")
            ]
            assert len(names) == 1, (
                f"{aggregate_py.name}: expected exactly one .jsonl literal in "
                f"_default_log_path, found {names}"
            )
            return names[0]
    raise AssertionError(f"{aggregate_py} has no _default_log_path")


@pytest.mark.parametrize(
    "skill, prose, aggregate_py",
    _LEDGER_CONTRACTS,
    ids=[c[0] for c in _LEDGER_CONTRACTS],
)
def test_the_writer_and_reader_name_the_same_ledger(skill, prose, aggregate_py):
    text = prose.read_text(encoding="utf-8")
    written = set(_WRITER_RE.findall(text))
    assert written, (
        f"{prose.relative_to(_PLUGIN_ROOT)} no longer shows a `log_run.py "
        f"<ledger>.jsonl` invocation — either the writer moved (update this "
        f"check) or {skill} stopped logging (which nothing else would notice)"
    )
    assert len(written) == 1, (
        f"{prose.relative_to(_PLUGIN_ROOT)} names more than one ledger: {written}"
    )
    read = _reader_ledger_name(aggregate_py)
    assert written.pop() == read, (
        f"{skill} WRITES a different ledger than its retro READS: prose says "
        f"{written} in {prose.name}, {aggregate_py.name} opens {read!r}. The "
        f"write succeeds, the read finds nothing, and the retro reports a cold "
        f"start — the run history is silently unreachable."
    )


_CLA_SETUP = _PLUGIN_ROOT / "skills" / "cla-setup" / "SKILL.md"


def _ledgers_written_by_skills() -> dict[str, Path]:
    """Every ledger a shipped skill or reference appends to, and where."""
    found: dict[str, Path] = {}
    for md in sorted(_PLUGIN_ROOT.glob("skills/**/*.md")):
        for name in _WRITER_RE.findall(md.read_text(encoding="utf-8")):
            found.setdefault(name, md)
    return found


def test_skills_write_exactly_the_ledgers_the_writer_accepts():
    """A name outside `SHAPES` is refused at the end of every run that writes it;
    a shape no skill writes is a ledger nobody keeps."""
    written = _ledgers_written_by_skills()
    assert set(written) == set(log_run.SHAPES), {
        name: str(path.relative_to(_PLUGIN_ROOT)) for name, path in written.items()}


def test_cla_setup_seeds_exactly_the_ledgers_the_writer_accepts():
    text = _CLA_SETUP.read_text(encoding="utf-8")
    match = re.search(r'for f in ([^;]*); do\n  \[ -e "\$ROOT/cla\.io/retro/\$f\.jsonl" \] \|\| :', text)
    assert match, "cla-setup/SKILL.md: no ledger seed loop found"
    assert {f"{name}.jsonl" for name in match.group(1).split()} == set(log_run.SHAPES)
