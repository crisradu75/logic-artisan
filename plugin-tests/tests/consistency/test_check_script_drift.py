"""Tests for check_script_drift.py."""

from __future__ import annotations

import re
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
    # Named exactly, not matched on a substring: a second group with "resolver"
    # in its name now exists (the fleet repo-list one), and `next` over a dict
    # would have silently picked whichever came first.
    resolver = next((g for name, g in groups.items()
                     if name.startswith("retro ledger dir resolver")), None)
    assert resolver is not None, (
        f"no ledger-dir resolver group left in SIBLING_GROUPS: {sorted(groups)}"
    )
    assert set(resolver["files"]) == {
        "lib/log_run.py",
        "skills/codify-retro/scripts/codify_aggregate.py",
        "skills/spec-to-pr-retro/scripts/spec_to_pr_aggregate.py",
        # A THIRD reader of the same dir. It was added outside this group and the
        # group's own name still said "both readers" — a reader nothing compared
        # against the writer is the exact silence this group exists for.
        "lib/ledger_summary.py",
    }, f"the writer/reader set changed: {resolver['files']}"
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
        "retro ledger dir resolver (writer + every reader)",
        "retro aggregator record loading",
        "fleet repo-list resolver (both aggregators + the summariser)",
        "make_dir_alias test helper",
    }
    assert names == expected, (
        f"SIBLING_GROUPS changed: missing {sorted(expected - names)}, "
        f"unexpected {sorted(names - expected)}. Adding a group is welcome — add it "
        "here in the same commit. Removing one needs a reason, because each group "
        "exists for a divergence that was silent when it happened."
    )


# ---------------------------------------------------------------- issue #249
#
# The group's MEMBERSHIP, derived rather than declared. Everything above pins
# what the declared file set IS; nothing asked whether it is everything.
#
# `check_script_drift.py`'s own docstring says the group covers "the ledger
# WRITER and the two READERS of what it writes", and when issue #249 was filed a
# fifth file resolved the same directory and was not in it: a PostToolUse hook
# (since deleted) that did it inline rather than through
# `_git_toplevel`/`_runs_dir`. A hand-written file list cannot notice another
# arriving the same way, and the failure is the one this whole script exists
# for: a file writing to a directory the readers do not read is silent, and
# reads as a cold start.
# TWO PATTERNS, NOT ONE LITERAL. The first cut was the single substring
# `environ.get("CLAUDE_RETRO_DIR"`, which is narrower than the exemption below
# claims: `os.getenv("CLAUDE_RETRO_DIR")`, a single-quoted spelling, and — the
# one that matters — a file that hardcodes `cla.io/retro` with NO override at
# all were each invisible to it. The no-override spelling is the likeliest drift
# this group exists for, since it is what someone writes who does not know the
# override exists.
#
# When this widening landed, all three rules found the same files on the tree
# as it then stood, so it changed no verdict. It is here for the next one.
_LEDGER_DIR_PATTERNS = (
    # Any reference to the override, however it is spelled or quoted.
    re.compile(r"CLAUDE_RETRO_DIR"),
    # The dir built literally, joined or segment-by-segment.
    re.compile(r"""cla\.io[/\\]retro|["']cla\.io["']\s*[/,]\s*["']retro["']"""),
)

# Files that resolve the retro ledger dir and are deliberately NOT compared
# against the group, keyed to the reason. Verified below to still exist, still
# resolve the dir, and still not be group members. Empty today: its one entry
# was the commit-provenance hook, deleted with its ledger. An entry added here
# must state why the file's contract makes it incomparable with the group.
_LEDGER_DIR_EXEMPT: dict[str, str] = {}


def ledger_dir_resolvers(plugin_root: Path, patterns) -> set[str]:
    """Every shipped `.py` that resolves the retro ledger dir, plugin-relative.

    Both inputs are parameters so a planted tree can drive this, the rule the
    sibling guards state for a helper a test asserts over.

    SCOPED TO `.py`, and that is a real limit rather than an oversight: every
    shipped file that could resolve this directory today is Python. A `.sh` hook
    doing it would be invisible here, and the limit is stated so the exemption
    below is not read as broader than the check that backs it."""
    return {
        p.relative_to(plugin_root).as_posix()
        for p in sorted(plugin_root.rglob("*.py"))
        if "__pycache__" not in p.parts
        and any(
            pat.search(p.read_text(encoding="utf-8", errors="replace"))
            for pat in patterns
        )
    }


def unregistered_resolvers(found, members, exempt) -> list[str]:
    """Resolvers accounted for by neither the group nor the exemption map."""
    return sorted(set(found) - set(members) - set(exempt))


def _resolver_group() -> dict:
    return next(
        g for g in csd.SIBLING_GROUPS
        if g["name"].startswith("retro ledger dir resolver")
    )


def test_every_ledger_dir_resolver_is_accounted_for():
    """The direction the declared file list cannot close (issue #249).

    When #249 was filed, five files in the shipped tree read `CLAUDE_RETRO_DIR`
    and the group named four; the fifth was a hook that has since been deleted.
    Re-derive the current set rather than trusting a list here::

        $ grep -rln 'CLAUDE_RETRO_DIR' .claude/plugins/cla --include=*.py
    """
    found = ledger_dir_resolvers(csd.PLUGIN_ROOT, _LEDGER_DIR_PATTERNS)
    assert found, (
        "no shipped .py resolves the retro ledger dir any more — either the "
        "override was renamed or the ledger tools have left the plugin. Either "
        "way this check and the group it polices are scanning nothing."
    )
    unregistered = unregistered_resolvers(
        found, _resolver_group()["files"], _LEDGER_DIR_EXEMPT
    )
    assert not unregistered, (
        f"{unregistered} resolve the retro ledger directory but are neither "
        "compared by the ledger-dir group nor exempted from it, so nothing "
        "checks that they agree with the writer. A reader that disagrees finds "
        "no records and reports a cold start. Add it to the group's `files` if "
        "it resolves the dir the same way; to _LEDGER_DIR_EXEMPT, with a reason, "
        "if its cwd or failure contract makes it incomparable."
    )


def test_every_ledger_dir_exemption_still_earns_itself():
    """An exemption must not outlive its reason, nor cover a file that has since
    joined the group — either way the entry stops being a record of a decision
    and becomes a pressure valve."""
    found = ledger_dir_resolvers(csd.PLUGIN_ROOT, _LEDGER_DIR_PATTERNS)
    members = set(_resolver_group()["files"])
    for rel, reason in _LEDGER_DIR_EXEMPT.items():
        assert reason.strip(), f"{rel} is exempt with no reason given"
        assert (csd.PLUGIN_ROOT / rel).is_file(), (
            f"{rel} is exempted but does not exist — delete the entry"
        )
        assert rel in found, (
            f"{rel} no longer resolves the ledger dir, so the exemption covers "
            "nothing — delete the entry"
        )
        assert rel not in members, (
            f"{rel} is both a group member and exempted from the group; the "
            "exemption would then excuse a file that is already compared"
        )


def test_an_unregistered_resolver_is_reported():
    """The planted half — the real tree is clean by construction, so without this
    nothing shows the two maps can be told apart."""
    assert unregistered_resolvers(
        {"lib/log_run.py", "hooks/new-writer.py"}, ("lib/log_run.py",), {}
    ) == ["hooks/new-writer.py"]
    assert unregistered_resolvers(
        {"lib/log_run.py", "hooks/new-writer.py"},
        ("lib/log_run.py",),
        {"hooks/new-writer.py": "a stated reason"},
    ) == []


def test_the_resolver_marker_still_discriminates(tmp_path: Path):
    """`ledger_dir_resolvers` is a substring scan, so a marker weakened to
    something every file contains would report the whole tree and a marker
    weakened to nothing would report none — both read as "no unregistered
    resolvers". Pinned against a planted tree rather than the real one."""
    (tmp_path / "a.py").write_text(
        'import os\nos.environ.get("CLAUDE_RETRO_DIR")\n', encoding="utf-8"
    )
    (tmp_path / "b.py").write_text("x = 1\n", encoding="utf-8")
    assert ledger_dir_resolvers(tmp_path, _LEDGER_DIR_PATTERNS) == {"a.py"}
    # The no-override spelling the single-literal rule could not see: no
    # `CLAUDE_RETRO_DIR` anywhere in the file, just the directory built by
    # hand. This is the shape someone writes who does not know the override
    # exists, and it is the likeliest sixth resolver.
    (tmp_path / "c.py").write_text(
        'LEDGER = root / "cla.io" / "retro" / "runs.jsonl"\n', encoding="utf-8"
    )
    assert ledger_dir_resolvers(tmp_path, _LEDGER_DIR_PATTERNS) == {"a.py", "c.py"}
    # And the spellings of the override itself that the literal missed.
    (tmp_path / "d.py").write_text(
        "import os\nos.getenv('CLAUDE_RETRO_DIR')\n", encoding="utf-8"
    )
    assert ledger_dir_resolvers(tmp_path, _LEDGER_DIR_PATTERNS) == {
        "a.py", "c.py", "d.py"
    }


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


def test_the_two_diverged_helpers_stay_registered() -> None:
    """`_load_ledgers` and `_window` are pinned because they ALREADY diverged.

    Both were copied verbatim into the two aggregators and then fixed in only one
    — the window kept inverting in codify after spec-to-pr learned to sort, and a
    reviewer caught it rather than the gate. Dropping either name from the group
    would restore exactly that hole while every other test stayed green.
    """
    import check_script_drift

    group = next(g for g in check_script_drift.SIBLING_GROUPS
                 if g["name"] == "retro aggregator record loading")
    assert "_load_ledgers" in group["functions"]
    assert "_window" in group["functions"]
