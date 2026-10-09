"""Mutants for the suite-wide temp-dir isolation in plugin-tests/tests/conftest.py.

The guard is a session-finish check, not a test: it fails the run when the REAL
temp dir gained a `cla-annotate` entry. The target below renders pages with no
`out=`, so with the redirect gone they land in the real temp dir and the guard
has to say so.

    python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_temp_dir_isolation.py

A killed mutant here HAS leaked: it leaves page folders in the real
%TEMP%/cla-annotate, which is the bug being planted. Delete what the run's
message names afterwards.
"""
from pathlib import Path

DEV = Path(__file__).resolve().parents[2]                 # <repo>/plugin-tests
CONFTEST = DEV / "tests" / "conftest.py"
TESTS = [DEV / "tests" / "skills" / "annotate" / "test_render_change.py"]

MUTANTS = [
    ("the run's temp dir is no longer redirected in process",
     CONFTEST,
     "    tempfile.tempdir = redirected",
     "    pass",
     TESTS),
]
# No mutant disables the guard on its own: with the redirect in force nothing
# leaks, so a disabled guard and a working one cannot be told apart. The mutant
# above is the guard's test — it only dies if the guard reports the leak.
