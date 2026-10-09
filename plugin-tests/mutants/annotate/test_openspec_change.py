"""Mutants for the change model in openspec_change.py.

    python3 plugin-tests/mutate.py plugin-tests/mutants/annotate/test_openspec_change.py
"""
from pathlib import Path

DEV = Path(__file__).resolve().parents[2]                 # <repo>/plugin-tests
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
OC = PLUGIN / "skills" / "annotate" / "scripts" / "openspec_change.py"
TESTS = [DEV / "tests" / "skills" / "annotate" / "test_openspec_change.py",
         DEV / "tests" / "skills" / "annotate" / "test_review_findings.py"]

MUTANTS = [
    # ------------------------------------------------ a capability mentioned
    ("a capability the proposal mentions is never counted as named",
     OC,
     '    return re.search(pattern, text or "", re.I) is not None',
     "    return False",
     TESTS),

    ("a longer name ending in the capability counts as a mention of it",
     OC,
     '    pattern = r"(?<![\\w/-])" + re.escape(name) + r"(?![\\w/-])"',
     '    pattern = re.escape(name) + r"(?![\\w/-])"',
     TESTS),

    ("a longer name starting with the capability counts as a mention of it",
     OC,
     '    pattern = r"(?<![\\w/-])" + re.escape(name) + r"(?![\\w/-])"',
     '    pattern = r"(?<![\\w/-])" + re.escape(name)',
     TESTS),

    ("the last segment of a capability path counts as a mention of another one",
     OC,
     '    pattern = r"(?<![\\w/-])" + re.escape(name) + r"(?![\\w/-])"',
     '    pattern = r"(?<![\\w-])" + re.escape(name) + r"(?![\\w/-])"',
     TESTS),

    ("the first segment of a capability path counts as a mention of another one",
     OC,
     '    pattern = r"(?<![\\w/-])" + re.escape(name) + r"(?![\\w/-])"',
     '    pattern = r"(?<![\\w/-])" + re.escape(name) + r"(?![\\w-])"',
     TESTS),

    # ------------------------------------------------ OpenSpec 1.14 shapes
    ("a nested capability path gets no file, as before",
     OC,
     '        if "spec.md" in names and os.path.abspath(dirpath) != os.path.abspath(specs):',
     '        if "spec.md" in names and os.path.dirname(os.path.abspath(dirpath))'
     ' == os.path.abspath(specs):',
     TESTS),

    ("a box with a space before its x is not done",
     OC,
     '                          done=m.group(1).strip().lower() == "x", group=group))',
     '                          done=m.group(1).lower() == "x", group=group))',
     TESTS),

    ("only [ ], [x] and [X] are tasks again",
     OC,
     'TASK_RE = re.compile(r"^\\s*[-*]\\s*\\[(\\s*\\S?\\s*)\\](?!\\()',
     'TASK_RE = re.compile(r"^\\s*[-*]\\s*\\[( |x|X)\\](?!\\()',
     TESTS),

    ("a bullet opening with a link reads as a task",
     OC,
     'TASK_RE = re.compile(r"^\\s*[-*]\\s*\\[(\\s*\\S?\\s*)\\](?!\\()',
     'TASK_RE = re.compile(r"^\\s*[-*]\\s*\\[(\\s*\\S?\\s*)\\]',
     TESTS),

    ("a box under Workflow follow-up is counted as a task",
     OC,
     "        if group.lower() in UNTRACKED_TASK_SECTIONS:",
     "        if False:",
     TESTS),

    ("a mention only counts in the exact case the heading spells",
     OC,
     '    return re.search(pattern, text or "", re.I) is not None',
     '    return re.search(pattern, text or "", 0) is not None',
     TESTS),

    # ------------------------------------------------ requirement diffs
    ("a diff deletes the new words and inserts the main spec's",
     OC,
     '        rec["state"], rec["ops"] = "diff", _word_ops(base[1], new)',
     '        rec["state"], rec["ops"] = "diff", _word_ops(new, base[1])',
     TESTS),

    ("an archived change is compared against the main spec it already wrote",
     OC,
     "        if archived:",
     "        if False:",
     TESTS),

    ("a long unchanged run is never collapsed",
     OC,
     "            if len(run) <= DIFF_COLLAPSE:",
     "            if True:",
     TESTS),

    ("a MODIFIED header matches the main spec in any case",
     OC,
     '    return " ".join(name.split())',
     '    return " ".join(name.lower().split())',
     TESTS),

    ("a MODIFIED header matches the main spec only with identical spacing",
     OC,
     '    return " ".join(name.split())',
     "    return name",
     TESTS),

    ("a requirement's diff stops at its first scenario",
     OC,
     '_BODY_END_RE = re.compile(r"^#{2,3}\\s")',
     '_BODY_END_RE = re.compile(r"^#{2,4}\\s")',
     TESTS),

    ("an unreadable main spec is treated as text",
     OC,
     "        if not isinstance(base_text, str):",
     "        if False:",
     TESTS),
]
