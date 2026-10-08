"""Chain run notes stay local; the spec-to-pr run record is the one run record committed.

multi-lite and multi-pr keep their run notes as gitignored working state: no recipe
adds, commits or pushes them, each refuses to start while git would see them, and a
resume without them falls back to GitHub state, where multi-lite finds no recorded
head and so merges nothing and multi-pr stops before any later change. cla-init
writes the ignore line into a consuming repo's `.gitignore` and offers to untrack
notes already tracked; its blocks, and the chains' check, run under bash here.

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


# requirement: change-chains / A later change is held to what an earlier one owes it
def test_a_multi_pr_resume_without_its_notes_stops_before_a_later_change() -> None:
    loop = _read(_PR / "references" / "change-loop.md")
    resume = _between(loop, "## Resume behavior", None)
    assert ("**It then stops before running any not-yet-shipped change that has an earlier change in the "
            "sequence** (an archived `depends_on` counts as one), since what an earlier change owes it is "
            "unknown.") in resume
    assert ("resume on the machine that holds the notes, or run the remaining changes one at a time with "
            "`/cla:spec-to-pr`") in resume
    assert "were not carried" not in loop
    skill = _between(_read(_PR / "SKILL.md"), "## Resume behavior", "\n## ")
    assert ("A resume with no running notes stops before any not-yet-shipped change that has an earlier "
            "change, since its obligations are unknown.") in skill


def test_this_repo_ignores_new_run_notes() -> None:
    assert _LINE in _read(_REPO / ".gitignore").splitlines()


_needs_bash = pytest.mark.skipif(_BASH is None, reason="bash is not installed")
# Hermetic: a user's global excludes file must not decide what these repos ignore.
_GIT_ENV = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def _block(marker: str) -> str:
    match = re.search(r"```bash\n(: \"\$\{ROOT:\?[^`]*?" + re.escape(marker) + r"[^`]*?)```", _read(_CLA_INIT))
    assert match, f"cla-init/SKILL.md: no block holding {marker!r}"
    return match.group(1)


def _bash(script: str, root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [_BASH, "-c", script], cwd=root,
        # Forward slashes: a POSIX shell reads `C:\...` backslashes as escapes.
        env={**_GIT_ENV, "ROOT": str(root).replace("\\", "/")},
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )


def _run(root: Path, marker: str = "run-notes line") -> str:
    out = _bash(_block(marker), root)
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, env=_GIT_ENV, check=True,
                          capture_output=True, text=True, encoding="utf-8", errors="replace").stdout


def _repo(tmp_path: Path, gitignore: bytes | None = None) -> Path:
    _git(tmp_path, "init", "-q", ".")
    if gitignore is not None:
        (tmp_path / ".gitignore").write_bytes(gitignore)
    return tmp_path


def _ignored(root: Path, path: str) -> bool:
    out = subprocess.run(["git", "check-ignore", "-q", "--no-index", path], cwd=root,
                         env=_GIT_ENV, capture_output=True)
    return out.returncode == 0


# requirement: repo-context / Setting up a repo's cla.io directory
@_needs_bash
def test_cla_init_creates_the_ignore_line_and_a_rerun_keeps_it(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    assert _run(root) == "created: .gitignore run-notes line"
    gitignore = root / ".gitignore"
    assert gitignore.read_bytes() == f"{_LINE}\n".encode()
    assert _ignored(root, "cla.io/retro/multi-lite-run-notes-2026-10-08.md")
    assert _ignored(root, "cla.io/retro/multi-pr-run-notes-2026-10-08.md")
    assert not _ignored(root, "cla.io/retro/spec-to-pr-runs.jsonl")
    assert _run(root) == "exists (skipped): .gitignore run-notes line"
    assert gitignore.read_bytes() == f"{_LINE}\n".encode()


# requirement: repo-context / Setting up a repo's cla.io directory
@_needs_bash
def test_cla_init_appends_to_an_existing_gitignore_without_changing_it(tmp_path: Path) -> None:
    # No trailing newline, and a line that only contains the pattern.
    before = f"node_modules/\n{_LINE}.bak"
    root = _repo(tmp_path, before.encode())
    assert _run(root) == "created: .gitignore run-notes line"
    assert (root / ".gitignore").read_bytes() == f"{before}\n{_LINE}\n".encode()


# requirement: repo-context / Setting up a repo's cla.io directory
@_needs_bash
@pytest.mark.parametrize("before", [
    f"node_modules/\r\n{_LINE}\r\n",        # CRLF
    f"{_LINE}   \n",                          # trailing spaces
    f"/{_LINE}\n",                            # anchored, same files
    "cla.io/retro/\n",                        # a wider pattern
])
def test_cla_init_takes_an_equivalent_line_for_the_line(tmp_path: Path, before: str) -> None:
    root = _repo(tmp_path, before.encode())
    assert _run(root) == "exists (skipped): .gitignore run-notes line"
    assert (root / ".gitignore").read_bytes() == before.encode()


# requirement: repo-context / Setting up a repo's cla.io directory
@_needs_bash
def test_cla_init_leaves_a_deliberate_un_ignore_alone(tmp_path: Path) -> None:
    before = f"{_LINE}\n!cla.io/retro/multi-lite-run-notes-*.md\n"
    root = _repo(tmp_path, before.encode())
    out = _run(root)
    assert out.startswith("un-ignored (left as is): .gitignore:2:!cla.io/retro/multi-lite-run-notes-*.md"), out
    assert (root / ".gitignore").read_bytes() == before.encode()
    item_8 = _between(_read(_CLA_INIT), "### 8. Ignore", "## Report")
    assert "the chains will not start until that `!` line" in item_8


def _commit_all(root: Path) -> None:
    _git(root, "add", "-A")
    _git(root, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "seed")


def _seed_tracked_notes(root: Path) -> list[str]:
    retro = root / "cla.io" / "retro"
    retro.mkdir(parents=True)
    tracked = ["cla.io/retro/multi-lite-run-notes-2026-08-04.md", "cla.io/retro/multi-pr-run-notes-2026-08-23.md"]
    for name in [*tracked, "cla.io/retro/spec-to-pr-runs.jsonl"]:
        (root / name).write_text("x\n", encoding="utf-8")
    _commit_all(root)  # committed before any ignore line, as in a repo onboarded earlier
    assert _run(root) == "created: .gitignore run-notes line"
    (retro / "multi-lite-run-notes-2026-10-08.md").write_text("new\n", encoding="utf-8")  # untracked
    return tracked


def _listed(root: Path) -> list[str]:
    prefix = "tracked run notes: "
    lines = _run(root, prefix).splitlines()
    assert all(line.startswith(prefix) for line in lines), lines
    return [line.removeprefix(prefix) for line in lines]


# requirement: repo-context / Setting up a repo's cla.io directory
@_needs_bash
def test_cla_init_lists_tracked_notes_and_changes_nothing_without_a_yes(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    assert _listed(root) == []
    tracked = _seed_tracked_notes(root)
    status = _git(root, "status", "--porcelain")
    assert _listed(root) == tracked
    assert _git(root, "status", "--porcelain") == status  # the "no" path: nothing moved
    item_8 = _between(_read(_CLA_INIT), "### 8. Ignore", "## Report")
    assert "Only on an explicit yes" in item_8
    assert "loses its working copies on its next pull (history keeps them)" in item_8


# requirement: repo-context / Setting up a repo's cla.io directory
@_needs_bash
def test_cla_init_untracks_exactly_the_listed_notes_on_a_yes(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    tracked = _seed_tracked_notes(root)
    item_8 = _between(_read(_CLA_INIT), "### 8. Ignore", "## Report")
    match = re.search(r"`(git -C \"\$ROOT\" rm [^`]*?)<each listed path>`", item_8)
    assert match, "item 8 names no untrack command"
    out = _bash(match.group(1) + " ".join(_listed(root)), root)
    assert out.returncode == 0, out.stderr
    assert _git(root, "ls-files").split() == ["cla.io/retro/spec-to-pr-runs.jsonl"]
    assert all((root / name).read_text(encoding="utf-8") == "x\n" for name in tracked)  # still on disk
    # Staged as removals, and the files on disk are now ignored rather than untracked noise.
    assert sorted(_git(root, "status", "--porcelain").splitlines()) == sorted(
        ["?? .gitignore", *(f"D  {name}" for name in tracked)])


def _chain_check(skill_text: str, chain: str) -> str:
    probe = f"cla.io/retro/{chain}-run-notes-x.md"
    line = (f"`git check-ignore -q --no-index {probe}`. Non-zero → stop: "
            "\"run /cla:cla-init first (run notes would be visible to git)\".")
    assert line in skill_text, chain
    return f"git check-ignore -q --no-index {probe}"


# requirement: run-ledgers / Chain run notes stay local
@_needs_bash
@pytest.mark.parametrize("chain, doc", [
    ("multi-lite", _LITE / "references" / "bootstrap-and-tracking.md"),
    ("multi-pr", _PR / "SKILL.md"),
])
def test_each_chain_refuses_to_start_while_its_notes_are_not_ignored(tmp_path: Path, chain: str, doc: Path) -> None:
    text = _read(doc)
    command = _chain_check(_between(text, "## Phase 0", "\n## Phase "), chain)
    root = _repo(tmp_path, b"node_modules/\n")
    assert _bash(command, root).returncode != 0
    _run(root)  # cla-init's block adds the line
    assert _bash(command, root).returncode == 0
