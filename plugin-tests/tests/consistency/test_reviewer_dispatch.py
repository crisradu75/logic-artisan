"""How the PR reviewers are dispatched: the one safeguard the plugin has for them.

CLA dispatches the `pr-review-toolkit` reviewers (`code-reviewer`, `silent-failure-hunter`,
`comment-analyzer`). Those agents hold Bash and Edit, and the toolkit's `code-reviewer` defaults to
reviewing `git diff` itself, so the prompt a dispatch site sends is all that stands between a
reviewer and `git checkout` in the owner's tree. Peer repos lost uncommitted work that way. The
rule is prose, so these tests read the prose: each dispatch site must carry the diff-review rule
verbatim (the forbidden verbs included), name the toolkit agents, and pass `model:` every time.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_PLUGIN = _ROOT / ".claude" / "plugins" / "cla"
_SKILLS = _PLUGIN / "skills"
_SITES = {
    "lite-pr Review": _SKILLS / "lite-pr" / "SKILL.md",
    "Revise": _SKILLS / "spec-to-pr" / "references" / "revise.md",
    "the shared brief": _SKILLS / "spec-to-pr" / "references" / "subagent-brief.md",
}
_ROUTING = _SKILLS / "_shared" / "references" / "model-routing.md"
_REVIEWERS = ("code-reviewer", "silent-failure-hunter", "comment-analyzer")
_VERBS = ("checkout", "switch", "stash", "reset", "clean", "commit", "branch")
_MODEL_PHRASE = "`model:` on EVERY dispatch"

# The diff-review rule. Whitespace is collapsed before comparing, so a re-wrapped line is fine and
# a changed word is not.
_RULE = (
    "Review only the change in the diff file at `<absolute path>`; run no git command (not `git diff`, "
    "and never `git checkout`, `git switch`, `git stash`, `git reset`, `git clean`, `git commit` or "
    "`git branch`) and edit, write or delete no file. Give `line` as the line number in the changed "
    "file after the change (the number after the `+` in the hunk header, counted forward through the "
    "hunk), never a line counted inside the diff file."
)


def _flat(text: str) -> str:
    return " ".join(text.split())


def site_problems(name: str, text: str, *, dispatches: bool) -> list[str]:
    """What is missing from one dispatch site's text; empty when it holds."""
    flat = _flat(text)
    found = []
    if _RULE not in flat:
        found.append(f"{name} does not carry the diff-review rule verbatim")
    if dispatches:
        found += [f"{name} does not name `pr-review-toolkit:{r}`" for r in _REVIEWERS
                  if f"`pr-review-toolkit:{r}`" not in flat]
        if _MODEL_PHRASE not in flat:
            found.append(f"{name} does not say to pass {_MODEL_PHRASE}")
    return found


# requirement: review-agents / A reviewer is dispatched with a diff file, a ban on state changes and a named model
@pytest.mark.parametrize("name", sorted(_SITES))
def test_each_dispatch_site_carries_the_rule_names_the_toolkit_agents_and_passes_a_model(name: str) -> None:
    text = _SITES[name].read_text(encoding="utf-8")
    assert site_problems(name, text, dispatches=name != "the shared brief") == []


# requirement: review-agents / A reviewer is dispatched with a diff file, a ban on state changes and a named model
def test_the_rule_names_every_state_changing_git_verb_and_forbids_edits() -> None:
    for verb in _VERBS:
        assert f"`git {verb}`" in _RULE, f"the rule does not name git {verb}"
    assert "edit, write or delete no file" in _RULE
    assert "not `git diff`" in _RULE, "the toolkit code-reviewer defaults to `git diff`; the rule must stop that"


# requirement: review-agents / A reviewer is dispatched with a diff file, a ban on state changes and a named model
def test_the_routing_guidance_says_to_pass_the_model_on_every_reviewer_dispatch() -> None:
    flat = _flat(_ROUTING.read_text(encoding="utf-8"))
    assert _MODEL_PHRASE in flat
    for reviewer in _REVIEWERS:
        assert f"`pr-review-toolkit:{reviewer}`" in flat, f"model-routing.md does not name {reviewer}"


# requirement: review-agents / A reviewer is dispatched with a diff file, a ban on state changes and a named model
def test_no_shipped_file_dispatches_or_ships_a_cla_reviewer() -> None:
    """A `cla:` reviewer name would dispatch to nothing; the removed agents must not return unnoticed."""
    stale = re.compile(r"cla:(?:%s)\b|agents/(?:%s)\b" % ("|".join(_REVIEWERS), "|".join(_REVIEWERS)))
    hits = [str(p.relative_to(_PLUGIN)) for p in sorted(_PLUGIN.rglob("*"))
            if p.is_file() and p.suffix in {".md", ".py", ".json", ".sh", ".mjs", ".yaml", ".yml"}
            and stale.search(p.read_text(encoding="utf-8", errors="replace"))]
    assert hits == [], f"shipped files still name a CLA reviewer agent: {hits}"
    for reviewer in _REVIEWERS:
        assert not (_PLUGIN / "agents" / f"{reviewer}.md").exists()
        assert not (_PLUGIN / "com.github.copilot" / "agents" / f"{reviewer}.agent.md").exists()


def test_every_agent_file_the_routing_guidance_names_exists() -> None:
    text = _ROUTING.read_text(encoding="utf-8")
    named = set(re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/agents/([A-Za-z0-9._-]+\.md)", text))
    assert named, "the routing guidance names no agent file; the test would pass on nothing"
    assert [f for f in sorted(named) if not (_PLUGIN / "agents" / f).is_file()] == []


_GOOD = "x `pr-review-toolkit:code-reviewer` `pr-review-toolkit:silent-failure-hunter` " \
        "`pr-review-toolkit:comment-analyzer` pass `model:` on EVERY dispatch. " + _RULE


def test_the_baseline_fixture_is_clean() -> None:
    assert site_problems("s", _GOOD, dispatches=True) == []


@pytest.mark.parametrize("label, text, expect", [
    ("a verb dropped", _GOOD.replace(", `git stash`", ""), "diff-review rule"),
    ("edits no longer forbidden", _GOOD.replace("edit, write or delete no file", "edit carefully"), "diff-review rule"),
    ("git diff allowed again", _GOOD.replace("(not `git diff`, and never", "(never"), "diff-review rule"),
    ("a cla: name returns", _GOOD.replace("`pr-review-toolkit:code-reviewer`", "`cla:code-reviewer`"),
     "pr-review-toolkit:code-reviewer"),
    ("the model phrase is gone", _GOOD.replace(_MODEL_PHRASE, "a model when needed"), "model:"),
])
def test_a_broken_site_is_reported(label: str, text: str, expect: str) -> None:
    assert any(expect in p for p in site_problems("s", text, dispatches=True)), label
