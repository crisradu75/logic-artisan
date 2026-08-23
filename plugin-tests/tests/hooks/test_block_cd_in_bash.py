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
