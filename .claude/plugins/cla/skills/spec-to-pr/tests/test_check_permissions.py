"""check_permissions.py tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import check_permissions


def _write_required(skill_dir: Path, patterns: list[str]) -> None:
    refs = skill_dir / "references"
    refs.mkdir(parents=True, exist_ok=True)
    (refs / "required-permissions.json").write_text(
        json.dumps({"permissions": {"allow": patterns}}, indent=2), encoding="utf-8")


def _setup(tmp_path: Path, monkeypatch, required: list[str], present: dict | None):
    skill_dir = tmp_path / ".claude" / "skills" / "spec-to-pr"
    skill_dir.mkdir(parents=True)
    _write_required(skill_dir, required)
    settings_path = tmp_path / ".claude" / "settings.local.json"
    if present is not None:
        settings_path.write_text(json.dumps(present, indent=2), encoding="utf-8")
    monkeypatch.setattr(check_permissions, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check_permissions, "SKILL_DIR", skill_dir)
    monkeypatch.setattr(check_permissions, "REQUIRED_PATH_DEFAULT",
                        skill_dir / "references" / "required-permissions.json")
    monkeypatch.setattr(check_permissions, "SETTINGS_PATH", settings_path)
    return settings_path


def test_check_no_settings_file(tmp_path, monkeypatch, capsys):
    _setup(tmp_path, monkeypatch, ["Bash(git *)", "Bash(python *)"], present=None)
    rc = check_permissions.cmd_check()
    assert rc == 1
    out = capsys.readouterr().out
    assert "Bash(git *)" in out


def test_check_all_present(tmp_path, monkeypatch, capsys):
    _setup(tmp_path, monkeypatch, ["Bash(git *)"],
           present={"permissions": {"allow": ["Bash(git *)"]}})
    rc = check_permissions.cmd_check()
    assert rc == 0
    assert "ok" in capsys.readouterr().out


def test_apply_writes_union(tmp_path, monkeypatch):
    settings_path = _setup(tmp_path, monkeypatch,
                            ["Bash(git *)", "Bash(python *)"],
                            present={"permissions": {"allow": ["Bash(existing *)"]}})
    rc = check_permissions.cmd_apply()
    assert rc == 0
    saved = json.loads(settings_path.read_text(encoding="utf-8"))
    assert "Bash(existing *)" in saved["permissions"]["allow"]
    assert "Bash(git *)" in saved["permissions"]["allow"]
    assert "Bash(python *)" in saved["permissions"]["allow"]


def test_apply_preserves_unrelated_top_level_keys(tmp_path, monkeypatch):
    settings_path = _setup(tmp_path, monkeypatch, ["Bash(git *)"],
                            present={"permissions": {"allow": []},
                                     "someOtherKey": {"foo": "bar"}})
    rc = check_permissions.cmd_apply()
    assert rc == 0
    saved = json.loads(settings_path.read_text(encoding="utf-8"))
    assert saved["someOtherKey"] == {"foo": "bar"}


def test_apply_additive_only(tmp_path, monkeypatch):
    settings_path = _setup(tmp_path, monkeypatch, ["Bash(git *)"],
                            present={"permissions": {"allow":
                                ["Bash(npm *)", "Bash(extra-pattern *)"]}})
    check_permissions.cmd_apply()
    saved = json.loads(settings_path.read_text(encoding="utf-8"))
    assert "Bash(npm *)" in saved["permissions"]["allow"]
    assert "Bash(extra-pattern *)" in saved["permissions"]["allow"]


def test_apply_when_permissions_key_missing(tmp_path, monkeypatch):
    """settings file with no `permissions` key at all — must add it without crashing."""
    settings_path = _setup(tmp_path, monkeypatch, ["Bash(git *)"],
                            present={"someOtherKey": "x"})
    rc = check_permissions.cmd_apply()
    assert rc == 0
    saved = json.loads(settings_path.read_text(encoding="utf-8"))
    assert "Bash(git *)" in saved["permissions"]["allow"]
    assert saved["someOtherKey"] == "x"


def test_apply_when_permissions_is_null(tmp_path, monkeypatch):
    """settings file with `permissions: null` — must coerce to dict and not crash."""
    settings_path = _setup(tmp_path, monkeypatch, ["Bash(git *)"],
                            present={"permissions": None, "someOtherKey": "x"})
    rc = check_permissions.cmd_apply()
    assert rc == 0
    saved = json.loads(settings_path.read_text(encoding="utf-8"))
    assert "Bash(git *)" in saved["permissions"]["allow"]
    assert saved["someOtherKey"] == "x"


def test_apply_when_allow_is_null(tmp_path, monkeypatch):
    """settings file with `permissions.allow: null` — must coerce to list and not crash."""
    settings_path = _setup(tmp_path, monkeypatch, ["Bash(git *)"],
                            present={"permissions": {"allow": None}})
    rc = check_permissions.cmd_apply()
    assert rc == 0
    saved = json.loads(settings_path.read_text(encoding="utf-8"))
    assert saved["permissions"]["allow"] == ["Bash(git *)"]


def test_load_settings_corrupt_json_raises_systemexit(tmp_path, monkeypatch):
    skill_dir = tmp_path / ".claude" / "skills" / "spec-to-pr"
    skill_dir.mkdir(parents=True)
    _write_required(skill_dir, ["Bash(git *)"])
    settings_path = tmp_path / ".claude" / "settings.local.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(check_permissions, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check_permissions, "SKILL_DIR", skill_dir)
    monkeypatch.setattr(check_permissions, "REQUIRED_PATH_DEFAULT",
                        skill_dir / "references" / "required-permissions.json")
    monkeypatch.setattr(check_permissions, "SETTINGS_PATH", settings_path)
    with pytest.raises(SystemExit) as exc:
        check_permissions.cmd_check()
    assert "not valid JSON" in str(exc.value)


def test_audit_covered(tmp_path, monkeypatch, capsys):
    skill_dir = tmp_path / ".claude" / "skills" / "spec-to-pr"
    skill_dir.mkdir(parents=True)
    (skill_dir / "scripts").mkdir()
    (skill_dir / "SKILL.md").write_text(
        "Run: Bash(git status) and Bash(python -m pytest tests)\n", encoding="utf-8")
    _write_required(skill_dir, ["Bash(git *)", "Bash(python *)"])
    monkeypatch.setattr(check_permissions, "SKILL_DIR", skill_dir)
    monkeypatch.setattr(check_permissions, "REQUIRED_PATH_DEFAULT",
                        skill_dir / "references" / "required-permissions.json")
    rc = check_permissions.cmd_audit()
    assert rc == 0
    assert "ok" in capsys.readouterr().out


def _setup_narrow(tmp_path: Path, monkeypatch, default_patterns: list[str],
                  narrow_patterns: list[str], present: dict | None):
    """Like `_setup` but provisions BOTH the default and narrow files so tests
    that exercise --narrow / --replace have realistic state."""
    skill_dir = tmp_path / ".claude" / "skills" / "spec-to-pr"
    refs = skill_dir / "references"
    refs.mkdir(parents=True)
    (refs / "required-permissions.json").write_text(
        json.dumps({"permissions": {"allow": default_patterns}}), encoding="utf-8")
    (refs / "required-permissions-narrow.json").write_text(
        json.dumps({"permissions": {"allow": narrow_patterns}}), encoding="utf-8")
    settings_path = tmp_path / ".claude" / "settings.local.json"
    if present is not None:
        settings_path.write_text(json.dumps(present, indent=2), encoding="utf-8")
    monkeypatch.setattr(check_permissions, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check_permissions, "SKILL_DIR", skill_dir)
    monkeypatch.setattr(check_permissions, "REQUIRED_PATH_DEFAULT",
                        refs / "required-permissions.json")
    monkeypatch.setattr(check_permissions, "REQUIRED_PATH_NARROW",
                        refs / "required-permissions-narrow.json")
    monkeypatch.setattr(check_permissions, "SETTINGS_PATH", settings_path)
    return settings_path


def test_apply_narrow_refuses_when_wildcard_already_present(tmp_path, monkeypatch, capsys):
    """The fix for the silent-failure-hunter Critical: --apply --narrow over a
    settings file that contains the wildcard default patterns must refuse rather
    than silently union both sets, leaving tightening as a no-op."""
    settings_path = _setup_narrow(
        tmp_path, monkeypatch,
        default_patterns=["Bash(git *)"],
        narrow_patterns=["Bash(git status)", "Bash(git diff *)"],
        present={"permissions": {"allow": ["Bash(git *)"]}})
    rc = check_permissions.cmd_apply(narrow=True)
    err = capsys.readouterr().err
    assert rc == 2
    assert "refusing" in err
    assert "Bash(git *)" in err  # tells the user which patterns are blocking
    # Settings file untouched.
    saved = json.loads(settings_path.read_text(encoding="utf-8"))
    assert saved["permissions"]["allow"] == ["Bash(git *)"]


def test_apply_narrow_replace_drops_wildcards_then_adds_narrow(tmp_path, monkeypatch, capsys):
    """--apply --narrow --replace: removes any wildcard-default patterns AND
    adds the narrow set in one transaction. Tightening actually takes effect."""
    settings_path = _setup_narrow(
        tmp_path, monkeypatch,
        default_patterns=["Bash(git *)", "Bash(gh *)"],
        narrow_patterns=["Bash(git status)", "Bash(git diff *)"],
        present={"permissions": {"allow": ["Bash(git *)", "Bash(gh *)", "Bash(unrelated *)"]}})
    rc = check_permissions.cmd_apply(narrow=True, replace=True)
    assert rc == 0
    saved = json.loads(settings_path.read_text(encoding="utf-8"))
    allow = set(saved["permissions"]["allow"])
    # Wildcard defaults removed:
    assert "Bash(git *)" not in allow
    assert "Bash(gh *)" not in allow
    # Narrow set added:
    assert "Bash(git status)" in allow
    assert "Bash(git diff *)" in allow
    # Unrelated existing pattern preserved:
    assert "Bash(unrelated *)" in allow
    out = capsys.readouterr().out
    assert "- Bash(git *)" in out  # diff output shows what was removed
    assert "+ Bash(git status)" in out


def test_apply_narrow_no_wildcards_present_proceeds_normally(tmp_path, monkeypatch):
    """--apply --narrow on a clean (or wildcard-free) settings file: just adds
    the narrow set. Refusal logic only triggers when wildcards are present."""
    settings_path = _setup_narrow(
        tmp_path, monkeypatch,
        default_patterns=["Bash(git *)"],
        narrow_patterns=["Bash(git status)"],
        present={"permissions": {"allow": []}})
    rc = check_permissions.cmd_apply(narrow=True)
    assert rc == 0
    saved = json.loads(settings_path.read_text(encoding="utf-8"))
    assert "Bash(git status)" in saved["permissions"]["allow"]


def test_narrow_loads_alternate_pattern_set(tmp_path, monkeypatch, capsys):
    """`--narrow` reads required-permissions-narrow.json instead of the default."""
    skill_dir = tmp_path / ".claude" / "skills" / "spec-to-pr"
    refs = skill_dir / "references"
    refs.mkdir(parents=True)
    (refs / "required-permissions.json").write_text(
        json.dumps({"permissions": {"allow": ["Bash(git *)"]}}), encoding="utf-8")
    (refs / "required-permissions-narrow.json").write_text(
        json.dumps({"permissions": {"allow": ["Bash(git status)"]}}), encoding="utf-8")
    settings_path = tmp_path / ".claude" / "settings.local.json"
    monkeypatch.setattr(check_permissions, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check_permissions, "SKILL_DIR", skill_dir)
    monkeypatch.setattr(check_permissions, "REQUIRED_PATH_DEFAULT",
                        refs / "required-permissions.json")
    monkeypatch.setattr(check_permissions, "REQUIRED_PATH_NARROW",
                        refs / "required-permissions-narrow.json")
    monkeypatch.setattr(check_permissions, "SETTINGS_PATH", settings_path)
    rc = check_permissions.cmd_check(narrow=True)
    out = capsys.readouterr().out
    assert rc == 1
    assert "Bash(git status)" in out
    assert "Bash(git *)" not in out  # narrow mode must NOT use the default file


def test_audit_uncovered(tmp_path, monkeypatch, capsys):
    skill_dir = tmp_path / ".claude" / "skills" / "spec-to-pr"
    skill_dir.mkdir(parents=True)
    (skill_dir / "scripts").mkdir()
    (skill_dir / "SKILL.md").write_text(
        "Run: Bash(unknownTool subcommand)\n", encoding="utf-8")
    _write_required(skill_dir, ["Bash(git *)"])
    monkeypatch.setattr(check_permissions, "SKILL_DIR", skill_dir)
    monkeypatch.setattr(check_permissions, "REQUIRED_PATH_DEFAULT",
                        skill_dir / "references" / "required-permissions.json")
    rc = check_permissions.cmd_audit()
    assert rc == 1
    out = capsys.readouterr().out
    assert "uncovered" in out
    assert "unknownTool" in out
