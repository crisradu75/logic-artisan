from pathlib import Path


_PLUGIN = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla"
_UNSUPPORTED_SKILLS = (
    "diagnose",
    "lite-pr",
    "multi-lite",
    "multi-pr",
    "multi-spec",
    "project-review",
    "review-change",
    "right-model",
    "save-permissions",
    "spec-to-pr",
)


# requirement: copilot-cli / Documenting Copilot CLI validation status
def test_claude_runtime_dependent_skills_are_marked_unsupported_in_copilot():
    for skill in _UNSUPPORTED_SKILLS:
        contents = (_PLUGIN / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
        assert "**Copilot CLI support: unsupported.**" in contents, skill


# requirement: copilot-cli / Documenting Copilot CLI validation status
def test_copilot_response_style_documents_runtime_specific_limits():
    contents = (_PLUGIN / "output-styles" / "COPILOT.md").read_text(encoding="utf-8")
    assert "AskUserQuestion" in contents
    assert "CLAUDE_PLUGIN_ROOT" in contents
    assert "nested `Skill(cla:...)`" in contents


# requirement: copilot-cli / Documenting Copilot CLI validation status
def test_copilot_cli_guide_documents_updates_troubleshooting_and_style_location():
    root_readme = (_PLUGIN.parents[2] / "README.md").read_text(encoding="utf-8")
    plugin_readme = (_PLUGIN / "README.md").read_text(encoding="utf-8")
    assert ".claude/plugins/cla/README.md" in root_readme
    assert "copilot plugin marketplace update cris-logic-artisan" in plugin_readme
    assert "copilot plugin update cla@cris-logic-artisan" in plugin_readme
    assert "copilot instruction list" in plugin_readme
    assert ".github/copilot-instructions.md" in plugin_readme
    assert "output-styles/COPILOT.md" in plugin_readme
    assert "After updating the plugin, refresh any copied CLA guidance" in plugin_readme
