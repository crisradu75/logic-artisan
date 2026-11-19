"""Unit tests for `hooks/_shell_read.py`, the shell reading every Bash guard shares.

The guards' own tests reach this module only through a hook, so a defect here
showed as one guard's wrong verdict and named nothing. These call its two public
readings directly: `guard_parts`, the wrapper bodies the dispatcher hands every
guard that reads parts, and `expand`, the parts `ask-destructive-git.py` reads.
Each test pins one rule of the section comments in that module.
"""

from __future__ import annotations

import base64
import importlib.util
import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))


def _load():
    # A fresh module object, so patching a cap here touches no other test's copy.
    spec = importlib.util.spec_from_file_location("shell_read_under_test", _HOOKS_DIR / "_shell_read.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


shell = _load()


@pytest.fixture(autouse=True)
def _fresh_caches():
    shell.guard_parts.cache_clear()
    shell.expand.cache_clear()
    yield
    shell.guard_parts.cache_clear()
    shell.expand.cache_clear()


def _parts(command: str) -> tuple[str, ...]:
    parts, complete = shell.guard_parts(command)
    assert complete, f"the reading of {command!r} stopped early"
    return parts


# --------------------------------------------------------------------------- #
# guard_parts: the body each wrapper form runs, its own option words dropped
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "command,body",
    [
        ("bash -c 'cp a ../b'", "cp a ../b"),
        ("sh -c 'cp a ../b'", "cp a ../b"),
        ("zsh -c 'cp a ../b'", "cp a ../b"),
        ("/bin/bash -c 'cp a ../b'", "cp a ../b"),
        ("bash.exe -c 'cp a ../b'", "cp a ../b"),
        ('eval "cp a ../b"', "cp a ../b"),
        ("pwsh -Command 'Remove-Item ../x'", "Remove-Item ../x"),
        ("powershell -File run.ps1", "run.ps1"),
        ("cmd /c del x", "del x"),
        ("su root -c 'rm x'", "rm x"),
        ("su --command='rm x'", "rm x"),
        ("iex 'Remove-Item x'", "Remove-Item x"),
        ("Invoke-Expression -Command 'Remove-Item x'", "Remove-Item x"),
    ],
)
def test_each_wrapper_form_hands_on_the_command_it_runs(command, body):
    assert _parts(command) == (body,)


def test_an_encoded_powershell_command_is_decoded():
    encoded = base64.b64encode("rm -rf ../x".encode("utf-16-le")).decode()
    assert _parts(f"pwsh -EncodedCommand {encoded}") == ("rm -rf ../x",)
    assert _parts(f"pwsh -ec {encoded}") == ("rm -rf ../x",)


@pytest.mark.parametrize(
    "command",
    [
        "bash -lc 'make test'",                # -c inside a short-option cluster
        "bash --norc -c 'make test'",          # a value-less long option
        "bash -o pipefail -c 'make test'",     # -o takes the next word
        "bash --rcfile rc -c 'make test'",     # --rcfile takes the next word
        "pwsh -NoProfile -Command 'make test'",
        "pwsh -ExecutionPolicy Bypass -c 'make test'",  # a value parameter, then -Command abbreviated
        "cmd /s /c \"make test\"",
    ],
)
def test_the_wrappers_own_option_words_are_not_part_of_the_body(command):
    assert _parts(command) == ("make test",)


def test_after_dash_c_only_the_command_string_is_the_body():
    # The words after it are the inner shell's $0 and $1, not commands.
    assert _parts('sh -c "echo hi" arg0 ../arg1') == ("echo hi",)


def test_without_dash_c_the_script_and_its_arguments_are_the_body():
    assert _parts("bash script.sh ../a") == ("script.sh ../a",)
    assert _parts("bash -- script.sh ../a") == ("script.sh ../a",)


def test_a_command_with_no_wrapper_has_no_parts():
    assert shell.guard_parts("cp a ../b") == ((), True)


def test_a_wrapper_inside_a_backtick_span_is_read():
    assert _parts("echo `bash -c 'ls ..'` more") == ("ls ..",)


# --------------------------------------------------------------------------- #
# guard_parts: heredoc text is data
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("delimiter", ["'EOF'", '"EOF"', "\\EOF"])
def test_a_quoted_heredoc_body_is_data(delimiter):
    assert shell.guard_parts(f"cat <<{delimiter}\nbash -c 'rm ../x'\nEOF") == ((), True)
    # Even its substitutions: the shell does not run them in a quoted body.
    assert shell.guard_parts(f"cat <<{delimiter}\n$(bash -c 'rm ../y')\nEOF") == ((), True)


def test_an_unquoted_heredoc_body_is_data_but_its_substitutions_run():
    command = "cat <<EOF\nbash -c 'rm ../x'\n$(bash -c 'rm ../y')\n`bash -c 'rm ../z'`\nEOF"
    assert _parts(command) == ("rm ../y", "rm ../z")


def test_a_wrapper_after_the_heredoc_ends_is_read():
    # `<<-` strips leading tabs, so the tab-indented delimiter ends the body.
    assert _parts("cat <<-EOF\n\tbash -c 'a'\n\tEOF\nbash -c 'b'") == ("b",)
    assert _parts("cat <<'EOF'\nbash -c 'a'\nEOF\nbash -c 'b'") == ("b",)


def test_a_heredoc_operator_inside_a_string_is_no_operator():
    assert _parts("echo '<<EOF'\nbash -c 'b'\nEOF") == ("b",)


# --------------------------------------------------------------------------- #
# guard_parts: a wrapper run by a remote runner is skipped
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "command",
    [
        "docker exec c bash -c 'rm -rf ../x'",
        "kubectl exec pod -- bash -c 'rm ../x'",
        "ssh host bash -c 'rm ../x'",
        "/usr/bin/ssh host bash -c 'rm ../x'",
        "timeout 5 ssh host bash -c 'rm ../x'",       # a prefix and its duration
        "sudo -u admin ssh host bash -c 'rm ../x'",   # a prefix option and its value
        "sudo --user=admin ssh host bash -c 'rm ../x'",
        "X=1 ssh host bash -c 'rm ../x'",              # an assignment before the runner
    ],
)
def test_a_wrapper_a_remote_runner_runs_is_skipped(command):
    assert shell.guard_parts(command) == ((), True)


@pytest.mark.parametrize(
    "command",
    [
        "sudo -u docker bash -c 'rm ../x'",       # the runner's name as an option value
        "GIT_SSH=/usr/bin/ssh bash -c 'rm ../x'",  # ... as an assignment's value
        "sudo --user docker bash -c 'rm ../x'",    # a long option whose value it cannot see
        "echo ssh; bash -c 'rm ../x'",             # ... in an earlier command
    ],
)
def test_a_runner_name_elsewhere_in_the_command_is_not_a_runner(command):
    assert _parts(command) == ("rm ../x",)


# --------------------------------------------------------------------------- #
# guard_parts: assignments the body names are carried in front of it
# --------------------------------------------------------------------------- #


def test_an_earlier_assignment_the_body_names_is_carried():
    assert _parts("X=../x; bash -c 'rm $X'") == ("export X=../x; rm $X",)
    assert _parts("export X=../x; bash -c 'rm ${X}'") == ("export X=../x; rm ${X}",)


def test_an_assignment_the_body_does_not_name_is_not_carried():
    assert _parts("Y=2; bash -c 'echo hi'") == ("echo hi",)


def test_an_assignment_after_the_wrapper_is_not_carried():
    assert _parts("bash -c 'echo $Z'; Z=3") == ("echo $Z",)


def test_the_last_value_before_the_wrapper_wins():
    assert _parts("X=1; X=2; bash -c 'echo $X'") == ("export X=2; echo $X",)


# --------------------------------------------------------------------------- #
# guard_parts: nesting, and the caps that make the reading say it stopped
# --------------------------------------------------------------------------- #


def test_nested_wrappers_are_read_to_the_depth_cap():
    command = "bash -c \"bash -c 'bash -c \\\"echo x\\\"'\""
    assert shell._WRAP_DEPTH == 3
    assert _parts(command) == (
        "bash -c 'bash -c \"echo x\"'",
        'bash -c "echo x"',
        "echo x",
    )


def test_a_wrapper_past_the_depth_cap_makes_the_reading_incomplete():
    command = "bash -c \"bash -c 'bash -c \\\"bash -c x\\\"'\""
    parts, complete = shell.guard_parts(command)
    assert not complete
    assert parts[-1] == "bash -c x", "what was found above the cap is still handed on"


def test_appended_text_past_the_cap_stops_the_reading():
    def nested(n: int) -> str:
        return f"bash -c \"bash -c 'bash -c \\\"echo {'A' * n}\\\"'\""

    # Three levels of a body about as long as the command: inside the cap at
    # 1,000 characters, past `len(command) + _EXPAND_SLACK` at 3,000.
    assert shell.guard_parts(nested(1000))[1] is True
    parts, complete = shell.guard_parts(nested(3000))
    assert not complete
    assert len(parts) == 2, "the levels read before the cap are kept"


def test_the_work_cap_stops_the_reading_and_is_restored(monkeypatch):
    command = "echo a; bash -c 'rm ../x'"
    assert shell.guard_parts(command) == (("rm ../x",), True)
    shell.guard_parts.cache_clear()
    monkeypatch.setattr(shell, "_WORK_FACTOR", 0)
    assert shell.guard_parts(command) == ((), False)
    assert shell._WORK_LEFT[0] == float("inf"), "the cap must not leak into the next reading"


def test_a_body_found_twice_is_handed_on_once():
    assert _parts("bash -c 'ls ..'; bash -c 'ls ..'") == ("ls ..",)


# --------------------------------------------------------------------------- #
# expand: what ask-destructive-git reads
# --------------------------------------------------------------------------- #


def test_expand_leaves_a_plain_command_as_it_is():
    assert shell.expand("git status") == (("git status",), None)


def test_expand_appends_a_wrapper_body_that_holds_git():
    parts, unread = shell.expand("bash -c 'git push -f origin x'")
    assert unread is None
    assert parts[0] == "bash -c 'git push -f origin x'"
    assert any("git push -f origin x" in p for p in parts[1:])


def test_expand_skips_a_wrapper_body_with_no_git():
    assert shell.expand("bash -c 'ls ..'") == (("bash -c 'ls ..'",), None)


def test_expand_fills_in_an_assigned_subcommand():
    parts, unread = shell.expand("X=push; git $X -f origin x")
    assert unread is None
    assert "git push -f origin x" in parts


def test_expand_tries_every_value_a_name_is_given():
    parts, unread = shell.expand("X=status; X=push; git $X -f")
    assert unread is None
    assert {"git status -f", "git push -f"} <= set(parts)


def test_expand_reads_a_quoted_flag():
    parts, unread = shell.expand('git push "-f" origin x')
    assert unread is None
    assert "git push -f origin x" in parts


@pytest.mark.parametrize("command", ["git $UNSET status", "git push $F origin x", "X=$(date); git $X"])
def test_expand_asks_about_an_expansion_it_cannot_resolve(command):
    assert shell.expand(command)[1] == shell.UNRESOLVED_REASON


def test_expand_leaves_an_operand_expansion_alone():
    assert shell.expand("git push origin $BRANCH")[1] is None


def test_expand_asks_about_a_git_wrapper_past_the_depth_cap():
    command = 'bash -c "bash -c \'bash -c \\"bash -c \\\\\\"git push\\\\\\"\\"\'"'
    assert shell.expand(command)[1] == shell.WRAP_DEPTH_REASON
    # The same depth with no git in the innermost body reads in full.
    assert shell.expand(command.replace("git push", "echo hi"))[1] is None


def test_expand_past_the_work_cap_asks(monkeypatch):
    monkeypatch.setattr(shell, "_WORK_FACTOR", 0)
    parts, unread = shell.expand("X=push; git $X -f origin x")
    assert unread == shell.UNRESOLVED_REASON
    assert parts[0] == "X=push; git $X -f origin x"
    assert shell._WORK_LEFT[0] == float("inf")


# --------------------------------------------------------------------------- #
# The word helpers both readings use
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "word,value",
    [
        ("main", "main"),
        ("'main'", "main"),
        ('"main"', "main"),
        ('ma"in"', "main"),
        ("$'ma\\x69n'", "main"),
        ("$'a\\tb'", "a\tb"),
        ('"a\\"b"', 'a"b'),
        ("a\\ b", "a b"),
        ("'unterminated", "unterminated"),
    ],
)
def test_unquote_reads_a_word_as_the_command_receives_it(word, value):
    assert shell._unquote(word) == value


def test_abbrev_matches_every_prefix_down_to_the_floor():
    import re

    pattern = re.compile(shell._abbrev("worktree", 3) + "$")
    assert all(pattern.match("worktree"[:n]) for n in range(3, 9))
    assert not pattern.match("wo")
    assert not pattern.match("worktreex")
