"""The implementer's model is stated once, in `model-routing.md`, and every other file points there.

A re-review found three answers to one question: `model-routing.md` and spec-to-pr's Implement
delegate sent every implementer to sonnet, while the economy rules rendered into every consuming
repo sent a high-risk implementer to Opus. The one statement now sits inside the review-sizing span
of `model-routing.md`, so `/cla:cla-setup` renders the same text into a consuming repo's
`.claude/rules/cla-economy.md`, and the routing table's Implement row points at it. multi-spec's
per-change authoring dispatch, which had no row, has one, and multi-spec points at it.

The scan below reads every shipped prose file. A sentence or table row that names implementing and
a model (opus, sonnet or haiku) anywhere but the one implementer table is a second statement.
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_PLUGIN = _ROOT / ".claude" / "plugins" / "cla"
_SKILLS = _PLUGIN / "skills"
_REFS = _SKILLS / "_shared" / "references"
_ROUTING = _REFS / "model-routing.md"
_BEGIN = "<!-- economy-rules-file:review-sizing:begin -->"
_END = "<!-- economy-rules-file:review-sizing:end -->"
_HEADING = "**The implementer's model.**"
_POINTER = "The implementer's model"
_ROWS = ("| Low risk | Sonnet |", "| High risk | Opus |")

_IMPLEMENTS = re.compile(r"\bimplement(?:s|er|ers|ing)?\b|coding `Agent`|fix-delegate", re.I)
_MODEL = re.compile(r"\b(?:opus|sonnet|haiku)\b", re.I)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _implementer_block(text: str) -> str:
    """The implementer paragraph and its table, from the heading to the end of the table."""
    assert text.count(_HEADING) == 1, f"{_HEADING!r} occurs {text.count(_HEADING)} times in model-routing.md"
    start = text.index(_HEADING)
    end = text.index(_ROWS[1], start) + len(_ROWS[1])
    return text[start:end]


def units(text: str) -> list[str]:
    """Sentences of prose (whitespace collapsed, so a wrapped line is one sentence), each table
    row, and each line inside a code fence, which is a diagram or a command, not a sentence."""
    found: list[str] = []
    prose: list[str] = []
    fenced = False

    def flush() -> None:
        flat = " ".join(" ".join(prose).split())
        found.extend(s for s in re.split(r"(?<=[.!?])\s+", flat) if s)
        prose.clear()

    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            flush()
            fenced = not fenced
        elif fenced or line.lstrip().startswith("|"):
            flush()
            found.append(line)
        elif not line.strip():
            flush()
        else:
            prose.append(line)
    flush()
    return found


def second_statements(name: str, text: str) -> list[str]:
    return [f"{name}: {u.strip()[:160]}" for u in units(text) if _IMPLEMENTS.search(u) and _MODEL.search(u)]


def test_model_routing_holds_the_one_implementer_table_inside_the_rendered_span() -> None:
    """Inside the review-sizing markers, so cla-setup copies it into every consuming repo."""
    text = _read(_ROUTING)
    span = text.split(_BEGIN, 1)[1].split(_END, 1)[0]
    block = _implementer_block(span)
    for row in _ROWS:
        assert row in block, f"the implementer table lost the row {row}"
    assert "unsure means high" in " ".join(block.split())


def test_the_routing_table_points_its_implementer_row_at_the_implementer_table() -> None:
    table = _read(_ROUTING).split("## Routing table", 1)[1].split("\n## ", 1)[0].split("<!--", 1)[0]
    row = next(line for line in table.splitlines() if line.startswith("| Implement big-mechanical delegate"))
    assert f'per "{_POINTER}"' in row
    assert not _MODEL.search(row), "the routing table's implementer row states a model of its own"
    authoring = [line for line in table.splitlines() if line.startswith("| `multi-spec` Phase 3 per-change proposal authoring |")]
    assert len(authoring) == 1, "the routing table has no row for multi-spec's per-change authoring dispatch"
    assert "| opus" in authoring[0]


def test_no_other_shipped_file_states_an_implementer_model() -> None:
    hits: list[str] = []
    for path in sorted(_PLUGIN.rglob("*.md")):
        text = _read(path)
        if path == _ROUTING:
            text = text.replace(_implementer_block(text), "")
        hits += second_statements(str(path.relative_to(_PLUGIN)), text)
    assert hits == [], "a second statement of an implementer's model; point at model-routing.md's table instead:\n" + "\n".join(hits)


def test_every_implementer_site_points_at_the_table() -> None:
    for rel in (
        "spec-to-pr/SKILL.md",
        "spec-to-pr/references/implement-delegate.md",
        "spec-to-pr/references/revise.md",
        "_shared/references/runtime-rules.md",
    ):
        assert _POINTER in " ".join(_read(_SKILLS / rel).split()), f"{rel} does not point at {_POINTER!r}"
    # The rendered rules cannot name a plugin file; they name the table that renders beside them.
    for rel in ("_shared/references/economy-rules-file.md", "_shared/references/orchestration-economy.md"):
        assert "implementer table" in " ".join(_read(_SKILLS / rel).split()), f"{rel} does not point at the implementer table"


def test_multi_spec_points_its_authoring_dispatch_at_the_routing_row() -> None:
    for rel in ("multi-spec/SKILL.md", "multi-spec/references/authoring-brief.md"):
        flat = " ".join(_read(_SKILLS / rel).split())
        assert 'model: "opus"' not in flat, f"{rel} pins the authoring model itself"
        assert "`multi-spec` authoring row" in flat, f"{rel} does not point at the routing table's authoring row"


def test_the_scanner_is_not_vacuous() -> None:
    assert second_statements("s", "Dispatch ONE coding `Agent` at `model: sonnet` to do the edits.")
    assert second_statements("s", "6. **Put high-risk implementers\n   on Opus.** Others use Sonnet.")
    assert second_statements("s", "| Implement delegate | sonnet | inherited |")
    assert second_statements("s", "```\n│ IMPLEMENT │ big change → sonnet\n```")
    assert not second_statements("s", "Implement the task. Then the reviewer runs on Opus.")
    assert not second_statements("s", 'Pass the `model:` that "The implementer\'s model" gives.')
