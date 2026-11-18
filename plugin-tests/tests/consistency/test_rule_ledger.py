"""`docs/rule-ledger.md` covers every absolute rule in the shipped plugin's text.

Principle 6 of `cla.io/decisions/cla-foundation-2026-11-17.md`: each rule carries one line, its
origin and the protected area it covers, and a rule with no protected area becomes guidance or goes
on a removal list. The lines live in the ledger, not in the shipped text, so the text that loads in
every session does not grow. This test is what keeps the ledger true: a prose limit with no check
failed in every repo that had one (the same decision's evidence base).

What it checks:
- every whole word `never`, `always`, `must` or `mustn't` in a shipped prose file sits inside the fragment of
  one of that file's ledger entries, so a rule added to a line that already has an entry is caught
  (one fragment may still span two words when they belong to one rule);
- every fragment occurs in its file as many times as it has entries (once, unless the file repeats a
  rule word for word), so a reworded or deleted rule makes its entry fail;
- verdicts and areas agree: a `keep` names a protected area, `guidance` and `remove?` name `none`.

Prose files are the `.md` files and the `.json` files (whose `_comment` strings an agent reads). The
code files (`.py`, `.sh`, `.ps1`, the git hook) are not scanned: a `never` in a comment or docstring
there describes what the code below it does, and that code's own tests hold it, so a ledger line
would add a second, weaker check of the same thing.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
_PLUGIN = _REPO / ".claude" / "plugins" / "cla"
_LEDGER = _REPO / "docs" / "rule-ledger.md"

KEYWORD = re.compile(r"\b(never|always|must|mustn['\u2019]t)\b", re.IGNORECASE)
PROSE_SUFFIXES = {".md", ".json"}
VERDICTS = {"keep", "guidance", "remove?", "not-a-rule"}
PROTECTED = {
    "money", "personal data", "accessibility", "user's files", "shipped to other repos",
    "security", "safe writes", "honesty",
}
MIN_FRAGMENT = 20


def parse_ledger(text: str) -> tuple[dict[str, list[tuple[str, str, str, str]]], list[str]]:
    """Return ({path: [(verdict, area, origin, fragment), ...]}, problems)."""
    sections: dict[str, list[tuple[str, str, str, str]]] = {}
    problems: list[str] = []
    current: str | None = None
    for n, line in enumerate(text.splitlines(), 1):
        if line.startswith("## "):
            current = line[3:].strip()
            if current in sections:
                problems.append(f"line {n}: duplicate section {current}")
            sections.setdefault(current, [])
            continue
        if not line.startswith("- ") or current is None:
            continue
        parts = line[2:].split(" | ", 3)
        if len(parts) != 4:
            problems.append(f"line {n}: not `- verdict | area | origin | fragment`: {line}")
            continue
        sections[current].append(tuple(p if i == 3 else p.strip() for i, p in enumerate(parts)))
    return sections, problems


def shipped_prose() -> list[Path]:
    return sorted(p for p in _PLUGIN.rglob("*") if p.is_file() and p.suffix in PROSE_SUFFIXES)


@pytest.fixture(scope="module")
def ledger():
    sections, problems = parse_ledger(_LEDGER.read_text(encoding="utf-8"))
    assert not problems, "\n".join(problems)
    return sections


def test_the_ledger_parses_and_is_not_empty(ledger):
    assert sum(len(v) for v in ledger.values()) > 100


def test_every_section_names_a_shipped_file(ledger):
    missing = [p for p in ledger if not (_PLUGIN / p).is_file()]
    assert not missing, f"ledger sections with no such shipped file: {missing}"


def test_every_entry_has_a_valid_verdict_and_a_matching_area(ledger):
    bad = []
    for path, entries in ledger.items():
        for verdict, area, origin, fragment in entries:
            if verdict not in VERDICTS:
                bad.append(f"{path}: unknown verdict {verdict!r}: {fragment}")
            elif verdict == "keep" and area not in PROTECTED:
                bad.append(f"{path}: `keep` needs a protected area, got {area!r}: {fragment}")
            elif verdict in ("guidance", "remove?") and area != "none":
                bad.append(f"{path}: `{verdict}` guards no protected area, so area is `none`: {fragment}")
            elif verdict == "not-a-rule" and area != "-":
                bad.append(f"{path}: `not-a-rule` has area `-`: {fragment}")
            if not origin:
                bad.append(f"{path}: empty origin (write `none found` or `-`): {fragment}")
    assert not bad, "\n".join(bad)


def test_every_fragment_occurs_once_per_entry_in_its_file(ledger):
    """A fragment occurs as many times as it has entries: once, unless the file repeats a rule
    word for word (one copy per agent prompt), in which case each copy has its own entry."""
    bad = []
    for path, entries in ledger.items():
        target = _PLUGIN / path
        if not target.is_file():
            continue
        text = target.read_text(encoding="utf-8")
        wanted = Counter(e[3] for e in entries)
        for fragment, n in wanted.items():
            if len(fragment) < MIN_FRAGMENT:
                bad.append(f"{path}: fragment under {MIN_FRAGMENT} characters: {fragment!r}")
            elif "\n" in fragment or fragment != fragment.strip():
                bad.append(f"{path}: fragment must be one trimmed line: {fragment!r}")
            elif (count := text.count(fragment)) != n:
                bad.append(f"{path}: fragment occurs {count} times, {n} entries: {fragment!r}")
    assert not bad, "\n".join(bad)


def covered_keywords(line: str, fragments: list[str]) -> set[int]:
    """The start offsets of the never/always/must occurrences in `line` that a fragment spans."""
    spans = []
    for f in fragments:
        start = line.find(f)
        while start != -1:
            spans.append((start, start + len(f)))
            start = line.find(f, start + 1)
    return {m.start() for m in KEYWORD.finditer(line) if any(a <= m.start() and m.end() <= b for a, b in spans)}


def uncovered_keywords(line: str, fragments: list[str]) -> list[str]:
    """The never/always/must occurrences in `line` that no fragment found in `line` spans.

    Per word, not per line: a second rule added to a line that already has an entry needs its own
    entry, so one fragment cannot stand in for every rule on its line."""
    spans = []
    for f in fragments:
        start = line.find(f)
        while start != -1:
            spans.append((start, start + len(f)))
            start = line.find(f, start + 1)
    return [m.group(0) for m in KEYWORD.finditer(line)
            if not any(a <= m.start() and m.end() <= b for a, b in spans)]


def test_every_absolute_rule_in_the_shipped_text_has_an_entry(ledger):
    """A new never/always/must in a shipped prose file needs its ledger line in the same change."""
    missing = []
    for md in shipped_prose():
        rel = md.relative_to(_PLUGIN).as_posix()
        fragments = [e[3] for e in ledger.get(rel, [])]
        for n, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
            if words := uncovered_keywords(line, fragments):
                missing.append(f"{rel}:{n}: {', '.join(words)} not inside a fragment: {line.strip()}")
    assert not missing, (
        "lines with never/always/must and no entry in docs/rule-ledger.md "
        "(add `- verdict | area | origin | fragment` under the file's heading):\n" + "\n".join(missing)
    )


def test_no_not_a_rule_fragment_spans_a_real_rules_keyword(ledger):
    """A `not-a-rule` fragment that also covers a rule's keyword would keep the test green if that
    rule's own entry were deleted, so each keyword is covered by one kind of entry only."""
    bad = []
    for path, entries in ledger.items():
        target = _PLUGIN / path
        if not target.is_file():
            continue
        words = [e[3] for e in entries if e[0] == "not-a-rule"]
        rules = [e[3] for e in entries if e[0] != "not-a-rule"]
        for n, line in enumerate(target.read_text(encoding="utf-8").splitlines(), 1):
            if covered_keywords(line, words) & covered_keywords(line, rules):
                bad.append(f"{path}:{n}: a not-a-rule fragment spans a rule's keyword: {line.strip()}")
    assert not bad, "\n".join(bad)


def test_a_second_rule_on_an_entered_line_is_still_reported():
    line = "Never push to main, and the check must run first."
    assert uncovered_keywords(line, ["Never push to main"]) == ["must"]
    assert uncovered_keywords(line, ["Never push to main", "the check must run first"]) == []


def test_the_keyword_catches_mustnt_in_both_apostrophes():
    assert [m.group(0) for m in KEYWORD.finditer("You mustn't push; you mustn\u2019t merge.")] == ["mustn't", "mustn\u2019t"]


def test_a_json_file_is_scanned():
    assert any(p.suffix == ".json" for p in shipped_prose())


def test_the_parser_rejects_a_malformed_entry():
    sections, problems = parse_ledger("## a.md\n- keep | security | x\n")
    assert problems and not sections["a.md"]


def test_the_fragment_keeps_a_pipe_inside_it():
    sections, problems = parse_ledger("## a.md\n- keep | security | #1 | run `a | b` never twice here\n")
    assert not problems
    assert sections["a.md"][0][3] == "run `a | b` never twice here"
