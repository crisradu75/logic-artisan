"""Tests for `block-dishonest-commit.py` and the argument reader it shares,
`_git_commit_args.py`.

The hook reads command text only, so most tests need no repository. The ones
that read a `-F` message file write it into `tmp_path`. Each trigger is pinned
with its near-misses: a rule that also fires on a commit that merely mentions
`Measured-by: none`, or on every `--allow-empty`, would stall the chains it is
meant to keep honest.
"""

from __future__ import annotations

import importlib.util
import io
import json
import re
import sys
import time
from pathlib import Path

import pytest

_PLUGIN = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
_HOOKS_DIR = _PLUGIN / "hooks"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, _HOOKS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hook = _load("block_dishonest_commit", "block-dishonest-commit.py")
args = _load("git_commit_args_for_tests", "_git_commit_args.py")


def _run(command, monkeypatch, capsys, cwd: Path | str | None = None, raw: str | None = None):
    if raw is None:
        payload: dict = {"tool_input": {"command": command}}
        if cwd is not None:
            payload["cwd"] = str(cwd)
        raw = json.dumps(payload)
    monkeypatch.setattr(sys, "stdin", io.StringIO(raw))
    code = hook.main()
    captured = capsys.readouterr()
    assert captured.out == "", "this hook speaks on stderr only"
    return code, captured.err


def _blocked(command, monkeypatch, capsys, cwd=None) -> str:
    code, err = _run(command, monkeypatch, capsys, cwd)
    assert code == 2, f"expected a block for {command!r}, got {code}: {err}"
    assert "(hook: block-dishonest-commit.py)" in err
    return err


def _silent(command, monkeypatch, capsys, cwd=None) -> None:
    code, err = _run(command, monkeypatch, capsys, cwd)
    assert (code, err) == (0, ""), f"expected silence for {command!r}, got {code}: {err}"


def _warned(command, monkeypatch, capsys, cwd=None) -> None:
    code, err = _run(command, monkeypatch, capsys, cwd)
    assert code == 0, err
    assert err.startswith("[block-dishonest-commit] `git commit --allow-empty`"), err


HEREDOC_MESSAGE = "git commit -m \"$(cat <<'EOF'\nfix: x\n\nMeasured-by: none\nEOF\n)\""

_NONE_FORMS = [
    'git commit -m "fix: x" -m "Measured-by: none"',
    'git commit -m "fix: x" -m "Measured-by: none (docs only)"',
    'git commit -m "fix: x" -m "Measured-by: none — nothing measured"',
    'git commit -m "fix: x" -m "Measured-by: none."',
    'git commit -m "fix: x" -m "measured-BY :  NONE"',
    'git commit -m "fix: x\n\nMeasured-by: none"',
    'git commit -m "fix: x" -m "Co-Authored-By: a <b@c.d>\nMeasured-by: none\nClaude-Session: s"',
    "git commit -m 'fix: x' -m 'Measured-by: none'",
    "git commit -m $'fix: x\\n\\nMeasured-by: none'",
    'git commit --message "Measured-by: none"',
    'git commit --message="Measured-by: none"',
    'git commit "--message=Measured-by: none"',
    'git commit --mess "Measured-by: none"',
    'git commit -qam "Measured-by: none"',
    'git commit -m"Measured-by: none"',
    HEREDOC_MESSAGE,
    "git commit -F - <<'EOF'\nfix: x\n\nMeasured-by: none\nEOF",
    "git commit -F - <<-EOF\n\tfix: x\n\n\tMeasured-by: none\n\tEOF",
    "git commit --file=- <<EOF\nfix: x\nMeasured-by: none\nEOF\n",
    'git commit -m x --trailer "Measured-by: none"',
    'git commit -m x --trailer=Measured-by=none',
    'git commit -m x --trailer "measured-by:none"',
    # a later `-m` among several, and options after the pathspecs
    'git commit src/a.py -m "fix: x" -m "body" -m "Measured-by: none"',
    'git commit -m "fix: x" -m "Measured-by: none - nothing to measure"',
]


# requirement: git-guards / A commit message carrying Measured-by none is refused
@pytest.mark.parametrize("command", _NONE_FORMS)
def test_each_measured_by_none_form_is_blocked(command, monkeypatch, capsys):
    err = _blocked(command, monkeypatch, capsys)
    assert "`Measured-by: none`" in err
    assert "Delete the line, or run the measurement" in err


_NONE_NEAR_MISSES = [
    # Prose mentioning the rule is not a trailer line.
    'git commit -m "fix: never write Measured-by: none"',
    'git commit -m "docs: Measured-by: none is now refused"',
    'git commit -m "fix: x" -m "Measured-by: nonesuch"',
    'git commit -m "fix: x" -m "Measured-by: pytest -q — none failed"',
    'git commit -m "fix: x" -m "Measured-by: none-the-wiser"',
    'git commit -m "fix: x" -m "X-Measured-by: none"',
    # Not a commit message.
    'echo "Measured-by: none"',
    "git log --grep 'Measured-by: none'",
    'git tag -m "Measured-by: none" v1',
    "git commit-tree HEAD^{tree} -m 'Measured-by: none'",
    # No commit is made.
    'git commit --dry-run -m "Measured-by: none"',
    # git refuses these command lines outright.
    'git commit --bogus -m "Measured-by: none"',
    'git commit -X -m "Measured-by: none"',
    'git commit --re x -m "Measured-by: none"',
]


@pytest.mark.parametrize("command", _NONE_NEAR_MISSES)
def test_near_misses_of_measured_by_none_stay_silent(command, monkeypatch, capsys):
    _silent(command, monkeypatch, capsys)


@pytest.mark.parametrize("command", [
    'git -C /tmp commit -m "Measured-by: none"',
    'git -c user.name=x -C "/a dir" commit -m "Measured-by: none"',
    'git --no-pager commit -m "Measured-by: none"',
    'GIT.EXE commit -m "Measured-by: none"',
    '/usr/bin/git commit -m "Measured-by: none"',
    'git add a.py && git commit -m "Measured-by: none"',
    'git status; git commit -m "Measured-by: none"',
    'git status | cat\ngit commit -m "Measured-by: none"',
    'true || git commit -m "Measured-by: none"',
    '(git commit -m "Measured-by: none")',
    '{ git commit -m "Measured-by: none"; }',
    'env GIT_AUTHOR_NAME=x git commit -m "Measured-by: none"',
    'command git commit -m "Measured-by: none"',
    'sudo git commit -m "Measured-by: none"',
    'git commit -m "fix: ok" && git commit --amend -m "Measured-by: none"',
    'git commit \\\n  -m "fix: x" \\\n  -m "Measured-by: none"',
    'git commit -m "fix: x" -m "Measured-by: none" 2>&1 | tail -3',
    'git commit -m "fix: x" -m "Measured-by: none" > /dev/null',
])
def test_the_commit_is_found_in_every_command_position(command, monkeypatch, capsys):
    _blocked(command, monkeypatch, capsys)


def test_a_quoted_or_echoed_git_commit_is_not_a_commit(monkeypatch, capsys):
    _silent("echo 'git commit -m \"Measured-by: none\"'", monkeypatch, capsys)
    _silent('printf "%s" "git commit --allow-empty -m x"', monkeypatch, capsys)


def test_a_message_file_is_read_relative_to_the_commit_directory(tmp_path, monkeypatch, capsys):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "msg.txt").write_text("fix: x\n\nMeasured-by: none\n", encoding="utf-8")
    _blocked("git commit -F sub/msg.txt", monkeypatch, capsys, cwd=tmp_path)
    _blocked("git -C sub commit --file msg.txt", monkeypatch, capsys, cwd=tmp_path)
    _blocked("git commit -Fsub/msg.txt", monkeypatch, capsys, cwd=tmp_path)
    (tmp_path / "ok.txt").write_text("fix: x\n\nMeasured-by: pytest -q — 3 passed\n", encoding="utf-8")
    _silent("git commit -F ok.txt", monkeypatch, capsys, cwd=tmp_path)
    # A missing file, or a repository named another way, is out of sight: silence.
    _silent("git commit -F missing.txt", monkeypatch, capsys, cwd=tmp_path)
    _silent("git --git-dir=.git commit -F sub/msg.txt", monkeypatch, capsys, cwd=tmp_path)
    _silent("GIT_DIR=.git git commit -F sub/msg.txt", monkeypatch, capsys, cwd=tmp_path)


def test_a_message_this_hook_cannot_see_is_allowed(monkeypatch, capsys):
    for command in (
        "git commit",
        "git commit -C HEAD",
        "git commit --amend --no-edit",
        "printf 'Measured-by: none' | git commit -F -",
        'git commit -m "$(cat msg.txt)"',
    ):
        _silent(command, monkeypatch, capsys)


# --------------------------------------------------------------------------- #
# --allow-empty
# --------------------------------------------------------------------------- #


_ROUND_FORMS = [
    'git commit --allow-empty -m "fix: review round 2"',
    'git commit -m "fix: review round 1" --allow-empty',
    "git commit --allow-empty -m 'fix: review round 3' -m 'body'",
    "git commit --allow-empty -m \"$(cat <<'EOF'\nfix: review round 2\n\nnothing applied\nEOF\n)\"",
    "git commit --allow-empty -F - <<'EOF'\n\nfix: review round 2\nEOF",
    'cd_ok=1 && (git -C . commit --allow-empty -qm "fix: review round 4")',
]


# requirement: git-guards / An empty review-round commit is refused
@pytest.mark.parametrize("command", _ROUND_FORMS)
def test_an_empty_review_round_commit_is_blocked(command, monkeypatch, capsys):
    err = _blocked(command, monkeypatch, capsys)
    assert "`fix: review round <N>`" in err
    assert "Handoff report" in err


# requirement: git-guards / An empty review-round commit is refused
@pytest.mark.parametrize("command", [
    'git commit --allow-empty -m "init"',
    'git commit --allow-empty -m "chore: trigger CI"',
    'git commit --allow-empty -m "fix: review round two"',
    'git commit --allow-empty -m "Fix: review round 2"',
    'git commit --allow-empty -m "chore: x" -m "fix: review round 2"',
    "git commit --allow-empty",
    "git commit --allow-empty -C HEAD",
    'git commit --allow-empty -m "$(cat msg.txt)"',
])
def test_any_other_empty_commit_only_warns(command, monkeypatch, capsys):
    _warned(command, monkeypatch, capsys)


@pytest.mark.parametrize("command", [
    'git commit -m "fix: review round 2"',
    'git commit --allow-empty --no-allow-empty -m "fix: review round 2"',
    'git commit --allow-empty-message -m ""',
    'git commit --dry-run --allow-empty -m "fix: review round 2"',
])
def test_a_commit_that_is_not_empty_says_nothing(command, monkeypatch, capsys):
    _silent(command, monkeypatch, capsys)


def test_the_round_pattern_matches_the_counter_it_protects():
    """The block is only as good as its agreement with `probe_state.py`, which
    counts rounds by subject: a commit the counter reads must be refused, and
    one it ignores is not "for the counter"."""
    probe = (_PLUGIN / "skills" / "spec-to-pr" / "scripts" / "probe_state.py").read_text(encoding="utf-8")
    counter = re.search(r're\.compile\((r"\^fix: review round[^"]*")\)', probe)
    assert counter, "probe_state.py no longer compiles the round pattern this hook mirrors"
    assert counter.group(1) == 'r"' + hook._ROUND_SUBJECT.pattern + '"'


def test_a_block_wins_over_an_earlier_warning(monkeypatch, capsys):
    command = 'git commit --allow-empty -m init && git commit -m x -m "Measured-by: none"'
    err = _blocked(command, monkeypatch, capsys)
    assert "`Measured-by: none`" in err


# --------------------------------------------------------------------------- #
# Failing open, and time
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("raw", [
    "", "{", "null", "[]", '"git commit"', "{}",
    '{"tool_input": null}', '{"tool_input": {"command": 7}}',
    '{"tool_input": {"command": ""}}', '{"tool_input": {"command": "git commit -m x"}, "cwd": 3}',
])
def test_malformed_input_fails_open(raw, monkeypatch, capsys):
    code, err = _run(None, monkeypatch, capsys, raw=raw)
    assert (code, err) == (0, "")


@pytest.mark.parametrize("command", [
    'git commit -m "Measured-by: none',            # unterminated double quote
    "git commit -m 'Measured-by: none",            # unterminated single quote
    'git commit -m "$(cat <<EOF\nMeasured-by: none\n"',  # unterminated substitution
    "git commit -m " + "$(" * 40 + "x" + ")" * 40 + ' -m "Measured-by: none"',  # nested too deep
])
def test_unreadable_command_text_fails_open(command, monkeypatch, capsys):
    _silent(command, monkeypatch, capsys)


@pytest.mark.parametrize("unit", [
    'git commit -m "Measured-by: ok" ; ',
    "git commit -m x git commit -m y ",
    "git -c git -c git -c ",
    "git commit -m $(",
    "git commit -F - <<E\n",
    "git commit -m \"$(cat <<'EOF'\nfix\nEOF\n)\"\n",
    "'\"",
])
def test_a_500k_hostile_command_stays_fast(unit, monkeypatch, capsys):
    command = unit * (500_000 // len(unit))
    started = time.perf_counter()
    _run(command, monkeypatch, capsys)
    assert time.perf_counter() - started < 3.0


# --------------------------------------------------------------------------- #
# The shared reader, directly
# --------------------------------------------------------------------------- #


def _words(text: str) -> list[str]:
    words, _bodies, _end = args.command_words(text, 0)
    return [w.message for w in words]


@pytest.mark.parametrize("text, expected", [
    ("a 'b c' \"d e\"", ["a", "b c", "d e"]),
    ("a\\ b c", ["a b", "c"]),
    ('"a\\"b" \'x\'y', ['a"b', "xy"]),
    ("$'a\\nb'", ["a\nb"]),
    ("a; b", ["a"]),
    ("a && b", ["a"]),
    ("a | b", ["a"]),
    ("a\nb", ["a"]),
    ("a) b", ["a"]),
    ("a # b", ["a"]),
    ("a 2>&1 b >out c < in d &>log e", ["a", "b", "c", "d", "e"]),
    ("a <<< 'here' b", ["a", "b"]),
    ('a "$(echo "x y")" b', ["a", "$(echo \"x y\")", "b"]),
    ("a `echo x` b", ["a", "`echo x`", "b"]),
    ("a \"$(cat <<'EOF'\nline ) one\nwon't\nEOF\n)\" b", ["a", "line ) one\nwon't", "b"]),
    ("a \"$(cat <<EOF\n  x\nEOF\n)\"", ["a", "  x"]),
    ("a \"pre $(cat <<'EOF'\nx\nEOF\n)\"", ["a", "pre $(cat <<'EOF'\nx\nEOF\n)"]),
])
def test_the_word_reader(text, expected):
    assert _words(text) == expected


def test_the_word_reader_returns_its_own_heredoc_bodies_and_consumes_them():
    text = "git commit -F - <<'EOF' && echo done\nbody one\nEOF\nnext"
    words, bodies, end = args.command_words(text, len("git commit"))
    assert [w.text for w in words] == ["-F", "-"]
    assert bodies == [("", "body one")]
    assert text[end:] == "next"


def test_a_match_inside_consumed_text_is_not_read_again():
    # The heredoc body holds a `git commit` line; it is message text, not a command.
    command = "git commit -F - <<'EOF'\nfix: x\ngit commit --allow-empty\nEOF\n"
    dispatch = _load("dispatch_lib_for_commit_tests", "_dispatch_lib.py")
    matcher = dispatch.GitInvocation(args.COMMIT_OR_ADD, capture_opts=True)
    found = args.find_invocations(command, dispatch.strip_quoted_spans(command), matcher, "/")
    assert len(found) == 1
    assert found[0].messages == ["fix: x\ngit commit --allow-empty"]
    assert not found[0].allow_empty


def test_read_add_names_what_it_stages():
    dispatch = _load("dispatch_lib_for_add_tests", "_dispatch_lib.py")
    matcher = dispatch.GitInvocation(args.COMMIT_OR_ADD, capture_opts=True)

    def adds(command):
        return [
            (a.pathspecs, a.whole_tree, a.tracked_only)
            for a in args.find_invocations(command, dispatch.strip_quoted_spans(command), matcher, "/r")
            if isinstance(a, args.Add)
        ]

    assert adds("git add a.py 'b c.py'") == [(["a.py", "b c.py"], False, False)]
    assert adds("git add -A") == [([], True, False)]
    assert adds("git add -u") == [([], True, True)]
    assert adds("git add -- -odd") == [(["-odd"], False, False)]
    assert adds("git add ':!x'") == [([], True, False)]
    assert adds("git add --chmod +x a.py") == [(["a.py"], False, False)]
    for nothing in ("git add", "git add -n a.py", "git add -p", "git add --pathspec-from-file=f", "git add --bogus a"):
        assert adds(nothing) == [], nothing
