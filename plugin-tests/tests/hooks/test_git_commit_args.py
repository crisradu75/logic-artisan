"""Unit tests for `hooks/_git_commit_args.py`, the argument reader the two
commit-honesty guards share (`block-dishonest-commit.py` and
`ask-staged-debug-tag.py`).

Those guards' tests reach it only through a verdict, so a misread message or
flag showed as one guard's wrong answer. These call the reader directly: the
shell-word reader, the simple-command reader, and what `read_commit`,
`read_add` and `find_invocations` make of the words.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, _HOOKS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


args = _load("git_commit_args_under_test", "_git_commit_args.py")
text = _load("shell_text_for_commit_args", "_shell_text.py")
_MATCHER = text.GitInvocation(args.COMMIT_OR_ADD, capture_opts=True)


def _found(command: str, cwd: str = "/r") -> list:
    return args.find_invocations(command, text.strip_quoted_spans(command), _MATCHER, cwd)


def _commit(command: str, cwd: str | None = "/r"):
    """`read_commit` on the first `git ... commit`, refused or not."""
    m = _MATCHER.search(text.strip_quoted_spans(command))
    assert m is not None and m.group(2) == "commit", command
    return args.read_commit(command, m.start(), m.end(), command[m.start(1):m.end(1)], cwd)


def _add(command: str, cwd: str | None = "/r"):
    m = _MATCHER.search(text.strip_quoted_spans(command))
    assert m is not None and m.group(2) == "add", command
    return args.read_add(command, m.start(), m.end(), command[m.start(1):m.end(1)], cwd)


# --------------------------------------------------------------------------- #
# read_word: one shell word, quotes removed
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "source,value",
    [
        ("plain rest", "plain"),
        ("'a b' rest", "a b"),
        ('"a b" rest', "a b"),
        ('"a\\"b" rest', 'a"b'),
        ('"a\\nb" rest', "a\\nb"),        # inside double quotes `\n` stays two characters
        ("$'a\\nb' rest", "a\nb"),         # ANSI-C quoting decodes it
        ("a\\ b rest", "a b"),
        ("ab;cd", "ab"),
        ('"x $(date) y" rest', "x $(date) y"),  # a substitution is kept as written
        ("`echo hi` rest", "`echo hi`"),
    ],
)
def test_read_word_reads_one_word_as_the_command_receives_it(source, value):
    word, end = args.read_word(source, 0)
    assert word.text == value
    assert word.heredoc is None
    assert source[end:] in ("", " rest", ";cd")


def test_a_cat_heredoc_substitution_word_takes_the_heredoc_body():
    source = "\"$(cat <<'EOF'\nsubject\n\nbody\nEOF\n)\" rest"
    word, end = args.read_word(source, 0)
    assert word.heredoc == "subject\n\nbody"
    assert word.message == "subject\n\nbody"
    assert source[end:] == " rest"


@pytest.mark.parametrize(
    "source",
    ["\"x $(cat <<'EOF'\nbody\nEOF\n)\"", "\"$(cat <<'EOF'\nbody\nEOF\n) tail\""],
)
def test_a_word_with_more_than_the_substitution_keeps_its_text(source):
    word, _ = args.read_word(source, 0)
    assert word.heredoc is None
    assert word.message == source[1:-1]


@pytest.mark.parametrize("source", ["'open", '"open', "$'open", "$(open", "`open", '"$(open"'])
def test_an_unterminated_word_raises(source):
    with pytest.raises(args.ParseError):
        args.read_word(source, 0)


def test_substitutions_nested_past_the_depth_cap_raise():
    deep = "$(" * (args._MAX_DEPTH + 1) + ")" * (args._MAX_DEPTH + 1)
    with pytest.raises(args.ParseError):
        args.read_word(deep, 0)
    shallow = "$(" * args._MAX_DEPTH + ")" * args._MAX_DEPTH
    assert args.read_word(shallow, 0)[0].text == shallow


# --------------------------------------------------------------------------- #
# command_words: one simple command, its redirections and heredocs
# --------------------------------------------------------------------------- #


def test_command_words_stop_at_the_end_of_the_simple_command():
    for sep in (";", "&&", "|", "\n", ")"):
        words, bodies, end = args.command_words(f"a b{sep}c", 0)
        assert [w.text for w in words] == ["a", "b"], sep
        assert bodies == [] and end == 3


def test_command_words_stop_at_a_comment():
    words, _bodies, _end = args.command_words("a b # c d", 0)
    assert [w.text for w in words] == ["a", "b"]


def test_redirections_and_their_targets_are_not_words():
    words, _bodies, _end = args.command_words("a > out 2>&1 < in b 2> err c <<< here d", 0)
    assert [w.text for w in words] == ["a", "b", "c", "d"]


def test_a_line_continuation_joins_words():
    words, _bodies, _end = args.command_words("a \\\n b", 0)
    assert [w.text for w in words] == ["a", "b"]


def test_heredoc_bodies_are_returned_with_their_fd_and_consumed():
    source = "a <<'X' 3<<-Y\nfirst\nX\n\tsecond\n\tY\nnext"
    words, bodies, end = args.command_words(source, 0)
    assert [w.text for w in words] == ["a"]
    assert bodies == [("", "first"), ("3", "second")]
    assert source[end:] == "next"


# --------------------------------------------------------------------------- #
# directory_of: where git runs
# --------------------------------------------------------------------------- #


def test_directory_of_follows_each_global_dash_c():
    assert args.directory_of("/r", "-C sub -C ../o ") == "/r/o"
    assert args.directory_of("/r", "") == "/r"


@pytest.mark.parametrize("opts", ["--git-dir=/x ", "--work-tree /x ", "-C a --git-dir /x "])
def test_directory_of_is_none_when_the_repository_is_named_elsewhere(opts):
    assert args.directory_of("/r", opts) is None


def test_directory_of_is_none_without_a_cwd():
    assert args.directory_of(None, "-C sub ") is None


# --------------------------------------------------------------------------- #
# read_commit: the message
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "command,messages",
    [
        ('git commit -m "a b"', ["a b"]),
        ("git commit -m a -m b", ["a", "b"]),
        ("git commit -mfoo", ["foo"]),
        ("git commit -qm x", ["x"]),
        ("git commit --message=x", ["x"]),
        ("git commit --message x", ["x"]),
        ("git commit --mes x", ["x"]),           # a unique abbreviation
        ("git commit -m $'a\\nb'", ["a\nb"]),
        ("git commit -m \"$(cat <<'EOF'\nsubject\n\nbody\nEOF\n)\"", ["subject\n\nbody"]),
        ("git commit -F - <<'EOF'\nsubject\nEOF\n", ["subject"]),
        ("git commit -F /dev/stdin <<EOF\nsubject\nEOF\n", ["subject"]),
    ],
)
def test_read_commit_reads_each_message(command, messages):
    commit = _commit(command)
    assert not commit.refused
    assert commit.messages == messages
    assert not commit.message_hidden


def test_a_message_file_is_read_from_the_commit_directory(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "msg.txt").write_text("from file\n", encoding="utf-8")
    commit = _commit("git -C sub commit --file=msg.txt", cwd=str(tmp_path))
    assert commit.messages == ["from file\n"]
    assert not commit.message_hidden


def test_a_message_file_that_cannot_be_read_hides_the_message(tmp_path):
    assert _commit("git commit -F missing.txt", cwd=str(tmp_path)).message_hidden
    assert _commit("git commit -F msg.txt", cwd=None).message_hidden


@pytest.mark.parametrize(
    "command",
    [
        "git commit",                     # the editor
        "git commit --amend --no-edit",   # the commit being amended
        "git commit -C HEAD",
        "git commit --reuse-message=HEAD",
        "git commit -c HEAD",
        "git commit --fixup HEAD",
        "git commit -t tpl",
        "git commit -t tpl -m x",         # the template adds to what is seen
        "git commit -F - ",               # stdin with no heredoc
    ],
)
def test_a_message_from_elsewhere_is_hidden(command):
    commit = _commit(command)
    assert commit.message_hidden
    assert commit.subject is None


def test_the_subject_is_the_first_non_blank_line():
    assert _commit("git commit -m '  ' -m 'real\nmore'").subject == "real"
    assert _commit("git commit -m ''").subject is None


def test_trailers_are_kept_apart_from_the_message():
    commit = _commit("git commit --trailer 'Co: x' -m y")
    assert commit.trailers == ["Co: x"]
    assert commit.messages == ["y"]


# --------------------------------------------------------------------------- #
# read_commit: flags, pathspecs, refusals
# --------------------------------------------------------------------------- #


def test_read_commit_reads_its_flags():
    assert _commit("git commit --allow-empty -m x").allow_empty
    assert not _commit("git commit --allow-empty --no-allow-empty -m x").allow_empty
    assert _commit("git commit --dry-run -m x").dry_run
    assert _commit("git commit -am x").all_files
    assert _commit("git commit --all -m x").all_files
    assert _commit("git commit --pathspec-from-file=f -m x").pathspec_from_file
    plain = _commit("git commit -m x")
    assert not (plain.allow_empty or plain.dry_run or plain.all_files or plain.pathspec_from_file)


def test_read_commit_collects_pathspecs():
    assert _commit("git commit -m x a.py").pathspecs == ["a.py"]
    assert _commit("git commit -m x -- -odd b.py").pathspecs == ["-odd", "b.py"]


def test_an_optional_value_option_does_not_take_the_next_word():
    commit = _commit("git commit -S -m x")
    assert commit.messages == ["x"] and not commit.refused
    assert _commit("git commit -Skey -m x").messages == ["x"]


@pytest.mark.parametrize(
    "command",
    [
        "git commit --bogus -m x",   # unknown
        "git commit --a -m x",       # ambiguous abbreviation
        "git commit -Z -m x",        # unknown short flag
        "git commit -m",             # a value is required
        "git commit --message",
    ],
)
def test_a_command_line_git_refuses_is_refused(command):
    assert _commit(command).refused


def test_the_commit_ends_where_its_command_ends():
    command = "git commit -m x; echo done"
    commit = _commit(command)
    assert command[commit.start:commit.end].rstrip() == "git commit -m x"


# --------------------------------------------------------------------------- #
# read_add
# --------------------------------------------------------------------------- #


def test_read_add_names_its_pathspecs():
    add = _add("git add a.py 'b c.py'")
    assert add.pathspecs == ["a.py", "b c.py"] and not add.whole_tree


@pytest.mark.parametrize("command", ["git add -A", "git add --all", "git add ':!x'", "git add -u"])
def test_read_add_reads_a_whole_tree_add(command):
    assert _add(command).whole_tree


def test_read_add_marks_a_tracked_only_add():
    assert _add("git add -u").tracked_only
    assert _add("git add --update .").tracked_only
    assert not _add("git add -A").tracked_only


def test_a_value_option_takes_its_value():
    assert _add("git add --chmod +x a").pathspecs == ["a"]
    assert _add("git add --chmod=+x a").pathspecs == ["a"]


@pytest.mark.parametrize(
    "command",
    [
        "git add",
        "git add -n .",
        "git add --dry-run .",
        "git add -p .",
        "git add --pathspec-from-file=f",
        "git add --bogus .",
        "git add -Z .",
    ],
)
def test_an_add_that_stages_nothing_nameable_is_refused(command):
    assert _add(command).refused


# --------------------------------------------------------------------------- #
# find_invocations
# --------------------------------------------------------------------------- #


def test_find_invocations_returns_each_readable_invocation_in_order():
    found = _found("git add a && git commit -m x; git commit -m y")
    assert [type(f).__name__ for f in found] == ["Add", "Commit", "Commit"]
    assert [f.messages for f in found[1:]] == [["x"], ["y"]]


def test_find_invocations_leaves_out_a_refused_one():
    assert [f.messages for f in _found("git commit --bogus -m x; git commit -m y")] == [["y"]]


def test_find_invocations_skips_text_inside_a_heredoc_body():
    command = "cat <<'EOF'\ngit commit -m inner\nEOF\ngit commit -m outer"
    assert [f.messages for f in _found(command)] == [["outer"]]


def test_find_invocations_skips_text_an_earlier_invocation_consumed():
    command = "git commit -F - <<'EOF'\nfix: x\ngit commit --allow-empty\nEOF\n"
    found = _found(command)
    assert len(found) == 1 and not found[0].allow_empty


def test_a_git_command_inside_a_message_substitution_is_not_read_again():
    # The double-quoted `$(...)` stays visible to the matcher, so only the
    # first invocation's consumed span keeps the inner one out.
    found = _found('git commit -m "$(echo git commit --allow-empty)"')
    assert len(found) == 1 and not found[0].allow_empty


def test_find_invocations_stops_at_unreadable_text():
    assert [f.messages for f in _found("git commit -m x; git commit -m 'open; git commit -m y")] == [["x"]]


def test_a_git_dir_assignment_clears_every_directory():
    assert [f.directory for f in _found("GIT_DIR=/x git commit -m a; git commit -m b")] == [None, None]
    assert [f.directory for f in _found("git -C sub commit -m a")] == ["/r/sub"]
