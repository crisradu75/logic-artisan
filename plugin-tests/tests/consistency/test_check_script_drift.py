"""Tests for check_script_drift.py."""

from __future__ import annotations

import textwrap
from pathlib import Path

import check_script_drift as csd


def test_no_drift_in_the_real_repo_today():
    """This is the actual enforcement: the suite runs this on every pass, so a
    future edit that lands in one sibling but not the others fails here instead
    of silently drifting.

    Each group carries its own root — the siblings live in two different trees
    since the dev tree moved out of the plugin — so passing one root for all of
    them would resolve a third of the files to nothing."""
    problems = []
    for group in csd.SIBLING_GROUPS:
        problems.extend(csd.check_group(group, group["root"]))
    assert problems == [], problems


def test_the_ledger_resolver_group_still_covers_the_writer_and_both_readers():
    """Non-vacuity for the group that matters most.

    `test_no_drift_in_the_real_repo_today` passes just as happily over a group
    that has been quietly narrowed — measured: dropping `lib/log_run.py` from
    the file list killed no test. But the WRITER is the whole reason this group
    exists. Two readers agreeing with each other and disagreeing with the writer
    is the silent failure (the retro reports zero runs, which reads as a cold
    start), so pin all three by name.
    """
    groups = {g["name"]: g for g in csd.SIBLING_GROUPS}
    resolver = next((g for name, g in groups.items() if "resolver" in name), None)
    assert resolver is not None, (
        f"no ledger-dir resolver group left in SIBLING_GROUPS: {sorted(groups)}"
    )
    assert set(resolver["files"]) == {
        "lib/log_run.py",
        "skills/codify-retro/scripts/codify_aggregate.py",
        "skills/spec-to-pr-retro/scripts/spec_to_pr_aggregate.py",
    }, f"the writer/reader trio changed: {resolver['files']}"
    assert "_runs_dir" in resolver["functions"], (
        "the dir resolver itself must be compared, not only `_git_toplevel`"
    )


def test_every_group_still_compares_at_least_two_files_and_one_function():
    """The same non-vacuity the resolver group gets, for the groups that had none.

    `test_no_drift_in_the_real_repo_today` iterates whatever `SIBLING_GROUPS`
    holds, so a group quietly narrowed to one file — or to no functions — compares
    nothing and the suite stays green. Measured: emptying group 3's `functions`,
    and narrowing group 2 to a single function, were both invisible to every test
    here. The resolver group was pinned by name; the other two were not, so the
    protection stopped exactly where someone had last been burned.

    A comparison needs two files to compare and at least one function to compare
    in them. Below that a group is decorative.
    """
    thin = []
    for group in csd.SIBLING_GROUPS:
        if len(group["files"]) < 2 or not group["functions"]:
            thin.append(
                f"{group['name']}: {len(group['files'])} file(s), "
                f"{len(group['functions'])} function(s)"
            )
    assert not thin, (
        "these groups compare nothing and would pass silently: " + "; ".join(thin)
    )


def test_the_group_set_itself_has_not_shrunk():
    """A group deleted outright is the same silent loss, one level up.

    Narrowing a group is caught above; removing it is not, because the loop then
    has nothing to iterate for it. Pinned by name so a rename is a deliberate edit
    rather than a quiet disappearance.
    """
    names = {g["name"] for g in csd.SIBLING_GROUPS}
    expected = {
        "retro ledger dir resolver (writer + both readers)",
        "retro aggregator record loading",
        "make_dir_alias test helper",
    }
    assert names == expected, (
        f"SIBLING_GROUPS changed: missing {sorted(expected - names)}, "
        f"unexpected {sorted(names - expected)}. Adding a group is welcome — add it "
        "here in the same commit. Removing one needs a reason, because each group "
        "exists for a divergence that was silent when it happened."
    )


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


def test_a_filename_difference_is_drift_now_that_the_exemption_is_gone(tmp_path: Path):
    """No string inside a guarded function is exempt any more. The exemption that
    normalized `<name>-runs.jsonl` existed for `_default_log_path`, which is no
    longer compared; keeping it could only have hidden a real difference."""
    _write(tmp_path / "a.py", '''
        def _runs_dir():
            return root / "cla.io" / "retro" / "codify-runs.jsonl"
    ''')
    _write(tmp_path / "b.py", '''
        def _runs_dir():
            return root / "cla.io" / "retro" / "spec-to-pr-runs.jsonl"
    ''')
    group = {
        "name": "synthetic",
        "functions": ("_runs_dir",),
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
