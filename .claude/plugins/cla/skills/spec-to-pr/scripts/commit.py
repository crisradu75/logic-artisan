"""Stage paths and commit, with the message supplied either as a single-line
string (`--message`/`-m`) or read from a file (positional `MESSAGE_FILE`, for
multi-paragraph messages where bash discipline forbids inline heredocs).

Refuses if neither/both message sources are supplied, if the file is missing,
or if no changes are staged after `git add`.
"""

# Spec: spec-to-pr-orchestration#helper-scripts-wrap-variable-arg-commands
# Spec: spec-to-pr-orchestration#three-commit-branch-convention

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from _git_common import repo_root as _repo_root

REPO_ROOT = _repo_root()


def _force_utf8_stdout() -> None:
    """Force UTF-8 on stdout/stderr so echoing a commit message or git output
    containing non-ASCII (e.g. an em dash or `→`) doesn't crash with
    UnicodeEncodeError on Windows' cp1252 console."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    # encoding="utf-8" is explicit so Windows doesn't decode commit messages
    # or git stderr as cp1252 and corrupt non-ASCII content.
    return subprocess.run(cmd, cwd=cwd if cwd is not None else REPO_ROOT,
                          capture_output=True, text=True, encoding="utf-8")


def main(argv: list[str]) -> int:
    _force_utf8_stdout()
    parser = argparse.ArgumentParser(prog="commit")
    msg_group = parser.add_mutually_exclusive_group(required=True)
    msg_group.add_argument("-m", "--message", default=None,
                           help="Single-line commit message.")
    msg_group.add_argument("-F", "--message-file", dest="message_file", default=None,
                           help="Path to a file holding the commit message "
                                "(for multi-paragraph messages).")
    parser.add_argument("paths", nargs="+",
                        help="Paths to stage and commit.")
    args = parser.parse_args(argv)

    if args.message_file is not None:
        msg_path = Path(args.message_file)
        if not msg_path.is_file():
            print(f"message-file does not exist: {msg_path}", file=sys.stderr)
            return 2
        commit_msg_args: list[str] = ["-F", str(msg_path)]
    else:
        commit_msg_args = ["-m", args.message]

    add = _run(["git", "add", "--", *args.paths])
    if add.returncode != 0:
        print(add.stderr.strip(), file=sys.stderr)
        return add.returncode

    diff = _run(["git", "diff", "--cached", "--quiet"])
    if diff.returncode == 0:
        print("no staged changes after git add; refusing to commit", file=sys.stderr)
        return 3

    commit = _run(["git", "commit", *commit_msg_args])
    if commit.returncode != 0:
        print(commit.stderr.strip(), file=sys.stderr)
        return commit.returncode

    print(commit.stdout.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
