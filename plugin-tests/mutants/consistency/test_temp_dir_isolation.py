"""Mutants for the suite-wide temp-dir redirect in plugin-tests/tests/conftest.py.

    python3 plugin-tests/mutate.py plugin-tests/mutants/consistency/test_temp_dir_isolation.py

The covering tests assert where temp paths resolve — in this process and in a
subprocess — so no other process on the machine can make them fail. A killed
mutant here may still have leaked: with the redirect gone, the target's
rendering tests write page folders into the real temp dir's cla-annotate.
"""
from pathlib import Path

DEV = Path(__file__).resolve().parents[2]                 # <repo>/plugin-tests
CONFTEST = DEV / "tests" / "conftest.py"
TESTS = [DEV / "tests" / "skills" / "annotate" / "test_temp_dir_isolation.py"]

MUTANTS = [
    ("this process's temp dir is no longer redirected",
     CONFTEST,
     "    tempfile.tempdir = redirected",
     "    pass",
     TESTS),

    ("a subprocess's temp dir is no longer redirected",
     CONFTEST,
     "        os.environ[k] = redirected",
     "        pass",
     TESTS),
]
