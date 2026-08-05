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
    "ask-destructive-git.py",
    "ask-git-identity.py",
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


# --------------------------------------------------------------------------- #
# default_base_branch -- the harness must not assume `master`
# --------------------------------------------------------------------------- #


class _FakeCompleted:
    def __init__(self, stdout="", returncode=0):
        self.stdout = stdout
        self.returncode = returncode


def _fake_git(responses):
    """Build a subprocess.run stand-in driven by an {args-suffix: result} map."""
    def run(cmd, **kwargs):
        key = " ".join(cmd[1:]) if cmd and cmd[0] == "git" else " ".join(cmd)
        for suffix, result in responses.items():
            if key.endswith(suffix):
                return result
        return _FakeCompleted(returncode=1)
    return run


@pytest.fixture(autouse=True)
def _clear_base_branch_cache():
    lib._BASE_BRANCH_CACHE.clear()
    yield
    lib._BASE_BRANCH_CACHE.clear()


def test_default_base_branch_prefers_origin_head(monkeypatch):
    monkeypatch.setattr(lib.subprocess, "run", _fake_git({
        "symbolic-ref --quiet refs/remotes/origin/HEAD": _FakeCompleted("refs/remotes/origin/trunk\n"),
        # The symref is trusted only once its target verifies — see the
        # dangling-symref test below for why.
        "rev-parse --verify --quiet refs/remotes/origin/trunk": _FakeCompleted("abc123\n"),
    }))
    assert lib.default_base_branch() == "trunk"


def test_default_base_branch_ignores_a_dangling_origin_head(monkeypatch):
    # `refs/remotes/origin/HEAD` is a clone-time cache git never auto-refreshes,
    # and `symbolic-ref` exits 0 even when its target is gone. After an upstream
    # `master`→`main` rename it therefore names a ref that no longer exists —
    # and trusting it unverified returned `master` in a `main`-default repo,
    # after which the caller's `master..HEAD` died with `unknown revision`. That
    # is precisely the failure this resolver exists to prevent.
    monkeypatch.setattr(lib.subprocess, "run", _fake_git({
        "symbolic-ref --quiet refs/remotes/origin/HEAD": _FakeCompleted("refs/remotes/origin/master\n"),
        # No stub for `rev-parse --verify --quiet refs/remotes/origin/master` →
        # rc 1, i.e. the symref dangles. `main` is what actually exists.
        "rev-parse --verify --quiet refs/heads/main": _FakeCompleted("abc123\n"),
    }))
    assert lib.default_base_branch() == "main"


def test_default_base_branch_handles_a_slash_containing_default_branch(monkeypatch):
    # `rsplit("/", 1)[-1]` would truncate `release/main` to `main` — and
    # `rev-parse --verify` on the FULL target still succeeds regardless of
    # what candidate name was derived from it, so the truncated name passed
    # every check here and resolved to a branch that doesn't exist.
    monkeypatch.setattr(lib.subprocess, "run", _fake_git({
        "symbolic-ref --quiet refs/remotes/origin/HEAD": _FakeCompleted("refs/remotes/origin/release/main\n"),
        "rev-parse --verify --quiet refs/remotes/origin/release/main": _FakeCompleted("abc123\n"),
    }))
    assert lib.default_base_branch() == "release/main"


def test_default_base_branch_rejects_a_self_referential_origin_head(monkeypatch):
    # A last segment of `HEAD` is never a branch name.
    monkeypatch.setattr(lib.subprocess, "run", _fake_git({
        "symbolic-ref --quiet refs/remotes/origin/HEAD": _FakeCompleted("refs/remotes/origin/HEAD\n"),
        "rev-parse --verify --quiet refs/heads/main": _FakeCompleted("abc123\n"),
    }))
    assert lib.default_base_branch() == "main"


def test_default_base_branch_falls_back_to_an_existing_main(monkeypatch):
    # The live bug this fixes: in a `main`-default repo there is NO `master`
    # ref, so a hardcoded `master..HEAD` range fails with `unknown revision`
    # rather than merely returning a wrong answer.
    monkeypatch.setattr(lib.subprocess, "run", _fake_git({
        "rev-parse --verify --quiet refs/heads/main": _FakeCompleted("abc123\n"),
    }))
    assert lib.default_base_branch() == "main"


def test_default_base_branch_still_finds_master_when_that_is_the_convention(monkeypatch):
    monkeypatch.setattr(lib.subprocess, "run", _fake_git({
        "rev-parse --verify --quiet refs/remotes/origin/master": _FakeCompleted("abc123\n"),
    }))
    assert lib.default_base_branch() == "master"


def test_default_base_branch_falls_back_to_master_when_git_says_nothing(monkeypatch, capsys):
    # No remote, no conventional branch — preserve the harness's historical
    # assumption rather than inventing one, but SAY SO: this arm cannot tell
    # "this repo genuinely uses master" from "git is unusable and I guessed",
    # and every range built on the result then fails as `unknown revision`.
    monkeypatch.setattr(lib.subprocess, "run", _fake_git({}))
    assert lib.default_base_branch() == "master"
    assert "warn" in capsys.readouterr().err.lower()


def test_default_base_branch_survives_git_being_unavailable(monkeypatch, capsys):
    def _raise(*args, **kwargs):
        raise OSError("git not found")

    monkeypatch.setattr(lib.subprocess, "run", _raise)
    assert lib.default_base_branch() == "master"
    assert "warn" in capsys.readouterr().err.lower()


def test_a_successful_resolution_is_silent(monkeypatch, capsys):
    # The note belongs to the guess, not to every call — a warn on the happy
    # path would train people to ignore it.
    monkeypatch.setattr(lib.subprocess, "run", _fake_git({
        "rev-parse --verify --quiet refs/heads/main": _FakeCompleted("abc123\n"),
    }))
    assert lib.default_base_branch() == "main"
    assert capsys.readouterr().err == ""


def test_default_base_branch_caches_per_cwd(monkeypatch):
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        return _FakeCompleted("refs/remotes/origin/main\n")

    monkeypatch.setattr(lib.subprocess, "run", run)
    assert lib.default_base_branch("/repo") == "main"
    first = len(calls)
    assert lib.default_base_branch("/repo") == "main"
    assert len(calls) == first, "second call for the same cwd must be cached"


# --------------------------------------------------------------------------- #
# Deadline -- keeps a dispatcher inside the hooks.json handler timeout
# --------------------------------------------------------------------------- #


def test_deadline_with_a_spent_budget_reports_expired():
    assert lib.Deadline(budget_seconds=0.0).expired() is True


def test_deadline_with_budget_left_is_not_expired_and_reports_remaining():
    d = lib.Deadline(budget_seconds=30.0)
    assert d.expired() is False
    assert 0 < d.remaining() <= 30.0


def test_deadline_defaults_to_less_than_the_handler_timeout():
    # The default must leave headroom for interpreter startup before the first
    # hook and the dispatcher's own compose/print after the last — neither of
    # which the Deadline can observe. A default equal to the handler timeout
    # would guarantee an overshoot on a fully-spent budget.
    assert lib.Deadline().remaining() < lib.HANDLER_TIMEOUT_SECONDS


# --------------------------------------------------------------------------- #
# Output caps -- Claude Code truncates hook output past 10,000 chars, writing
# the payload to a file. For a warn hook that is a silent downgrade, so the
# dispatchers clamp deliberately and say that they did.
# --------------------------------------------------------------------------- #


def test_clamp_output_leaves_short_text_untouched():
    assert lib.clamp_output("short", 100) == "short"


def test_clamp_output_result_never_exceeds_the_limit():
    # The truncation notice is spent FROM the budget, not added on top of it —
    # otherwise clamping to the cap would itself breach the cap.
    out = lib.clamp_output("x" * 5000, 500)
    assert len(out) <= 500


def test_clamp_output_says_it_truncated():
    out = lib.clamp_output("x" * 5000, 500)
    assert "truncated" in out
    assert "5000" in out, "the notice should name the original size"


def test_compose_output_keeps_the_block_reason_whole():
    # The block reason arrives LAST, so a naive tail-truncation drops exactly
    # the part Claude has to act on. It is budgeted first instead.
    reason = "blocked: do not do that. (hook: some-hook.py)"
    out = lib.compose_output(["w" * 9000], must_keep=reason, limit=1000)
    assert out.endswith(reason)
    assert len(out) <= 1000
    assert "truncated" in out, "the sacrificed preamble should say it was cut"


def test_compose_output_drops_advisory_text_when_the_reason_fills_the_budget():
    reason = "b" * 400
    out = lib.compose_output(["advisory noise"], must_keep=reason, limit=400)
    assert "advisory noise" not in out
    assert len(out) <= 400


def test_compose_output_without_a_block_reason_still_caps():
    out = lib.compose_output(["w" * 9000], limit=800)
    assert len(out) <= 800


def test_compose_output_joins_sections_and_skips_empties():
    assert lib.compose_output(["a", "", "b"]) == "a\nb"


def test_compose_output_with_nothing_to_say_is_empty():
    # Callers gate their print on a truthy return, so this must not become a
    # bare newline — that would emit an empty warning block on every clean run.
    assert lib.compose_output([]) == ""


@pytest.mark.parametrize("filename", _GIT_HOOK_FILES)
def test_git_hooks_bootstrap_their_own_sys_path_for_standalone_runs(filename):
    # These are loaded two ways — in-process by a dispatcher, and directly by
    # pytest — and hooks.json invokes a few of them standalone. In a standalone
    # run the `_dispatch_lib` import resolves only because CPython sets
    # sys.path[0] to the script's dir, a property suppressed by
    # PYTHONSAFEPATH=1 / -I / -P; in the other two neither mechanism puts the
    # hooks dir first at all. Each hook therefore inserts its own dir explicitly,
    # so an ImportError can never silently disable a guard.
    source = (_HOOKS_DIR / filename).read_text(encoding="utf-8")
    assert "sys.path.insert(0, _HOOKS_DIR)" in source, (
        f"{filename} must bootstrap its own sys.path before importing _dispatch_lib"
    )
