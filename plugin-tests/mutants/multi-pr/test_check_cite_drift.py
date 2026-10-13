"""Mutation batch for multi-pr's check_cite_drift.py.

Each mutant breaks one judgement the checker makes: which cites it reads, how it
tells ok from drifted, gone, ambiguous and unchecked, what `--fix` rewrites and
how it writes, and when it refuses to run.

DELIBERATELY NOT MUTANTS:

  * `start < 1` and `end < start` in `judge`'s bounds check. `:0` and `5-3` slice
    to an empty block, which the all-blank check already reads as unchecked
    (with a different reason, which no test pins), so no exit code or status
    tells the two apart.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/multi-pr/test_check_cite_drift.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
SCRIPT = DEV.parent / ".claude" / "plugins" / "cla" / "skills" / "multi-pr" / "scripts" / "check_cite_drift.py"
TARGETS = [DEV / "tests" / "skills" / "multi-pr" / "test_check_cite_drift.py"]

MUTANTS = [
    # --- which cites are read
    ("every cite is read, not only those in files the merges changed", SCRIPT,
     "                if path not in changed:", "                if False:", TARGETS),
    ("a renamed file's old path is not seen as changed", SCRIPT,
     '_git(repo, "diff", "--no-renames", "--name-only", since, ref)',
     '_git(repo, "diff", "--name-only", since, ref)', TARGETS),
    ("a leading ./ is kept in the lookup path", SCRIPT,
     'path = match.group(1).removeprefix("./")', "path = match.group(1)", TARGETS),
    ("the regex requires a directory again, so root-level files are never checked", SCRIPT,
     r"((?:[\w.-]+/)*[\w.-]+", r"((?:[\w.-]+/)+[\w.-]+", TARGETS),
    # --- judging
    ("lines still in place are not recognised when they also occur elsewhere", SCRIPT,
     "    if start in places:", "    if False:", TARGETS),
    ("a block that was not unique at the start is moved anyway", SCRIPT,
     "    if len(_find(block, old)) > 1:", "    if False:", TARGETS),
    ("lines found at several places count as drifted to the first", SCRIPT,
     "    if len(places) == 1:", "    if len(places) >= 1:", TARGETS),
    ("ambiguous lines are reported as gone", SCRIPT,
     '    return ("ambiguous" if places else "gone"), None, ""', '    return "gone", None, ""', TARGETS),
    ("a cite of blank lines is judged", SCRIPT,
     "    if not any(line.strip() for line in block):", "    if False:", TARGETS),
    ("a cite of a file the change creates is judged", SCRIPT,
     "    if old is None:\n        return \"unchecked\"", "    if False:\n        return \"unchecked\"", TARGETS),
    ("a range running past the end of the file is judged on its truncated part", SCRIPT,
     "    if start < 1 or end < start or end > len(old):", "    if start < 1 or end < start:", TARGETS),
    ("a deleted file is not reported as gone", SCRIPT,
     "    if new is None:\n        return \"gone\", None, \"\"", "    if new is None:\n        return \"ok\", None, \"\"", TARGETS),
    # --- reading git and files
    ("a file absent at a ref is read with git show and fails the run", SCRIPT,
     '    if _git(repo, "cat-file", "-e", f"{ref}:{path}").returncode != 0:', "    if False:", TARGETS),
    ("a failed object read is taken for an absent file", SCRIPT,
     '        raise CannotRun(f"git show {ref}:{path} failed: {shown.stderr.strip()}")', "        return None", TARGETS),
    ("an artifact is read with newline translation, so --fix rewrites every CRLF", SCRIPT,
     '        return artifact.read_bytes().decode("utf-8")', '        return artifact.read_text(encoding="utf-8")', TARGETS),
    ("a non-UTF-8 artifact raises instead of exiting 2", SCRIPT,
     "    except (OSError, UnicodeDecodeError) as exc:\n        raise CannotRun(f\"cannot read",
     "    except OSError as exc:\n        raise CannotRun(f\"cannot read", TARGETS),
    # --- output, --fix and exit
    ("a drifted range keeps its old end line", SCRIPT,
     '(f"-{moved + end - start}" if match.group(3) else "")', '(f"-{end}" if match.group(3) else "")', TARGETS),
    ("--fix does not rewrite a drifted cite", SCRIPT,
     "                if status == \"drifted\" and fix:\n                    return new_cite",
     "                if status == \"drifted\" and fix:\n                    return cite", TARGETS),
    ("--fix rewrites gone and ambiguous cites too", SCRIPT,
     "                if status == \"drifted\" and fix:", "                if fix:", TARGETS),
    ("an unchecked cite fails the run", SCRIPT,
     "                if status == \"unchecked\":\n                    return cite\n", "", TARGETS),
    ("a gone cite exits clean", SCRIPT,
     "                needs_judging = True\n", "", TARGETS),
    ("--fix never writes the artifact", SCRIPT,
     '        if fix and "".join(out_lines) != text:', "        if False:", TARGETS),
    ("an unknown start commit is not named as such", SCRIPT,
     '        if _git(repo, "rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}").returncode != 0:',
     "        if False:", TARGETS),
    ("a change with no artifacts passes clean", SCRIPT,
     "    if not found:\n        raise CannotRun", "    if False:\n        raise CannotRun", TARGETS),
]
