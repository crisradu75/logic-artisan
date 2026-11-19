"""Mutant batch for `tests/hooks/test_warn_stacked_pr_merge.py`.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/hooks/test_warn_stacked_pr_merge.py

`hooks/warn-stacked-pr-merge.py` warns, and never blocks, when `gh pr merge --delete-branch` hits a
branch that open child PRs are based on (gh closes the children before any retarget). A warning hook
fails in two directions that both cost something: silent when it should speak (a child PR is closed
for good) and speaking when it should not (the warning is tuned out). The mutants re-break one
return path at a time:

- reading the command: which spellings of `gh pr merge` and of the delete flag count, which
  spellings of "do not delete" cancel it, and which bare integer is the PR number;
- resolving the branch: an explicit PR number asks gh, no number asks git in the session's own
  directory, and any failure on the way is a silent exit 0;
- reading gh's answer as untrusted data: not JSON, not a list, an empty list, elements that are not
  PR records, a record with no number;
- the warning itself: it names every child, and goes to stderr.

Two plantable-looking edits are NOT in the batch because no input can tell them from the original:
dropping the `||` alternative of the split pattern (a `|` alone already splits at the first bar of
`||`), and dropping `or not children` from the list check (an empty list leaves `listed` empty, and
the `if not listed` return that follows exits the same way). An unobservable mutant in a batch is a
survivor by construction.

Anchors sit within one physical line, or take the file's own line ending. Paths resolve from this
file.
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]  # <repo>/plugin-tests
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
HOOK = PLUGIN / "hooks" / "warn-stacked-pr-merge.py"
TARGETS = [DEV / "tests" / "hooks" / "test_warn_stacked_pr_merge.py"]

_SPEC = [
    # ---- reading the command ----------------------------------------------------------------
    ("`gh pr merge` is matched without a word boundary before `gh`",
     'r"\\b(?i:gh)(?:\\.(?i:exe|cmd|bat|com|ps1))?\\s+pr\\s+merge\\b"',
     'r"(?i:gh)(?:\\.(?i:exe|cmd|bat|com|ps1))?\\s+pr\\s+merge\\b"'),
    ("`gh pr merge` is matched case-sensitively",
     'r"\\b(?i:gh)(?:\\.(?i:exe|cmd|bat|com|ps1))?\\s+pr\\s+merge\\b"',
     'r"\\bgh(?:\\.(?i:exe|cmd|bat|com|ps1))?\\s+pr\\s+merge\\b"'),
    ("`gh.exe` and friends are not recognised",
     'r"\\b(?i:gh)(?:\\.(?i:exe|cmd|bat|com|ps1))?\\s+pr\\s+merge\\b"',
     'r"\\b(?i:gh)\\s+pr\\s+merge\\b"'),
    ("`gh pr merge` matches a longer subcommand",
     'r"\\b(?i:gh)(?:\\.(?i:exe|cmd|bat|com|ps1))?\\s+pr\\s+merge\\b"',
     'r"\\b(?i:gh)(?:\\.(?i:exe|cmd|bat|com|ps1))?\\s+pr\\s+merge"'),
    ("`-d` / `--delete-branch` is matched inside another word",
     '_DELETE_BRANCH = re.compile(r"(?:^|\\s)(?:--delete-branch|-d)(?:\\s|=|$)")',
     '_DELETE_BRANCH = re.compile(r"(?:--delete-branch|-d)(?:\\s|=|$)")'),
    ("`-d` is matched as a prefix of a longer flag",
     '_DELETE_BRANCH = re.compile(r"(?:^|\\s)(?:--delete-branch|-d)(?:\\s|=|$)")',
     '_DELETE_BRANCH = re.compile(r"(?:^|\\s)(?:--delete-branch|-d)")'),
    ("the short `-d` is not recognised",
     '_DELETE_BRANCH = re.compile(r"(?:^|\\s)(?:--delete-branch|-d)(?:\\s|=|$)")',
     '_DELETE_BRANCH = re.compile(r"(?:^|\\s)(?:--delete-branch)(?:\\s|=|$)")'),
    ("`--delete-branch=false` still warns",
     '    if re.search(r"--delete-branch=(?:false|0|no)\\b", cmd):',
     "    if False:"),
    ("`--delete-branch=0` still warns",
     '    if re.search(r"--delete-branch=(?:false|0|no)\\b", cmd):',
     '    if re.search(r"--delete-branch=(?:false|no)\\b", cmd):'),
    ("`--delete-branch=no` still warns",
     '    if re.search(r"--delete-branch=(?:false|0|no)\\b", cmd):',
     '    if re.search(r"--delete-branch=(?:false|0)\\b", cmd):'),
    ("`--delete-branch=falsey` is read as false",
     '    if re.search(r"--delete-branch=(?:false|0|no)\\b", cmd):',
     '    if re.search(r"--delete-branch=(?:false|0|no)", cmd):'),
    ("a command needs `gh pr merge` OR the delete flag, not both",
     "    if not _GH_MERGE.search(cmd) or not _DELETE_BRANCH.search(cmd):",
     "    if not _GH_MERGE.search(cmd) and not _DELETE_BRANCH.search(cmd):"),
    ("a PR number is read inside a longer token",
     '_PR_NUMBER = re.compile(r"(?:^|\\s)(\\d+)(?:\\s|$)")',
     '_PR_NUMBER = re.compile(r"(\\d+)(?:\\s|$)")'),
    ("a PR number is read at the start of a longer token",
     '_PR_NUMBER = re.compile(r"(?:^|\\s)(\\d+)(?:\\s|$)")',
     '_PR_NUMBER = re.compile(r"(?:^|\\s)(\\d+)")'),
    ("the merge target is looked for in the whole rest of the command",
     '    sub = re.split(r"\\s*(?:&&|\\|\\||;|\\|)\\s*", cmd[m.end():], maxsplit=1)[0]',
     "    sub = cmd[m.end():]"),
    ("a number after `&&` is read as the target",
     '    sub = re.split(r"\\s*(?:&&|\\|\\||;|\\|)\\s*", cmd[m.end():], maxsplit=1)[0]',
     '    sub = re.split(r"\\s*(?:\\|\\||;|\\|)\\s*", cmd[m.end():], maxsplit=1)[0]'),
    ("a number after `;` is read as the target",
     '    sub = re.split(r"\\s*(?:&&|\\|\\||;|\\|)\\s*", cmd[m.end():], maxsplit=1)[0]',
     '    sub = re.split(r"\\s*(?:&&|\\|\\||\\|)\\s*", cmd[m.end():], maxsplit=1)[0]'),
    ("a number after a pipe is read as the target",
     '    sub = re.split(r"\\s*(?:&&|\\|\\||;|\\|)\\s*", cmd[m.end():], maxsplit=1)[0]',
     '    sub = re.split(r"\\s*(?:&&|\\|\\||;)\\s*", cmd[m.end():], maxsplit=1)[0]'),
    ("a command without `gh pr merge` has a target",
     "    if not m:",
     "    if False:"),
    # ---- main(): the entry checks -----------------------------------------------------------
    ("a non-object payload is read as one",
     "    if not isinstance(payload, dict):",
     "    if False:"),
    ("a non-dict tool_input is read as a dict",
     '    cmd = tool_input.get("command", "") if isinstance(tool_input, dict) else ""',
     '    cmd = tool_input.get("command", "")'),
    ("a non-string command is searched",
     "    if not isinstance(cmd, str) or not cmd:",
     "    if not cmd:"),
    ("every command goes on to the gh calls",
     "    if not _wants_stacked_check(cmd):",
     "    if False:"),
    ("a machine without gh is not skipped",
     '    if shutil.which("gh") is None:',
     "    if False:"),
    # ---- main(): resolving the head branch --------------------------------------------------
    ("an explicit PR number is not looked up",
     "    if number:",
     "    if False:"),
    ("the PR lookup asks for a different field",
     'head = _gh(["pr", "view", number, "--json", "headRefName", "-q", ".headRefName"])',
     'head = _gh(["pr", "view", number, "--json", "baseRefName", "-q", ".baseRefName"])'),
    ("the current-branch lookup ignores the payload cwd",
     "        head = _current_branch(cwd if isinstance(cwd, str) and cwd else None)",
     "        head = _current_branch(None)"),
    ("a non-string cwd is passed through",
     "        head = _current_branch(cwd if isinstance(cwd, str) and cwd else None)",
     "        head = _current_branch(cwd or None)"),
    ("a failed head lookup goes on to list children",
     '    if not head or head == "HEAD":',
     "    if False:"),
    ("a detached HEAD is treated as a branch",
     '    if not head or head == "HEAD":',
     "    if not head:"),
    # ---- main(): reading gh's answer --------------------------------------------------------
    ("the child listing asks for the wrong base",
     'raw = _gh(["pr", "list", "--base", head, "--state", "open", "--json", "number,title"])',
     'raw = _gh(["pr", "list", "--head", head, "--state", "open", "--json", "number,title"])'),
    ("the child listing includes closed PRs",
     'raw = _gh(["pr", "list", "--base", head, "--state", "open", "--json", "number,title"])',
     'raw = _gh(["pr", "list", "--base", head, "--state", "all", "--json", "number,title"])'),
    ("a failed child listing is parsed",
     "    if not raw:",
     "    if False:"),
    ("a non-JSON child listing crashes",
     "    except (json.JSONDecodeError, ValueError):\n        return 0\n    if not isinstance(children",
     "    except KeyError:\n        return 0\n    if not isinstance(children"),
    ("a non-list child listing is iterated",
     "    if not isinstance(children, list) or not children:",
     "    if not children:"),
    ("a non-dict element is read as a PR",
     "        f\"#{c['number']}\" for c in children if isinstance(c, dict) and c.get(\"number\")",
     "        f\"#{c['number']}\" for c in children if c.get(\"number\")"),
    ("a PR record with no number is listed",
     "        f\"#{c['number']}\" for c in children if isinstance(c, dict) and c.get(\"number\")",
     "        f\"#{c.get('number')}\" for c in children if isinstance(c, dict)"),
    ("a warning is printed with nothing to name",
     "    if not listed:",
     "    if False:"),
    ("the children are named without separators",
     '    listed = ", ".join(',
     '    listed = " ".join('),
    ("the warning goes to stdout",
     "        file=sys.stderr,",
     "        file=sys.stdout,"),
    # ---- the two subprocess helpers ---------------------------------------------------------
    ("a gh that fails still returns its output",
     "    return r.stdout.strip() if r.returncode == 0 else None\n\n\ndef _current_branch",
     "    return r.stdout.strip()\n\n\ndef _current_branch"),
    ("a gh that cannot run raises",
     "    except (OSError, subprocess.SubprocessError):\n        return None\n    return r.stdout.strip() if r.returncode == 0 else None\n\n\ndef _current_branch",
     "    except KeyError:\n        return None\n    return r.stdout.strip() if r.returncode == 0 else None\n\n\ndef _current_branch"),
    ("a slow gh waits forever",
     "            timeout=_GH_TIMEOUT_SECONDS,",
     "            timeout=None,"),
    ("a git without `-C` asks about the hook's own directory",
     '["git", *(["-C", cwd] if cwd else []), "rev-parse", "--abbrev-ref", "HEAD"],',
     '["git", "rev-parse", "--abbrev-ref", "HEAD"],'),
    ("a failed git still returns its output",
     "    return r.stdout.strip() if r.returncode == 0 else None\n\n\ndef _wants_stacked_check",
     "    return r.stdout.strip()\n\n\ndef _wants_stacked_check"),
]

# Multi-line anchors take the file's own line ending, so the batch runs on LF and CRLF checkouts.
_NL = "\r\n" if b"\r\n" in HOOK.read_bytes() else "\n"
MUTANTS = [(name, HOOK, old.replace("\n", _NL), new.replace("\n", _NL), TARGETS) for name, old, new in _SPEC]
