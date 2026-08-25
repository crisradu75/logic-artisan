"""`mutate.py` is the one script here that writes to source files. Test it hard.

Lives beside the other checks on this repo's own source: `mutate.py` is a
developer tool at the dev tree's root, not a shipped plugin asset.

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

_DEV_TREE_ROOT = Path(__file__).resolve().parents[2]
_MUTATE = _DEV_TREE_ROOT / "mutate.py"


def _load_mutate():
    """Import `mutate.py` for the few pure predicates worth unit-testing.

    Every other test here drives it as a subprocess, which is right for
    end-to-end behaviour but cannot reach a helper directly. `mutate.py` belongs
    to no pytest scope, so it is loaded by path rather than imported by name.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("_mutate_under_test", _MUTATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mutate = _load_mutate()


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


@pytest.mark.parametrize(
    "summary, ran, why",
    [
        ("1 failed, 3 passed in 0.4s", True, "a test genuinely failed"),
        ("3 passed in 0.2s", True, "tests ran and passed"),
        ("1 failed, 1 error in 2.0s", True, "a test failed alongside an error"),
        # The pair that matters. Both exit 1 and both summarise as `1 error`;
        # only the attribution differs. A mutation that breaks module
        # construction blows up in fixture setup constantly, so calling that
        # INCONCLUSIVE would report real kills as broken batches — which a
        # first version of this predicate did, by keying on the count line.
        ("ERROR tests/test_x.py::test_a\n1 error in 0.41s", True,
         "a per-TEST error: the test was selected and its setup ran"),
        ("ERROR tests/test_x.py\n!! Interrupted: 1 error during collection !!\n1 error in 0.46s",
         False, "a COLLECTION error: no `::nodeid`, nothing ran"),
        # The same collection failure WITHOUT the Interrupted banner. Whether
        # pytest prints that banner varies with how the target is spelled, so
        # the banner check cannot be the discriminator — the missing `::nodeid`
        # is. Measured: with both cases present, mutating either guard alone
        # used to survive, because each masked the other on the old corpus.
        ("ERROR tests/test_x.py\n!! stopping after 1 failures !!\n1 error in 0.41s",
         False, "a COLLECTION error with no banner: still no `::nodeid`"),
        ("no tests ran in 0.01s", False, "nothing to run"),
    ],
)
def test_killed_requires_evidence_that_a_test_actually_ran(summary, ran, why):
    """`killed` must mean "a test failed", never merely "pytest exited 1".

    Belt-and-braces, stated honestly: every collection failure I could construct
    exits 2, which the exit-code mapping already routes to INCONCLUSIVE. I could
    NOT reproduce an exit-1-with-zero-tests run, so this predicate guards a path
    that may currently be unreachable. It is cheap, and the cost of being wrong
    is the one failure this tool must never produce — manufacturing the
    confidence it exists to supply.

    The `1 error` case is not hypothetical in the other direction: a first draft
    of this predicate accepted pytest's `1 error in 0.46s` collection summary as
    proof a test had run.
    """
    assert mutate._a_test_actually_ran(summary) is ran, why


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
    """The deleted `run_tests.py` used to guard this; the tool did not, so under
    an interpreter with no pytest every mutant reported killed and the run
    exited 0. Now that the runner is gone, this is the only guard there is."""
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


def test_a_multi_line_anchor_against_a_crlf_file_names_the_cause(tmp_path):
    """The preflight already refuses this; the point is that it says WHY.

    Anchors match raw bytes, so a `\\n` in `old` finds nothing in a CRLF file
    even though the lines are plainly there. The module docstring explains it —
    130 lines above the error message nobody scrolls back from. Measured: the
    trap cost two preflight rounds across two batches in one session before the
    hint existed. Assert the hint, not just the refusal, or removing it leaves
    this test green and the next author on the same detour."""
    source, tests = _make_scope(tmp_path)
    source.write_bytes(b"\r\n".join([b"def verdict():", b"    return 'ON'", b""]))
    batch = _batch(
        tmp_path,
        f'("crlf", Path(r"{source}"), "def verdict():\\n    return \'ON\'", '
        f'"def verdict():\\n    return \'OFF\'", [Path(r"{tests}")]),',
    )
    out = _run(batch).stdout + _run(batch).stderr
    assert "anchor not found" in out
    assert "CRLF" in out, "the refusal did not name the cause it can detect"


def test_a_crlf_aware_anchor_that_simply_misses_is_not_blamed_on_crlf(tmp_path):
    """An anchor spelling the separator `\\r\\n` still contains `\\n`. Gating the
    hint on that alone told the one author who did it right to fix the one thing
    that was right."""
    source, tests = _make_scope(tmp_path)
    source.write_bytes(b"\r\n".join([b"def verdict():", b"    return 'ON'", b""]))
    batch = _batch(
        tmp_path,
        f'("crlf-aware", Path(r"{source}"), "nope\\r\\nstill nope", "x", '
        f'[Path(r"{tests}")]),',
    )
    out = _run(batch).stdout + _run(batch).stderr
    assert "anchor not found" in out
    assert "CRLF" not in out, "blamed CRLF for an anchor that already spells \\r\\n"


def test_a_missing_anchor_in_an_lf_file_does_not_blame_crlf(tmp_path):
    """The hint is gated on the file actually using CRLF. Ungated, it would fire
    on every missing anchor and become noise that gets read past — which is how
    a diagnostic stops being one."""
    source, tests = _make_scope(tmp_path)
    source.write_bytes(b"\n".join([b"def verdict():", b"    return 'ON'", b""]))
    batch = _batch(
        tmp_path,
        f'("lf", Path(r"{source}"), "not in the file at all", "x", [Path(r"{tests}")]),',
    )
    out = _run(batch).stdout + _run(batch).stderr
    assert "anchor not found" in out
    assert "CRLF" not in out, "blamed CRLF for a plain missing anchor in an LF file"


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


# ---------------------------------------------------------------- stale bytecode


def test_a_run_leaves_no_stale_bytecode_for_the_file_it_mutated(tmp_path):
    """The restore is byte-exact and still not enough on its own.

    CPython validates a `.pyc` on the source's mtime **in whole seconds** plus
    its size. This tool writes a mutant, runs pytest — which compiles and caches
    it — then restores the original, and a mutant is usually the SAME LENGTH as
    what it replaced. Land the cycle inside one second and the restored file's
    (mtime, size) matches the pair recorded for the MUTANT, so every later import
    gets the mutant's bytecode from a file whose bytes on disk are correct.

    Measured on this repo, 2026-08-25: a same-length palette swap left the
    mutant cached, and the next full suite went red on a test that had passed
    minutes earlier with `git diff` showing nothing. The same mechanism can leave
    a suite GREEN over mutant code, which is the expensive direction.

    `'ON'` -> `'OF'` deliberately: equal length, so this reproduces the collision
    rather than dodging it on a size difference."""
    source, tests = _make_scope(tmp_path)
    original = source.read_bytes()
    batch = _batch(tmp_path, f"(\"same length\", Path(r\"{source}\"), \"'ON'\", "
                             f"\"'OF'\", [Path(r\"{tests}\")]),")
    _run(batch)

    assert source.read_bytes() == original
    cached = sorted((source.parent / "__pycache__").glob("mymod.*.pyc"))
    assert cached == [], f"stale bytecode survived the restore: {cached}"


def test_the_bytecode_a_restore_leaves_behind_would_actually_be_reused(tmp_path):
    """The non-vacuity partner: proves the cache this tool drops is one CPython
    would really have trusted, rather than one it would have recompiled anyway.

    Without it the test above passes for the wrong reason the moment the cycle
    happens to straddle a second boundary, and a guard that only fires on a fast
    machine is not a guard."""
    source, _tests = _make_scope(tmp_path)
    original = source.read_bytes()
    import py_compile

    cache = py_compile.compile(str(source), doraise=True)
    mutant = original.replace(b"'ON'", b"'OF'")
    assert len(mutant) == len(original), "the fixture no longer reproduces the collision"

    stat = os.stat(source)
    source.write_bytes(mutant)
    # Same whole-second mtime and same size — exactly what a fast mutate/restore
    # cycle produces, and precisely the pair a pyc header records.
    os.utime(source, (stat.st_atime, stat.st_mtime))

    header = Path(cache).read_bytes()[:16]
    import struct

    _magic, _flags, mtime, size = struct.unpack("<IIII", header)
    assert mtime == int(os.stat(source).st_mtime) and size == os.stat(source).st_size, \
        "the cached header no longer matches the source; the collision is not reproduced"

    mutate._drop_bytecode(source)
    assert not Path(cache).exists()
