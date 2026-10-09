"""The run's temp dir is its own, not the developer's.

The annotate scripts write to the system temp dir by design — rendered pages
under `<temp>/cla-annotate/<hash of the repo root>`, the app window's browser
profile beside them — and a test's repo root is new every time, so before the
conftest redirect every rendering test left a folder in the real temp dir.

These checks assert WHERE temp paths resolve, not what appeared in the real
temp dir: a diff of a shared folder can be tripped by any other process, and
under mutate.py that would turn a survivor into a kill.
"""
import os
import subprocess
import sys
import tempfile

import annotate_server
import render_doc


def _under(path, base):
    path = os.path.normcase(os.path.realpath(path))
    base = os.path.normcase(os.path.realpath(base))
    return os.path.commonpath([path, base]) == base


def test_this_process_resolves_temp_paths_inside_the_run(run_temp_dir, tmp_path):
    assert _under(tempfile.gettempdir(), run_temp_dir), tempfile.gettempdir()
    pages = render_doc.page_dir(str(tmp_path))
    assert _under(pages, run_temp_dir), pages
    prof = annotate_server.profile_dir(pages)
    assert _under(prof, run_temp_dir), prof


def test_a_subprocess_resolves_its_temp_dir_inside_the_run(run_temp_dir):
    """A test that starts a script inherits this environment; the script's own
    `tempfile.gettempdir()` has to land in the run's dir too."""
    out = subprocess.run(
        [sys.executable, "-c", "import tempfile; print(tempfile.gettempdir())"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=True)
    got = out.stdout.strip()
    assert _under(got, run_temp_dir), got
