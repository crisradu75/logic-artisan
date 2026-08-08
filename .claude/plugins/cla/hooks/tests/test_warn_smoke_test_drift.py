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


# --------------------------------------------------------------------------- #
# Absent vs broken: silence is reserved for "this repo never opted in"
#
# A present-but-broken overlay used to be indistinguishable from no overlay at
# all, so a typo disabled the check permanently and silently. The repo stated
# intent by creating the file; a config it cannot use must say so.
# --------------------------------------------------------------------------- #


def _write_overlay(tmp_path, body: str, monkeypatch):
    fake_hook = tmp_path / "warn-smoke-test-drift.py"
    fake_hook.write_text("", encoding="utf-8")
    (tmp_path / "smoke-test-drift.local.md").write_text(body, encoding="utf-8")
    monkeypatch.setattr(hook, "__file__", str(fake_hook))
    return tmp_path


def test_an_absent_overlay_stays_completely_silent(hooks_dir_without_overlay, monkeypatch, capsys):
    _run(monkeypatch, {"file_path": "src/components/Foo.tsx", "content": "x"})
    assert capsys.readouterr().err == "", "not opting in must produce no noise"


@pytest.mark.parametrize(
    "body, expected_fragment",
    [
        ("---\ncomponent_path_substring: src/components/\n---\n", "missing"),
        ("no frontmatter at all\n", "frontmatter"),
        ("---\ncomponent_path_substring: src/components/\n", "closing"),
        # Present-but-EMPTY value: a distinct path from a missing key.
        (
            "---\ncomponent_path_substring: src/components/\ncomponent_ext:\n"
            "i18n_path_substring: src/i18n/\ni18n_ext: .json\n"
            "smoke_test_relpath: test-app.mjs\n---\n",
            "component_ext",
        ),
    ],
)
def test_a_broken_overlay_warns_rather_than_vanishing(
    body, expected_fragment, tmp_path, monkeypatch, capsys
):
    _write_overlay(tmp_path, body, monkeypatch)
    rc, out = _run(monkeypatch, {"file_path": "src/components/Foo.tsx", "content": "x"})
    assert rc == 0, "still fails open — a guard must never wedge the workflow"
    assert out == "", "a broken config produces no finding, only a warning"
    err = capsys.readouterr().err
    assert "warn" in err.lower()
    assert expected_fragment in err


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


# --------------------------------------------------------------------------- #
# AA-6 -- three defects in one hook, reported by a consuming repo
# --------------------------------------------------------------------------- #


def test_a_windows_absolute_path_still_matches_a_posix_authored_overlay(
    hooks_dir_with_overlay, tmp_path, monkeypatch
):
    """The hook was ENTIRELY dead on Windows, and said nothing about it.

    Edit/Write supply an ABSOLUTE `file_path`; its native Windows form is
    backslashed, so a substring test against a POSIX-authored overlay value
    (`src/i18n/`) never matched and no edit on that platform ever reached the
    locator comparison. Overlays stay POSIX-authored; the path is normalized."""
    repo = tmp_path / "repo"
    (repo / "src" / "i18n").mkdir(parents=True)
    (repo / "test-app.mjs").write_text("page.locator('text=Total reach')\n", encoding="utf-8")
    f = repo / "src" / "i18n" / "en.json"
    f.write_text('{"a": "Total reach"}', encoding="utf-8")

    windows_style = str(f).replace("/", "\\")
    rc, out = _run(
        monkeypatch,
        {"file_path": windows_style, "old_string": "Total reach", "new_string": "Total audience"},
        cwd=repo,
    )
    assert rc == 0
    assert "Total reach" in out, "a backslashed absolute path must still be checked"


def test_has_text_locators_are_harvested_including_apostrophes(
    hooks_dir_with_overlay, tmp_path, monkeypatch
):
    """`has-text(...)` is the form a smoke test uses for the elements it CLICKS,
    so harvesting only `text=` exempted the strings without which the script
    cannot advance.

    Matched with a quoted BACKREFERENCE, not a `[^"']+` class: a class cannot
    cross either quote, so an apostrophe in ordinary UI copy truncates the
    locator and silently re-opens the same gap. Measured: the naive class
    harvests 1 of these 3."""
    repo = tmp_path / "repo"
    (repo / "src" / "components").mkdir(parents=True)
    (repo / "test-app.mjs").write_text(
        "page.click(`button:has-text(\"What's included\")`)\n"
        "page.click(\"button:has-text('Next step')\")\n",
        encoding="utf-8",
    )
    f = repo / "src" / "components" / "Panel.tsx"
    f.write_text("<b>What's included</b><i>Next step</i>", encoding="utf-8")

    rc, out = _run(
        monkeypatch,
        {
            "file_path": str(f),
            "old_string": "What's included",
            "new_string": "What is included",
        },
        cwd=repo,
    )
    assert rc == 0
    # Parse rather than substring-match: the hook emits JSON, which escapes the
    # curly apostrophe as \u2019, so a raw-text search silently never matches.
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    assert "What's included" in ctx, "apostrophe locator was dropped"


def test_an_unreadable_smoke_test_is_announced(
    hooks_dir_with_overlay, tmp_path, monkeypatch, capsys
):
    """`smoke_test_relpath` was the one overlay key never validated for effect.
    The module's own policy says a typo that silently disables the check forever
    is the worse outcome -- applied to a missing frontmatter KEY, but not to a
    missing FILE."""
    repo = tmp_path / "repo"
    (repo / "src" / "i18n").mkdir(parents=True)
    f = repo / "src" / "i18n" / "en.json"
    f.write_text('{"a": "x"}', encoding="utf-8")  # note: no test-app.mjs

    rc, _ = _run(
        monkeypatch,
        {"file_path": str(f), "old_string": "x", "new_string": "y"},
        cwd=repo,
    )
    assert rc == 0
    assert "not readable" in capsys.readouterr().err
