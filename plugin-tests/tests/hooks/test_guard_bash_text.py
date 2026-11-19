"""Tests for `guard-bash-text.py`: three checks on the text of a shell command.

- BLOCK a literal `${CLAUDE_PLUGIN_ROOT}/` the shell would expand (the Bash tool's
  shell does not set the variable, so the path collapses to `/...`).
- ASK before a write whose target starts with `..` and lands outside the checkout.
- WARN on a multi-line `git commit -m` or `gh pr|issue ... --body`.

The hook reads only the command text, so most tests run it in-process. The `..`
check resolves against the payload's `cwd` and the nearest `.git` above it, so
those tests run from a real `git init` repo (`cached_git_repo`). Each trigger is
pinned with a silent near-miss one step away from it.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "hooks"
_HOOK = _HOOKS_DIR / "guard-bash-text.py"
_DISPATCH = _HOOKS_DIR / "dispatch-bash-pretooluse.py"

_BLOCK_REQ = "guard-hooks / An unresolved plugin root in a command is blocked"


def _load():
    spec = importlib.util.spec_from_file_location("guard_bash_text", _HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hook = _load()


def _init(path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(path)], check=True, capture_output=True)
    (path / "sub").mkdir()


@pytest.fixture
def repo(cached_git_repo, tmp_path) -> Path:
    """A real checkout at `tmp_path/checkout`, with a `sub/` directory."""
    return cached_git_repo("guard-bash-text", _init, tmp_path / "checkout")


@pytest.fixture(autouse=True)
def _no_plugin_root(monkeypatch):
    # The hook names the plugin root in its block reason when its own process
    # has the variable (Claude Code exports it to hooks); keep the suite's own
    # environment from deciding a result.
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)


def _run(monkeypatch, command, cwd, raw: str | None = None) -> tuple[int, str, str]:
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    if cwd is not None:
        payload["cwd"] = str(cwd)
    monkeypatch.setattr(sys, "stdin", io.StringIO(raw if raw is not None else json.dumps(payload)))
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)
    rc = hook.main()
    return rc, out.getvalue(), err.getvalue()


def _blocks(monkeypatch, command, cwd) -> str:
    rc, out, err = _run(monkeypatch, command, cwd)
    assert rc == 2, (command, out, err)
    assert out == ""
    return err


def _asks(monkeypatch, command, cwd) -> str:
    rc, out, err = _run(monkeypatch, command, cwd)
    assert rc == 0, (command, err)
    nested = json.loads(out)["hookSpecificOutput"]
    assert nested["hookEventName"] == "PreToolUse"
    assert nested["permissionDecision"] == "ask"
    return nested["permissionDecisionReason"]


def _warns(monkeypatch, command, cwd) -> str:
    rc, out, err = _run(monkeypatch, command, cwd)
    assert rc == 0, (command, err)
    assert out == "", out
    assert "[guard-bash-text]" in err, (command, err)
    return err


def _silent(monkeypatch, command, cwd) -> None:
    rc, out, err = _run(monkeypatch, command, cwd)
    assert (rc, out, err) == (0, "", ""), (command, rc, out, err)


# --------------------------------------------------------------------------- #
# 1. An unresolved plugin root blocks
# --------------------------------------------------------------------------- #

_PLACEHOLDER_COMMANDS = [
    "python3 ${CLAUDE_PLUGIN_ROOT}/skills/x/scripts/check.py",
    'python3 "${CLAUDE_PLUGIN_ROOT}/skills/x/scripts/check.py"',
    "python3 $CLAUDE_PLUGIN_ROOT/skills/x.py",
    'python3 "$CLAUDE_PLUGIN_ROOT/skills/x.py"',
    'python3 "$CLAUDE_PLUGIN_ROOT"/skills/x.py',
    'python3 "${CLAUDE_PLUGIN_ROOT}"/skills/x.py',
    "python ${CLAUDE_PLUGIN_ROOT}\\skills\\x.py",
    "git status && python3 ${CLAUDE_PLUGIN_ROOT}/x.py",
    "git status; python3 ${CLAUDE_PLUGIN_ROOT}/x.py",
    "ls | python3 ${CLAUDE_PLUGIN_ROOT}/x.py",
    "git status\npython3 ${CLAUDE_PLUGIN_ROOT}/x.py",
    "(python3 ${CLAUDE_PLUGIN_ROOT}/x.py)",
    "echo $(cat ${CLAUDE_PLUGIN_ROOT}/x)",
    'echo "$(cat "${CLAUDE_PLUGIN_ROOT}/x")"',
    "echo `cat ${CLAUDE_PLUGIN_ROOT}/x`",
    "env A=1 python3 ${CLAUDE_PLUGIN_ROOT}/x.py",
    'bash -c "python3 ${CLAUDE_PLUGIN_ROOT}/x.py"',
    "cat > notes.md <<EOF\nsee ${CLAUDE_PLUGIN_ROOT}/skills/x\nEOF\n",
    "cat > notes.md <<-EOF\n\tsee ${CLAUDE_PLUGIN_ROOT}/skills/x\n\tEOF\n",
]


# requirement: guard-hooks / An unresolved plugin root in a command is blocked
@pytest.mark.parametrize("command", _PLACEHOLDER_COMMANDS)
def test_an_expanded_plugin_root_path_blocks(monkeypatch, tmp_path, command):
    reason = _blocks(monkeypatch, command, tmp_path)
    assert "CLAUDE_PLUGIN_ROOT" in reason
    assert "absolute path" in reason
    assert "(hook: guard-bash-text.py)" in reason


_LITERAL_COMMANDS = [
    "grep -rn '${CLAUDE_PLUGIN_ROOT}/' skills",
    'grep -rn "\\${CLAUDE_PLUGIN_ROOT}/" skills',
    "grep -rn \\${CLAUDE_PLUGIN_ROOT}/ skills",
    "bash -c 'python3 ${CLAUDE_PLUGIN_ROOT}/x.py'",
    'echo "$CLAUDE_PLUGIN_ROOT"',
    "echo $CLAUDE_PLUGIN_ROOT",
    "echo ${CLAUDE_PLUGIN_ROOT}",
    'echo "${CLAUDE_PLUGIN_ROOT:-unset}/x"',
    "ls ${CLAUDE_PLUGIN_ROOT:?}/x",
    "ls $CLAUDE_PLUGIN_ROOTS/x",
    "ls ${CLAUDE_PLUGIN_DATA}/x",
    "cat > notes.md <<'EOF'\nsee ${CLAUDE_PLUGIN_ROOT}/skills/x\nEOF\n",
    'cat > notes.md <<"EOF"\nsee ${CLAUDE_PLUGIN_ROOT}/skills/x\nEOF\n',
    "cat > notes.md <<\\EOF\nsee ${CLAUDE_PLUGIN_ROOT}/skills/x\nEOF\n",
    "cat > notes.md <<EOF\nsee \\${CLAUDE_PLUGIN_ROOT}/skills/x\nEOF\n",
    "ls  # then run ${CLAUDE_PLUGIN_ROOT}/x.py",
    "export CLAUDE_PLUGIN_ROOT=/opt/p; python3 $CLAUDE_PLUGIN_ROOT/x.py",
    "CLAUDE_PLUGIN_ROOT=/opt/p bash -c 'python3 $CLAUDE_PLUGIN_ROOT/x.py'",
    "$env:CLAUDE_PLUGIN_ROOT = 'C:/p'; python $env:CLAUDE_PLUGIN_ROOT/x.py",
    "$CLAUDE_PLUGIN_ROOT = 'C:/p'; python ${CLAUDE_PLUGIN_ROOT}/x.py",
]


# requirement: guard-hooks / An unresolved plugin root in a command is blocked
@pytest.mark.parametrize("command", _LITERAL_COMMANDS)
def test_a_placeholder_the_shell_does_not_expand_is_silent(monkeypatch, tmp_path, command):
    _silent(monkeypatch, command, tmp_path)


def test_the_block_names_the_placeholder_once_per_spelling(monkeypatch, tmp_path):
    reason = _blocks(
        monkeypatch,
        "python3 ${CLAUDE_PLUGIN_ROOT}/a.py && python3 ${CLAUDE_PLUGIN_ROOT}/a.py",
        tmp_path,
    )
    assert reason.count("${CLAUDE_PLUGIN_ROOT}/a.py") == 1


def test_the_block_offers_the_plugin_root_the_hook_runs_from(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", "/opt/plugins/cla")
    reason = _blocks(monkeypatch, "python3 ${CLAUDE_PLUGIN_ROOT}/x.py", tmp_path)
    assert "`/opt/plugins/cla`" in reason


def test_without_the_variable_the_block_offers_no_root(monkeypatch, tmp_path):
    reason = _blocks(monkeypatch, "python3 ${CLAUDE_PLUGIN_ROOT}/x.py", tmp_path)
    assert "For a file of the cla plugin" not in reason


def test_the_block_also_carries_the_other_findings(monkeypatch, tmp_path):
    command = 'python3 ${CLAUDE_PLUGIN_ROOT}/x.py > ../out.log && git commit -m "a\nb"'
    reason = _blocks(monkeypatch, command, tmp_path)
    assert "Also: this command writes outside the checkout" in reason
    assert "`../out.log`" in reason
    assert "[guard-bash-text]" in reason


# --------------------------------------------------------------------------- #
# 2. A write outside the checkout through `..` asks
# --------------------------------------------------------------------------- #

_OUTSIDE_WRITES = [
    ("echo x > ../run.log", "../run.log"),
    ("echo x >> ../run.log", "../run.log"),
    ("echo x >| ../run.log", "../run.log"),
    ("echo x &> ../run.log", "../run.log"),
    ("echo x &>> ../run.log", "../run.log"),
    ("make 2>../err.log", "../err.log"),
    ("make >&../both.log", "../both.log"),
    ("exec 3<>../fd.log", "../fd.log"),
    ("echo x >../run.log", "../run.log"),
    ('echo x > "../a b.log"', "../a b.log"),
    ("echo x > '../run.log'", "../run.log"),
    ("cat > ../notes.md <<'EOF'\nhello\nEOF\n", "../notes.md"),
    ("ls | tee ../list.txt", "../list.txt"),
    ("ls | tee -a out.txt ../list.txt", "../list.txt"),
    ("mkdir ../x", "../x"),
    ("mkdir -p -m 755 ../x", "../x"),
    ("mkdir -pm 755 ../x", "../x"),
    ("mkdir --mode 755 ../x", "../x"),
    ("cp notes.md ../notes.md.bak", "../notes.md.bak"),
    ("cp -r a b ../c/", "../c/"),
    ("cp -t ../dir a b", "../dir"),
    ("cp -rt ../dir a", "../dir"),
    ("cp --target-directory=../dir a", "../dir"),
    ("cp --target-directory ../dir a", "../dir"),
    ("cp -S .old a ../b", "../b"),
    ("cp -- a ../b", "../b"),
    ("mv a ../b", "../b"),
    ("cp a ..", ".."),
    ("cp a ./sub/../../x", "./sub/../../x"),
    # A Windows separator, quoted: unquoted, bash reads `\x` as an escaped `x`.
    ("cp a '..\\x'", "..\\x"),
    ("git status && cp a ../b", "../b"),
    ("git status; cp a ../b", "../b"),
    ("git status || cp a ../b", "../b"),
    ("git status\ncp a ../b", "../b"),
    ("(cp a ../b)", "../b"),
    ("echo $(cp a ../b)", "../b"),
    ("echo `cp a ../b`", "../b"),
    ("{ cp a ../b; }", "../b"),
    ("if true; then cp a ../b; fi", "../b"),
    ("env A=1 cp a ../b", "../b"),
    ("env -u A cp a ../b", "../b"),
    ("command cp a ../b", "../b"),
    ("sudo cp a ../b", "../b"),
    ("sudo -u bob cp a ../b", "../b"),
    ("nohup cp a ../b", "../b"),
    ("A=1 B=2 cp a ../b", "../b"),
    ("/bin/cp a ../b", "../b"),
    ("CP.EXE a ../b", "../b"),
]


# requirement: guard-hooks / A write outside the checkout through .. asks first
@pytest.mark.parametrize("command,target", _OUTSIDE_WRITES)
def test_a_write_through_dot_dot_out_of_the_checkout_asks(monkeypatch, repo, command, target):
    reason = _asks(monkeypatch, command, repo)
    assert f"`{target}`" in reason
    assert "other projects" in reason
    assert "scratchpad" in reason
    assert "(hook: guard-bash-text.py)" in reason


_NOT_OUTSIDE_WRITES = [
    "cd ..",
    "ls ..",
    "ls ../x",
    "echo ../x",
    'echo "see ../x" > out.txt',
    "echo '> ../x'",
    'git commit -m "move to ../x"',
    "git -C ../x status",
    "cat < ../in.txt",
    "cat <<< ../x",
    "cp ../a b",
    "mv ../a b",
    "cp -t sub ../a",
    "mkdir sub/x",
    "cp a",
    "cp a sub/../y",
    "make 2>&1",
    "make >&2",
    "make >&-",
    "echo x > /tmp/out.log",
    "echo x > ~/out.log",
    "echo x > $HOME/../out.log",
    'echo x > "$(pwd)/../out.log"',
    "command -v cp ../b",
    "tee < ../in.txt",
    "diff <(cat a) ../b",
    "echo $((1 >> 2))",
]


# requirement: guard-hooks / A write outside the checkout through .. asks first
@pytest.mark.parametrize("command", _NOT_OUTSIDE_WRITES)
def test_a_dot_dot_that_is_not_a_write_out_of_the_checkout_is_silent(monkeypatch, repo, command):
    _silent(monkeypatch, command, repo)


def test_a_dot_dot_back_into_the_checkout_is_silent(monkeypatch, repo):
    _silent(monkeypatch, f"cp a ../{repo.name}/b", repo)


# requirement: guard-hooks / A write outside the checkout through .. asks first
def test_from_a_subdirectory_one_level_up_stays_in_the_checkout(monkeypatch, repo):
    _silent(monkeypatch, "echo x > ../out.txt", repo / "sub")
    assert "`../../out.txt`" in _asks(monkeypatch, "echo x > ../../out.txt", repo / "sub")


def test_a_linked_worktree_is_its_own_checkout(monkeypatch, repo):
    # A linked worktree's `.git` is a FILE; the boundary is the worktree, so a
    # write into a sibling worktree under the same main clone still asks.
    worktree = repo / ".claude" / "worktrees" / "wt"
    worktree.mkdir(parents=True)
    (worktree / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
    assert "`../other/x`" in _asks(monkeypatch, "cp a ../other/x", worktree)
    _silent(monkeypatch, "cp a sub/../x", worktree)


def test_outside_any_repository_the_cwd_is_the_boundary(monkeypatch, tmp_path):
    plain = tmp_path / "plain"
    (plain / "inner").mkdir(parents=True)
    _asks(monkeypatch, "echo x > ../x", plain)
    # From `inner`, `..` is `plain`: outside the boundary, which is `inner` itself.
    _asks(monkeypatch, "echo x > ../x", plain / "inner")
    _silent(monkeypatch, "echo x > ./y/../x", plain / "inner")


def test_a_missing_cwd_falls_back_to_the_process_directory(monkeypatch, repo):
    monkeypatch.chdir(repo / "sub")
    _silent(monkeypatch, "echo x > ../out.txt", None)
    monkeypatch.chdir(repo)
    _asks(monkeypatch, "echo x > ../out.txt", None)


def test_the_ask_names_five_targets_and_counts_the_rest(monkeypatch, repo):
    command = "; ".join(f"cp a ../t{n}" for n in range(8))
    reason = _asks(monkeypatch, command, repo)
    for n in range(5):
        assert f"`../t{n}`" in reason
    assert "`../t5`" not in reason
    assert "and 3 more" in reason


def test_the_ask_names_each_target_once(monkeypatch, repo):
    reason = _asks(monkeypatch, "cp a ../b; cp c ../b", repo)
    assert reason.count("`../b`") == 1


def test_the_ask_carries_none_of_the_copilot_failure_markers(monkeypatch, repo):
    # The Copilot adapter turns an ask whose reason says a guard "could not run"
    # or "did not run" into a deny; this ask is a real one and must stay one.
    reason = _asks(monkeypatch, "cp a ../b", repo).lower()
    assert "could not run" not in reason
    assert "did not run" not in reason


# --------------------------------------------------------------------------- #
# 3. A multi-line inline message warns
# --------------------------------------------------------------------------- #

_HEREDOC_MESSAGE = "\"$(cat <<'EOF'\nfeat: x\n\nbody\nEOF\n)\""

_MULTILINE_MESSAGES = [
    ('git commit -m "feat: x\n\nbody"', "`git commit -m`"),
    ("git commit -m " + _HEREDOC_MESSAGE, "`git commit -m`"),
    ('git commit -am "a\nb"', "`git commit -m`"),
    ('git commit -m"a\nb"', "`git commit -m`"),
    ("git commit -m 'a\nb'", "`git commit -m`"),
    ("git commit -m $'a\\nb'", "`git commit -m`"),
    ('git commit --message="a\nb"', "`git commit -m`"),
    ('git commit --message "a\nb"', "`git commit -m`"),
    ('git commit -m one -m "two\nthree"', "`git commit -m`"),
    ('git -C . commit -m "a\nb"', "`git commit -m`"),
    ('git -c user.name=x --no-pager commit -m "a\nb"', "`git commit -m`"),
    ('git.exe commit -m "a\nb"', "`git commit -m`"),
    ('GIT commit -m "a\nb"', "`git commit -m`"),
    ('env A=1 git commit -m "a\nb"', "`git commit -m`"),
    ('git add x && git commit -m "a\nb"', "`git commit -m`"),
    ('(git commit -m "a\nb")', "`git commit -m`"),
    ('gh pr create --title t --body "a\n## b"', "`gh pr create --body`"),
    ("gh pr create --title t --body " + _HEREDOC_MESSAGE, "`gh pr create --body`"),
    ('gh pr edit 5 -b "a\nb"', "`gh pr edit --body`"),
    ('gh pr comment 5 --body="a\nb"', "`gh pr comment --body`"),
    ('gh pr review 5 --approve -b"a\nb"', "`gh pr review --body`"),
    ('gh issue create --title t --body "a\nb"', "`gh issue create --body`"),
    ('gh issue comment 5 --body "a\nb"', "`gh issue comment --body`"),
    ("gh.exe issue edit 5 --body $'a\\nb'", "`gh issue edit --body`"),
]


# requirement: guard-warnings / A multi-line inline commit message or pull request body warns
@pytest.mark.parametrize("command,label", _MULTILINE_MESSAGES)
def test_a_multi_line_inline_message_warns(monkeypatch, tmp_path, command, label):
    warning = _warns(monkeypatch, command, tmp_path)
    assert label in warning
    assert "git commit -F <file>" in warning
    assert "--body-file <file>" in warning


_SINGLE_LINE_MESSAGES = [
    'git commit -m "fix: one line"',
    'git commit -m "subject" -m "body paragraph"',
    'git commit -m "a\\nb"',
    "git commit -F msg.txt",
    "git commit -F - <<'EOF'\nfeat: x\n\nbody\nEOF\n",
    'git commit -C HEAD -m "one"',
    'git commit --author "A <a@b>" -m "one"',
    'git commit -m "$(cat msg.txt)"',
    'git tag -m "a\nb" v1',
    'git log --grep "a\nb"',
    'echo "git commit -m \\"a\nb\\""',
    'gh pr create --title t --body "one line"',
    "gh pr create --title t --body-file body.md",
    'gh pr view 5 --json body --jq ".body"',
    'gh api repos/o/r/issues -f body="a\nb"',
    'gh release create v1 --notes "a\nb"',
]


# requirement: guard-warnings / A multi-line inline commit message or pull request body warns
@pytest.mark.parametrize("command", _SINGLE_LINE_MESSAGES)
def test_a_single_line_or_file_message_is_silent(monkeypatch, tmp_path, command):
    _silent(monkeypatch, command, tmp_path)


def test_a_warning_and_an_ask_travel_together(monkeypatch, repo):
    rc, out, err = _run(monkeypatch, 'git commit -m "a\nb" > ../log', repo)
    assert rc == 0
    assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert "[guard-bash-text]" in err


def test_two_kinds_of_message_are_both_named(monkeypatch, tmp_path):
    command = 'git commit -m "a\nb" && gh pr create --body "c\nd"'
    warning = _warns(monkeypatch, command, tmp_path)
    assert "`git commit -m` and `gh pr create --body`" in warning


# --------------------------------------------------------------------------- #
# Failing open
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        "[]",
        "{}",
        '{"tool_input": "x"}',
        '{"tool_input": {"command": 5}}',
        '{"tool_input": {"command": ""}}',
    ],
)
def test_malformed_input_fails_open(monkeypatch, raw):
    rc, out, err = _run(monkeypatch, None, None, raw=raw)
    assert (rc, out, err) == (0, "", "")


@pytest.mark.parametrize(
    "command",
    [
        'echo "unterminated > ../x',
        "echo 'unterminated > ../x",
        "echo $(cp a ../b",
        "echo ${CLAUDE_PLUGIN_ROOT/x",
        "python3 ${CLAUDE_PLUGIN_ROOT}/x.py `",
        "cat <<'EOF > ../x",
        "echo $'unterminated > ../x",
    ],
)
def test_a_command_the_shell_would_refuse_is_silent(monkeypatch, repo, command):
    _silent(monkeypatch, command, repo)


def test_an_internal_error_fails_open(monkeypatch, tmp_path):
    def boom(*_args):
        raise RuntimeError("boom")

    monkeypatch.setattr(hook, "check", boom)
    _silent(monkeypatch, "python3 ${CLAUDE_PLUGIN_ROOT}/x.py", tmp_path)


def test_a_non_dict_payload_root_fails_open(monkeypatch):
    rc, out, err = _run(monkeypatch, None, None, raw='"python3 ${CLAUDE_PLUGIN_ROOT}/x.py"')
    assert (rc, out, err) == (0, "", "")


# --------------------------------------------------------------------------- #
# Linear time on hostile input
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "unit",
    [
        "a;",
        "x\n",
        "$(",
        '"$(',
        "`",
        "((",
        "'",
        "\\",
        "${",
        "cat <<A\n",
        "<<A ",
        "cp a ../b; ",
        "> ../x ",
        "${CLAUDE_PLUGIN_ROOT}/ ",
        'git commit -m "a\nb"; ',
        "git -c git -c ",
        "$'\\n",
    ],
)
def test_a_long_hostile_command_stays_fast(monkeypatch, repo, unit):
    command = unit * (500_000 // len(unit))
    started = time.perf_counter()
    _run(monkeypatch, command, repo)
    assert time.perf_counter() - started < 5.0, unit


# --------------------------------------------------------------------------- #
# Through the real dispatcher
# --------------------------------------------------------------------------- #

def _dispatch(command: str, cwd: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "ALLOW_DESTRUCTIVE_GIT": "", "CLAUDE_PLUGIN_ROOT": ""}
    return subprocess.run(
        [sys.executable, str(_DISPATCH)],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)}),
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=str(cwd),
    )


# requirement: guard-hooks / An unresolved plugin root in a command is blocked
def test_the_dispatcher_blocks_an_unresolved_plugin_root(repo):
    r = _dispatch('python3 "${CLAUDE_PLUGIN_ROOT}/skills/x/scripts/check.py"', repo)
    assert r.returncode == 2
    assert "guard-bash-text.py" in r.stderr


# requirement: guard-hooks / A write outside the checkout through .. asks first
def test_the_dispatcher_reemits_the_outside_write_ask(repo):
    r = _dispatch("cp notes.md ../notes.md.bak", repo)
    assert r.returncode == 0, r.stderr
    nested = json.loads(r.stdout)["hookSpecificOutput"]
    assert nested["permissionDecision"] == "ask"
    assert "`../notes.md.bak`" in nested["permissionDecisionReason"]
    assert "guard-bash-text.py" in nested["permissionDecisionReason"]


# requirement: guard-warnings / A multi-line inline commit message or pull request body warns
def test_the_dispatcher_delivers_the_warning_as_context(tmp_path):
    r = _dispatch('git commit -m "a\nb"', tmp_path)
    assert r.returncode == 0, r.stderr
    nested = json.loads(r.stdout)["hookSpecificOutput"]
    assert "permissionDecision" not in nested
    assert "[guard-bash-text]" in nested["additionalContext"]


def test_the_dispatcher_stays_silent_on_a_clean_command(repo):
    r = _dispatch("cp notes.md sub/notes.md && git commit -m one", repo)
    assert r.returncode == 0
    assert "guard-bash-text" not in r.stdout + r.stderr


# --------------------------------------------------------------------------- #
# Edges found by planting a bug in each decision line
# --------------------------------------------------------------------------- #

_MORE_BLOCKS = [
    # a longer name that merely starts with the variable's name is a different variable: silent (below);
    # but a comparison is not an assignment, so a path use beside it still blocks
    '[ $CLAUDE_PLUGIN_ROOT == "" ] && ls $CLAUDE_PLUGIN_ROOT/x',
    # a `#` inside a word starts no comment
    "echo a#${CLAUDE_PLUGIN_ROOT}/x",
    # a heredoc closed by a tab-indented terminator ends there: the command after it is real code
    "cat <<-'EOF'\n\t${CLAUDE_PLUGIN_ROOT}/inside\n\tEOF\nls ${CLAUDE_PLUGIN_ROOT}/after",
    # ...and so is one closed by a CRLF terminator
    "cat <<'EOF'\r\nbody\r\nEOF\r\nls ${CLAUDE_PLUGIN_ROOT}/after",
    # a here-string is not a heredoc
    "cat <<< hello\nls ${CLAUDE_PLUGIN_ROOT}/after",
    # an arithmetic expansion closes at its own `))`
    "echo $(( (1+2)*3 )) && ls ${CLAUDE_PLUGIN_ROOT}/x",
    # a backtick substitution closes at its backtick even with an open paren inside
    "echo `echo (` && ls ${CLAUDE_PLUGIN_ROOT}/x",
]


# requirement: guard-hooks / An unresolved plugin root in a command is blocked
@pytest.mark.parametrize("command", _MORE_BLOCKS)
def test_the_edges_of_the_unresolved_root_block(monkeypatch, tmp_path, command):
    assert "CLAUDE_PLUGIN_ROOT" in _blocks(monkeypatch, command, tmp_path)


_MORE_SILENT = [
    # another variable whose name starts with the root's
    "ls $CLAUDE_PLUGIN_ROOT_OLD/x",
    "ls $CLAUDE_PLUGIN_ROOT9/x",
    # PowerShell's own assignment silences a plain use of the same name
    "$env:CLAUDE_PLUGIN_ROOT = 'C:/p'; python $CLAUDE_PLUGIN_ROOT/x.py",
    # a quoted `A=b` names a command, not an assignment: nothing after it is `git`
    "\"A\"=1 git commit -m $'a\\nb'",
    # `command -v` describes, it does not run
    "command -v git commit -m $'a\\nb'",
    "command -V git commit -m $'a\\nb'",
    # a quoted heredoc's body is text, even when its terminator never comes
    "cat <<-'EOF'\n\t${CLAUDE_PLUGIN_ROOT}/inside\n",
]


@pytest.mark.parametrize("command", _MORE_SILENT)
def test_the_edges_of_what_is_silent(monkeypatch, tmp_path, command):
    _silent(monkeypatch, command, tmp_path)


_MORE_ASKS = [
    ("tee \\../outside.txt", "../outside.txt"),              # an escaped first character is still that character
    ("tee .\\\n./outside.txt", "../outside.txt"),            # a backslash-newline joins the lines
    ("echo `echo (` > ../out", "../out"),                    # the backtick closes with a paren open
    ("mkdir -- -m ../out", "../out"),                        # after `--` an option-looking word is an operand
    ("cp - ../out", "../out"),                               # a lone `-` is an operand
    ("echo x &>> ../out", "../out"),
]


# requirement: guard-hooks / A write outside the checkout through .. asks first
@pytest.mark.parametrize("command,target", _MORE_ASKS)
def test_more_spellings_of_a_write_outside_the_checkout_ask(monkeypatch, repo, command, target):
    assert f"`{target}`" in _asks(monkeypatch, command, repo)


_MORE_NOT_OUTSIDE = [
    "cp ../a",                       # one operand: no destination
    "tee ~/../../x",                 # `~` is not knowable from the text, whatever it normalises to
    "tee $HOME/../../x",
    "tee C:/../../x",                # a Windows drive path
    "tee c:\\..\\..\\x",
    "tee ../a://b",                  # anything holding `://` is a URL, not a path
    "tee /a/../../x",
    "echo $((x >../../y))",          # inside `$((...))` a `>` is arithmetic, not a redirect
    "echo ${v:->../../x}",           # inside `${...}` a `>` is part of the default word, not a redirect
    "ls &>>| ../../x",               # `&>>|` is no operator: the `|` ends the command, no target is read
]


# requirement: guard-hooks / A write outside the checkout through .. asks first
@pytest.mark.parametrize("command", _MORE_NOT_OUTSIDE)
def test_more_paths_that_are_not_a_write_out_of_the_checkout_are_silent(monkeypatch, repo, command):
    _silent(monkeypatch, command, repo)


_MORE_WARNS = [
    "git 2>/dev/null commit -m $'a\\nb'",                    # the `2` of `2>` is a descriptor, not an argument
]


# requirement: guard-warnings / A multi-line inline commit message or pull request body warns
@pytest.mark.parametrize("command", _MORE_WARNS)
def test_more_spellings_of_a_multi_line_message_warn(monkeypatch, tmp_path, command):
    assert "git commit -m" in _warns(monkeypatch, command, tmp_path)


_MORE_NO_WARNING = [
    "git commit -um$'a\\nb'",                                # the rest of `-u`'s word is its value, not a message
    "git commit --author -m $'a\\nb'",                       # an option that takes a value swallows the next word
    "git commit -t -m $'a\\nb'",
    "gh pr view 5 --body $'a\\nb'",                          # only create, edit, comment and review take a body
    "gh issue view 5 --body $'a\\nb'",
    "gitx commit -m $'a\\nb'",                               # a longer command name is another command
    "ghost pr create --body $'a\\nb'",
]


# requirement: guard-warnings / A multi-line inline commit message or pull request body warns
@pytest.mark.parametrize("command", _MORE_NO_WARNING)
def test_more_commands_that_are_not_a_multi_line_message_are_silent(monkeypatch, tmp_path, command):
    _silent(monkeypatch, command, tmp_path)
