"""Conformance guard: every shipped agent is loadable, names its model, and cannot edit or run.

An agent file with no `model` runs on whatever the caller's session uses, and one whose
`tools` list holds Edit, Write, NotebookEdit or Bash can change the tree it was sent to
read. Nothing else in the suite reads these files, so a bad one ships silently.

Stdlib only: the frontmatter reader is a deliberate subset (leading `---`, flat
`key: value` lines, an inline list for `tools`).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_AGENTS = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "agents"
_MODELS = ("haiku", "sonnet", "opus")
_FORBIDDEN_TOOLS = ("Edit", "Write", "NotebookEdit", "Bash")
_REVIEWERS = ("code-reviewer", "silent-failure-hunter", "comment-analyzer")
_ROUTING = _AGENTS.parent / "skills" / "_shared" / "references" / "model-routing.md"


def _frontmatter(text: str) -> dict[str, str] | None:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    try:
        end = lines.index("---", 1)
    except ValueError:
        return None
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        key, sep, value = line.partition(":")
        if sep and key and not key[0].isspace():
            fields[key.strip()] = value.strip()
    return fields


def problems(text: str) -> list[str]:
    """Every way one agent file breaks the contract; empty when it holds."""
    fields = _frontmatter(text)
    if fields is None:
        return ["no readable frontmatter"]
    found = [f"missing `{key}`" for key in ("name", "description") if not fields.get(key)]
    if fields.get("model") not in _MODELS:
        found.append(f"`model` must be one of {', '.join(_MODELS)}, got {fields.get('model')!r}")
    raw = fields.get("tools")
    try:
        tools = json.loads(raw) if raw else None
    except ValueError:
        tools = None
    if not isinstance(tools, list) or not tools:
        found.append("`tools` must be a non-empty list")
    else:
        # Tool names compare case-insensitively, and "*" grants every tool, the forbidden ones included.
        named = {str(t).strip().lower() for t in tools}
        found += [f"`tools` includes {t}" for t in _FORBIDDEN_TOOLS if t.lower() in named]
        if "*" in named:
            found.append("`tools` includes *, which grants every tool")
    return found


_GOOD = (
    '---\nname: x\ndescription: "d"\nmodel: sonnet\ntools: ["Read", "Grep", "Glob"]\n---\nbody\n'
)


def test_the_baseline_fixture_is_clean() -> None:
    assert problems(_GOOD) == []


@pytest.mark.parametrize(
    "label, text, expect",
    [
        ("no frontmatter", "body only\n", "no readable frontmatter"),
        ("unterminated frontmatter", "---\nname: x\n", "no readable frontmatter"),
        ("no name", _GOOD.replace("name: x\n", ""), "missing `name`"),
        ("no description", _GOOD.replace('description: "d"\n', ""), "missing `description`"),
        ("no model", _GOOD.replace("model: sonnet\n", ""), "`model` must be one of"),
        ("unknown model", _GOOD.replace("sonnet", "gpt"), "`model` must be one of"),
        ("no tools", _GOOD.replace('tools: ["Read", "Grep", "Glob"]\n', ""), "`tools` must be"),
        ("tools not a list", _GOOD.replace('["Read", "Grep", "Glob"]', "Read"), "`tools` must be"),
        ("tools a quoted string", _GOOD.replace('["Read", "Grep", "Glob"]', '"Read"'), "`tools` must be"),
        ("frontmatter not at the top", "body\n" + _GOOD, "no readable frontmatter"),
        ("empty tools", _GOOD.replace('"Read", "Grep", "Glob"', ""), "`tools` must be"),
        ("Edit tool", _GOOD.replace('"Glob"', '"Glob", "Edit"'), "`tools` includes Edit"),
        ("Write tool", _GOOD.replace('"Glob"', '"Glob", "Write"'), "`tools` includes Write"),
        ("NotebookEdit tool", _GOOD.replace('"Glob"', '"Glob", "NotebookEdit"'),
         "`tools` includes NotebookEdit"),
        ("Bash tool", _GOOD.replace('"Glob"', '"Glob", "Bash"'), "`tools` includes Bash"),
        ("lower-case bash", _GOOD.replace('"Glob"', '"Glob", "bash"'), "`tools` includes Bash"),
        ("upper-case WRITE", _GOOD.replace('"Glob"', '"Glob", "WRITE"'), "`tools` includes Write"),
        ("wildcard tool", _GOOD.replace('"Glob"', '"Glob", "*"'), "`tools` includes *"),
    ],
)
def test_a_broken_agent_file_is_reported(label: str, text: str, expect: str) -> None:
    assert any(expect in p for p in problems(text)), f"{label}: {problems(text)}"


# requirement: review-agents / The plugin ships its own read-only reviewers
@pytest.mark.parametrize("path", sorted(_AGENTS.glob("*.md")), ids=lambda p: p.name)
def test_every_shipped_agent_conforms(path: Path) -> None:
    assert problems(path.read_text(encoding="utf-8")) == [], path.name


# requirement: review-agents / The plugin ships its own read-only reviewers
@pytest.mark.parametrize("name", _REVIEWERS)
def test_each_reviewer_is_shipped(name: str) -> None:
    path = _AGENTS / f"{name}.md"
    assert path.is_file(), f"{path.name} is not shipped"
    assert (_frontmatter(path.read_text(encoding="utf-8")) or {}).get("name") == name


def _sizing_rows() -> list[tuple[str, str]]:
    """(reviewers cell, model cell) for each row of the review-sizing table, low risk first."""
    rows = []
    for line in _ROUTING.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 3 and cells[0].lower().startswith(("low risk", "high risk")):
            rows.append((cells[1], cells[2].lower()))
    return rows


def test_the_sizing_table_is_read() -> None:
    assert len(_sizing_rows()) == 3, f"expected 3 review-sizing rows in model-routing.md, got {_sizing_rows()}"


# requirement: review-agents / The plugin ships its own read-only reviewers
@pytest.mark.parametrize("name", _REVIEWERS)
def test_each_reviewers_model_is_its_lowest_sizing_row(name: str) -> None:
    """An agent file's `model:` is its default. It must be the model of the lowest-risk row
    that names it; a higher row raises it per dispatch. Otherwise a reviewer drifting from
    opus to haiku in its own file would pass every other check."""
    expected = next(model for cell, model in _sizing_rows() if f"`{name}`" in cell)
    fields = _frontmatter((_AGENTS / f"{name}.md").read_text(encoding="utf-8")) or {}
    assert fields.get("model") == expected, (
        f"{name}.md runs on {fields.get('model')!r}, but its lowest sizing row names {expected!r}"
    )
