"""`mutate.py` is the one script here that writes to source files. Test it hard.

Lives in `consistency-checks/` for the same reason `test_runner_stream_encoding.py`
does: `mutate.py` sits at the plugin root and belongs to no pytest scope.

WHY THESE TESTS EXIST. The first version of the tool shipped with none, and a
review found four ways it reported `All mutants killed` while proving nothing:
pytest absent, a target path that did not exist, a target that collected zero
tests, and a mutation that merely broke the parse. Every one of those made pytest
exit non-zero, and the verdict was "any non-zero means killed". A verification
tool that resolves ambiguity into confidence is worse than no tool — so the
false-kill cases below are the load-bearing half of this file, and each one
fails against that first version.

The tool is exercised as a SUBPROCESS against a sandbox scope built in `tmp_path`,
never against this repo's own files. A test for a tool that mutates source must
not mutate the source it is running from.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

_PLUGIN_ROOT = Path(__file__).resolve().parents[2]
_MUTATE = _PLUGIN_ROOT / "mutate.py"


def _make_scope(root: Path, *, with_tests: bool = True) -> tuple[Path, Path]:
    """A miniature pytest scope shaped like this repo's real ones.

    Returns `(source_file, tests_dir)`. The source has one behaviour and the test
    asserts it, so mutating the behaviour is genuinely caught — the control every
    false-kill case below is measured against.
    """
    (root / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\ntestpaths = ["tests"]\npythonpath = ["scripts"]\n',
        encoding="utf-8",
    )
    scripts = root / "scripts"
    scripts.mkdir()
    source = scripts / "mymod.py"
    source.write_text("def verdict():\n    return 'ON'\n", encoding="utf-8")
    tests = root / "tests"
    tests.mkdir()
    if with_tests:
        (tests / "test_mymod.py").write_text(
            "from mymod import verdict\n\n\ndef test_verdict():\n"
            "    assert verdict() == 'ON'\n",
            encoding="utf-8",
        )
    return source, tests


def _batch(root: Path, entries: str, header: str = "") -> Path:
    path = root / "batch.py"
    path.write_text(
        f"from pathlib import Path\n{header}\nMUTANTS = [\n{textwrap.indent(entries, '    ')}\n]\n",
        encoding="utf-8",
    )
    return path


def _run(batch: Path, *, python: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [python or sys.executable, str(_MUTATE), str(batch)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(batch.parent),
    )


# --------------------------------------------------------------------------- #
# The control: the tool works on its happy path
# --------------------------------------------------------------------------- #

def test_a_real_mutation_caught_by_a_real_test_is_killed(tmp_path):
    source, tests = _make_scope(tmp_path)
    batch = _batch(tmp_path, f"(\"flip the verdict\", Path(r\"{source}\"), \"'ON'\", "
                             f"\"'OFF'\", [Path(r\"{tests}\")]),")
    result = _run(batch)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "killed" in result.stdout
    assert "All 1 mutant(s) killed." in result.stdout


def test_a_mutation_no_test_covers_is_reported_as_a_survivor(tmp_path):
    """Non-vacuity partner for the control: the tool must be able to say NO."""
    source, tests = _make_scope(tmp_path)
    source.write_text("def verdict():\n    return 'ON'\n\n\ndef unused():\n"
                      "    return 1\n", encoding="utf-8")
    batch = _batch(tmp_path, f"(\"nothing covers this\", Path(r\"{source}\"), "
                             f"\"return 1\", \"return 2\", [Path(r\"{tests}\")]),")
    result = _run(batch)
    assert result.returncode == 1
    assert "SURVIVED" in result.stdout


# --------------------------------------------------------------------------- #
# The false kills — each one reported "All mutants killed" before this fix
# --------------------------------------------------------------------------- #

def test_a_target_that_does_not_exist_is_refused_not_counted_as_a_kill(tmp_path):
    source, _ = _make_scope(tmp_path)
    missing = tmp_path / "no-such-dir"
    batch = _batch(tmp_path, f"(\"typo'd target\", Path(r\"{source}\"), \"'ON'\", "
                             f"\"'OFF'\", [Path(r\"{missing}\")]),")
    result = _run(batch)
    assert result.returncode != 0
    assert "killed" not in result.stdout
    assert "target does not exist" in result.stdout + result.stderr


def test_a_target_that_collects_no_tests_is_inconclusive_not_a_kill(tmp_path):
    """pytest exits 5 for "no tests ran". That is definitionally the state in
    which the mutant CANNOT have been killed, and the old mapping called it one."""
    source, tests = _make_scope(tmp_path, with_tests=False)
    batch = _batch(tmp_path, f"(\"empty target\", Path(r\"{source}\"), \"'ON'\", "
                             f"\"'OFF'\", [Path(r\"{tests}\")]),")
    result = _run(batch)
    assert result.returncode == 1
    assert "INCONCLUSIVE" in result.stdout
    assert "no tests were collected" in result.stdout


def test_a_mutation_that_only_breaks_the_parse_is_inconclusive_not_a_kill(tmp_path):
    """The common failure of naive string mutation: the module stops importing,
    pytest exits 2, and no test asserted anything about the behaviour."""
    source, tests = _make_scope(tmp_path)
    batch = _batch(tmp_path, f"(\"syntax break\", Path(r\"{source}\"), "
                             f"\"return 'ON'\", \"return\\n    ((\", [Path(r\"{tests}\")]),")
    result = _run(batch)
    assert result.returncode == 1
    assert "INCONCLUSIVE" in result.stdout
    assert "broken the parse" in result.stdout


def test_it_refuses_to_run_at_all_without_pytest(tmp_path):
    """`run_tests.py` guards this; the tool did not, so under an interpreter with
    no pytest every mutant reported killed and the run exited 0."""
    venv = tmp_path / "bare"
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv)], check=True)
    exe = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not exe.is_file():  # pragma: no cover - venv layout differs
        pytest.skip("could not build a pytest-free interpreter")
    source, tests = _make_scope(tmp_path)
    batch = _batch(tmp_path, f"(\"anything\", Path(r\"{source}\"), \"'ON'\", "
                             f"\"'OFF'\", [Path(r\"{tests}\")]),")
    result = _run(batch, python=str(exe))
    assert result.returncode != 0
    assert "killed" not in result.stdout
    assert "pytest is not available" in result.stdout + result.stderr


# --------------------------------------------------------------------------- #
# Byte fidelity — the restore must not rewrite the file it restores
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("ending", [b"\n", b"\r\n"])
def test_the_restore_is_byte_exact_for_both_line_endings(tmp_path, ending):
    """`read_text`/`write_text` translate newlines, so restoring an LF file on
    Windows rewrote every line to CRLF — silently, and invisibly to `git diff`
    for a path pinned `eol=lf`. This repo pins `cla` that way because
    a CRLF shebang breaks the POSIX launchers."""
    source, tests = _make_scope(tmp_path)
    raw = ending.join([b"def verdict():", b"    return 'ON'", b""])
    source.write_bytes(raw)
    batch = _batch(tmp_path, f"(\"flip\", Path(r\"{source}\"), \"'ON'\", \"'OFF'\", "
                             f"[Path(r\"{tests}\")]),")
    _run(batch)
    assert source.read_bytes() == raw, "the restore rewrote the file's line endings"


def test_a_crash_leaves_a_backup_beside_the_file_and_blocks_the_next_run(tmp_path):
    """The `finally` cannot run for a hard kill. A sidecar backup survives it, and
    refusing to start while one exists stops a half-restored tree from being
    mistaken for uncommitted work."""
    source, tests = _make_scope(tmp_path)
    backup = source.with_name(source.name + ".mutate-backup")
    backup.write_bytes(b"stale\n")
    batch = _batch(tmp_path, f"(\"flip\", Path(r\"{source}\"), \"'ON'\", \"'OFF'\", "
                             f"[Path(r\"{tests}\")]),")
    result = _run(batch)
    assert result.returncode != 0
    assert "did not finish" in result.stdout + result.stderr
    assert source.read_text(encoding="utf-8") == "def verdict():\n    return 'ON'\n"


def test_a_successful_run_leaves_no_backup_behind(tmp_path):
    source, tests = _make_scope(tmp_path)
    batch = _batch(tmp_path, f"(\"flip\", Path(r\"{source}\"), \"'ON'\", \"'OFF'\", "
                             f"[Path(r\"{tests}\")]),")
    _run(batch)
    assert not source.with_name(source.name + ".mutate-backup").exists()


# --------------------------------------------------------------------------- #
# Preflight — refuse before touching anything
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("entry,expected", [
    ('("missing anchor", Path(r"{src}"), "not in the file", "x", [Path(r"{tst}")]),',
     "anchor not found"),
    ('("no-op", Path(r"{src}"), "\'ON\'", "\'ON\'", [Path(r"{tst}")]),',
     "changes nothing"),
    ('("targets is a string", Path(r"{src}"), "\'ON\'", "\'OFF\'", Path(r"{tst}")),',
     "must be a LIST"),
    ('("wrong arity", Path(r"{src}"), "\'ON\'", "\'OFF\'"),',
     "expected a 5-tuple"),
])
def test_a_malformed_or_useless_mutant_is_refused_before_any_write(tmp_path, entry, expected):
    """All of these produced a pytest exit the old mapping read as a kill, and the
    arity error crashed mid-run after earlier mutants had already been applied."""
    source, tests = _make_scope(tmp_path)
    before = source.read_bytes()
    batch = _batch(tmp_path, entry.format(src=source, tst=tests))
    result = _run(batch)
    assert result.returncode != 0
    assert expected in result.stdout + result.stderr
    assert source.read_bytes() == before, "preflight must run before any file is touched"


def test_an_ambiguous_anchor_is_refused_rather_than_silently_taking_the_first(tmp_path):
    """Separate from the parametrized case above because the CONSEQUENCE is what
    matters: mutating a site you did not mean, and getting a kill that belongs to
    that other site, is indistinguishable from the fix being covered."""
    source, tests = _make_scope(tmp_path)
    source.write_text("FLAG = 'ON'\n\n\ndef verdict():\n    return 'ON'\n", encoding="utf-8")
    before = source.read_bytes()
    batch = _batch(tmp_path, f"(\"two sites\", Path(r\"{source}\"), \"'ON'\", "
                             f"\"'OFF'\", [Path(r\"{tests}\")]),")
    result = _run(batch)
    assert result.returncode != 0
    assert "anchor appears 2x" in result.stdout + result.stderr
    assert "killed" not in result.stdout
    assert source.read_bytes() == before, "refused before any write"


def test_a_batch_that_fails_to_load_says_so_instead_of_tracebacking(tmp_path):
    batch = tmp_path / "batch.py"
    batch.write_text("this is not python(\n", encoding="utf-8")
    result = _run(batch)
    assert result.returncode != 0
    assert "failed to load" in result.stdout + result.stderr
    assert "Traceback" not in result.stderr


def test_an_empty_mutants_list_is_refused(tmp_path):
    """A zero-mutant batch must not report "All 0 mutant(s) killed"."""
    batch = tmp_path / "batch.py"
    batch.write_text("MUTANTS = []\n", encoding="utf-8")
    result = _run(batch)
    assert result.returncode != 0
    assert "no non-empty MUTANTS" in result.stdout + result.stderr


def test_no_argument_prints_usage_and_exits_two(tmp_path):
    result = subprocess.run(
        [sys.executable, str(_MUTATE)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert result.returncode == 2
    assert "usage:" in result.stderr
    assert "MUTANTS" in result.stderr
