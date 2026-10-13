"""Mutant batch for `tests/test_project_facts_paths.py`.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/conformance/test_project_facts_paths.py

The guard was promoted out of this scope into a program at
`skills/cla-setup/scripts/check_fact_paths.py`; the tests for it stayed here.
So the mutants break the PROGRAM and the tests in this scope are the target.

Each entry breaks one branch where a wrong choice yields a SILENT CLEAN REPORT —
the failure this promotion could plausibly introduce and no green suite would
show. Two shapes:

  (i)  exit-code selection. `0` where the code returns `1`, and `1` where it
       returns `2`. A checker that answers "clean" when it found stale paths, or
       "stale paths found" when it could not look, is worse than no checker: a
       caller scripting the exit code acts on the wrong answer with confidence.
  (ii) violation accumulation. Stopping after the first stale path, or letting
       the trivial-pass branch swallow a repo that DOES have something to scan.

The last entry mutates what the promotion TOUCHED rather than what it targeted —
a carried-over extraction heuristic — because a promotion that quietly broke one
of those would pass every CLI test above it.

Paths resolve from this file's own location: a batch with an absolute developer
path works on one machine and leaks a repo name into synced core.
"""

from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
DEV = Path(__file__).resolve().parents[2]
CHECKER = PLUGIN / "skills" / "cla-setup" / "scripts" / "check_fact_paths.py"
TARGETS = [DEV / "tests" / "conformance"]
# The checker's own line ending, so an anchor spanning two lines matches on any checkout.
_NL = "\r\n" if b"\r\n" in CHECKER.read_bytes() else "\n"

MUTANTS = [
    (
        "stale paths are found but the program reports success",
        CHECKER,
        "    return EXIT_STALE",
        "    return EXIT_CLEAN",
        TARGETS,
    ),
    (
        "'I could not look' is reported as 'I found stale paths'",
        CHECKER,
        "            return EXIT_CANNOT_RUN",
        "            return EXIT_STALE",
        TARGETS,
    ),
    (
        "a broken extraction (zero candidates, facts file present) reads as clean",
        CHECKER,
        "        return EXIT_CANNOT_RUN  # branch: extraction yielded nothing",
        "        return EXIT_CLEAN  # branch: extraction yielded nothing",
        TARGETS,
    ),
    (
        "an unreadable input is reported as a staleness rather than a broken run",
        CHECKER,
        "        return EXIT_CANNOT_RUN  # branch: unreadable input",
        "        return EXIT_STALE  # branch: unreadable input",
        TARGETS,
    ),
    (
        "reporting stops at the first stale path instead of naming them all",
        CHECKER,
        '        print(f"{rel}:{lineno}  stale path {candidate!r}")',
        '        print(f"{rel}:{lineno}  stale path {candidate!r}"); break',
        TARGETS,
    ),
    (
        "the trivial-pass branch swallows a repo that DOES have files to scan",
        CHECKER,
        "    if not scanned_files:",
        "    if True:",
        TARGETS,
    ),
    (
        # IMPORTANT-2's own fix: the zero-candidates blocker used to be gated on
        # `facts_file.is_file()`, so an overlay-only repo (no facts file) that
        # extracted zero candidates exited 0 clean instead of 2. Restoring that
        # gate (using the module-level `PROJECT_FACTS_RELPATH` since the local
        # `facts_file` variable no longer exists) reverts the fix.
        "the zero-candidates blocker is re-gated on the facts file specifically",
        CHECKER,
        "    if checked == 0:",
        "    if (repo_root / PROJECT_FACTS_RELPATH).is_file() and checked == 0:",
        TARGETS,
    ),
    (
        # Anchored on the function body rather than on the regex literal. The
        # since-deleted guard `test_no_batch_hardcodes_an_absolute_path` USED TO read a
        # colon followed by a backslash as a Windows drive path, and the
        # line-suffix pattern contains exactly that pair before its digit class —
        # so quoting the pattern here tripped the guard rather than mutating the
        # code. That constraint is gone: the guard now borrows
        # `check_no_project_tokens.py`'s `WIN_ABS_PATH`, which requires a path
        # SHAPE (two separators) rather than a colon beside a backslash, so a
        # regex literal is safe to quote. This anchor is left as-is because it
        # works, not because it is still forced.
        "the carried-over `:line[:col]` strip stops removing the suffix",
        CHECKER,
        "    return _TRAILING_LINE_COL_RE.sub(\"\", token)",
        "    return token",
        TARGETS,
    ),
    (
        # Round 2: the diagnostic the test is NAMED for was never asserted — the
        # branch returns EXIT_CLEAN whether or not it prints, so deleting the
        # whole `if` survived. The test now captures stdout; this mutant is what
        # proves that.
        "the live iterdir-fallback diagnostic stops being printed",
        CHECKER,
        '    if _tracked_top_level_names(repo_root) is None and (repo_root / ".git").exists():',
        "    if False:",
        TARGETS,
    ),
    (
        # Round 2: one unreadable input used to raise out of `scan()`, discarding
        # every stale path found before it and returning 2 — a blocker outranking
        # confirmed violations. Collapsing the per-file guard back into a bare
        # read restores that inversion.
        "an unreadable input again discards the stale paths already found",
        CHECKER,
        "            unreadable.append((rel, f\"{type(exc).__name__}: {exc}\"))",
        "            raise",
        TARGETS,
    ),
    # --- machine-local skip (`_is_machine_local`, `scan`) ---
    (
        "a machine-local path is checked again, so an absent one reads stale",
        CHECKER,
        "                if _is_machine_local(candidate, tracked):",
        "                if False:",
        TARGETS,
    ),
    (
        "a TRACKED machine-local-named file is skipped like an untracked one",
        CHECKER,
        "    if tracked is None:",
        "    if True:",
        TARGETS,
    ),
    (
        "a tracked directory with a `.local` name is skipped as machine-local",
        CHECKER,
        '    return rel not in tracked and not any(p.startswith(rel + "/") for p in tracked)',
        "    return rel not in tracked",
        TARGETS,
    ),
    (
        "the machine-local test looks at every segment, not only the file name",
        CHECKER,
        '    if not _MACHINE_LOCAL_SEGMENT_RE.search(rel.rsplit("/", 1)[-1]):',
        "    if not _MACHINE_LOCAL_SEGMENT_RE.search(rel):",
        TARGETS,
    ),
    (
        "a directory named `local` is skipped as if it were machine-local",
        CHECKER,
        '_MACHINE_LOCAL_SEGMENT_RE = re.compile(r"[^/]\\.local(?:\\.|$)")',
        '_MACHINE_LOCAL_SEGMENT_RE = re.compile(r"local(?:\\.|$)")',
        TARGETS,
    ),
    (
        "a `.localized` name counts as machine-local (the tail of the pattern is dropped)",
        CHECKER,
        '_MACHINE_LOCAL_SEGMENT_RE = re.compile(r"[^/]\\.local(?:\\.|$)")',
        '_MACHINE_LOCAL_SEGMENT_RE = re.compile(r"[^/]\\.local")',
        TARGETS,
    ),
    (
        "the missing-index warning stops being printed",
        CHECKER,
        '    if _tracked_paths(repo_root) is None and (repo_root / ".git").exists():',
        "    if False:",
        TARGETS,
    ),
    # --- renamed or removed top-level directories (`_former_top_level_names`) ---
    (
        "the history walk sees only deletions, not the old side of a rename",
        CHECKER,
        '"log", "--relative", "--diff-filter=D", "--no-renames",',
        '"log", "--relative", "--diff-filter=D",',
        TARGETS,
    ),
    # No mutant drops `--diff-filter=D` from the log query: with the subtraction of
    # the current names and the staged-deletion query, listing every change returns
    # the same set (only the output size differs), so no test could tell.
    (
        "a rename or removal staged but not yet committed is not read",
        CHECKER,
        '    deleted = log.stdout.split("\\0") + staged.stdout.split("\\0")',
        '    deleted = log.stdout.split("\\0")',
        TARGETS,
    ),
    (
        "the history walk prints paths from the git top level, not the checked directory",
        CHECKER,
        '"log", "--relative", "--diff-filter=D",',
        '"log", "--diff-filter=D",',
        TARGETS,
    ),
    (
        "the staged-deletion query prints paths from the git top level",
        CHECKER,
        '"diff", "--cached", "--relative", "--diff-filter=D",',
        '"diff", "--cached", "--diff-filter=D",',
        TARGETS,
    ),
    (
        "a failed staged diff reads as no staged deletions",
        CHECKER,
        "    if staged.returncode != 0:",
        "    if False:",
        TARGETS,
    ),
    (
        "a deleted top-level FILE counts as a former directory name",
        CHECKER,
        '    names = {p.split("/", 1)[0] for p in deleted if "/" in p}',
        '    names = {p.split("/", 1)[0] for p in deleted if p}',
        TARGETS,
    ),
    (
        "a name that is a top-level entry now is also treated as former",
        CHECKER,
        "    return names - top_level_names, \"\"",
        "    return names, \"\"",
        TARGETS,
    ),
    (
        "a failed `git log` reads as an empty history instead of an unavailable one",
        CHECKER,
        "    if log.returncode != 0:",
        "    if False:",
        TARGETS,
    ),
    (
        "a shallow clone is trusted as full history",
        CHECKER,
        '        if shallow == "true":',
        "        if False:",
        TARGETS,
    ),
    (
        "a directory that is not a git repo is not told apart from one",
        CHECKER,
        '        if git("rev-parse", "--git-dir").returncode != 0:',
        "        if False:",
        TARGETS,
    ),
    (
        "a git too old to know the shallow flag is read as a full clone",
        CHECKER,
        '        if shallow != "false":',
        "        if False:",
        TARGETS,
    ),
    (
        "each git call gets the whole budget, not what is left of it",
        CHECKER,
        "timeout=max(deadline - time.monotonic(), 0.001),",
        "timeout=_HISTORY_BUDGET_SECONDS,",
        TARGETS,
    ),
    (
        "a git call past the budget is reported as git failing to run",
        CHECKER,
        "    except subprocess.TimeoutExpired:",
        "    except ZeroDivisionError:",
        TARGETS,
    ),
    (
        "git failing to run raises out of the checker",
        CHECKER,
        "    except (OSError, subprocess.SubprocessError) as exc:",
        "    except ZeroDivisionError as exc:",
        TARGETS,
    ),
    (
        "an unavailable history is no longer reported on stderr",
        CHECKER,
        "    if former_names is None:" + _NL + "        print(",
        "    if False:" + _NL + "        print(",
        TARGETS,
    ),
    (
        "an unavailable history is reported as a failed run",
        CHECKER,
        "    checked, stale, unreadable = scan(repo_root, former_names or set())",
        "    if former_names is None:" + _NL + "        return EXIT_STALE" + _NL
        + "    checked, stale, unreadable = scan(repo_root, former_names or set())",
        TARGETS,
    ),
    (
        "main stops handing the former names to the scan",
        CHECKER,
        "    checked, stale, unreadable = scan(repo_root, former_names or set())",
        "    checked, stale, unreadable = scan(repo_root, set())",
        TARGETS,
    ),
    (
        "scan stops handing the former names to the extraction",
        CHECKER,
        "            for candidate in extract_path_candidates(line, top_level_names, former_names):",
        "            for candidate in extract_path_candidates(line, top_level_names):",
        TARGETS,
    ),
    (
        "extraction stops handing the former names to the keep rule (second pass)",
        CHECKER,
        "        cleaned = _clean_candidate(raw)" + _NL + "        kept = _keep_if_path(cleaned, top_level_names, former_names)",
        "        cleaned = _clean_candidate(raw)" + _NL + "        kept = _keep_if_path(cleaned, top_level_names)",
        TARGETS,
    ),
    (
        "extraction stops handing the former names to the keep rule (backtick pass)",
        CHECKER,
        "        cleaned = _clean_candidate(match.group(1))" + _NL + "        kept = _keep_if_path(cleaned, top_level_names, former_names)",
        "        cleaned = _clean_candidate(match.group(1))" + _NL + "        kept = _keep_if_path(cleaned, top_level_names)",
        TARGETS,
    ),
    (
        "scan called alone no longer derives the former names",
        CHECKER,
        "    if former_names is None:" + _NL
        + "        former_names = _former_top_level_names(repo_root, top_level_names)[0] or set()",
        "    if former_names is None:" + _NL + "        former_names = set()",
        TARGETS,
    ),
    (
        "a never-top-level first segment is checked too (the shape-only rule that failed 3 repos)",
        CHECKER,
        "        if first_segment not in former_names:" + _NL + "            return None",
        "        if False:" + _NL + "            return None",
        TARGETS,
    ),
    (
        "a bare former directory (`docs/`) is reported",
        CHECKER,
        '        if not token.split("/", 1)[1].strip("/") or "\\\\" in token:',
        '        if "\\\\" in token:',
        TARGETS,
    ),
    (
        "a grep pattern under a former directory is reported",
        CHECKER,
        '        if not token.split("/", 1)[1].strip("/") or "\\\\" in token:',
        '        if not token.split("/", 1)[1].strip("/"):',
        TARGETS,
    ),
    (
        "every non-top-level first segment is rejected, former names included",
        CHECKER,
        "    if first_segment not in top_level_names:" + _NL + "        # A name that was",
        "    if True:" + _NL + "        return None" + _NL
        + "    if first_segment not in top_level_names:" + _NL + "        # A name that was",
        TARGETS,
    ),
]
