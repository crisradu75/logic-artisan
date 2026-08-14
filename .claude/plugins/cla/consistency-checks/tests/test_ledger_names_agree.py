"""The ledger name a skill WRITES must be the one its retro skill READS.

When `log_run.py` was consolidated into one shared writer, the ledger filename
moved out of Python and into markdown: each skill now names its own ledger as an
argument, in prose. The readers still hardcode it, as a constant in their
`aggregate.py`.

So the two halves of a single contract now live in different languages, in
different files, with nothing comparing them. A typo on the writer side is
accepted — `log_run.py` validates only the SHAPE of the argument
(`^[A-Za-z0-9][A-Za-z0-9._-]*\\.jsonl$`), so a misspelled name is happily written
to a brand-new file. The reader then finds nothing, and reports a cold start:
`runs_analyzed: 0`, which both retro skills explicitly instruct the model to read
as "the log doesn't exist yet — run the loop a few times first." Three silences
in a row, and the run history is simply gone.

`check_script_drift.py` guards the DIRECTORY half of this same contract across
writer and readers. This guards the FILENAME half, which that check deliberately
excludes.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

_PLUGIN_ROOT = Path(__file__).resolve().parents[2]

# (skill that writes, the prose file carrying the invocation, the reader's aggregate.py)
_LEDGER_CONTRACTS = [
    (
        "codify-learnings",
        _PLUGIN_ROOT / "skills" / "codify-learnings" / "SKILL.md",
        _PLUGIN_ROOT / "skills" / "codify-retro" / "scripts" / "aggregate.py",
    ),
    (
        "spec-to-pr",
        _PLUGIN_ROOT / "skills" / "_shared" / "references" / "run-log-schema.md",
        _PLUGIN_ROOT / "skills" / "spec-to-pr-retro" / "scripts" / "aggregate.py",
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
