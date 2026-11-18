"""Mutant batch for `tests/hooks/test_ask_broad_git_add.py` -- the best-effort ask
guard over a broad `git add`, in `ask-broad-git-add.py`.

Run:
    python3 plugin-tests/mutate.py plugin-tests/mutants/hooks/test_ask_broad_git_add.py

Every mutant edits the hook, never the test, and re-breaks one line the hook
added: the decision itself, each broad-form recogniser, each thing that makes an
add NOT broad, the directory the probe runs in, the parse that keeps the walk
linear, and the shared probe deadline. The two halves of the decision are both
here: a hook that never asks, and a hook that asks without an untracked file.

Deliberately absent, because no correct input can tell them from the real code:
dropping the `directory is not None` guard before `_parse_add` (a None directory
then raises inside the probe, which `main()` turns into the same silence), and
forcing `--ignored` onto every probe (without `-f`, only `??` entries are read,
so the extra `!!` lines change nothing).

The mutant on `i = max(j, i + 1)` makes the walk quadratic. It is caught by the
50,000-character step of the hostile-command test, which then takes several
seconds rather than hanging: the 400,000-character step never starts.

Paths resolve from this file's own location, never an absolute developer path.
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]          # <repo>/plugin-tests
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
HOOK = PLUGIN / "hooks" / "ask-broad-git-add.py"
GUARD = DEV / "tests" / "hooks" / "test_ask_broad_git_add.py"
TARGETS = [GUARD]

MUTANTS = [
    (
        "the hook never asks, whatever a broad add would sweep in",
        HOOK,
        "    return _ask_reason(swept) if swept else None",
        "    return None",
        TARGETS,
    ),
    (
        "the hook asks on every broad add, untracked files or not",
        HOOK,
        "    return _ask_reason(swept) if swept else None",
        "    return _ask_reason(swept)",
        TARGETS,
    ),
    (
        "-u no longer makes an add tracked-only",
        HOOK,
        "    if update or no_staging or from_file:",
        "    if no_staging or from_file:",
        TARGETS,
    ),
    (
        "-A with a named path is treated as the whole tree",
        HOOK,
        "        return None  # named paths only, with or without -A",
        "        return ([], force) if all_flag else None",
        TARGETS,
    ),
    (
        "a bare `.` is no longer a broad pathspec",
        HOOK,
        '    return rest in ("", ".", "*", "openspec")',
        '    return rest in ("", "*", "openspec")',
        TARGETS,
    ),
    (
        "a bare `openspec` is no longer a broad pathspec",
        HOOK,
        '    return rest in ("", ".", "*", "openspec")',
        '    return rest in ("", ".", "*")',
        TARGETS,
    ),
    (
        "the `:/` magic prefix is no longer read",
        HOOK,
        '    if rest.startswith(":/"):',
        "    if False:",
        TARGETS,
    ),
    (
        "an exclusion-only pathspec list no longer means the whole tree",
        HOOK,
        "    if all_flag or excludes:",
        "    if all_flag:",
        TARGETS,
    ),
    (
        "--no-ignore-removal is read as its opposite",
        HOOK,
        "                all_flag = negated",
        "                all_flag = not negated",
        TARGETS,
    ),
    (
        "an option git refuses no longer cancels the add",
        HOOK,
        "                return None  # git refuses the whole command",
        "                continue",
        TARGETS,
    ),
    (
        "-f no longer counts the ignored files it would add",
        HOOK,
        '        if "f" in letters:',
        "        if False:",
        TARGETS,
    ),
    (
        "`git -C <dir>` no longer moves the probe",
        HOOK,
        "                        directory = os.path.normpath(os.path.join(directory, value))",
        "                        directory = directory",
        TARGETS,
    ),
    (
        "`-c` no longer consumes its value, so the value reads as the subcommand",
        HOOK,
        "                if scanned_tokens[j] in _GLOBAL_VALUE_OPTS:",
        '                if scanned_tokens[j] == "-C":',
        TARGETS,
    ),
    (
        "--git-dir no longer stops the probe from guessing the repository",
        HOOK,
        "                    directory = None",
        "                    pass",
        TARGETS,
    ),
    (
        "a newline no longer ends the add's arguments",
        HOOK,
        '_SEGMENT = re.compile(r"[^&|;\\n(){}`]+")',
        '_SEGMENT = re.compile(r"[^&|;(){}`]+")',
        TARGETS,
    ),
    (
        "a backslash-continued newline ends the command instead of joining it",
        HOOK,
        '_CONTINUATION = re.compile(r"\\\\\\r?\\n")',
        '_CONTINUATION = re.compile(r"(?!)")',
        TARGETS,
    ),
    (
        "a redirection target is read as a pathspec, narrowing -A",
        HOOK,
        "                    if _REDIRECT.match(raw):",
        "                    if False:",
        TARGETS,
    ),
    (
        "a quoted -C value keeps its quotes",
        HOOK,
        "        return token[1:-1]",
        "        return token",
        TARGETS,
    ),
    (
        "the walk restarts inside a git token's options: quadratic on hostile input",
        HOOK,
        "            i = max(j, i + 1)",
        "            i += 1",
        TARGETS,
    ),
    (
        "each probe gets a fresh budget instead of what is left of one deadline",
        HOOK,
        "        entries = _status_entries(inv.directory, inv.probe_specs, inv.force, deadline - time.monotonic())",
        "        entries = _status_entries(inv.directory, inv.probe_specs, inv.force, STATUS_BUDGET_SECONDS)",
        TARGETS,
    ),
    (
        "the ask names more than ten files",
        HOOK,
        "MAX_NAMED = 10",
        "MAX_NAMED = 12",
        TARGETS,
    ),
]
