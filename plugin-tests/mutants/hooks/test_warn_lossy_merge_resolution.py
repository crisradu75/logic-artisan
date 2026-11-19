"""Mutation batch for test_warn_lossy_merge_resolution.py.

The hook warns before a merge commit whose result lacks lines the merged-in side
added. Its decisions are: which commands conclude a merge (`_directories`), which
files are read and what counts as the result (`_check`), the counting rule
(`_lost`, `_lines`), the cat-file reader, the message caps, and its wiring in the
Bash dispatcher. Each mutant below breaks one of them.

Not planted, with the reason:
- `--no-renames` and `--no-ext-diff` dropped from the two name-only diffs: on
  the test repos no rename or external diff driver exists, so no correct file
  tells the two apart. They are there for repos that have them.
- `if timeout <= 0: return None` removed: `subprocess.run` with a spent timeout
  raises `TimeoutExpired`, which `_git` already turns into None; the two forms
  agree on every input.
- `if head is None: return []` removed: `head.decode` on None raises, and
  `main` turns any exception into silence, the same outcome.
- The byte budget (`MAX_TOTAL_BYTES`): reaching it needs megabytes of fixture
  for a cap that only bounds cost.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/hooks/test_warn_lossy_merge_resolution.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
HOOKS = PLUGIN / "hooks"

HOOK = HOOKS / "warn-lossy-merge-resolution.py"
DISPATCH = HOOKS / "dispatch-bash-pretooluse.py"
LIB = HOOKS / "_dispatch_lib.py"

TESTS = DEV / "tests" / "hooks" / "test_warn_lossy_merge_resolution.py"
WIRING = DEV / "tests" / "hooks" / "test_hooks_wiring.py"
TARGETS = [TESTS]


def _nl(path: Path) -> str:
    """The file's own line separator, so a two-line anchor matches on a CRLF
    checkout too (`mutate.py`, "KEEP \\n OUT OF AN ANCHOR")."""
    return "\r\n" if b"\r\n" in path.read_bytes() else "\n"


_H, _D = _nl(HOOK), _nl(DISPATCH)

MUTANTS = [
    # ---- the counting rule ----
    (
        "a line both sides added identically is reported lost",
        HOOK,
        "if t[line] > b[line] and r[line] < t[line] and r[line] < o[line] + t[line] - b[line]:",
        "if t[line] > b[line] and r[line] < o[line] + t[line] - b[line]:",
        TARGETS,
    ),
    (
        "a line their side added where ours deleted a base copy is reported lost",
        HOOK,
        "if t[line] > b[line] and r[line] < t[line] and r[line] < o[line] + t[line] - b[line]:",
        "if t[line] > b[line] and r[line] < t[line]:",
        TARGETS,
    ),
    (
        "a base line their side only kept counts as their addition",
        HOOK,
        "if t[line] > b[line] and r[line] < t[line] and",
        "if t[line] >= b[line] and r[line] < t[line] and",
        TARGETS,
    ),
    (
        "trailing whitespace makes a kept line look lost",
        HOOK,
        "return [line.rstrip() for line in text.splitlines() if line.strip()]",
        "return [line for line in text.splitlines() if line.strip()]",
        TARGETS,
    ),
    (
        "blank lines are counted",
        HOOK,
        "return [line.rstrip() for line in text.splitlines() if line.strip()]",
        "return [line.rstrip() for line in text.splitlines()]",
        TARGETS,
    ),
    # ---- which commands conclude a merge ----
    (
        "any `git merge` counts, not only `--continue`",
        HOOK,
        'if not any(w.text == "--continue" for w in words):',
        'if not any(w.text.startswith("-") or True for w in words):',
        TARGETS,
    ),
    (
        "a dry-run commit is checked",
        HOOK,
        "if commit.refused or commit.dry_run or commit.directory is None:",
        "if commit.refused or commit.directory is None:",
        TARGETS,
    ),
    (
        "`GIT_DIR=` no longer hides the repository",
        HOOK,
        "base: str | None = None if _GIT_ENV_REPO.search(text) else cwd",
        "base: str | None = cwd",
        TARGETS,
    ),
    (
        "a commit inside a heredoc body is read as a command",
        HOOK,
        "            continue  # text inside a heredoc body is data, not a command",
        "            pass  # text inside a heredoc body is data, not a command",
        TARGETS,
    ),
    (
        "wrapper bodies are not read",
        HOOK,
        "            texts += list(_guard_parts(command)[0])",
        "            texts += []",
        TARGETS,
    ),
    (
        "`git -C` is ignored and the session directory is checked",
        HOOK,
        "directory, whole_tree = commit.directory, commit.all_files",
        "directory, whole_tree = base, commit.all_files",
        TARGETS,
    ),
    # ---- what is read as the result ----
    (
        "`-a` reads the index instead of the working tree",
        HOOK,
        "        if whole_tree or unmerged:",
        "        if unmerged:",
        TARGETS,
    ),
    (
        "an unmerged path is read as deleted",
        HOOK,
        "unmerged = staged is None and (stage2 is not None or stage3 is not None)",
        "unmerged = False",
        TARGETS,
    ),
    (
        "an unmerged path missing on disk is read as deleted",
        HOOK,
        'result = None if unmerged else b""',
        'result = b""',
        TARGETS,
    ),
    (
        "a file absent from the index is skipped instead of read as deleted",
        HOOK,
        'result = staged if staged is not None else b""',
        "result = staged",
        TARGETS,
    ),
    (
        "cleanly merged files are read too, and use up the file cap",
        HOOK,
        'paths = [p for p in theirs_changed if p in differs and "\\n" not in p][:MAX_FILES]',
        'paths = [p for p in theirs_changed if "\\n" not in p][:MAX_FILES]',
        TARGETS,
    ),
    (
        "a binary file is read as lines",
        HOOK,
        "            continue  # binary: lines mean nothing",
        "            pass  # binary: lines mean nothing",
        TARGETS,
    ),
    # ---- the cat-file reader ----
    (
        "a missing object's line is read as a header",
        HOOK,
        "contents.append(None)  # `<spec> missing`, or ambiguous: no object" + _H + "            continue",
        "contents.append(None)  # `<spec> missing`, or ambiguous: no object" + _H + "            pass",
        TARGETS,
    ),
    # ---- the message ----
    (
        "every lost line is quoted, uncapped",
        HOOK,
        "for line in lines[:MAX_LINES_SHOWN])",
        "for line in lines)",
        TARGETS,
    ),
    # ---- failing open ----
    (
        "an exception escapes main",
        HOOK,
        "    except Exception:  # noqa: BLE001 -- advisory: a failure to check is silence",
        "    except ImportError:  # noqa: BLE001 -- advisory: a failure to check is silence",
        TARGETS,
    ),
    # ---- wiring ----
    (
        "the hook runs once per wrapper part as well",
        DISPATCH,
        '"ask-destructive-git.py", "warn-lossy-merge-resolution.py"})',
        '"ask-destructive-git.py"})',
        TARGETS,
    ),
    (
        "the hook is no longer advisory, so budget pressure cannot skip it",
        DISPATCH,
        '    "warn-heredoc-escape-mangling.py",' + _D + '    "warn-lossy-merge-resolution.py",' + _D + "})",
        '    "warn-heredoc-escape-mangling.py",' + _D + "})",
        [WIRING],
    ),
    (
        "the budget table understates the hook's shared deadline",
        LIB,
        '"warn-lossy-merge-resolution.py": 4.0,',
        '"warn-lossy-merge-resolution.py": 0.0,',
        TARGETS,
    ),
]
