"""The lessons log stays small: older entries live in an archive beside it.

codify-learnings greps the folder and prepends to the live log, so a live log that
holds everything is read into context in full by anyone who opens it. The rule it
states: the live log stays under 6,000 words, older entries move whole to the
archive. These tests pin the rule and that a move never loses or duplicates an entry.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_DIR = _REPO / "cla.io" / "lessons-learned"
_LIVE = _DIR / "lessons-learned.md"
_ARCHIVE = _DIR / "lessons-learned-archive.md"
_SKILL = _REPO / ".claude" / "plugins" / "cla" / "skills" / "codify-learnings" / "SKILL.md"
_LIMIT = 6000


def _titles(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.startswith("## ")]


def test_the_archive_exists_and_holds_entries():
    assert _ARCHIVE.is_file()
    assert _titles(_ARCHIVE)


def test_the_live_log_is_under_the_stated_size():
    assert f"under {_LIMIT:,} words" in " ".join(_SKILL.read_text(encoding="utf-8").split())
    words = len(_LIVE.read_text(encoding="utf-8").split())
    assert words < _LIMIT, f"live log is {words} words; move its oldest entries to the archive"


def test_every_entry_title_appears_exactly_once_across_both_files():
    counts = Counter(_titles(_LIVE) + _titles(_ARCHIVE))
    assert counts
    assert {t: n for t, n in counts.items() if n != 1} == {}


def test_the_skill_says_the_one_grep_covers_the_archive():
    text = " ".join(_SKILL.read_text(encoding="utf-8").split())
    assert "grep -rn -i '<keyword>' cla.io/lessons-learned/" in text
    assert "also searches `cla.io/lessons-learned/lessons-learned-archive.md`" in text
