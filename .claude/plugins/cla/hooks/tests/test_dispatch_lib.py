"""Unit tests for `_dispatch_lib.py` — the module the two dispatcher scripts
share to run sibling hooks in-process. These target the load-isolation and
loud-fail-open behavior added after a code review found both were previously
silent: an unhandled exception discarded all its diagnostic output on exit 0
(stderr is dropped entirely on a non-blocking exit per the documented
PreToolUse hook contract), and a hook that failed to LOAD could crash the
whole dispatcher, taking out every hook positioned after it in the list.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

import pytest

_HOOKS_DIR = Path(__file__).resolve().parent.parent
_LIB_PATH = _HOOKS_DIR / "_dispatch_lib.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("dispatch_lib_under_test", _LIB_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


lib = _load_module()


def _stub_module(name: str, main_body: str) -> ModuleType:
    mod = ModuleType(name)
    exec(compile(main_body, f"<stub:{name}>", "exec"), mod.__dict__)
    return mod


# --------------------------------------------------------------------------- #
# run_hook: exception / SystemExit handling
# --------------------------------------------------------------------------- #

def test_run_hook_raising_main_is_loud_fail_open():
    mod = _stub_module("stub_raises", "def main():\n    raise RuntimeError('boom')\n")
    result = lib.run_hook(mod, "{}")
    assert result.code == 0
    assert result.errored is True
    assert "boom" in result.stderr
    assert "RuntimeError" in result.stderr


def test_run_hook_clean_main_is_not_flagged_errored():
    mod = _stub_module("stub_clean", "def main():\n    return 0\n")
    result = lib.run_hook(mod, "{}")
    assert result.code == 0
    assert result.errored is False


def test_run_hook_system_exit_int_code_preserved_and_not_errored():
    mod = _stub_module("stub_exit_2", "import sys\ndef main():\n    sys.exit(2)\n")
    result = lib.run_hook(mod, "{}")
    assert result.code == 2
    assert result.errored is False


def test_run_hook_bare_system_exit_is_not_errored():
    # A bare `sys.exit()` (no args) is a normal, intentional success exit —
    # must NOT be misclassified as an error (regression: e.code is None was
    # once treated the same as a non-int code).
    mod = _stub_module("stub_bare_exit", "import sys\ndef main():\n    sys.exit()\n")
    result = lib.run_hook(mod, "{}")
    assert result.code == 0
    assert result.errored is False


def test_run_hook_system_exit_non_int_code_is_loud_fail_open():
    mod = _stub_module("stub_exit_str", "import sys\ndef main():\n    sys.exit('bad happened')\n")
    result = lib.run_hook(mod, "{}")
    assert result.code == 0
    assert result.errored is True
    assert "bad happened" in result.stderr


# --------------------------------------------------------------------------- #
# run_hook_file: load-failure isolation
# --------------------------------------------------------------------------- #

def test_run_hook_file_isolates_load_failure():
    result = lib.run_hook_file("this-file-does-not-exist.py", "{}")
    assert result.code == 0
    assert result.errored is True
    assert "this-file-does-not-exist.py" in result.stderr


def test_run_hook_file_loads_and_runs_a_real_sibling():
    # Sanity check the happy path still works end-to-end through run_hook_file.
    result = lib.run_hook_file("warn-branch-base.py", '{"tool_input": {"command": "ls"}}')
    assert result.errored is False
    assert result.code == 0


# --------------------------------------------------------------------------- #
# GIT_GLOBAL_OPTS / strip_quoted_spans — shared by every git-matching hook.
# Tested once here at the source rather than duplicated per hook: a fix (or a
# regression) in the shared pattern shows up in exactly one place.
# --------------------------------------------------------------------------- #

def _git_push_pattern():
    return re.compile(r"\bgit\s+" + lib.GIT_GLOBAL_OPTS + r"push\b")


def _branch_create_pattern():
    return re.compile(
        r"\bgit\s+" + lib.GIT_GLOBAL_OPTS + r"(?:checkout\s+-b|switch\s+(?:-c|--create))\s+(\S+)"
    )


@pytest.mark.parametrize(
    "command",
    [
        "git push origin main",
        "git -c core.x=y push origin main",
        "git -C /some/path push origin main",
        "git --work-tree /some/path push origin main",
        "git --git-dir /some/path push origin main",
        "git --git-dir=/some/path push origin main",
        "git --namespace ns push origin main",
        "git --no-pager push origin main",
        "git --bare push origin main",
        "git -c core.x=y -C /some/path --work-tree /other push origin main",
    ],
)
def test_git_global_opts_recognizes_every_documented_prefix_shape(command):
    assert _git_push_pattern().search(command), f"expected a match for: {command!r}"


def test_git_global_opts_gap_fails_safe_without_eating_the_subcommand():
    # --exec-path is deliberately NOT in the named space-value-taking list
    # (see GIT_GLOBAL_OPTS's own docstring). Asserted as a SAFETY property, not
    # as required behavior: whatever this shape does, it must not produce a
    # garbled partial match that swallows the real subcommand token. Adding
    # `exec-path` to the named set later is a strict improvement and must NOT
    # make this test fail, so don't assert the no-match itself.
    command = "git --exec-path /x push origin main"
    m = _git_push_pattern().search(command)
    if m is not None:
        assert m.group(0).endswith("push"), (
            f"pattern matched but did not land on the `push` subcommand: {m.group(0)!r}"
        )


def test_git_global_opts_matches_a_legitimate_non_main_push_shape():
    # Push-SHAPE detection is separate from the main/master-target check a
    # caller layers on top. This asserts the shared pattern still matches an
    # ordinary feature-branch push (the target check is what spares it) — it is
    # not a false-positive test, despite what an earlier name here implied.
    assert _git_push_pattern().search("git push origin feature/x")


@pytest.mark.parametrize(
    "quoted_value",
    [
        '"/some/checkout path/with a space"',
        "'/some path/with a space'",
    ],
)
def test_strip_quoted_spans_lets_a_quoted_c_or_capital_c_value_with_a_space_match(quoted_value):
    # Before this fix, `-C "/path with space"` broke the mandatory trailing
    # `\s+` in GIT_GLOBAL_OPTS because `\S+` stopped at the space INSIDE the
    # still-quoted value — a real, not exotic, shape (e.g. a checkout under
    # something like "Documents/My Project" on macOS/Windows).
    command = f"git -C {quoted_value} push origin main"
    scanned = lib.strip_quoted_spans(command)
    assert _git_push_pattern().search(scanned), f"expected a match after stripping: {scanned!r}"


def test_strip_quoted_spans_is_length_preserving():
    # Length-preservation is load-bearing, not cosmetic: it's what lets a
    # caller capture a match GROUP against the scanned string (e.g. a branch
    # name) and re-slice the same offsets out of the ORIGINAL command to
    # recover real text a naive collapse-to-`''` would have destroyed.
    command = "git checkout -b 'feature/foo'"
    scanned = lib.strip_quoted_spans(command)
    assert len(scanned) == len(command)

    m = _branch_create_pattern().search(scanned)
    assert m is not None
    real_branch = command[m.start(1) : m.end(1)].strip("'\"")
    assert real_branch == "feature/foo"


def test_strip_quoted_spans_still_hides_a_git_command_mentioned_in_quoted_prose():
    # The original, pre-existing purpose of this function: a `git commit`
    # substring inside a quoted commit message / echoed string must not
    # itself look like a real invocation to a caller matching on `scanned`.
    command = 'echo "run git commit -m foo later" && ls'
    scanned = lib.strip_quoted_spans(command)
    assert "git commit" not in scanned


# --------------------------------------------------------------------------- #
# strip_quoted_spans -- the documented SCOPE of what it does and does not cover
# --------------------------------------------------------------------------- #


def test_strip_quoted_spans_collapses_backtick_spans_too():
    # Backticks are the third quoting form the helper handles; the other two
    # had coverage and this one did not.
    command = "echo `git commit -m x` && ls"
    scanned = lib.strip_quoted_spans(command)
    assert "git commit" not in scanned
    assert len(scanned) == len(command)


def test_strip_quoted_spans_does_not_cover_heredoc_bodies():
    # Pins a NAMED non-coverage, so nobody re-adds the (previously wrong)
    # docstring claim that heredocs are handled. A heredoc body is unquoted
    # text, so a git command inside one survives the scan and a caller WILL
    # match it. This is the git hooks' most likely real-world false positive;
    # it is accepted, and this test exists so it stays a known quantity.
    command = "cat > x.sh <<'EOF'\ngit " + "push origin main\nEOF"
    scanned = lib.strip_quoted_spans(command)
    assert "push origin main" in scanned


def test_strip_quoted_spans_matches_shell_semantics_for_a_midword_apostrophe():
    # `echo don't && git push origin main && echo won't` — bash reads the span
    # between the two apostrophes as ONE single-quoted literal and never runs
    # the push, so a hook that stops seeing the `git push` here is CORRECT, not
    # bypassed. Pinned because it looks like a bypass on first read: "fixing"
    # it (e.g. requiring quotes at token boundaries) would make the git hooks
    # fire on commands the shell would never execute.
    command = "echo don't && git " + "push origin main && echo won't"
    scanned = lib.strip_quoted_spans(command)
    assert "git push" not in scanned


# --------------------------------------------------------------------------- #
# import resolution -- the hooks' one non-stdlib dependency
# --------------------------------------------------------------------------- #


def test_ensure_hooks_dir_importable_is_idempotent_and_adds_the_hooks_dir():
    import sys

    hooks_dir = str(_HOOKS_DIR)
    original = list(sys.path)
    try:
        sys.path[:] = [p for p in sys.path if p != hooks_dir]
        lib.ensure_hooks_dir_importable()
        assert sys.path.count(hooks_dir) == 1
        lib.ensure_hooks_dir_importable()
        assert sys.path.count(hooks_dir) == 1, "second call must not duplicate the entry"
    finally:
        sys.path[:] = original


_GIT_HOOK_FILES = [
    "block-direct-push-to-main.py",
    "warn-branch-base.py",
    "warn-stray-scratch-artifact.py",
    "guard-worktree-isolation.py",
]


@pytest.mark.parametrize("filename", _GIT_HOOK_FILES)
def test_git_hooks_import_the_shared_pattern_instead_of_re_inlining_it(filename):
    # The whole point of consolidating GIT_GLOBAL_OPTS was that a bug fixed in
    # one copy no longer has to be fixed in four. A behavioral test can't catch
    # someone pasting a CORRECT duplicate back in — which silently re-creates
    # the drift this consolidation removed — so assert the structure directly.
    source = (_HOOKS_DIR / filename).read_text(encoding="utf-8")
    assert "from _dispatch_lib import GIT_GLOBAL_OPTS" in source, (
        f"{filename} must import the shared pattern, not define its own"
    )
    assert not re.search(r"^_G\s*=\s*r?['\"]\(\?:", source, re.MULTILINE), (
        f"{filename} appears to re-inline a local _G pattern literal"
    )


@pytest.mark.parametrize("filename", _GIT_HOOK_FILES)
def test_git_hooks_bootstrap_their_own_sys_path_for_standalone_runs(filename):
    # hooks.json invokes these standalone, where the `_dispatch_lib` import
    # resolves only because CPython sets sys.path[0] to the script's dir — a
    # property suppressed by PYTHONSAFEPATH=1 / -I / -P. Each hook inserts its
    # own dir explicitly so an ImportError can never silently disable a guard.
    source = (_HOOKS_DIR / filename).read_text(encoding="utf-8")
    assert "sys.path.insert(0, _HOOKS_DIR)" in source, (
        f"{filename} must bootstrap its own sys.path before importing _dispatch_lib"
    )
