"""The lessons log stays small: older entries live in an archive beside it.

codify-learnings greps the folder and prepends to the live log, so a live log that
holds everything is read into context in full by anyone who opens it. The rule it
states: the live log stays under 6,000 words, older entries move whole to the
archive. These tests pin the rule, that a move never duplicates an entry, and that
the entry count never drops below the 13 entries the log held when it was first split.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_DIR = _REPO / "cla.io" / "lessons-learned"
_LIVE = _DIR / "lessons-learned.md"
_ARCHIVE = _DIR / "lessons-learned-archive.md"
_SKILL = _REPO / ".claude" / "plugins" / "cla" / "skills" / "codify-learnings" / "SKILL.md"
_LIMIT = 6000
_ENTRIES_WHEN_SPLIT = 13


def _entries(path: Path) -> list[str]:
    """Whole entry texts: from each `## ` line to the next, minus the `---` separator."""
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    chunks = re.split(r"(?m)^(?=## )", text)[1:]
    return [re.sub(r"(?m)^---\s*\Z", "", c).strip() for c in chunks]


def test_the_archive_exists_and_holds_entries():
    assert _ARCHIVE.is_file()
    assert _entries(_ARCHIVE)


def test_the_live_log_is_under_the_stated_size():
    assert f"under {_LIMIT:,} words" in " ".join(_SKILL.read_text(encoding="utf-8").split())
    words = len(_LIVE.read_text(encoding="utf-8").split())
    assert words < _LIMIT, f"live log is {words} words; move its oldest entries to the archive"


def test_no_entry_is_duplicated_and_none_is_lost():
    counts = Counter(_entries(_LIVE) + _entries(_ARCHIVE))
    assert {e[:60]: n for e, n in counts.items() if n != 1} == {}
    assert sum(counts.values()) >= _ENTRIES_WHEN_SPLIT


def test_the_skill_says_the_one_grep_covers_the_archive():
    text = " ".join(_SKILL.read_text(encoding="utf-8").split())
    assert "grep -rn -i '<keyword>' cla.io/lessons-learned/" in text
    assert "also searches `cla.io/lessons-learned/lessons-learned-archive.md`" in text
