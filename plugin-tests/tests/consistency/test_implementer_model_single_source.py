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

import pytest

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

# Words that name implementing work or the agent that does it. Measured on this branch's head: no
# hit outside the one implementer table (`test_no_other_shipped_file_states_an_implementer_model`).
_IMPLEMENTS = re.compile(
    r"\bimplement\w*|\bcoding\b|\bdelegate\b|fix-?(?:delegate|applier)|apply(?:ing)? (?:the |review )?fix",
    re.I,
)
# Inside a fenced diagram a box (or a step inside one, after a `↓` line) is one unit, so a box label
# on one line and a model annotation on the next are read together.
_BOX_EDGE = re.compile(r"[┌└]|^[\s│]*[↓▼][\s│]*$")
_MIN_FILES = 80
_MODEL = re.compile(r"\b(?:opus|sonnet|haiku)\b", re.I)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _implementer_block(text: str) -> str:
    """The implementer paragraph and its table, from the heading to the end of the table."""
    assert text.count(_HEADING) == 1, f"{_HEADING!r} occurs {text.count(_HEADING)} times in model-routing.md"
    start = text.index(_HEADING)
    end = text.index(_ROWS[1], start) + len(_ROWS[1])
    return text[start:end]


def _fence_units(lines: list[str]) -> list[str]:
    """A fenced block is one unit, except that a box diagram splits at each box edge and `↓` step,
    so one box's label and its annotations are read together and apart from the next box's."""
    found: list[str] = []
    part: list[str] = []
    for line in lines:
        if _BOX_EDGE.search(line):
            if part:
                found.append("\n".join(part))
            part = []
        else:
            part.append(line)
    if part:
        found.append("\n".join(part))
    return found


def units(text: str) -> list[str]:
    """Sentences of prose (whitespace collapsed, so a wrapped line is one sentence), each table
    row, and each fenced block (split per box when it is a diagram; see `_fence_units`)."""
    found: list[str] = []
    prose: list[str] = []
    fence: list[str] = []
    fenced = False

    def flush() -> None:
        flat = " ".join(" ".join(prose).split())
        found.extend(s for s in re.split(r"(?<=[.!?])\s+", flat) if s)
        prose.clear()

    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            flush()
            if fenced:
                found.extend(_fence_units(fence))
                fence.clear()
            fenced = not fenced
        elif fenced:
            fence.append(line)
        elif line.lstrip().startswith("|"):
            flush()
            found.append(line)
        elif not line.strip():
            flush()
        else:
            prose.append(line)
    flush()
    if fence:  # an unclosed fence still gets read
        found.extend(_fence_units(fence))
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
    files = sorted(_PLUGIN.rglob("*.md"))
    assert len(files) > _MIN_FILES, f"the scan read {len(files)} files; a moved plugin tree would pass on nothing"
    for path in files:
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


# The restatement this change removed from `workflow-diagram.md`: the box label is one line above
# the model annotation.
_OLD_DIAGRAM_BOX = """```
            ┌──────────────────────┐
            │  IMPLEMENT           │   post-check: openspec status --change <name> --json
            │  apply-change skill  │   ✓ artifacts ready + all ticked / ⚠ gaps (big change → sonnet delegate)
            └──────────┬───────────┘
```"""


@pytest.mark.parametrize("text", [
    "Dispatch ONE coding `Agent` at `model: sonnet` to do the edits.",
    "6. **Put high-risk implementers\n   on Opus.** Others use Sonnet.",
    "| Implement delegate | sonnet | inherited |",
    _OLD_DIAGRAM_BOX,
    "For a big change, hand it to a coding agent on sonnet.",
    "Dispatch an implementation agent at `model: sonnet`.",
    "The change is implemented by a Sonnet delegate.",
    "The fix-applier runs on sonnet.",
    "Apply review fixes with `Agent(model: sonnet)`.",
])
def test_the_scanner_catches_a_restatement(text: str) -> None:
    assert second_statements("s", text), text


@pytest.mark.parametrize("text", [
    "Implement the task. Then the reviewer runs on Opus.",
    'Pass the `model:` that "The implementer\'s model" gives.',
    "The tier is `code-reviewer` `sonnet` at low risk and `opus` at high, `silent-failure-hunter` `opus`.",
    '"it will probably get this wrong on Sonnet" justifies escalating; "it would do a bit better on Opus" does not.',
    "```\n---\nname: fact-gatherer\nmodel: haiku\ntools: [\"Read\"]\n---\n```",
    # A REVIEW box and the APPLY REVIEW FIXES step below its arrow are two units.
    "```\n│  REVIEW   │  sub-Opus + RETHINK → opus 2nd\n│     ↓     │\n│  APPLY REVIEW FIXES  │  ✓ all-applied\n```",
])
def test_the_scanner_passes_other_model_talk(text: str) -> None:
    assert not second_statements("s", text), text
