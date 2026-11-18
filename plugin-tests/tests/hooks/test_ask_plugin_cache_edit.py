"""Tests for `ask-plugin-cache-edit.py`: ask before an Edit or Write lands in an
installed plugin copy.

Every test builds a fake home, config directory or plugins root under `tmp_path`
and points `HOME` (and `USERPROFILE`, which `expanduser` reads on Windows) at it.
The four variables the hook reads are cleared first, so neither the developer's
real `~/.claude` nor the variables of the session running the suite can decide a
result. Each asking rule is pinned with a silent partner one step away from it:
`data/` beside `cache/`, a sibling `cache-old/`, a `--plugin-dir` working tree.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "hooks"
_HOOK = _HOOKS_DIR / "ask-plugin-cache-edit.py"
_DISPATCH = _HOOKS_DIR / "dispatch-edit-write-pretooluse.py"

_VARS = ("CLAUDE_CONFIG_DIR", "CLAUDE_CODE_PLUGIN_CACHE_DIR", "CLAUDE_PLUGIN_ROOT")


def _load():
    spec = importlib.util.spec_from_file_location("ask_plugin_cache_edit", _HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hook = _load()


@pytest.fixture
def home(tmp_path, monkeypatch) -> Path:
    """A fake home whose `.claude/plugins` holds one cached version, one
    marketplace clone and one data directory, as Claude Code lays them out."""
    home = tmp_path / "home"
    plugins = home / ".claude" / "plugins"
    (plugins / "cache" / "mkt" / "cla" / "2.3.0" / "skills" / "x").mkdir(parents=True)
    (plugins / "marketplaces" / "mkt" / "plugins").mkdir(parents=True)
    (plugins / "data" / "cla-mkt").mkdir(parents=True)
    for name in _VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home


def _plugins(home: Path) -> Path:
    return home / ".claude" / "plugins"


def _version(home: Path) -> Path:
    return _plugins(home) / "cache" / "mkt" / "cla" / "2.3.0"


def _payload(target, tool: str = "Write", cwd=None) -> dict:
    tool_input = {"file_path": str(target)}
    if tool == "Edit":
        tool_input.update(old_string="a", new_string="b")
    else:
        tool_input["content"] = "x\n"
    payload = {"tool_name": tool, "tool_input": tool_input}
    if cwd is not None:
        payload["cwd"] = str(cwd)
    return payload


def _run(monkeypatch, payload) -> tuple[int, str]:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr(sys, "stdin", io.StringIO(text))
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    rc = hook.main()
    return rc, out.getvalue()


def _asks(monkeypatch, payload) -> str:
    rc, out = _run(monkeypatch, payload)
    assert rc == 0, "an ask exits 0; only a block exits 2"
    nested = json.loads(out)["hookSpecificOutput"]
    assert nested["hookEventName"] == "PreToolUse"
    assert nested["permissionDecision"] == "ask"
    return nested["permissionDecisionReason"]


def _silent(monkeypatch, payload) -> None:
    rc, out = _run(monkeypatch, payload)
    assert rc == 0
    assert out == "", out


# --------------------------------------------------------------------------- #
# The two installed subtrees, for each tool the dispatcher receives
# --------------------------------------------------------------------------- #


# requirement: guard-hooks / A write into an installed plugin copy asks first
@pytest.mark.parametrize("tool", ["Edit", "Write"])
@pytest.mark.parametrize(
    "relative",
    [
        "cache/mkt/cla/2.3.0/skills/x/SKILL.md",
        "marketplaces/mkt/plugins/README.md",
    ],
)
def test_a_write_into_an_installed_subtree_asks(home, monkeypatch, tool, relative):
    reason = _asks(monkeypatch, _payload(_plugins(home) / relative, tool, cwd=home))
    assert "lost" in reason
    assert "cla.io/overlays/<skill>.md" in reason
    assert "cla.io/project-facts.md" in reason
    assert "(hook: ask-plugin-cache-edit.py)" in reason


def test_the_reason_names_the_target_and_the_installed_copy(home, monkeypatch):
    target = _version(home) / "README.md"
    reason = _asks(monkeypatch, _payload(target))
    assert str(target) in reason
    assert str(_plugins(home) / "cache") in reason


def test_the_reason_carries_none_of_the_copilot_failure_markers(home, monkeypatch):
    # The Copilot adapter turns an ask whose reason says a guard "could not run"
    # or "did not run" into a deny; this ask is a real one and has to stay one.
    reason = _asks(monkeypatch, _payload(_version(home) / "README.md")).lower()
    assert "could not run" not in reason
    assert "did not run" not in reason


# requirement: guard-hooks / A write into an installed plugin copy asks first
def test_the_plugin_data_directory_stays_silent(home, monkeypatch):
    # `${CLAUDE_PLUGIN_DATA}` is where a plugin is meant to keep state.
    _silent(monkeypatch, _payload(_plugins(home) / "data" / "cla-mkt" / "state.json"))


def test_a_sibling_whose_name_starts_like_the_subtree_stays_silent(home, monkeypatch):
    # Containment is by path component, not by string prefix.
    _silent(monkeypatch, _payload(_plugins(home) / "cache-old" / "x.md"))
    _silent(monkeypatch, _payload(_plugins(home) / "marketplaces.json"))


def test_the_plugins_root_records_stay_silent(home, monkeypatch):
    _silent(monkeypatch, _payload(_plugins(home) / "installed_plugins.json"))


# requirement: guard-hooks / A write into an installed plugin copy asks first
def test_an_ordinary_repo_file_stays_silent(home, tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _silent(monkeypatch, _payload(repo / "src" / "app.py", "Edit", cwd=repo))
    _silent(monkeypatch, _payload(home / "notes.md", cwd=repo))


# --------------------------------------------------------------------------- #
# Resolution: symlinks, `..`, relative paths, `~`
# --------------------------------------------------------------------------- #


def test_a_path_through_a_symlink_into_the_cache_asks(home, tmp_path, monkeypatch, make_dir_alias):
    alias = tmp_path / "looks-like-a-repo"
    make_dir_alias(alias, _version(home))
    _asks(monkeypatch, _payload(alias / "skills" / "x" / "SKILL.md", "Edit", cwd=tmp_path))


def test_a_dotdot_path_into_the_cache_asks(home, monkeypatch):
    sneaky = _plugins(home) / "data" / ".." / "cache" / "mkt" / "cla" / "2.3.0" / "x.md"
    _asks(monkeypatch, _payload(sneaky))


def test_a_dotdot_path_out_of_the_cache_stays_silent(home, monkeypatch):
    out = _plugins(home) / "cache" / ".." / "data" / "cla-mkt" / "state.json"
    _silent(monkeypatch, _payload(out))


def test_a_symlinked_config_directory_is_resolved_on_the_root_side(tmp_path, monkeypatch, make_dir_alias):
    # `~/.claude` kept in a dotfiles folder and linked into place: the write
    # arrives by its real path, so the roots have to be resolved too.
    home = tmp_path / "home"
    real = tmp_path / "dotfiles" / "claude"
    (real / "plugins" / "cache" / "mkt" / "cla" / "2.3.0").mkdir(parents=True)
    home.mkdir()
    make_dir_alias(home / ".claude", real)
    for name in _VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    _asks(monkeypatch, _payload(real / "plugins" / "cache" / "mkt" / "cla" / "2.3.0" / "x.md"))


def test_a_relative_path_resolves_against_the_payload_cwd(home, tmp_path, monkeypatch):
    _asks(monkeypatch, _payload("skills/x/SKILL.md", "Edit", cwd=_version(home)))
    repo = tmp_path / "repo"
    repo.mkdir()
    _silent(monkeypatch, _payload("skills/x/SKILL.md", "Edit", cwd=repo))


def test_a_relative_path_with_no_payload_cwd_uses_the_process_cwd(home, monkeypatch):
    monkeypatch.chdir(_version(home))
    _asks(monkeypatch, _payload("README.md"))


def test_a_relative_path_climbing_into_the_cache_asks(home, monkeypatch):
    _asks(monkeypatch, _payload("../cache/mkt/cla/2.3.0/x.md", cwd=_plugins(home) / "data"))


def test_a_tilde_path_is_expanded(home, monkeypatch):
    _asks(monkeypatch, _payload("~/.claude/plugins/cache/mkt/cla/2.3.0/x.md", cwd=home))


# --------------------------------------------------------------------------- #
# $CLAUDE_PLUGIN_ROOT
# --------------------------------------------------------------------------- #


# requirement: guard-hooks / A write into an installed plugin copy asks first
def test_a_plugin_dir_working_tree_stays_silent(home, tmp_path, monkeypatch):
    # `--plugin-dir`: the root is a git working tree outside every plugins root,
    # even when that tree itself sits under the home directory.
    for tree in (tmp_path / "logic-artisan", home / "code" / "logic-artisan"):
        root = tree / ".claude" / "plugins" / "cla"
        (root / "skills" / "x").mkdir(parents=True)
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(root))
        _silent(monkeypatch, _payload(root / "skills" / "x" / "SKILL.md", "Edit", cwd=tree))
        _silent(monkeypatch, _payload("hooks/hooks.json", "Write", cwd=root))


def test_other_plugins_copies_under_synced_ask(home, monkeypatch):
    _asks(monkeypatch, _payload(_plugins(home) / "synced" / "abc" / "x.md"))


def test_a_path_in_another_case_asks_on_macos_and_windows_only(home, monkeypatch):
    target = _plugins(home).parent / "Plugins" / "Cache" / "mkt" / "x.md"
    _silent(monkeypatch, _payload(str(target).replace("/plugins/", "/PLUGINS/")))
    monkeypatch.setattr(sys, "platform", "darwin")
    _asks(monkeypatch, _payload(str(target).replace("/Plugins/", "/PLUGINS/")))


# --------------------------------------------------------------------------- #
# CLAUDE_CONFIG_DIR and CLAUDE_CODE_PLUGIN_CACHE_DIR
# --------------------------------------------------------------------------- #


def test_claude_config_dir_moves_the_plugins_root(home, tmp_path, monkeypatch):
    config = tmp_path / "work-config"
    (config / "plugins" / "cache" / "m" / "p" / "1").mkdir(parents=True)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config))
    _asks(monkeypatch, _payload(config / "plugins" / "cache" / "m" / "p" / "1" / "x.md"))
    _asks(monkeypatch, _payload(config / "plugins" / "marketplaces" / "m" / "x.md"))
    _silent(monkeypatch, _payload(config / "plugins" / "data" / "p" / "x.json"))
    _silent(monkeypatch, _payload(config / "settings.json"))
    # The default root still holds installed copies, so it is still checked.
    _asks(monkeypatch, _payload(_version(home) / "x.md"))


def test_the_plugin_cache_dir_variable_is_the_whole_plugins_root(home, tmp_path, monkeypatch):
    # Despite its name it sets the parent of `cache/` and `marketplaces/`.
    root = tmp_path / "plugins-root"
    root.mkdir()
    monkeypatch.setenv("CLAUDE_CODE_PLUGIN_CACHE_DIR", str(root))
    _asks(monkeypatch, _payload(root / "cache" / "m" / "p" / "1" / "x.md"))
    _asks(monkeypatch, _payload(root / "marketplaces" / "m" / "x.md"))
    _silent(monkeypatch, _payload(root / "data" / "p" / "x.json"))
    _silent(monkeypatch, _payload(root / "x.md"))


def test_a_tilde_in_the_config_dir_is_expanded(home, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "~/alt")
    _asks(monkeypatch, _payload(home / "alt" / "plugins" / "cache" / "m" / "p" / "1" / "x.md"))


# --------------------------------------------------------------------------- #
# Fail open
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "not json",
        "[]",
        "null",
        '{"tool_input": null}',
        '{"tool_input": []}',
        '{"tool_input": {}}',
        '{"tool_input": {"file_path": 5}}',
        '{"tool_input": {"file_path": ""}}',
        '{"tool_input": {"file_path": "a\\u0000b"}}',
        "[" * 100_000 + "]" * 100_000,
    ],
)
def test_malformed_input_fails_open_silently(home, monkeypatch, raw):
    _silent(monkeypatch, raw)


def test_an_empty_file_path_is_not_read_as_the_cwd(home, monkeypatch):
    # Joined to a cwd inside the cache, "" would otherwise name the cache itself.
    _silent(monkeypatch, {"tool_input": {"file_path": ""}, "cwd": str(_version(home))})


def test_a_cache_path_with_a_bad_cwd_still_asks(home, monkeypatch):
    # A non-string `cwd` falls back to the process cwd; an absolute target does
    # not depend on it, so the ask still fires.
    payload = _payload(_version(home) / "x.md")
    payload["cwd"] = 7
    _asks(monkeypatch, payload)


def test_an_unresolvable_path_fails_open(home, monkeypatch):
    def broken(path, *a, **k):
        raise OSError("planted")

    monkeypatch.setattr(hook.os.path, "realpath", broken)
    _silent(monkeypatch, _payload(_version(home) / "x.md"))


# --------------------------------------------------------------------------- #
# Through the real dispatcher process
# --------------------------------------------------------------------------- #


def _dispatch(payload: dict, home: Path, cwd: Path, **extra: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in _VARS}
    env.update(HOME=str(home), USERPROFILE=str(home), ALLOW_WORKTREE_PATH_ESCAPE="", **extra)
    return subprocess.run(
        [sys.executable, str(_DISPATCH)],
        input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8",
        errors="replace", cwd=str(cwd), env=env, timeout=60,
    )


# requirement: guard-hooks / A write into an installed plugin copy asks first
@pytest.mark.parametrize("tool", ["Edit", "Write"])
def test_the_dispatcher_reemits_the_ask(home, tmp_path, tool):
    r = _dispatch(_payload(_version(home) / "README.md", tool, cwd=tmp_path), home, tmp_path)
    assert r.returncode == 0, r.stderr
    nested = json.loads(r.stdout)["hookSpecificOutput"]
    assert nested["permissionDecision"] == "ask"
    assert "ask-plugin-cache-edit.py" in nested["permissionDecisionReason"]


def test_the_dispatcher_keeps_an_advisory_warning_beside_the_ask(home, tmp_path):
    payload = _payload(_version(home) / "hooks" / "x.py", "Edit", cwd=tmp_path)
    payload["tool_input"]["new_string"] = "x = 1  # fixed 2026-01-01\n"
    r = _dispatch(payload, home, tmp_path)
    nested = json.loads(r.stdout)["hookSpecificOutput"]
    assert nested["permissionDecision"] == "ask"
    assert "ask-plugin-cache-edit.py" in nested["permissionDecisionReason"]
    assert "YYYY-MM-DD" in nested["additionalContext"]


def test_the_dispatcher_stays_silent_for_a_plugin_dir_tree(home, tmp_path):
    root = tmp_path / "repo" / ".claude" / "plugins" / "cla"
    root.mkdir(parents=True)
    r = _dispatch(_payload(root / "README.md", "Edit", cwd=tmp_path / "repo"), home, tmp_path,
                  CLAUDE_PLUGIN_ROOT=str(root))
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == ""
