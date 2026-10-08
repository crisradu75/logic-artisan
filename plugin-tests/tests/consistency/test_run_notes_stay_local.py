"""Chain run notes stay local; the spec-to-pr run record is the one run record committed.

multi-lite and multi-pr keep their run notes as gitignored working state: no recipe
adds, commits or pushes them, and a resume without them falls back to GitHub state,
where multi-lite finds no recorded head and so merges nothing. cla-init writes the
ignore line into a consuming repo's `.gitignore`; its block is run under bash here.

spec-to-pr's run record is the contrast: it is still committed, on the branch of the
PR the run opened and never the base branch.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]
_SKILLS = _REPO / ".claude" / "plugins" / "cla" / "skills"
_HANDOFF = _SKILLS / "spec-to-pr" / "references" / "handoff.md"
_LITE = _SKILLS / "multi-lite"
_PR = _SKILLS / "multi-pr"
_CLA_INIT = _SKILLS / "cla-init" / "SKILL.md"
_LINE = "cla.io/retro/*-run-notes-*.md"
_BASH = shutil.which("bash")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _between(text: str, start: str, end: str | None) -> str:
    i = text.index(start)
    j = text.index(end, i) if end else len(text)
    return text[i:j]


# requirement: run-ledgers / The spec-to-pr run record rides its pull request
def test_spec_to_pr_commits_its_record_on_the_feature_branch_only() -> None:
    step_6 = _between(_read(_HANDOFF), "## 6. Commit the run-log line", "Steps 5 and 6")
    assert "--expect-branch <branch>" in step_6
    assert "git add -- cla.io/retro/spec-to-pr-runs.jsonl" in step_6
    assert "Do this ONLY when Ship opened a PR" in step_6


_STAGES = re.compile(r"git (add|commit|rm|push)\b")
_NAMES_NOTES = re.compile(r"run-notes|<notes(-path|-message)?>")


# requirement: run-ledgers / Chain run notes stay local
def test_no_recipe_stages_or_commits_run_notes() -> None:
    files = sorted(_SKILLS.rglob("*.md"))
    assert len(files) > 50, "the scan found too few files to mean anything"
    hits = [f"{p.relative_to(_REPO)}:{n}" for p in files
            for n, line in enumerate(_read(p).splitlines(), 1)
            if _STAGES.search(line) and _NAMES_NOTES.search(line)]
    assert not hits, f"a recipe stages or commits run notes: {hits}"
    for chain in (_LITE, _PR):
        text = "".join(_read(p) for p in chain.rglob("*.md"))
        assert "<notes-message>" not in text and "run notes for" not in text, chain.name


# requirement: run-ledgers / Chain run notes stay local
def test_each_chain_says_its_notes_are_local() -> None:
    boot = _read(_LITE / "references" / "bootstrap-and-tracking.md")
    assert f"`.gitignore` ignores `{_LINE}` (`/cla:cla-init` adds the line), nothing in this run adds or commits it" in boot
    loop = _read(_PR / "references" / "change-loop.md")
    assert "**The running notes are local working state:** gitignored, never added or committed." in loop
    assert "falls back to GitHub state" in boot and "falls back to GitHub state" in loop


# requirement: small-change-chains / A resumed small-change chain merges only the head it checked
def test_a_multi_lite_resume_without_its_notes_merges_nothing() -> None:
    skill = _read(_LITE / "SKILL.md")
    assert ("Without it (another machine, or the file deleted) resume falls back to GitHub state, and a PR "
            "found there has no `head_sha`, so it is left open as `head unverifiable (ledger lost)`, never merged."
            ) in skill
    loop = _read(_LITE / "references" / "candidate-loop.md")
    assert "a PR it finds has no recorded `head_sha`, so the moved-head arm leaves it open" in loop
    assert "and merges nothing it finds that way" in loop


def test_this_repo_ignores_new_run_notes() -> None:
    assert _LINE in _read(_REPO / ".gitignore").splitlines()


def _script() -> str:
    match = re.search(r"```bash\n(: \"\$\{ROOT:\?[^`]*?run-notes line[^`]*?)```", _read(_CLA_INIT))
    assert match, "cla-init/SKILL.md: no run-notes ignore block found"
    return match.group(1)


def _run(root: Path) -> str:
    out = subprocess.run(
        [_BASH, "-c", _script()],
        # Forward slashes: a POSIX shell reads `C:\...` backslashes as escapes.
        env={**os.environ, "ROOT": str(root).replace("\\", "/")},
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


_needs_bash = pytest.mark.skipif(_BASH is None, reason="bash is not installed")


def _ignored(root: Path, path: str) -> bool:
    out = subprocess.run(["git", "check-ignore", "-q", "--no-index", path], cwd=root,
                         env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull}, capture_output=True)
    return out.returncode == 0


# requirement: repo-context / Setting up a repo's cla.io directory
@_needs_bash
def test_cla_init_creates_the_ignore_line_and_a_rerun_keeps_it(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    assert _run(tmp_path) == "created: .gitignore run-notes line"
    gitignore = tmp_path / ".gitignore"
    assert gitignore.read_bytes() == f"{_LINE}\n".encode()
    assert _ignored(tmp_path, "cla.io/retro/multi-lite-run-notes-2026-10-08.md")
    assert _ignored(tmp_path, "cla.io/retro/multi-pr-run-notes-2026-10-08.md")
    assert not _ignored(tmp_path, "cla.io/retro/spec-to-pr-runs.jsonl")
    assert _run(tmp_path) == "exists (skipped): .gitignore run-notes line"
    assert gitignore.read_bytes() == f"{_LINE}\n".encode()


# requirement: repo-context / Setting up a repo's cla.io directory
@_needs_bash
def test_cla_init_appends_to_an_existing_gitignore_without_changing_it(tmp_path: Path) -> None:
    # No trailing newline, and a line that only contains the pattern.
    before = f"node_modules/\n{_LINE}.bak"
    (tmp_path / ".gitignore").write_bytes(before.encode())
    assert _run(tmp_path) == "created: .gitignore run-notes line"
    assert (tmp_path / ".gitignore").read_bytes() == f"{before}\n{_LINE}\n".encode()
