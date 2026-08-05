"""discover_tests.py tests.

some-repo is a single root npm package; discovery emits `npm run <script>`
for whichever of `build`/`lint`/`test` the root `package.json` defines, in that
run order, when at least one changed path is source-affecting. It emits nothing
otherwise (no package.json, none of those scripts, or an openspec-/docs-only
change).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import discover_tests

# The scripts this repo defines today (no vitest `test` yet).
_BUILD_LINT = {"build": "tsc -b && vite build", "lint": "oxlint"}


@pytest.fixture(autouse=True)
def _repo_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(discover_tests, "REPO_ROOT", tmp_path)


def _with_package_json(tmp_path: Path, scripts: dict | None = None) -> None:
    body = {"name": "some-repo", "scripts": _BUILD_LINT if scripts is None else scripts}
    (tmp_path / "package.json").write_text(json.dumps(body) + "\n", encoding="utf-8")


def test_no_package_json_returns_empty(tmp_path: Path):
    # No root package.json → not an npm project → skip.
    assert discover_tests.discover(["src/App.tsx"]) == []


def test_source_change_emits_build_and_lint(tmp_path: Path):
    _with_package_json(tmp_path)
    assert discover_tests.discover(["src/App.tsx"]) == [
        ["npm", "run", "build"],
        ["npm", "run", "lint"],
    ]


def test_test_script_emitted_when_present(tmp_path: Path):
    # Once the repo defines a `test` script (e.g. vitest), it is emitted last.
    _with_package_json(tmp_path, {**_BUILD_LINT, "test": "vitest run"})
    assert discover_tests.discover(["src/logic/AllocationEngine.ts"]) == [
        ["npm", "run", "build"],
        ["npm", "run", "lint"],
        ["npm", "run", "test"],
    ]


def test_only_defined_scripts_emitted(tmp_path: Path):
    # A package with no build/lint/test scripts → nothing to run.
    _with_package_json(tmp_path, {"dev": "vite"})
    assert discover_tests.discover(["src/App.tsx"]) == []


def test_docs_only_change_returns_empty(tmp_path: Path):
    _with_package_json(tmp_path)
    # An openspec-/docs-only change touches nothing the checks cover.
    assert discover_tests.discover([
        "openspec/changes/x/proposal.md",
        "openspec/changes/x/tasks.md",
        "README.md",
    ]) == []


def test_config_json_change_is_source_affecting(tmp_path: Path):
    _with_package_json(tmp_path)
    # tsconfig / .oxlintrc.json / package.json edits affect build+lint.
    assert discover_tests.discover(["tsconfig.json"]) == [
        ["npm", "run", "build"],
        ["npm", "run", "lint"],
    ]


def test_mixed_change_emits_checks_once(tmp_path: Path):
    _with_package_json(tmp_path)
    # A change mixing docs and source emits the checks exactly once (not per-file).
    result = discover_tests.discover([
        "openspec/changes/x/proposal.md",
        "src/logic/AllocationEngine.ts",
    ])
    assert result == [["npm", "run", "build"], ["npm", "run", "lint"]]


def test_absolute_path_under_src_detected(tmp_path: Path):
    _with_package_json(tmp_path)
    abs_src = str(tmp_path / "src" / "components" / "BriefingForm.tsx")
    assert discover_tests.discover([abs_src]) == [
        ["npm", "run", "build"],
        ["npm", "run", "lint"],
    ]


# --- staged mode ---------------------------------------------------------


def test_staged_partitions_lint_as_smoke(tmp_path: Path):
    # lint is the cheap smoke tier; build (and test, when present) is the full tier.
    _with_package_json(tmp_path, {**_BUILD_LINT, "test": "vitest run"})
    assert discover_tests.discover_staged(["src/App.tsx"]) == {
        "smoke": [["npm", "run", "lint"]],
        "full": [["npm", "run", "build"], ["npm", "run", "test"]],
    }


def test_staged_full_order_preserved_without_test(tmp_path: Path):
    # Without a test script, full is just build; smoke is still lint.
    _with_package_json(tmp_path)
    assert discover_tests.discover_staged(["src/App.tsx"]) == {
        "smoke": [["npm", "run", "lint"]],
        "full": [["npm", "run", "build"]],
    }


def test_staged_empty_smoke_when_no_lint(tmp_path: Path):
    # A package with build+test but no lint → empty smoke tier, full carries both.
    _with_package_json(tmp_path, {"build": "tsc -b && vite build", "test": "vitest run"})
    assert discover_tests.discover_staged(["src/App.tsx"]) == {
        "smoke": [],
        "full": [["npm", "run", "build"], ["npm", "run", "test"]],
    }


def test_staged_docs_only_change_both_empty(tmp_path: Path):
    _with_package_json(tmp_path)
    assert discover_tests.discover_staged(["README.md"]) == {"smoke": [], "full": []}


def test_staged_full_empty_when_only_lint(tmp_path: Path):
    # The inverse partition: lint-only package → smoke carries it, full is empty.
    _with_package_json(tmp_path, {"lint": "oxlint"})
    assert discover_tests.discover_staged(["src/App.tsx"]) == {
        "smoke": [["npm", "run", "lint"]],
        "full": [],
    }
