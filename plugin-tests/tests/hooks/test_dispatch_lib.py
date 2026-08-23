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
import json
import re
from pathlib import Path
from types import ModuleType

import pytest

_HOOKS_DIR = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "hooks"
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
    result = lib.run_hook_file("warn-stray-scratch-artifact.py", '{"tool_input": {"command": "ls"}}')
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
    "warn-stray-scratch-artifact.py",
    "ask-destructive-git.py",
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


# The exact `for-each-ref` invocation `default_base_branch` uses to probe all
# four candidate refs in ONE spawn (it previously issued up to four `rev-parse`
# calls; that cost landed inside an enforcing hook's handler budget). Mocks key
# on it so a change to the call shape shows up here rather than silently sending
# every test down the fallback arm.
_CANDIDATE_PROBE = (
    "for-each-ref --format=%(refname) refs/heads/main refs/remotes/origin/main "
    "refs/heads/master refs/remotes/origin/master"
)


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
        _CANDIDATE_PROBE: _FakeCompleted("refs/heads/main\n"),
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
        _CANDIDATE_PROBE: _FakeCompleted("refs/heads/main\n"),
    }))
    assert lib.default_base_branch() == "main"


def test_default_base_branch_falls_back_to_an_existing_main(monkeypatch):
    # The live bug this fixes: in a `main`-default repo there is NO `master`
    # ref, so a hardcoded `master..HEAD` range fails with `unknown revision`
    # rather than merely returning a wrong answer.
    monkeypatch.setattr(lib.subprocess, "run", _fake_git({
        _CANDIDATE_PROBE: _FakeCompleted("refs/heads/main\n"),
    }))
    assert lib.default_base_branch() == "main"


def test_default_base_branch_still_finds_master_when_that_is_the_convention(monkeypatch):
    monkeypatch.setattr(lib.subprocess, "run", _fake_git({
        _CANDIDATE_PROBE: _FakeCompleted("refs/remotes/origin/master\n"),
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
        _CANDIDATE_PROBE: _FakeCompleted("refs/heads/main\n"),
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


def test_fit_json_payload_measures_the_serialized_envelope_not_the_inner_text():
    """The whole reason this exists instead of a bare `clamp_output` call.

    Both dispatchers print JSON, so the cap applies to the SERIALIZED payload —
    envelope keys plus escaping — and clamping only the inner string left the
    printed total over the cap in both of them. The function ran on every
    non-trivial dispatcher call, and `test_dispatch.py` asserts on the JSON they
    print — but nothing measured the SERIALIZED size, so a rewrite that
    pre-clamped `text` and skipped the re-measure loop passed the suite while
    re-opening that.

    Quote characters are the honest expansion to test with: each escapes to two
    chars, so `clamp_output(text, limit)` alone leaves `text` comfortably under
    the limit while the JSON around it is over — the exact shape of the bug.
    """
    limit = 2000
    text = '"' * 1200

    naive = lib.clamp_output(text, limit)
    assert len(naive) <= limit, "the pre-clamp does bound the STRING..."
    assert len(json.dumps({"additionalContext": naive})) > limit, (
        "...and the payload around it is still over the cap, which is why "
        "clamping the inner string is not enough"
    )

    out = lib.fit_json_payload(lambda t: {"additionalContext": t}, text, limit=limit)
    assert len(out) <= limit, (
        "the size is measured on the JSON, not on the string that goes into it"
    )
    assert json.loads(out)["additionalContext"], (
        "and it must still carry text — emptying the payload is not a fit"
    )


@pytest.mark.parametrize(
    "char,name",
    [
        ("a", "ascii (1:1)"),
        ('"', "quote (2:1)"),
        ("—", "em dash (6:1)"),
        ("日", "CJK (6:1)"),
        ("\U0001F600", "emoji (12:1, surrogate pair)"),
    ],
)
def test_fit_json_payload_keeps_text_at_every_expansion_factor(char, name):
    """The size guarantee held at one sampled ratio; the CONTENT guarantee did
    not, and the previous test's `'"' * 1200` fixture sat at the one ratio where
    it happened to survive.

    `json.dumps` defaults to `ensure_ascii=True`, so a non-ASCII character costs
    six serialized chars and an astral one costs twelve. The old subtractive
    re-clamp took `len(text) - overflow` with the two operands in DIFFERENT
    UNITS, over-correcting by the whole expansion factor. Measured before the
    fix, at limit=10,000 over a 20,000-char message:

        ascii 9968 | 1% em-dash 8975 | 10% em-dash 0 | CJK 0 | quotes 0

    A zero there is a hook that ran, produced output, and delivered an empty
    string — and `clamp_output`'s `keep == 0` branch drops its own truncation
    notice, so nothing said so. This repo's house style alone (em dashes, `…`,
    `→`) reaches that regime.
    """
    limit = 10_000
    text = char * 20_000
    out = lib.fit_json_payload(lambda t: {"additionalContext": t}, text, limit=limit)

    assert len(out) <= limit, f"{name}: the size guarantee is absolute"
    kept = json.loads(out)["additionalContext"]
    assert kept, f"{name}: silently delivering nothing is the failure being fixed"

    # The floor is on the SERIALIZED payload, not on the character count. A
    # 12:1 astral character legitimately yields ~830 characters of text in a
    # 10,000-char budget, so a flat character floor would demand the impossible
    # at high ratios and prove nothing at low ones. What must hold at EVERY
    # ratio is that the budget is actually spent — an over-correcting re-clamp
    # shows up here as a payload far below the cap it was allowed to fill.
    assert len(out) >= limit * 0.5, (
        f"{name}: used only {len(out)} of a {limit}-char budget; the re-clamp "
        "is over-correcting again, which is how this reached zero before"
    )


@pytest.mark.parametrize("char,name", [("a", "ascii"), ("—", "em dash")])
def test_fit_json_payload_budgets_around_a_fixed_component(char, name):
    """The real dispatcher shape: `build` closes over a `reason` that does NOT
    shrink, so the room left for `text` is `limit` minus that fixed part.

    This is the case that separates a correct expansion ratio from a
    tautological one. Dividing the whole payload by the text it contains cancels
    to `len(out)/len(text)`, which makes `fixed` zero — the arithmetic then
    hands `text` the entire budget and the fixed part pushes the total over.
    Measured with a 5,000-char reason: 10,266 characters against a 10,000 cap
    for ascii, 10,190 for em dashes, versus exactly 10,000 and 9,183 when the
    fixed part is subtracted.

    A test with no fixed component cannot see this — both forms agree there,
    which is why the first version of these tests missed it.
    """
    limit = 10_000
    reason = "R" * 5_000

    def build(t):
        nested = {"hookEventName": "PreToolUse", "permissionDecisionReason": reason}
        if t:
            nested["additionalContext"] = t
        return {"hookSpecificOutput": nested}

    out = lib.fit_json_payload(build, char * 20_000, limit=limit)

    assert len(out) <= limit, (
        f"{name}: {len(out)} chars against a {limit} cap — the fixed component "
        "is not being subtracted before the text is sized"
    )
    kept = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert kept, f"{name}: room remained for text and none was delivered"
    assert json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"] == reason, (
        "the fixed component must survive intact — it is the part that cannot "
        "be shrunk, not the part to sacrifice"
    )


def test_fit_json_payload_says_so_when_the_overflow_is_not_the_hook_text(capsys):
    """It can only shrink `text`. Both dispatchers close over `reason`, which
    `compose_output` caps at exactly `limit` — so the envelope always pushes the
    payload over and no choice of `text` fits.

    Measured: a 9,990-char reason prints 10,077 characters. Claude Code then
    writes the payload to a file and shows a preview, downgrading an `ask` on
    the one channel that cannot be ignored. This cannot be fixed here (the
    caller owns the fixed part), so the requirement is that it is ANNOUNCED
    rather than returned quietly.
    """
    reason = "R" * 9_990

    def build(t):
        nested = {"hookEventName": "PreToolUse", "permissionDecisionReason": reason}
        if t:
            nested["additionalContext"] = t
        return {"hookSpecificOutput": nested}

    capsys.readouterr()
    out = lib.fit_json_payload(build, "advisory text " * 20, limit=10_000)

    assert len(out) > 10_000, "this fixture exists to reach the unfittable case"
    err = capsys.readouterr().err
    assert str(len(out)) in err, "the diagnostic should name the actual size"
    assert "cannot be shrunk further" in err


def test_fit_json_payload_stays_silent_when_it_does_fit(capsys):
    """Non-vacuity partner: a diagnostic on every ordinary payload is noise that
    trains the reader to ignore the one that matters."""
    capsys.readouterr()
    lib.fit_json_payload(lambda t: {"additionalContext": t}, "short", limit=10_000)
    assert capsys.readouterr().err == ""


def test_fit_json_payload_leaves_a_payload_that_already_fits_alone():
    """Non-vacuity partner: a function that clamped unconditionally would pass
    the test above and silently truncate every ordinary hook message."""
    out = lib.fit_json_payload(lambda t: {"additionalContext": t}, "short", limit=500)
    assert json.loads(out) == {"additionalContext": "short"}


def test_every_environment_escape_hatch_is_neutralised_by_conftest():
    """`conftest.py` clears the guard-disabling env vars for the whole scope, so
    a "must stay silent" assertion cannot pass vacuously. That list is written
    by hand, and nothing about a clean local environment reveals it is wrong —
    mutating an entry to a bogus name left the whole scope green, because the
    variable is unset on this machine anyway. The list only matters on a machine
    where a hatch IS exported.

    So pin the list against its source instead: every `os.environ.get("ALLOW_…")`
    in `hooks/*.py` must be neutralised. That kills the rename AND catches the
    real future failure — a new guard shipping a new hatch nobody adds here.
    Measured with `ALLOW_DESTRUCTIVE_GIT=1` exported before the fixture existed:
    64 tests failed and the one non-vacuity guarantee passed vacuously.
    """
    # Loaded by PATH, not as `import conftest`. The dev tree is one pytest scope
    # holding five sibling `conftest.py` files, so a bare `import conftest`
    # resolves to whichever one reached `sys.modules` first — which is not
    # necessarily this directory's, and the wrong one has no `_ESCAPE_HATCHES`.
    spec = importlib.util.spec_from_file_location(
        "_ut_hooks_conftest", Path(__file__).resolve().parent / "conftest.py"
    )
    conftest = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(conftest)

    hatches = set()
    for path in _HOOKS_DIR.glob("*.py"):
        src = path.read_text(encoding="utf-8")
        hatches |= set(re.findall(r'os\.environ\.get\(\s*"(ALLOW_[A-Z_]+)"', src))

    assert hatches, "found no escape hatches at all — the pattern has drifted"
    missing = hatches - set(conftest._ESCAPE_HATCHES)
    assert not missing, (
        f"these guard-disabling env vars are read in hooks/ but not cleared by "
        f"conftest.py, so every 'must stay silent' test in this scope passes "
        f"vacuously when one is exported: {sorted(missing)}"
    )
    stale = set(conftest._ESCAPE_HATCHES) - hatches
    assert not stale, (
        f"conftest.py clears env vars no hook reads any more: {sorted(stale)}"
    )


def test_hook_output_char_limit_is_the_documented_cap():
    """The constant is the one number the whole clamp layer is calibrated to,
    and every production caller takes it as a DEFAULT argument — so a change
    here re-tunes `clamp_output`, `compose_output` and `fit_json_payload`
    together.

    Not a change-detector: measured, `10_000 -> 300` breaks eight other tests,
    but `10_000 -> 12_000` is invisible to every one of them. A RAISED cap is
    precisely the silent downgrade the comment at the constant describes — the
    payload starts going to a file Claude may never open — so the only guard
    against a modest re-tune is naming the value here.

    10,000 is Claude Code's cap, not this plugin's choice; it is an external
    fact with no local source of truth, so re-derive it from current Claude Code
    docs before changing this line rather than treating the number as ours.
    """
    assert lib.HOOK_OUTPUT_CHAR_LIMIT == 10_000


def test_deadline_has_room_weighs_the_cost_rather_than_just_asking_if_time_is_up():
    """The REAL `Deadline.has_room`, which no test ever ASSERTED anything about.

    It did run — `test_dispatch.py` drives both dispatchers through `main()` as
    subprocesses, and each builds a real `Deadline` and calls `has_room` for
    every advisory hook. But the only `has_room` a reader could find in
    `hooks/tests/` was `_ExpiredDeadline`'s hardcoded `False`, and nothing
    anywhere pinned what the real one returns.

    Revert the body to `return not self.expired()` — the exact pre-fix bug it
    was written to replace — and the whole suite passes. This is the case that
    separates them: budget left, but less than the hook's worst case. The
    reverted version starts a hook it cannot finish and lets the handler
    timeout cut it off, taking every later hook with it.
    """
    fresh = lib.Deadline(budget_seconds=5.0)
    assert not fresh.expired(), "the discriminating case has budget remaining"
    assert not fresh.has_room(60.0), (
        "a hook whose worst case exceeds the remaining budget must be skipped, "
        "not started and cut off by the handler timeout"
    )
    assert fresh.has_room(1.0), "non-vacuity: a hook that does fit is admitted"


def test_deadline_has_room_refuses_even_a_zero_cost_hook_once_overspent():
    """Pins what the `>=` actually does, against a docstring that used to
    promise otherwise.

    Both dispatchers do `HOOK_WORST_CASE_SECONDS.get(filename, 0.0)`, so an
    UNCOSTED hook arrives here as zero-cost — absence of data, not proof it is
    free. Once `remaining()` is negative the handler is already late and the
    refusal is right; recorded so a reader trusting the old wording does not
    "restore" admission and re-open an overrun.
    """
    spent = lib.Deadline(budget_seconds=-1.0)
    assert spent.expired()
    assert not spent.has_room(0.0)


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


# --------------------------------------------------------------------------- #
# GIT_CMD -- the executable token
#
# Added after a consuming repo found that `\bgit\s+` cannot match `git.exe`
# (`\s` does not match `.`), so EVERY git guard in the plugin silently allowed
# the Windows extension spellings. Measured before the fix: `git push origin
# main` blocked, `git.exe push origin main` allowed. Reachable by ordinary use --
# PowerShell tab-completion emits `git.exe`.
#
# The whole class was invisible because no test anywhere varied the executable
# token; every case in this file and its siblings hardcoded a bare `git`.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "exe",
    [
        "git", "git.exe", "git.cmd", "git.EXE", "git.Cmd",
        # The command NAME, not just the extension. These RUN on a
        # case-insensitive filesystem, so a guard that misses them is bypassed
        # by typing, not by evasion.
        "GIT", "GIT.EXE", "Git", "Git.Exe", "gIt.cMd",
    ],
)
def test_git_cmd_matches_every_runnable_spelling(exe):
    """Every spelling a case-insensitive shell will actually execute."""
    assert re.search(lib.GIT_CMD + r"\s", f"{exe} push origin main")


@pytest.mark.parametrize(
    "text",
    [
        "gitfoo push origin main",   # \b must not let a longer name through
        "mygit push origin main",
        "git.py push origin main",   # not an executable extension
        "digit push",
        "DIGIT push",                # the case-folded name must not relax \b
    ],
)
def test_git_cmd_does_not_over_match(text):
    """A guard that fires on `gitfoo` is worse than one that misses `git.exe`.

    `re.search`, NOT `re.match`, because every consumer of this constant uses
    `.search` — the guards scan a whole command line, not a string anchored at
    position 0. Under `re.match` the two cases that exist to prove the leading
    `\\b` (`mygit`, `digit`) passed VACUOUSLY: they are rejected by the anchor
    before `\\b` is ever consulted, so deleting `\\b` from GIT_CMD left this
    test green. Measured on a `\\b`-stripped pattern: `re.match` rejected all
    four, `re.search` matched `mygit push origin main` and `digit push`.
    """
    assert not re.search(lib.GIT_CMD + r"\s", text)


def test_git_cmd_over_blocks_only_where_the_subcommand_is_an_english_word():
    """The measured COST of case-folding the command name, pinned as a trade.

    A terminal uppercase `GIT` path segment followed by the matched subcommand
    now matches. That is only reachable where the subcommand is also an
    ordinary word, so it lands on `commit`, not on `push`. Pinned in both
    directions so a future reader sees the real shape of the trade rather than
    a claim that widening was free.
    """
    assert re.search(lib.GIT_CMD + r"\s+commit\b", "cd /srv/GIT commit")
    # `push` gains the SAME exposure — the earlier comment here claimed it did
    # not, and the assertion below could not have caught the error because its
    # subject contained no `push` at all: it passed for every possible value of
    # GIT_CMD, including `.*`. Measured against the real guard,
    # `ls /d/GIT push --force origin main` does fire. The trade is that an
    # over-blocking enforcing guard announces itself and is trivially worked
    # around, while the `GIT push` bypass it closes is silent and total.
    assert re.search(lib.GIT_CMD + r"\s+push\b", "ls /d/GIT push --force origin main")
    assert not re.search(lib.GIT_CMD + r"\s+push\b", "cd /srv/GIT && ls")


def test_every_git_guard_uses_the_shared_constant():
    """The point of the constant is that the fix lands once. A hook that
    re-anchors on a bare `\bgit` has opted out of it, which is how six copies
    drifted apart the first time.

    This is a LINT, and its limits are worth stating plainly rather than
    overselling it as a guarantee. It previously matched only the
    DOUBLE-QUOTED literal `r"\\bgit`, so re-introducing the identical bypassed
    regex with single quotes evaded it entirely and the whole suite stayed
    green with the bug live. Both quote styles are matched now, and the
    positive half — that the hook actually imports `GIT_CMD` — is asserted
    too, since a hook can equally opt out by spelling `re.compile("git...",
    re.I)` and never mentioning the literal at all.

    What it still cannot see: a hook that imports the constant and then
    composes it wrongly. Behavioural coverage for that lives in each hook's
    own test file, and `test_every_git_global_opts_consumer_strips_quoted_spans`
    below closes the one composition mistake that actually occurred.
    """
    reanchored, unimported = [], []
    for f in _HOOKS_DIR.glob("*.py"):
        # NOTE: this skip means the two dispatchers are never scanned. That is
        # deliberate (they route, they do not match git commands) but it is a
        # hole if one ever grows a matcher.
        if f.name.startswith(("_", "dispatch-")):
            continue
        src = f.read_text(encoding="utf-8")
        body = "\n".join(
            ln for ln in src.splitlines() if not ln.lstrip().startswith("#")
        )
        if re.search(r"""r['"]\\bgit""", body):
            reanchored.append(f.name)
        elif f.name in _GIT_HOOK_FILES and "GIT_CMD" not in body:
            unimported.append(f.name)
    assert not reanchored, (
        f"re-anchor on the bare pattern instead of GIT_CMD: {reanchored}"
    )
    assert not unimported, (
        f"a git guard that never references GIT_CMD has opted out silently: {unimported}"
    )


@pytest.mark.parametrize("filename", _GIT_HOOK_FILES)
def test_every_git_global_opts_consumer_strips_quoted_spans(filename):
    """`GIT_GLOBAL_OPTS`' precondition, which lived in prose only.

    Its value-consuming alternatives use `\\S+`, which cannot span an
    un-stripped internal space, so a command MUST pass through
    `strip_quoted_spans` before matching. The docstring says so and every
    consumer in `_GIT_HOOK_FILES` honours it; nothing checked that they do.

    Not hypothetical: a consuming repo added a further consumer that imported
    both `GIT_CMD` and `GIT_GLOBAL_OPTS` and skipped the pre-pass, in an
    ENFORCING hook. `git -C "/path with space" commit` then simply did not
    match — a guard that matches nothing allows everything — and it survived a
    full green suite, because the import test above sees exactly the right
    imports. Measured there: `old=False, new=False, new+strip=True`.

    Textual, and deliberately so: importing the helper is not proof of calling
    it before the match. A stricter AST version could assert the call wraps the
    match argument. This closes the failure that actually occurred — adopting
    the constant and never reaching for the helper at all — and puts the
    precondition in front of whoever adds the next consumer.

    Asserting the IMPORT of the genuine symbol rather than a bare substring,
    which a mutation caught: aliasing a different function to the same local
    name (`import fit_json_payload as _strip_quoted_spans`) leaves the string
    `strip_quoted_spans` in the file at the call site, so a substring check
    stayed green while the pre-pass was gone. Every consumer imports it from
    `_dispatch_lib` by its real name, so the import form is the stable thing to
    pin. (`_GIT_HOOK_FILES` is the single place that list is maintained — by
    hand, so it is not self-updating either. Name the files there rather than
    restating a count in prose; a count was already wrong once.)
    """
    source = (_HOOKS_DIR / filename).read_text(encoding="utf-8")
    if "GIT_GLOBAL_OPTS" not in source:
        pytest.skip(f"{filename} does not consume GIT_GLOBAL_OPTS")
    assert re.search(
        r"^from _dispatch_lib import [^\n]*\bstrip_quoted_spans\b", source, re.MULTILINE
    ), (
        f"{filename} consumes GIT_GLOBAL_OPTS but does not import "
        "strip_quoted_spans from _dispatch_lib; its `\\S+` alternatives cannot "
        "match a quoted global-option value, so every "
        "`git -C \"/path with space\" ...` silently bypasses this guard"
    )
    assert "strip_quoted_spans(" in source, (
        f"{filename} imports strip_quoted_spans but never calls it"
    )
