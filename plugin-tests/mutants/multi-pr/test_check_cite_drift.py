"""Mutation batch for multi-pr's check_cite_drift.py.

Each mutant breaks one judgement the checker makes: which cites it reads, how it
tells ok from drifted, gone and ambiguous, what `--fix` rewrites, and when it
refuses to run.

DELIBERATELY NOT MUTANTS:

  * The `end > len(old)` bound in `judge`. A cite past the end of the file
    slices to an empty block, which the all-blank check already reads as
    unchecked, so no input tells the two apart.
  * The directory requirement in `CITE`. A bare filename that matched would be
    looked up as a root-level path, which no chain changed in these tests; the
    behaviour is pinned by `test_cites_the_check_cannot_judge_are_left_alone`
    only through that lookup, so the mutant is equivalent here.

Run: python3 plugin-tests/mutate.py plugin-tests/mutants/multi-pr/test_check_cite_drift.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]
SCRIPT = DEV.parent / ".claude" / "plugins" / "cla" / "skills" / "multi-pr" / "scripts" / "check_cite_drift.py"
TARGETS = [DEV / "tests" / "skills" / "multi-pr" / "test_check_cite_drift.py"]

MUTANTS = [
    ("every cite is read, not only those in files the merges changed", SCRIPT,
     "                if path not in changed:", "                if False:", TARGETS),
    ("lines still in place are not recognised when they also occur elsewhere", SCRIPT,
     "    if start in places:", "    if False:", TARGETS),
    ("lines found at several places count as drifted to the first", SCRIPT,
     "    if len(places) == 1:", "    if len(places) >= 1:", TARGETS),
    ("ambiguous lines are reported as gone", SCRIPT,
     '    return ("ambiguous" if places else "gone"), None', '    return "gone", None', TARGETS),
    ("a cite of blank lines is judged", SCRIPT,
     "    if not any(line.strip() for line in block):", "    if False:", TARGETS),
    ("a cite of a file the change creates is judged", SCRIPT,
     "    if old is None or end > len(old)", "    if end > len(old)", TARGETS),
    ("a deleted file is not reported as gone", SCRIPT,
     "    if new is None:\n        return \"gone\", None", "    if new is None:\n        return \"ok\", None", TARGETS),
    ("a drifted range keeps its old end line", SCRIPT,
     '(f"-{moved + end - start}" if match.group(3) else "")', '(f"-{end}" if match.group(3) else "")', TARGETS),
    ("--fix does not rewrite a drifted cite", SCRIPT,
     "                if status == \"drifted\" and fix:\n                    return new_cite",
     "                if status == \"drifted\" and fix:\n                    return match.group(0)", TARGETS),
    ("--fix rewrites gone and ambiguous cites too", SCRIPT,
     "                if status == \"drifted\" and fix:", "                if fix:", TARGETS),
    ("a gone cite exits clean", SCRIPT,
     "                needs_judging = True\n", "", TARGETS),
    ("--fix never writes the artifact", SCRIPT,
     "            if fixed != text:", "            if False:", TARGETS),
    ("an unknown start commit is not named as such", SCRIPT,
     '        if _git(repo, "rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}").returncode != 0:',
     "        if False:", TARGETS),
    ("a change with no artifacts passes clean", SCRIPT,
     "    if not artifacts:\n        raise CannotRun", "    if False:\n        raise CannotRun", TARGETS),
]
