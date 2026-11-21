"""The report-upstream skill states each outcome the upstream-reports spec requires.

Spec: openspec/specs/upstream-reports. The skill is prose, so these tests pin the text that carries
each outcome, and the one mismatch found while specifying it: the skill tells the model to write a
body file, so its frontmatter must grant a tool that writes one.
"""

from __future__ import annotations

import json
from pathlib import Path

_PLUGIN = Path(__file__).resolve().parents[4] / ".claude" / "plugins" / "cla"
_SKILL = _PLUGIN / "skills" / "report-upstream" / "SKILL.md"


def _flat() -> str:
    lines = [line.removeprefix("> ") for line in _SKILL.read_text(encoding="utf-8").splitlines()]
    return " ".join(" ".join(lines).split())


def _allowed_tools() -> list[str]:
    for line in _SKILL.read_text(encoding="utf-8").splitlines():
        if line.startswith("allowed-tools:"):
            return [tool.strip() for tool in line.split(":", 1)[1].split(",")]
    raise AssertionError("report-upstream lost its allowed-tools line")


# requirement: upstream-reports / Only a defect every repo shares is reported
def test_a_local_preference_reports_nothing_and_an_unclear_case_asks():
    text = _flat()
    assert "would **every** repo running the plugin be better off?" in text
    assert "report nothing, and change nothing" in text
    assert "cla.io/overlays/<skill>.md" in text
    assert "ask the user rather than guessing" in text


# requirement: upstream-reports / A report rests on facts read this run
def test_the_report_quotes_a_file_read_this_run_with_path_version_and_local_edits():
    text = _flat()
    assert "Read the actual core file" in text
    assert "only if you verified it **this run**" in text
    assert "exact path" in text
    assert ".claude-plugin/plugin.json" in text
    assert "local modifications" in text


# requirement: upstream-reports / The report goes where the plugin's manifest says
def test_the_target_comes_from_the_manifest_and_is_never_guessed():
    text = _flat()
    assert "`repository` field of `.claude-plugin/plugin.json`" in text
    assert "stop and ask the user" in text
    assert "Never hardcode one in this file" in text
    manifest = json.loads((_PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["repository"].startswith("https://github.com/")


# requirement: upstream-reports / A known defect gets a comment, not a second issue
def test_an_open_duplicate_gets_a_comment_and_a_closed_one_a_question():
    text = _flat()
    assert "gh issue list --repo <owner/repo> --search" in text
    assert "**add a comment**" in text
    assert "Do not open a second issue" in text
    assert "ask the user whether this is a regression before opening anything" in text


# requirement: upstream-reports / A report opens an issue and changes nothing else
def test_the_issue_has_the_required_parts_is_opened_from_a_body_file_and_ends_with_its_url():
    text = _flat()
    for part in ("**Path:**", "**Plugin version:**", "**Platform:**", "### What happens",
                 "### Why it belongs in core", "### Suggested fix"):
        assert part in text
    assert "--body-file" in text
    assert "Report the issue URL as the last line of output" in text
    assert "It does not fix anything" in text


# requirement: upstream-reports / A report opens an issue and changes nothing else
def test_the_skill_holds_a_tool_to_write_the_body_file_it_asks_for():
    assert "Write" in _allowed_tools()
    assert "Write` tool" in _flat()


# requirement: upstream-reports / Nothing is posted before the user approves the text
def test_the_draft_is_shown_and_approved_before_any_comment_or_new_issue():
    text = _flat()
    assert "Show the draft before anything is posted" in text
    assert "ask with `AskUserQuestion` whether to post it" in text
    assert "Post only on an explicit yes" in text
    assert "covers both `gh issue comment` and `gh issue create`" in text
    assert text.index("Post only on an explicit yes") < text.index("gh issue create --repo")
    assert "AskUserQuestion" in _allowed_tools()


# requirement: upstream-reports / A known defect gets a comment, not a second issue
def test_a_failed_gh_call_stops_and_the_draft_carries_no_secrets():
    text = _flat()
    assert "If `gh issue list` exits non-zero" in text and 'An error is not "no match"' in text
    assert "it carries no secret, env value, token, local absolute path or username" in text
    assert "paths relative to the plugin root" in text
    assert "only if `gh` printed one" in text
    assert "A failed `gh issue create` or `gh issue comment` shows its error and stops" in text
    assert "step 4 drafts the comment text instead of an issue" in text


# requirement: upstream-reports / A known defect gets a comment, not a second issue
def test_a_match_must_share_a_concrete_detail_and_is_shown_to_the_user():
    text = _flat()
    assert "a symbol, an error text or a file path" in text
    assert "Show each match to the user and have them confirm" in text
