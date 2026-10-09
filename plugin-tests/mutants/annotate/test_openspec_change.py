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
]
