"""Mutant batch for the commit-honesty guards: `block-dishonest-commit.py` and
`ask-staged-debug-tag.py`. One mutant per decision line, each checked by hand.

Run:
    python3 plugin-tests/mutate.py plugin-tests/mutants/hooks/test_commit_honesty_guards.py
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]          # <repo>/plugin-tests
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
BLOCK = PLUGIN / "hooks" / "block-dishonest-commit.py"
ASK = PLUGIN / "hooks" / "ask-staged-debug-tag.py"
BLOCK_TESTS = [DEV / "tests" / "hooks" / "test_block_dishonest_commit.py"]
ASK_TESTS = [DEV / "tests" / "hooks" / "test_ask_staged_debug_tag.py"]

MUTANTS = [
    ("a Measured-by none trailer no longer blocks", BLOCK,
     "            return 2, _BLOCK_NONE", "            return 0, _BLOCK_NONE", BLOCK_TESTS),
    ("an empty review-round commit no longer blocks", BLOCK,
     "                return 2, _BLOCK_ROUND", "                return 0, _BLOCK_ROUND", BLOCK_TESTS),
    ("an empty review-round commit only warns", BLOCK,
     "            if _review_round(commit):", "            if False:", BLOCK_TESTS),
    ("an empty commit no longer warns", BLOCK,
     "            warn = True", "            warn = False", BLOCK_TESTS),
    ("a dry run is checked", BLOCK,
     "if isinstance(inv, Commit) and not inv.dry_run", "if isinstance(inv, Commit)", BLOCK_TESTS),
    ("the debug-tag hook never asks", ASK,
     "    return _ask_reason(hits) if hits else None", "    return None", ASK_TESTS),
    ("the debug-tag hook asks with no hit", ASK,
     "    return _ask_reason(hits) if hits else None", "    return _ask_reason(hits)", ASK_TESTS),
]
