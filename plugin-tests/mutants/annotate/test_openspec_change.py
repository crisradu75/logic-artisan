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
     '    pattern = r"(?<![\\w-])" + re.escape(name) + r"(?![\\w-])"',
     '    pattern = re.escape(name) + r"(?![\\w-])"',
     TESTS),

    ("a longer name starting with the capability counts as a mention of it",
     OC,
     '    pattern = r"(?<![\\w-])" + re.escape(name) + r"(?![\\w-])"',
     '    pattern = r"(?<![\\w-])" + re.escape(name)',
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

    ("an unreadable main spec is treated as text",
     OC,
     "        if not isinstance(base_text, str):",
     "        if False:",
     TESTS),
]
