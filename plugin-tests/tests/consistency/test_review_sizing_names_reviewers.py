"""The routing table names the agent file behind each reviewer the sizing table assigns.

`skills/_shared/references/model-routing.md` holds the review-sizing table (which reviewer, on
which model) and, beside it, the "Routing table" whose rows name the agent files a dispatch
resolves to. A reviewer the sizing table assigns but no routing row ties to an existing file would
dispatch to nothing, or to another plugin's agent that holds Edit and Bash.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_PLUGIN = _ROOT / ".claude" / "plugins" / "cla"
_ROUTING = _PLUGIN / "skills" / "_shared" / "references" / "model-routing.md"
_SIZING_BEGIN = "<!-- economy-rules-file:review-sizing:begin -->"
_SIZING_END = "<!-- economy-rules-file:review-sizing:end -->"
_FILE_REF = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/agents/([A-Za-z0-9._-]+\.md)")
# The shipped reviewers; a reviewer the sizing table names that is one of these must have a file.
_SHIPPED_REVIEWERS = ("code-reviewer", "silent-failure-hunter", "comment-analyzer")


def routing_files(text: str) -> list[str]:
    """The agent file names the "Routing table" section's rows name."""
    section = text.split("\n## Routing table", 1)[1].split("\n## ", 1)[0]
    return _FILE_REF.findall(section)


def sizing_reviewers(text: str) -> list[str]:
    """The shipped reviewers the sizing table's rows name."""
    table = text.split(_SIZING_BEGIN, 1)[1].split(_SIZING_END, 1)[0]
    rows = [line for line in table.splitlines() if line.startswith("|")]
    return [r for r in _SHIPPED_REVIEWERS if any(f"`{r}`" in row for row in rows)]


def problems(text: str, agents: Path) -> list[str]:
    named = routing_files(text)
    found = [f"sizing table names `{r}` but the Routing table names no `{r}.md`"
             for r in sizing_reviewers(text) if f"{r}.md" not in named]
    found += [f"Routing table names agents/{f}, which does not exist"
              for f in sorted(set(named)) if not (agents / f).is_file()]
    return found


# requirement: review-agents / Review sizing names each reviewer it uses
def test_every_reviewer_the_sizing_table_assigns_has_a_named_file() -> None:
    text = _ROUTING.read_text(encoding="utf-8")
    assert sorted(sizing_reviewers(text)) == ["code-reviewer", "comment-analyzer", "silent-failure-hunter"]
    assert problems(text, _PLUGIN / "agents") == []


_GOOD = (
    "# T\n\n## Routing table\n\n| a | b |\n|---|---|\n"
    "| x | `${CLAUDE_PLUGIN_ROOT}/agents/code-reviewer.md` |\n\n## Next\n"
    + _SIZING_BEGIN + "\n| Low risk | `code-reviewer` | Sonnet |\n" + _SIZING_END + "\n"
)


@pytest.fixture()
def agents(tmp_path: Path) -> Path:
    (tmp_path / "code-reviewer.md").write_text("x", encoding="utf-8")
    return tmp_path


def test_the_baseline_fixture_is_clean(agents: Path) -> None:
    assert problems(_GOOD, agents) == []


def test_a_reviewer_with_no_routing_row_is_reported(agents: Path) -> None:
    text = _GOOD.replace("`${CLAUDE_PLUGIN_ROOT}/agents/code-reviewer.md`", "n/a")
    assert any("names no `code-reviewer.md`" in p for p in problems(text, agents))


def test_a_routing_row_naming_a_missing_file_is_reported(agents: Path) -> None:
    text = _GOOD.replace("code-reviewer.md`", "code-reviewer.md`, `${CLAUDE_PLUGIN_ROOT}/agents/ghost.md`")
    assert any("agents/ghost.md" in p for p in problems(text, agents))


def test_a_file_named_outside_the_routing_table_does_not_count(agents: Path) -> None:
    text = _GOOD.replace("`${CLAUDE_PLUGIN_ROOT}/agents/code-reviewer.md`", "n/a").replace(
        "## Next", "## Next\n`${CLAUDE_PLUGIN_ROOT}/agents/code-reviewer.md`")
    assert any("names no `code-reviewer.md`" in p for p in problems(text, agents))
