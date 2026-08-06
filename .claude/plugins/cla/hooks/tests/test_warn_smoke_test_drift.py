"""Tests for the warn-smoke-test-drift PreToolUse hook.

This hook holds no repo-specific facts itself (per CLAUDE.md's fact/procedure
split) — it reads them from an overlay file, `smoke-test-drift.local.md`, a
`*.local.md` leaf name (the repo-neutral overlay marker `update-cla` already
recognizes and never syncs). No overlay file means the repo hasn't configured
the check, so the hook no-ops — that is what keeps this repo (which ships no
product code) seeing no behavior change from before the parameterization.
"""

import importlib.util
import io
import json
from pathlib import Path

import pytest

_HOOK = Path(__file__).resolve().parent.parent / "warn-smoke-test-drift.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("warn_smoke_test_drift", _HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hook = _load_module()

_CONFIG_BODY = """---
component_path_substring: src/components/
component_ext: .tsx
i18n_path_substring: src/i18n/
i18n_ext: .json
smoke_test_relpath: test-app.mjs
---

Free-form notes the hook never reads.
"""


def _run(monkeypatch, tool_input: dict, cwd: Path | None = None) -> tuple[int, str]:
    payload = {"tool_input": tool_input}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    buf = io.StringIO()
    monkeypatch.setattr("sys.stdout", buf)
    if cwd is not None:
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(cwd))
    rc = hook.main()
    return rc, buf.getvalue()


@pytest.fixture
def hooks_dir_without_overlay(tmp_path, monkeypatch):
    """Point the hook's own `__file__`-derived dir at an overlay-free tmp dir."""
    fake_hook = tmp_path / "warn-smoke-test-drift.py"
    fake_hook.write_text("", encoding="utf-8")
    monkeypatch.setattr(hook, "__file__", str(fake_hook))
    return tmp_path


@pytest.fixture
def hooks_dir_with_overlay(tmp_path, monkeypatch):
    fake_hook = tmp_path / "warn-smoke-test-drift.py"
    fake_hook.write_text("", encoding="utf-8")
    (tmp_path / "smoke-test-drift.local.md").write_text(_CONFIG_BODY, encoding="utf-8")
    monkeypatch.setattr(hook, "__file__", str(fake_hook))
    return tmp_path


def test_no_overlay_file_is_a_noop(hooks_dir_without_overlay, monkeypatch):
    rc, out = _run(monkeypatch, {"file_path": "src/components/Foo.tsx", "content": "x"})
    assert rc == 0
    assert out == ""


def test_malformed_overlay_missing_a_key_is_a_noop(tmp_path, monkeypatch):
    fake_hook = tmp_path / "warn-smoke-test-drift.py"
    fake_hook.write_text("", encoding="utf-8")
    (tmp_path / "smoke-test-drift.local.md").write_text(
        "---\ncomponent_path_substring: src/components/\n---\n", encoding="utf-8"
    )
    monkeypatch.setattr(hook, "__file__", str(fake_hook))
    rc, out = _run(monkeypatch, {"file_path": "src/components/Foo.tsx", "content": "x"})
    assert rc == 0
    assert out == ""


def test_overlay_present_but_path_does_not_match_is_a_noop(hooks_dir_with_overlay, monkeypatch):
    rc, out = _run(monkeypatch, {"file_path": "src/other/Foo.ts", "content": "x"})
    assert rc == 0
    assert out == ""


def test_overlay_present_but_no_smoke_test_file_is_a_noop(
    hooks_dir_with_overlay, tmp_path, monkeypatch
):
    project = tmp_path / "project"
    project.mkdir()
    rc, out = _run(
        monkeypatch,
        {"file_path": "src/components/Foo.tsx", "content": "x"},
        cwd=project,
    )
    assert rc == 0
    assert out == ""


def test_disappearing_locator_warns(hooks_dir_with_overlay, tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "test-app.mjs").write_text(
        "await page.waitForSelector('text=Save Changes');", encoding="utf-8"
    )
    rc, out = _run(
        monkeypatch,
        {
            "file_path": "src/components/Foo.tsx",
            "old_string": "<button>Save Changes</button>",
            "new_string": "<button>Save</button>",
        },
        cwd=project,
    )
    assert rc == 0
    payload = json.loads(out)
    context = payload["hookSpecificOutput"]["additionalContext"]
    assert "Save Changes" in context
    assert "test-app.mjs" in context


def test_locator_preserved_does_not_warn(hooks_dir_with_overlay, tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "test-app.mjs").write_text(
        "await page.waitForSelector('text=Save Changes');", encoding="utf-8"
    )
    rc, out = _run(
        monkeypatch,
        {
            "file_path": "src/components/Foo.tsx",
            "old_string": "<button>Save Changes</button>",
            "new_string": "<button className=\"x\">Save Changes</button>",
        },
        cwd=project,
    )
    assert rc == 0
    assert out == ""


def test_write_mode_compares_against_on_disk_content(
    hooks_dir_with_overlay, tmp_path, monkeypatch
):
    project = tmp_path / "project"
    project.mkdir()
    (project / "test-app.mjs").write_text(
        "await page.waitForSelector('text=Delete Item');", encoding="utf-8"
    )
    component_rel = "src/components/Foo.tsx"
    component = project / "src" / "components" / "Foo.tsx"
    component.parent.mkdir(parents=True)
    component.write_text("<button>Delete Item</button>", encoding="utf-8")
    monkeypatch.chdir(project)  # so the hook's relative-path `open(path)` resolves here

    rc, out = _run(
        monkeypatch,
        {
            "file_path": component_rel,
            "content": "<button>Remove Item</button>",
        },
        cwd=project,
    )
    assert rc == 0
    payload = json.loads(out)
    assert "Delete Item" in payload["hookSpecificOutput"]["additionalContext"]


def test_malformed_stdin_fails_open(hooks_dir_with_overlay, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    buf = io.StringIO()
    monkeypatch.setattr("sys.stdout", buf)
    assert hook.main() == 0
    assert buf.getvalue() == ""
