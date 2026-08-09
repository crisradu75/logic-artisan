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


# --------------------------------------------------------------------------- #
# MD-8 — three empty outcomes rendered as one wrong reason
#
# `discover` returned [] for THREE different conditions and SKILL.md mapped all
# of them to "no source-affecting changed paths (docs-/openspec-only change)".
# So a repo with no root package.json announced every source change as docs-only
# and its whole suite never ran -- a skipped correctness gate reported as a
# deliberate skip, which is worse than a missing one, because the reason is
# plausible enough that nobody questions it.
#
# logic-artisan is itself such a repo: the canonical source shipped a
# test-discovery script that cannot discover its own tests.
# --------------------------------------------------------------------------- #


def test_no_manifest_is_distinguishable_from_a_docs_only_change(tmp_path: Path):
    """The two cases that used to be identical. One is a real skip; the other
    means no correctness gate ran at all."""
    checks, reason = discover_tests.discover_with_reason(["src/App.tsx"])
    assert checks == []
    assert reason == discover_tests.NO_MANIFEST

    _with_package_json(tmp_path)
    checks, reason = discover_tests.discover_with_reason(["docs/readme.md"])
    assert checks == []
    assert reason == discover_tests.NO_SOURCE_PATHS


def test_a_manifest_without_check_scripts_says_so(tmp_path: Path):
    _with_package_json(tmp_path, {"dev": "vite"})
    checks, reason = discover_tests.discover_with_reason(["src/App.tsx"])
    assert checks == []
    assert reason == discover_tests.NO_CHECK_SCRIPTS


def test_a_successful_discovery_carries_no_reason(tmp_path: Path):
    """Non-vacuity partner: `reason` must be None on the normal path, or the
    orchestrator would treat every run as a degraded one."""
    _with_package_json(tmp_path)
    checks, reason = discover_tests.discover_with_reason(["src/App.tsx"])
    assert checks and reason is None


def test_a_python_source_path_counts_as_source_affecting(tmp_path: Path):
    """`.py` was absent from _SOURCE_SUFFIXES, so in a Python repo a source
    change did not even register as source-affecting."""
    _with_package_json(tmp_path, {"test": "pytest"})
    _, reason = discover_tests.discover_with_reason(["app/service.py"])
    assert reason is None, "a .py change must be source-affecting"


def test_the_staged_shape_carries_the_reason_to_the_orchestrator(tmp_path, capsys):
    """The reason is only useful if it reaches the caller that renders the
    status. The bare shape keeps its list contract, so no existing caller had to
    change to get the fix."""
    assert discover_tests.main(["--staged", "src/App.tsx"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["smoke"] == [] and payload["full"] == []
    assert payload["reason"] == discover_tests.NO_MANIFEST


def test_a_docs_only_change_reports_a_true_skip_even_with_no_manifest(tmp_path: Path):
    """The reason the two checks were reordered.

    The manifest check is repo-GLOBAL and the source-paths check is per-change,
    so testing the manifest first made `NO_SOURCE_PATHS` unreachable in any repo
    without a root `package.json`. A genuinely docs-only change — a real skip —
    was reported as `no-package-json`, which `SKILL.md` maps to `warn`. Every
    run in such a repo therefore carried a Test-phase warning, and a warning
    that fires on every run is one nobody reads.
    """
    # No package.json written: this is the non-npm repo case.
    checks, reason = discover_tests.discover_with_reason(
        ["openspec/changes/x/proposal.md", "README.md"]
    )
    assert checks == []
    assert reason == discover_tests.NO_SOURCE_PATHS


def test_a_source_change_with_no_manifest_still_warns(tmp_path: Path):
    """Non-vacuity partner: the reorder must not turn the case that genuinely
    needs a gate into a silent skip. `no-package-json` is the one outcome that
    means "a source change ran no correctness gate at all"."""
    checks, reason = discover_tests.discover_with_reason(["app/service.py"])
    assert checks == []
    assert reason == discover_tests.NO_MANIFEST
