"""Tests for `block-cd-in-bash.py`.

This guard shipped untested — the only coverage was incidental, via
`test_dispatch.py` using it as a convenient hook to break. That gap is how the
shadowing hole survived: `cd () { ...` (with a space) was blocked by the
directive matcher as a side effect, `cd() { ...` (without one) was not, and
nothing asserted either way.

Two behaviours are pinned here, and they are separate rules:
  - the directive rule — a real `cd` that would move the working directory;
  - the shadowing rule — a redefinition of `cd`, blocked because it disables
    the guard rather than because it changes any directory.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_HOOK = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "hooks" / "block-cd-in-bash.py"


def _load():
    spec = importlib.util.spec_from_file_location("block_cd_in_bash", _HOOK)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


mod = _load()


# ---------------------------------------------------------------- directives


@pytest.mark.parametrize(
    "cmd",
    [
        "cd /tmp",
        "cd subdir && pytest",
        "ls; cd /tmp",
        "make build | tee log\ncd dist",
        "cd () { :; }",  # space form — caught by the directive matcher too
    ],
)
def test_a_real_cd_is_a_directive(cmd):
    assert mod.cd_outside_quotes(cmd) is True


@pytest.mark.parametrize(
    "cmd",
    [
        'git commit -m "cd into the dir first"',
        "echo 'cd /tmp'",
        "grep -rn 'cd ' src/",
        "git -C /repo status",  # the sanctioned alternative
        "echo cdrom",  # substring, not the command
    ],
)
def test_quoted_or_unrelated_cd_is_allowed(cmd):
    assert mod.cd_outside_quotes(cmd) is False


# requirement: guard-hooks / A cd inside a shell command is blocked
@pytest.mark.parametrize(
    "cmd",
    [
        "{ cd /tmp; }",
        "builtin cd /tmp",
        "command cd /tmp",
        "if true; then cd /tmp; fi",
        "if cd /tmp; then ls; fi",
        "for d in a b; do cd $d; done",
        "\\cd /tmp",
        "! cd /tmp",
        "time cd /tmp",
    ],
)
def test_every_persisting_directory_change_is_a_directive(cmd):
    """Each of these changes the directory for later calls and used to pass the matcher."""
    assert mod.cd_outside_quotes(cmd) is True, cmd


@pytest.mark.parametrize(
    "cmd",
    [
        "(cd /tmp && make)",  # a subshell's change ends with it
        "echo $(cd /tmp && pwd)",
        "Push-Location C:/wt; python3 x.py; Pop-Location",  # CLAUDE.md's sanctioned form
        "find . -name x -exec rm {} +",
        "echo {cd x}",  # a brace group needs the space after `{`
        "git log --format=%h{cd x}",
        "echo to-do cd later",  # a keyword that is not at a command position
        "git commit -F - <<'EOF'\ndocs: explain what happens if cd fails\nEOF",
        "cat > notes.md <<'EOF'\nBuild it, then cd build and run the tests.\nEOF",
        "git log --format='%h {cd x}'",
    ],
)
def test_a_change_that_does_not_persist_is_allowed(cmd):
    """Non-vacuity partner: subshells, braces that are not a group, and look-alike words."""
    assert mod.cd_outside_quotes(cmd) is False, cmd


@pytest.mark.parametrize(
    "cmd",
    [
        "git commit -m 'stage first; cd into dist'",  # single
        'git commit -m "stage first; cd into dist"',  # double
        "echo `true; cd /tmp`x",  # backtick
    ],
)
def test_a_separator_inside_a_quoted_span_does_not_arm_the_matcher(cmd):
    """The quote-stripper's real job.

    Every other quoting case in this file has the `cd` sitting after a quote
    character, which is not a separator — so the matcher would decline them even
    with the stripper removed, and mutating the stripper survived. These three
    put a `;` INSIDE the quotes, which is the only shape where blanking the span
    is load-bearing: one per quote style, since each is a separate `re.sub`.
    """
    assert mod.cd_outside_quotes(cmd) is False


# ---------------------------------------------------------------- shadowing


@pytest.mark.parametrize(
    "cmd",
    [
        'cd() { echo "blocked"; };  cd /tmp && ls',  # the exact evasion that happened
        "cd() { :; }",
        "cd ()  {  :; }",
        "function cd { :; }",
        "function cd() { :; }",
        "alias cd=true",
        "alias cd=/bin/true; cd /tmp",
        "ls; cd() { :; }",  # after a separator
    ],
)
def test_redefining_cd_is_blocked(cmd):
    assert mod.shadows_cd(cmd) is True


@pytest.mark.parametrize(
    "cmd",
    [
        "echo 'cd() { :; }'",  # quoted prose, not a definition
        'git commit -m "document cd() { :; } as an anti-pattern"',
        "cdate() { :; }",  # different command, not a shadow of cd
        "mycd() { :; }",
        "alias cdp=pushd",  # different alias name
        "grep -n 'function cd' hooks/",
        "cd /tmp",  # a plain directive is not a shadow
    ],
)
def test_non_shadowing_commands_are_not_flagged(cmd):
    assert mod.shadows_cd(cmd) is False


def test_the_no_space_form_was_the_hole():
    """Regression pin: the space form was already caught, the no-space form
    was not, and only the shadow check covers it."""
    assert mod.cd_outside_quotes("cd() { :; }") is False
    assert mod.shadows_cd("cd() { :; }") is True


def test_shadowing_is_blocked_even_with_no_cd_afterwards():
    """The redefinition is the offense — it does not need a `cd` to follow it."""
    cmd = "cd() { :; }"
    assert mod.cd_outside_quotes(cmd) is False
    assert mod.shadows_cd(cmd) is True


# ---------------------------------------------------------------- exit codes


def _run(monkeypatch, capsys, command):
    import io
    import json as _json

    monkeypatch.setattr(
        "sys.stdin", io.StringIO(_json.dumps({"tool_input": {"command": command}}))
    )
    code = mod.main()
    return code, capsys.readouterr().err


# requirement: guard-hooks / A cd inside a shell command is blocked
def test_main_blocks_a_directive(monkeypatch, capsys):
    code, err = _run(monkeypatch, capsys, "cd /tmp && ls")
    assert code == 2
    assert "block-cd-in-bash.py" in err


def test_main_blocks_a_shadow_with_its_own_message(monkeypatch, capsys):
    code, err = _run(monkeypatch, capsys, 'cd() { echo "blocked"; }; cd /tmp')
    assert code == 2
    assert "redefines `cd`" in err
    assert "do not route around it" in err


def test_main_allows_an_ordinary_command(monkeypatch, capsys):
    code, err = _run(monkeypatch, capsys, "git -C /repo status")
    assert code == 0
    assert err == ""


def test_malformed_payload_does_not_block(monkeypatch, capsys):
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    assert mod.main() == 0


# ---------------------------------------------------------------- linear time


def test_whitespace_runs_keep_their_verdicts():
    # A run of whitespace is shrunk before matching; a run holding a newline is
    # still a separator, and any run still separates the words of a directive.
    for cmd in (
        "ls \n \n \n cd x",
        "ls   \t  ;   \t  cd x",
        "{ \n\t \n cd x; }",
        "if x; then \n \t cd x",
        "builtin \n\n  cd   x",
        "\n\n\n   cd x",
        "alias \t\t cd=true",
        "ls\n \n function \n cd \n ( \n ) \n {",
        "ls\r\n\x0b\x0c cd x",
    ):
        assert mod.cd_outside_quotes(cmd) or mod.shadows_cd(cmd), repr(cmd)
    for cmd in (
        "echo \n \n cd",
        "echo   cd   x",
        "ls \n \n pushd x",
        "cd\n \n",
    ):
        assert not mod.cd_outside_quotes(cmd) and not mod.shadows_cd(cmd), repr(cmd)


def test_keyword_and_prefix_chains_keep_their_verdicts():
    for cmd in (
        "then\ndo\n!\ncommand\ntime\ncd x",
        "ls;\nif\n!\nbuiltin cd x",
        "{ then\ndo cd x; }",
        "a &&\n\\cd x",
        "!\nthen\ncd x",           # a keyword after a prefix is not part of the chain, but a later start is
        "x\n!\n!\n!\ncd x",
    ):
        assert mod.cd_outside_quotes(cmd), repr(cmd)
    for cmd in (
        "builtin then cd x",       # a keyword after a prefix: not a command position
        "!\nthen\nfoo cd x",
        "then\ndo\n!\ncd",         # no argument
        "thenx cd y",
        "x\n!\n!\n!\nls cd x",
    ):
        assert not mod.cd_outside_quotes(cmd), repr(cmd)


def test_chains_split_by_newlines_are_fast_and_keep_their_verdict():
    import time

    # Main (Windows, Git Bash): 19 s for 20000 `\n!`, 38 s for 20000 `\nthen`.
    for unit in ("\n!", "\nthen", "\ndo", "\ntime", "\nbuiltin", "\nthen\n!", "; !", "\n{", "\n if"):
        for tail, blocked in ((" cd x", True), (" ls", False)):
            command = unit * 20000 + tail
            started = time.perf_counter()
            found = mod.cd_outside_quotes(command)
            assert time.perf_counter() - started < 2.0, repr(unit)
            assert found is blocked, (repr(unit), tail)


def test_a_wall_of_newlines_is_fast_for_the_directive_walk():
    import time

    # Without the whitespace shrink the walk skips the rest of the run from every
    # newline in it: 13 s for this input, 0.05 s with it.
    started = time.perf_counter()
    assert mod.cd_outside_quotes("\n" * 100000 + "x") is False
    assert time.perf_counter() - started < 5.0


def test_long_whitespace_runs_are_fast_and_keep_their_verdict(monkeypatch, capsys):
    import time

    # The hook timeout is 15 s and a killed hook lets the command through, and
    # this hook runs first in the dispatcher. Measured on main (Windows, Git
    # Bash): 24 s for 12000 repeats of " \n", more than 40 s for 200000.
    # 12000 repeats is already 24 s on main (more than that for the directive walk
    # without the shrink), so a broken form fails far above the threshold.
    for unit in (" \n", "\n", "\t\n", "\r\n", "\u00a0\n", " "):
        for tail, blocked in (("cd x", True), ("rm -rf ~", False), ("cd() { :; }", True)):
            command = unit * 30000 + tail
            started = time.perf_counter()
            code, _ = _run(monkeypatch, capsys, command)
            assert time.perf_counter() - started < 6.0, (repr(unit), tail)
            assert (code == 2) is blocked, (repr(unit), tail)
    for command in ("x" + ";" * 400000, "&|" * 200000, "; " * 200000 + "cd x", "{ " * 200000):
        started = time.perf_counter()
        _run(monkeypatch, capsys, command)
        assert time.perf_counter() - started < 6.0, command[:20]
