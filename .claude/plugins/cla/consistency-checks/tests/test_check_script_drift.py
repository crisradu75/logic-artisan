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
    """Normalization blanks STRING constants only — an int/float/bool literal
    is real logic (a threshold, a timeout) and must still match exactly."""
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
