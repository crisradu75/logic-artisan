"""`check_shipped_tree.py` refuses a release whose plugin tree carries a dev asset.

WHY SEEDED INPUTS. A scan is the shape that passes vacuously: point it at nothing
and it reports "0 violations" forever. So every test below PLANTS a violating file
in a throwaway git repo and asserts the scan exits 1 AND NAMES THAT FILE. Asserting
the exit code alone would pass against a scan that had stopped reading the tree.

The four shapes named "the draft accepted this" are not hypothetical. An earlier
11-pattern version of the allowlist was measured against planted files and accepted
all four; they are the reason the pattern set is 14 and not 11. A suite that omitted
them would pass on the draft that was wrong.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import check_shipped_tree as cst

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SCRIPT = _REPO_ROOT / ".claude" / "skills" / "release" / "scripts" / "check_shipped_tree.py"

# One file of each legitimately-shipped shape, so a seeded repo is otherwise
# clean and the planted violation is the only thing the scan can object to.
_CLEAN_TREE = (
    "README.md",
    ".claude-plugin/plugin.json",
    "agents/doc-sweeper.md",
    "hooks/hooks.json",
    "skills/annotate/SKILL.md",
)


def _seed(tmp_path: Path, *extra: str) -> Path:
    """A git repo holding a minimal plugin tree, plus `extra` paths."""
    repo = tmp_path / "repo"
    plugin = repo / ".claude" / "plugins" / "cla"
    plugin.mkdir(parents=True)
    for rel in (*_CLEAN_TREE, *extra):
        f = plugin / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    return repo


def _run(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), str(repo)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=120,
    )


@pytest.mark.parametrize(
    "planted",
    [
        # The five shapes a denylist also catches.
        pytest.param("skills/annotate/tests/test_render_doc.py", id="tests-dir"),
        pytest.param("pyproject.toml", id="pyproject"),
        pytest.param("skills/annotate/mutants/test_render_doc.py", id="mutants-dir"),
        pytest.param("skills/project-review/scripts/x.test.mjs", id="test-mjs"),
        pytest.param("skills/annotate/tests/conftest.py", id="conftest"),
        # The four the 11-pattern draft ACCEPTED. These are why the list is 14.
        pytest.param("skills/project-review/scripts/mechanical-checks.test.mjs",
                     id="draft-accepted-compound-mjs"),
        pytest.param("skills/annotate/scripts/conftest.py",
                     id="draft-accepted-conftest-as-script"),
        pytest.param("hooks/tests/test_dispatch.py",
                     id="draft-accepted-hooks-tests"),
        pytest.param("hooks/pyproject.toml",
                     id="draft-accepted-hooks-pyproject"),
    ],
)
def test_a_planted_dev_asset_is_refused_and_named(tmp_path, planted):
    repo = _seed(tmp_path, planted)
    result = _run(repo)
    assert result.returncode == cst.EXIT_VIOLATIONS, (
        f"planted {planted!r} but the scan exited {result.returncode}\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert planted in result.stdout, (
        f"the scan refused but never NAMED {planted!r} — an operator cannot act "
        f"on that.\nSTDOUT:\n{result.stdout}"
    )


def test_the_clean_seeded_tree_itself_passes(tmp_path):
    repo = _seed(tmp_path)
    result = _run(repo)
    assert result.returncode == cst.EXIT_CLEAN, (
        f"a tree of nothing but shipped shapes was refused\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert f"{len(_CLEAN_TREE)} files" in result.stdout


def test_every_offender_is_named_in_one_run(tmp_path):
    """Reporting one at a time turns a single cleanup into as many release
    attempts as there are files."""
    planted = [
        "pyproject.toml",
        "hooks/tests/test_dispatch.py",
        "skills/annotate/tests/conftest.py",
    ]
    repo = _seed(tmp_path, *planted)
    result = _run(repo)
    assert result.returncode == cst.EXIT_VIOLATIONS
    for rel in planted:
        assert rel in result.stdout, f"{rel} was not named"
    assert "3 violation(s)" in result.stdout


def test_an_empty_enumeration_is_could_not_run_not_clean(tmp_path):
    """The load-bearing row of the exit contract. A scan run from the wrong
    directory enumerates nothing; reporting that as `0 violations` is a clean
    verdict over a tree it never read."""
    repo = tmp_path / "empty"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    result = _run(repo)
    assert result.returncode == cst.EXIT_CANNOT_RUN, (
        f"an empty enumeration exited {result.returncode}, not "
        f"{cst.EXIT_CANNOT_RUN}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert "ZERO files" in result.stderr


def test_a_git_failure_is_could_not_run(tmp_path):
    """Not a git repo at all: still a could-not-run, never a clean result."""
    repo = tmp_path / "notarepo"
    repo.mkdir()
    result = _run(repo)
    assert result.returncode == cst.EXIT_CANNOT_RUN


def test_the_real_tree_passes_with_the_real_file_count():
    """Exit 0 alone is not the check — the files-examined count must agree with
    an independently-measured `git ls-files`."""
    expected = subprocess.run(
        ["git", "ls-files", cst.PLUGIN_PREFIX],
        cwd=str(_REPO_ROOT), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120,
    )
    assert expected.returncode == 0
    count = len([line for line in expected.stdout.splitlines() if line.strip()])
    assert count > 0, "git ls-files found no plugin files — this test cannot judge"

    result = _run(_REPO_ROOT)
    assert result.returncode == cst.EXIT_CLEAN, (
        f"the real plugin tree was refused\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert f"{count} files" in result.stdout, (
        f"the scan examined a different number of files than `git ls-files` "
        f"reports ({count})\nSTDOUT:\n{result.stdout}"
    )


def test_the_allowlist_is_capped_and_every_entry_carries_a_reason():
    """The pressure valve, bounded — the same convention `_EXEMPT` runs in
    test_guards_have_mutant_batches.py.

    The list was 14 when the convention landed. A fifteenth pattern lands by
    raising this cap in the SAME commit that adds the pattern and its reason;
    growth is allowed, growth nobody argued for is not."""
    assert len(cst.ALLOWLIST) == 14, (
        f"the allowlist has {len(cst.ALLOWLIST)} patterns; it was 14 when the "
        "convention landed. Adding one is fine — raise this cap in the same "
        "commit, with the pattern's reason."
    )
    for pattern, reason in cst.ALLOWLIST:
        assert isinstance(reason, str) and reason.strip(), (
            f"pattern {pattern!r} carries no reason. The reason column is the "
            "discipline, not decoration — it is what makes a future addition "
            "arguable."
        )


def test_the_patterns_are_anchored_at_both_ends():
    """An unanchored pattern is a silent widening: `skills/[^/]+/SKILL\\.md`
    without `$` also accepts `skills/x/SKILL.md.bak`."""
    for rx in cst._COMPILED:
        assert rx.pattern.startswith("^") and rx.pattern.endswith("$"), (
            f"{rx.pattern!r} is not anchored at both ends"
        )


def test_conftest_is_rejected_wherever_it_appears():
    """Rejected by LEAF NAME, ahead of every pattern — it is the one dev-asset
    shape whose name is otherwise a legal script name."""
    assert not cst.is_allowed("skills/annotate/scripts/conftest.py")
    assert not cst.is_allowed("hooks/conftest.py")
    assert cst.is_allowed("skills/annotate/scripts/render_doc.py")


def test_a_compound_extension_cannot_pass_as_a_script_or_a_reference():
    """The `[^/.]+` stem in patterns 13 and 14 is exactly what D1a's measurement
    added; `[^/]+` swallowed the `.test` segment."""
    assert not cst.is_allowed("skills/project-review/scripts/mechanical-checks.test.mjs")
    assert cst.is_allowed("skills/project-review/scripts/mechanical-checks.mjs")
    assert not cst.is_allowed("skills/annotate/references/notes.draft.md")
    assert cst.is_allowed("skills/annotate/references/notes.md")
