"""Tests for the warn-lint-on-edit PostToolUse hook.

Unit-tests the pure pieces (`_find_linter`, `_run_oxlint`, `_format_diagnostics`)
and `main()`'s fail-open behavior on odd payloads and non-lintable files. The
live oxlint subprocess is never invoked; `_run_oxlint`'s subprocess call is
exercised via a monkeypatched `subprocess.run`, and `main()`'s happy path via
monkeypatched `_find_linter`/`_run_oxlint`.
"""

import importlib.util
import io
import json
from pathlib import Path

_HOOK = Path(__file__).resolve().parent.parent / "warn-lint-on-edit.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("warn_lint_on_edit", _HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hook = _load_module()


# --------------------------------------------------------------------------- #
# _find_linter -- walk up to the nearest package with an oxlint binary
# --------------------------------------------------------------------------- #

def _make_bin(pkg_dir: Path) -> Path:
    bin_dir = pkg_dir / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    # Match whatever the running platform looks for first.
    name = hook._binary_candidates()[0]
    binp = bin_dir / name
    binp.write_text("", encoding="utf-8")
    return binp


def test_finds_oxlint_in_the_files_own_package(tmp_path):
    pkg = tmp_path / "apps" / "demo"
    pkg.mkdir(parents=True)
    binp = _make_bin(pkg)
    src = pkg / "src"
    src.mkdir()
    f = src / "App.tsx"
    f.write_text("", encoding="utf-8")

    found = hook._find_linter(f, tmp_path)
    assert found is not None
    package_dir, oxlint_bin = found
    assert package_dir == pkg
    assert oxlint_bin == binp


def test_finds_nearest_package_when_nested(tmp_path):
    # An outer and an inner package each with a bin; the inner (nearest) wins.
    outer = tmp_path / "repo"
    outer.mkdir()
    _make_bin(outer)
    inner = outer / "apps" / "demo"
    inner.mkdir(parents=True)
    inner_bin = _make_bin(inner)
    f = inner / "src" / "a.ts"
    f.parent.mkdir()
    f.write_text("", encoding="utf-8")

    package_dir, oxlint_bin = hook._find_linter(f, tmp_path)
    assert package_dir == inner
    assert oxlint_bin == inner_bin


def test_returns_none_when_no_oxlint_anywhere(tmp_path):
    f = tmp_path / "loose.ts"
    f.write_text("", encoding="utf-8")
    assert hook._find_linter(f, tmp_path) is None


def test_walk_stops_at_ceiling(tmp_path):
    # The bin lives ABOVE the ceiling, so the bounded walk must not find it.
    _make_bin(tmp_path)
    ceiling = tmp_path / "sub"
    ceiling.mkdir()
    f = ceiling / "x.ts"
    f.write_text("", encoding="utf-8")
    assert hook._find_linter(f, ceiling) is None


# --------------------------------------------------------------------------- #
# _run_oxlint -- subprocess wrapper (subprocess.run monkeypatched)
# --------------------------------------------------------------------------- #

class _FakeProc:
    def __init__(self, stdout):
        self.stdout = stdout
        self.stderr = ""
        self.returncode = 1  # oxlint returns non-zero even on clean/empty runs


def test_run_oxlint_parses_diagnostics(monkeypatch, tmp_path):
    diags = [{"severity": "error", "message": "boom", "labels": []}]
    monkeypatch.setattr(
        hook.subprocess, "run",
        lambda *a, **kw: _FakeProc(json.dumps({"diagnostics": diags})),
    )
    out = hook._run_oxlint(tmp_path / "oxlint", tmp_path, tmp_path / "src" / "a.ts")
    assert out == diags


def test_run_oxlint_returns_none_on_non_json(monkeypatch, tmp_path):
    monkeypatch.setattr(hook.subprocess, "run", lambda *a, **kw: _FakeProc("not json"))
    assert hook._run_oxlint(tmp_path / "oxlint", tmp_path, tmp_path / "a.ts") is None


def test_run_oxlint_returns_none_on_subprocess_error(monkeypatch, tmp_path):
    def _raise(*a, **kw):
        raise OSError("oxlint not found")
    monkeypatch.setattr(hook.subprocess, "run", _raise)
    assert hook._run_oxlint(tmp_path / "oxlint", tmp_path, tmp_path / "a.ts") is None


def test_run_oxlint_returns_none_when_diagnostics_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(hook.subprocess, "run", lambda *a, **kw: _FakeProc("{}"))
    assert hook._run_oxlint(tmp_path / "oxlint", tmp_path, tmp_path / "a.ts") is None


def test_run_oxlint_returns_none_on_non_object_payload(monkeypatch, tmp_path):
    # Valid JSON that is a bare array/scalar (oxlint version/mode drift) must NOT
    # crash `.get` — the guard turns it into a silent None, not an AttributeError.
    for body in ("[]", "5", '"x"'):
        monkeypatch.setattr(hook.subprocess, "run", lambda *a, _b=body, **kw: _FakeProc(_b))
        assert hook._run_oxlint(tmp_path / "oxlint", tmp_path, tmp_path / "a.ts") is None


def test_run_oxlint_returns_none_when_diagnostics_not_a_list(monkeypatch, tmp_path):
    monkeypatch.setattr(hook.subprocess, "run", lambda *a, **kw: _FakeProc('{"diagnostics": {"a": 1}}'))
    assert hook._run_oxlint(tmp_path / "oxlint", tmp_path, tmp_path / "a.ts") is None


def test_run_oxlint_invokes_with_json_flag_relpath_and_pkg_cwd(monkeypatch, tmp_path):
    # Lock the cross-platform contract the whole hook exists for: absolute binary,
    # `-f json`, the file passed RELATIVE to the package, and cwd = package dir.
    captured = {}

    def _capture(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["cwd"] = kwargs.get("cwd")
        return _FakeProc('{"diagnostics": []}')

    monkeypatch.setattr(hook.subprocess, "run", _capture)
    pkg = tmp_path / "apps" / "demo"
    binp = pkg / "node_modules" / ".bin" / "oxlint"
    hook._run_oxlint(binp, pkg, pkg / "src" / "a.ts")

    assert captured["cmd"] == [str(binp), "-f", "json", "src/a.ts"]
    assert captured["cwd"] == str(pkg)


def test_run_oxlint_falls_back_to_str_path_when_file_outside_package(monkeypatch, tmp_path):
    # A file not under package_dir can't be made relative — the ValueError branch
    # passes the path through as-is rather than crashing.
    captured = {}

    def _capture(cmd, **kwargs):
        captured["cmd"] = cmd
        return _FakeProc('{"diagnostics": []}')

    monkeypatch.setattr(hook.subprocess, "run", _capture)
    pkg = tmp_path / "pkg"
    outside = tmp_path / "elsewhere" / "a.ts"
    hook._run_oxlint(pkg / "oxlint", pkg, outside)
    assert captured["cmd"][-1] == str(outside)


# --------------------------------------------------------------------------- #
# _format_diagnostics
# --------------------------------------------------------------------------- #

def test_format_includes_severity_location_and_message():
    diags = [{
        "severity": "error",
        "message": "Identifier `x` has already been declared",
        "labels": [{"span": {"line": 2, "column": 7}}],
    }]
    msg = hook._format_diagnostics(diags, "apps/demo/src/a.ts")
    assert "apps/demo/src/a.ts" in msg
    assert "[error]" in msg
    assert "L2:C7" in msg
    assert "already been declared" in msg
    assert "advisory, not a block" in msg


def test_format_caps_and_counts_overflow():
    diags = [{"severity": "warning", "message": f"m{i}", "labels": []} for i in range(hook._MAX_DIAGS + 3)]
    msg = hook._format_diagnostics(diags, "a.ts")
    assert "…and 3 more" in msg
    assert f"found {hook._MAX_DIAGS + 3} issue(s)" in msg


def test_format_omits_location_when_no_span():
    # A diagnostic with empty labels (no span) renders its message with NO L/C
    # prefix — never `LNone` or a stray colon.
    msg = hook._format_diagnostics([{"severity": "warning", "message": "m0", "labels": []}], "a.ts")
    assert "  [warning] m0" in msg
    assert "L" not in msg.split("m0")[0].split("[warning]")[1]  # nothing between severity and message


def test_format_omits_column_when_line_present_but_column_missing():
    # Must read `L5`, never the literal `L5:CNone`.
    diags = [{"severity": "error", "message": "boom", "labels": [{"span": {"line": 5}}]}]
    msg = hook._format_diagnostics(diags, "a.ts")
    assert "L5 " in msg
    assert "CNone" not in msg
    assert "L5:C" not in msg


def test_format_survives_null_span_and_non_dict_diag():
    # A `{"span": null}` label and a non-dict diagnostic element must neither crash
    # nor emit a bogus location (fail-open shape tolerance for oxlint drift).
    diags = ["not-a-dict", {"severity": "error", "message": "boom", "labels": [{"span": None}]}]
    msg = hook._format_diagnostics(diags, "a.ts")
    assert "  [error] boom" in msg
    assert "None" not in msg.split("boom")[0]  # no `LNone`/`CNone` leaked into the location


# --------------------------------------------------------------------------- #
# main() -- fail-open on odd payloads / non-lintable, and the happy path
# --------------------------------------------------------------------------- #

def test_main_exits_zero_on_malformed_json(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("{not json"))
    assert hook.main() == 0
    assert capsys.readouterr().out == ""


def test_main_exits_zero_on_non_object_json(monkeypatch, capsys):
    # Valid JSON that isn't an object (`42`, `[..]`) hits the isinstance guard,
    # not the decode-error path — mirrors the sibling suite's convention.
    monkeypatch.setattr("sys.stdin", io.StringIO("42"))
    assert hook.main() == 0
    assert capsys.readouterr().out == ""


def test_main_exits_zero_on_non_dict_tool_input(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO('{"tool_input": "a.ts"}'))
    assert hook.main() == 0
    assert capsys.readouterr().out == ""


def test_main_skips_non_lintable_extension(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO('{"tool_input": {"file_path": "notes.md"}}'))
    # Should return before ever touching the filesystem/oxlint.
    assert hook.main() == 0
    assert capsys.readouterr().out == ""


def test_main_skips_when_file_missing(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.setattr("sys.stdin", io.StringIO('{"tool_input": {"file_path": "gone.ts"}}'))
    assert hook.main() == 0
    assert capsys.readouterr().out == ""


def test_main_emits_additional_context_on_diagnostics(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    src = tmp_path / "apps" / "demo" / "src"
    src.mkdir(parents=True)
    f = src / "a.ts"
    f.write_text("const y = 1;\n", encoding="utf-8")

    monkeypatch.setattr(hook, "_find_linter", lambda fp, ceiling, stem="oxlint": (tmp_path, tmp_path / "oxlint"))
    monkeypatch.setattr(
        hook, "_run_oxlint",
        lambda b, p, fp, extra=(): [{"severity": "error", "message": "boom", "labels": [{"span": {"line": 1, "column": 1}}]}],
    )
    rel = "apps/demo/src/a.ts"
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"tool_input": {"file_path": rel}})))

    assert hook.main() == 0
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert "boom" in out["hookSpecificOutput"]["additionalContext"]
    assert rel in out["hookSpecificOutput"]["additionalContext"]


def test_main_silent_when_no_diagnostics(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    f = tmp_path / "a.ts"
    f.write_text("const y = 1;\n", encoding="utf-8")
    monkeypatch.setattr(hook, "_find_linter", lambda fp, ceiling, stem="oxlint": (tmp_path, tmp_path / "oxlint"))
    monkeypatch.setattr(hook, "_run_oxlint", lambda b, p, fp, extra=(): [])
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"tool_input": {"file_path": "a.ts"}})))
    assert hook.main() == 0
    assert capsys.readouterr().out == ""


# --------------------------------------------------------------------------- #
# MD-9 — the overlay that makes this a lint hook rather than an oxlint hook
# --------------------------------------------------------------------------- #


def test_no_overlay_keeps_the_js_defaults_exactly(tmp_path):
    """The adoption cost has to be zero for a JS repo, or the fix is a
    regression for every consumer already using it."""
    exts, stem, args = hook.lint_profile(str(tmp_path))
    assert exts == hook.LINTABLE_EXTS
    assert stem == "oxlint"


def test_an_overlay_switches_extensions_binary_and_args(tmp_path):
    """`ruff check --output-format json` is a near drop-in: same
    JSON-diagnostics shape, same one-file invocation."""
    (tmp_path / "lint-on-edit.local.md").write_text(
        "---\nextensions: .py\nbinary: ruff\nargs: check --output-format json\n---\n",
        encoding="utf-8",
    )
    exts, stem, args = hook.lint_profile(str(tmp_path))
    assert exts == (".py",)
    assert stem == "ruff"
    assert args == ("check", "--output-format", "json")


def test_an_extension_without_a_dot_is_normalized(tmp_path):
    (tmp_path / "lint-on-edit.local.md").write_text(
        "---\nextensions: py rs\nbinary: ruff\n---\n", encoding="utf-8"
    )
    exts, _, _ = hook.lint_profile(str(tmp_path))
    assert exts == (".py", ".rs")


def test_a_malformed_overlay_announces_and_falls_back(tmp_path, capsys):
    """Absent is the only silent case. A typo that silently reverts to the JS
    defaults is indistinguishable from having no overlay — the same split
    `warn-smoke-test-drift` makes, for the same reason."""
    (tmp_path / "lint-on-edit.local.md").write_text(
        "extensions: .py\nbinary: ruff\n", encoding="utf-8"  # no opening ---
    )
    exts, stem, _ = hook.lint_profile(str(tmp_path))
    assert (exts, stem) == (hook.LINTABLE_EXTS, "oxlint")
    assert "no opening" in capsys.readouterr().err


def test_the_binary_resolves_from_path_when_node_modules_has_nothing(tmp_path, monkeypatch):
    """The PATH fallback is what makes a non-JS linter reachable at all: `ruff`
    is not installed under `node_modules`, so the walk alone always returned
    None and the hook stayed the permanent no-op this change fixes."""
    monkeypatch.setattr(hook.shutil, "which", lambda s: "/usr/bin/" + s)
    src = tmp_path / "app"
    src.mkdir()
    f = src / "x.py"
    f.write_text("x = 1\n", encoding="utf-8")
    found = hook._find_linter(f, tmp_path, "ruff")
    assert found is not None
    package_dir, binary = found
    assert package_dir == tmp_path
    assert binary.name == "ruff"


def test_no_binary_anywhere_still_returns_none(tmp_path, monkeypatch):
    """Non-vacuity partner: the PATH fallback must not make this always succeed."""
    monkeypatch.setattr(hook.shutil, "which", lambda s: None)
    f = tmp_path / "x.py"
    f.write_text("x = 1\n", encoding="utf-8")
    assert hook._find_linter(f, tmp_path, "ruff") is None
