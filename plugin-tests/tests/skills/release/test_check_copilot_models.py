"""The release check requires generated Copilot profiles to inherit the session model."""

from __future__ import annotations

import re
from pathlib import Path

import check_copilot_models as ccm
import sync_copilot_agents as sync

_REPO = Path(__file__).resolve().parents[4]
_SKILL_MD = _REPO / ".claude" / "skills" / "release" / "SKILL.md"
_AGENT = (
    '---\nname: a\ndescription: "read-only test agent"\nmodel: haiku\n'
    'tools: ["Read", "Grep"]\ncolor: blue\n---\nInstructions\n'
)


def _seed(monkeypatch, tmp_path: Path, model: str = "haiku") -> tuple[Path, Path]:
    claude, copilot = tmp_path / "agents", tmp_path / "copilot"
    claude.mkdir()
    copilot.mkdir()
    source = _AGENT.replace("model: haiku", f"model: {model}")
    (claude / "a.md").write_text(source, encoding="utf-8", newline="\n")
    (copilot / "a.agent.md").write_text(sync.render(source), encoding="utf-8", newline="\n")
    monkeypatch.setattr(sync, "CLAUDE_DIR", claude)
    monkeypatch.setattr(sync, "COPILOT_DIR", copilot)
    return claude, copilot


# requirement: copilot-cli / Copilot helper-agent profiles are validated locally
def test_release_check_accepts_session_model_inheritance(monkeypatch, tmp_path, capsys):
    _seed(monkeypatch, tmp_path)
    assert ccm.main() == ccm.EXIT_OK
    assert "inherit the session model" in capsys.readouterr().out


# requirement: copilot-cli / Copilot helper-agent profiles are validated locally
def test_release_check_rejects_an_explicit_profile_model(monkeypatch, tmp_path, capsys):
    _, copilot = _seed(monkeypatch, tmp_path)
    path = copilot / "a.agent.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            'tools: ["read", "search"]',
            'model: gpt-6-luna\ntools: ["read", "search"]',
        ),
        encoding="utf-8",
    )
    assert ccm.main() == ccm.EXIT_INVALID
    assert "explicit model pins an account-specific" in capsys.readouterr().err


# requirement: copilot-cli / Copilot helper-agent profiles are validated locally
def test_release_check_rejects_a_stale_generated_copy(monkeypatch, tmp_path, capsys):
    _, copilot = _seed(monkeypatch, tmp_path)
    path = copilot / "a.agent.md"
    path.write_text(path.read_text(encoding="utf-8") + "stale\n", encoding="utf-8")
    assert ccm.main() == ccm.EXIT_INVALID
    assert "out of step" in capsys.readouterr().err


def test_release_check_rejects_an_unmapped_source_model(monkeypatch, tmp_path, capsys):
    claude, copilot = _seed(monkeypatch, tmp_path)
    (claude / "a.md").write_text(
        _AGENT.replace("model: haiku", "model: turbo"),
        encoding="utf-8",
    )
    (copilot / "a.agent.md").unlink()
    assert ccm.main() == ccm.EXIT_CANNOT_CHECK
    assert "no Copilot session-model policy" in capsys.readouterr().err


def test_release_check_refuses_an_empty_agent_set(monkeypatch, tmp_path, capsys):
    claude, copilot = tmp_path / "agents", tmp_path / "copilot"
    claude.mkdir()
    copilot.mkdir()
    monkeypatch.setattr(sync, "CLAUDE_DIR", claude)
    monkeypatch.setattr(sync, "COPILOT_DIR", copilot)
    assert ccm.main() == ccm.EXIT_CANNOT_CHECK
    assert "no source agents found" in capsys.readouterr().err


def test_the_release_skill_runs_the_local_model_check_before_a_tag():
    body = _SKILL_MD.read_text(encoding="utf-8")
    step1 = body.split("## Step 1", 1)[1].split("## Step 2", 1)[0]
    runnable = "\n".join(
        re.findall(r"```(?:bash|sh)?\n(.*?)```", step1, re.S)
    )
    assert "python3 .claude/skills/release/scripts/check_copilot_models.py" in runnable
    table = step1.replace(runnable, "")
    assert "check_copilot_models.py" in table
    assert "inherit the session model" in table
