"""Tests for check_script_drift.py."""

from __future__ import annotations

import textwrap
from pathlib import Path

import check_script_drift as csd


def test_no_drift_in_the_real_repo_today():
    """This is the actual enforcement: run_tests.py runs this scope on every
    pass, so a future edit that lands in one sibling but not the others fails
    the suite here instead of silently drifting."""
    problems = []
    for group in csd.SIBLING_GROUPS:
        problems.extend(csd.check_group(group, csd.PLUGIN_ROOT))
    assert problems == [], problems


def _write(path: Path, source: str) -> None:
    path.write_text(textwrap.dedent(source), encoding="utf-8")


def test_prose_only_differences_are_not_flagged(tmp_path: Path):
    _write(tmp_path / "a.py", '''
        def _helper(x):
            """Docstring for a.py, mentions /skill-a."""
            if x > 0:
                return x + 1
            return 0
    ''')
    _write(tmp_path / "b.py", '''
        def _helper(x):
            """Totally different docstring, mentions /skill-b instead."""
            if x > 0:
                return x + 1
            return 0
    ''')
    group = {
        "name": "synthetic",
        "functions": ("_helper",),
        "files": ("a.py", "b.py"),
    }
    assert csd.check_group(group, tmp_path) == []


def test_real_logic_drift_is_flagged(tmp_path: Path):
    _write(tmp_path / "a.py", '''
        def _helper(x):
            if x > 0:
                return x + 1
            return 0
    ''')
    _write(tmp_path / "b.py", '''
        def _helper(x):
            if x >= 0:
                return x + 1
            return 0
    ''')
    group = {
        "name": "synthetic",
        "functions": ("_helper",),
        "files": ("a.py", "b.py"),
    }
    problems = csd.check_group(group, tmp_path)
    assert len(problems) == 1
    assert "_helper" in problems[0] and "b.py" in problems[0]


def test_a_missing_function_is_flagged(tmp_path: Path):
    _write(tmp_path / "a.py", '''
        def _helper(x):
            return x
    ''')
    _write(tmp_path / "b.py", '''
        def _other(x):
            return x
    ''')
    group = {
        "name": "synthetic",
        "functions": ("_helper",),
        "files": ("a.py", "b.py"),
    }
    problems = csd.check_group(group, tmp_path)
    assert len(problems) == 1
    assert "missing `_helper`" in problems[0] and "b.py" in problems[0]


def test_a_missing_file_is_flagged(tmp_path: Path):
    group = {
        "name": "synthetic",
        "functions": ("_helper",),
        "files": ("does-not-exist.py",),
    }
    problems = csd.check_group(group, tmp_path)
    assert len(problems) == 1
    assert "file not found" in problems[0]


def test_int_constants_must_still_match(tmp_path: Path):
    """An int/float/bool literal is real logic (a threshold, a timeout) and
    must match exactly."""
    _write(tmp_path / "a.py", '''
        def _helper(x):
            return x < 4096
    ''')
    _write(tmp_path / "b.py", '''
        def _helper(x):
            return x < 2048
    ''')
    group = {
        "name": "synthetic",
        "functions": ("_helper",),
        "files": ("a.py", "b.py"),
    }
    problems = csd.check_group(group, tmp_path)
    assert len(problems) == 1


# --------------------------------------------------------------------------- #
# Strings that ARE the logic
#
# The first version of this checker blanked every string constant, which
# silently defeated it — the guarded functions are almost entirely string
# literals (`["git", "rev-parse", "--show-toplevel"]`, `"cla.io" / "retro"`).
# Both cases below were reported CLEAN before that was fixed.
# --------------------------------------------------------------------------- #


def test_argv_drift_is_caught(tmp_path: Path):
    """A sibling switching git plumbing must not compare equal."""
    _write(tmp_path / "a.py", '''
        def _git_toplevel():
            return subprocess.run(["git", "rev-parse", "--show-toplevel"])
    ''')
    _write(tmp_path / "b.py", '''
        def _git_toplevel():
            return subprocess.run(["git", "rev-parse", "--git-dir"])
    ''')
    group = {
        "name": "synthetic",
        "functions": ("_git_toplevel",),
        "files": ("a.py", "b.py"),
    }
    assert len(csd.check_group(group, tmp_path)) == 1


def test_ledger_directory_drift_is_caught(tmp_path: Path):
    """A sibling writing its ledger to a different DIRECTORY is the exact
    failure these resolvers' docstrings warn about ("runs vanish silently")."""
    _write(tmp_path / "a.py", '''
        def _runs_dir():
            return root / "cla.io" / "retro"
    ''')
    _write(tmp_path / "b.py", '''
        def _runs_dir():
            return root / "cla.io" / "runs"
    ''')
    group = {
        "name": "synthetic",
        "functions": ("_runs_dir",),
        "files": ("a.py", "b.py"),
    }
    assert len(csd.check_group(group, tmp_path)) == 1


def test_the_per_skill_ledger_filename_is_allowed_to_differ(tmp_path: Path):
    """The one deliberate exemption: `_default_log_path` builds the same path
    the same way and names its own skill's ledger at the end. Without this the
    real repo reports false drift between the two retro aggregators."""
    _write(tmp_path / "a.py", '''
        def _default_log_path():
            return root / "cla.io" / "retro" / "codify-runs.jsonl"
    ''')
    _write(tmp_path / "b.py", '''
        def _default_log_path():
            return root / "cla.io" / "retro" / "spec-to-pr-runs.jsonl"
    ''')
    group = {
        "name": "synthetic",
        "functions": ("_default_log_path",),
        "files": ("a.py", "b.py"),
    }
    assert csd.check_group(group, tmp_path) == []


def test_the_ledger_exemption_does_not_swallow_a_different_extension(tmp_path: Path):
    """The exemption is scoped to `<name>-runs.jsonl`; a sibling writing a
    different KIND of file is still drift."""
    _write(tmp_path / "a.py", '''
        def _default_log_path():
            return root / "codify-runs.jsonl"
    ''')
    _write(tmp_path / "b.py", '''
        def _default_log_path():
            return root / "codify-runs.txt"
    ''')
    group = {
        "name": "synthetic",
        "functions": ("_default_log_path",),
        "files": ("a.py", "b.py"),
    }
    assert len(csd.check_group(group, tmp_path)) == 1


def test_a_nested_def_does_not_shadow_the_top_level_one(tmp_path: Path):
    """`ast.walk` matched nested defs, so a same-named inner function could
    overwrite the real one and the comparison ran against the wrong body."""
    _write(tmp_path / "a.py", '''
        def _helper(x):
            return x + 1
    ''')
    _write(tmp_path / "b.py", '''
        def _helper(x):
            return x + 1

        def _wrapper():
            def _helper(x):
                return x + 999
            return _helper
    ''')
    group = {
        "name": "synthetic",
        "functions": ("_helper",),
        "files": ("a.py", "b.py"),
    }
    assert csd.check_group(group, tmp_path) == []


def test_every_missing_file_is_reported_not_just_the_first(tmp_path: Path):
    _write(tmp_path / "a.py", '''
        def _helper(x):
            return x
    ''')
    group = {
        "name": "synthetic",
        "functions": ("_helper",),
        "files": ("gone-a.py", "gone-b.py", "a.py"),
    }
    problems = csd.check_group(group, tmp_path)
    assert len([p for p in problems if "file not found" in p]) == 2
