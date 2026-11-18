"""setup_guard.py tests: real git repos, a snapshot at the start, a change, then verify.

Every repo here is a copy of one template: `CLAUDE.md`, `AGENTS.md`, the feedback notes, the
terminology file and one overlay committed, and a gitignored `cla.io/project-tokens.local.md`.
Snapshots go to `tmp_path / "snap.json"`, outside the repo, as the skill tells the agent to.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[4]
_SKILL = _REPO / ".claude" / "plugins" / "cla" / "skills" / "cla-setup" / "SKILL.md"
_SCRIPT = _SKILL.parent / "scripts" / "setup_guard.py"

TOKENS = "cla.io/project-tokens.local.md"
OVERLAY = "cla.io/overlays/review-change.md"
TERMS = "cla.io/terminology.md"
NOTES = "cla.io/feedback/notes.md"

# Every protected path the template holds, with whether a yes may cover a change to it.
PRESENT = {
    "CLAUDE.md": False,
    "AGENTS.md": False,
    NOTES: False,
    TERMS: True,
    OVERLAY: True,
    TOKENS: True,
}


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=True,
    )


def _build(root: Path) -> None:
    work = root / "work"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    _git(work, "config", "user.email", "test@example.com")
    _git(work, "config", "user.name", "Test")
    files = {
        ".gitignore": "*.local.md\ntemp/\n",
        "CLAUDE.md": "# Rules\n",
        "AGENTS.md": "# Agents\n",
        NOTES: "# App experience notes\n- a note\n",
        TERMS: "# Terminology\n",
        OVERLAY: "# review-change overlay\n- a rule\n",
        TOKENS: "widgetco\n",
        "cla.io/project-facts.md": "# Facts\n",
    }
    for rel, text in files.items():
        p = work / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    _git(work, "add", ".")
    _git(work, "commit", "-q", "-m", "initial")


@pytest.fixture
def work(tmp_path: Path, cached_git_repo) -> Path:
    cached_git_repo("cla-setup/setup_guard", _build, tmp_path)
    return tmp_path / "work"


def _run(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    # A neutral cwd: the script must act on --root, not wherever it was started.
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args], cwd=Path(__file__).parent,
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
    )


def _snap(work: Path) -> Path:
    out = work.parent / "snap.json"
    r = _run("snapshot", "--root", str(work), "--out", str(out))
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.startswith("OK snapshot:")
    return out


def _verify(work: Path, snap: Path, *approved: str) -> subprocess.CompletedProcess[str]:
    extra = [a for rel in approved for a in ("--approved", rel)]
    return _run("verify", "--root", str(work), "--snapshot", str(snap), *extra)


def _problems(r: subprocess.CompletedProcess[str]) -> list[str]:
    return [line for line in r.stdout.splitlines() if line.startswith("PROBLEM ")]


def _write(work: Path, rel: str, text: str) -> None:
    p = work / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------- passes


# requirement: cla-setup / Setup checks that its protected files were left alone
def test_a_run_that_touches_nothing_protected_passes(work: Path) -> None:
    snap = _snap(work)
    # The writes cla-setup makes unasked, or on a yes to an unprotected file.
    _write(work, ".claude/rules/cla-economy.md", "# Economy rules\n")
    (work / ".gitignore").write_text("*.local.md\ntemp/\ncla.io/retro/*-run-notes-*.md\n", encoding="utf-8")
    _write(work, "cla.io/project-facts.md", "# Facts\n## Ports\n- 3000\n")
    _write(work, "cla.io/retro/spec-to-pr-runs.jsonl", "")
    r = _verify(work, snap)
    assert r.returncode == 0, r.stdout
    assert r.stdout.startswith("OK verify:")
    assert not _problems(r)


# requirement: cla-setup / Setup checks that its protected files were left alone
def test_a_file_already_dirty_before_the_run_and_left_alone_passes(work: Path) -> None:
    # The owner edited CLAUDE.md and an overlay before the run. Git shows both as modified
    # whatever the run does, which is why the guard compares with a snapshot, not with HEAD.
    _write(work, "CLAUDE.md", "# Rules\n- the owner's uncommitted line\n")
    _write(work, OVERLAY, "# review-change overlay\n- an uncommitted rule\n")
    _write(work, "cla.io/overlays/untracked.md", "# an untracked overlay from before\n")
    status = _git(work, "status", "--porcelain").stdout
    assert " M CLAUDE.md" in status and "?? cla.io/overlays/untracked.md" in status
    snap = _snap(work)
    r = _verify(work, snap)
    assert r.returncode == 0, r.stdout


# requirement: cla-setup / Setup checks that its protected files were left alone
def test_notes_created_where_there_were_none_passes(work: Path) -> None:
    (work / NOTES).unlink()
    snap = _snap(work)
    _write(work, NOTES, "# App experience notes\n")  # item 3's seed
    r = _verify(work, snap)
    assert r.returncode == 0, r.stdout


# ---------------------------------------------------------------- changed, created, deleted


# requirement: cla-setup / Setup checks that its protected files were left alone
@pytest.mark.parametrize("rel", sorted(PRESENT))
def test_every_protected_file_changed_without_a_yes_fails(work: Path, rel: str) -> None:
    snap = _snap(work)
    (work / rel).write_text((work / rel).read_text(encoding="utf-8") + "- added by the run\n", encoding="utf-8")
    r = _verify(work, snap)
    assert r.returncode == 1, r.stdout
    assert r.stdout.startswith("FAIL verify: 1 protected file problem(s)")
    assert len(_problems(r)) == 1 and _problems(r)[0].startswith(f"PROBLEM changed: {rel} (")


# requirement: cla-setup / Setup checks that its protected files were left alone
@pytest.mark.parametrize("rel", sorted(PRESENT))
def test_every_protected_file_deleted_without_a_yes_fails(work: Path, rel: str) -> None:
    snap = _snap(work)
    (work / rel).unlink()
    r = _verify(work, snap)
    assert r.returncode == 1, r.stdout
    assert len(_problems(r)) == 1 and _problems(r)[0].startswith(f"PROBLEM deleted: {rel} (")


# requirement: cla-setup / Setup checks that its protected files were left alone
@pytest.mark.parametrize(
    "rel",
    ["CLAUDE.md", "AGENTS.md", "CLAUDE.local.md", ".claude/CLAUDE.md", ".claude/CLAUDE.local.md",
     ".claude/AGENTS.md", ".claude/settings.json", ".claude-plugin/plugin.json",
     ".claude/rules/house.md", ".claude/rules/sub/more.md", TERMS, OVERLAY, TOKENS, "cla.io/fleet.local.md"],
)
def test_every_protected_file_created_without_a_yes_fails(work: Path, rel: str) -> None:
    if (work / rel).exists():
        (work / rel).unlink()
    snap = _snap(work)
    _write(work, rel, "# made by the run\n")
    r = _verify(work, snap)
    assert r.returncode == 1, r.stdout
    assert len(_problems(r)) == 1 and _problems(r)[0].startswith(f"PROBLEM created: {rel} (")


# requirement: cla-setup / Setup checks that its protected files were left alone
def test_a_nested_instruction_file_is_protected(work: Path) -> None:
    _write(work, "app/CLAUDE.md", "# app rules\n")
    _git(work, "add", "app/CLAUDE.md")
    snap = _snap(work)
    _write(work, "app/CLAUDE.md", "# app rules\n- added by the run\n")
    _write(work, "lib/AGENTS.md", "# made by the run\n")
    r = _verify(work, snap)
    assert r.returncode == 1, r.stdout
    assert _problems(r) == [
        "PROBLEM changed: app/CLAUDE.md (an instruction file; cla-setup never touches it, so a yes does not cover it)",
        "PROBLEM created: lib/AGENTS.md (an instruction file; cla-setup never touches it, so a yes does not cover it)",
    ]


# requirement: cla-setup / Setup checks that its protected files were left alone
def test_a_gitignored_local_file_reshaped_fails_though_git_sees_nothing(work: Path) -> None:
    snap = _snap(work)
    _write(work, TOKENS, "- widgetco\n")
    assert _git(work, "status", "--porcelain").stdout == ""
    r = _verify(work, snap)
    assert r.returncode == 1, r.stdout
    assert _problems(r) == [
        f"PROBLEM changed: {TOKENS} (a machine-read local file; changed without the owner's yes)"
    ]


# ---------------------------------------------------------------- overlays


# requirement: cla-setup / Setup creates no overlay and no terminology file
def test_an_overlay_created_fails_even_when_approved(work: Path) -> None:
    snap = _snap(work)
    _write(work, "cla.io/overlays/spec-to-pr.md", "# made by the run\n")
    r = _verify(work, snap, "cla.io/overlays/spec-to-pr.md")
    assert r.returncode == 1, r.stdout
    assert _problems(r) == [
        "PROBLEM created: cla.io/overlays/spec-to-pr.md (an overlay; cla-setup never creates one, "
        "so a yes does not cover it)"
    ]
    # The overlays present at the start are derived from the files map; no second list to disagree.
    snap_data = json.loads(snap.read_text(encoding="utf-8"))
    assert "overlays" not in snap_data
    assert [k for k, v in snap_data["files"].items() if k.startswith("cla.io/overlays/") and v] == [OVERLAY]


# requirement: cla-setup / Setup creates no overlay and no terminology file
def test_the_terminology_file_created_fails_even_when_approved(work: Path) -> None:
    (work / TERMS).unlink()
    snap = _snap(work)
    _write(work, TERMS, "# Terminology\n")
    r = _verify(work, snap, TERMS)
    assert r.returncode == 1, r.stdout
    assert _problems(r)[0].startswith(f"PROBLEM created: {TERMS} (the terminology file; cla-setup never creates it")


# ---------------------------------------------------------------- approval


# requirement: cla-setup / Setup checks that its protected files were left alone
@pytest.mark.parametrize("rel", sorted(r for r, ok in PRESENT.items() if ok))
@pytest.mark.parametrize("action", ["changed", "deleted"])
def test_an_approved_change_passes(work: Path, rel: str, action: str) -> None:
    snap = _snap(work)
    if action == "changed":
        _write(work, rel, "# reconciled on a yes\n")
    else:
        (work / rel).unlink()
    r = _verify(work, snap, str(work / rel))  # an absolute path works as well as a relative one
    assert r.returncode == 0, r.stdout
    assert r.stdout.startswith("OK verify:") and f"approved: {rel} {action}" in r.stdout


# requirement: cla-setup / Setup checks that its protected files were left alone
def test_a_token_list_created_on_a_yes_passes(work: Path) -> None:
    (work / TOKENS).unlink()
    snap = _snap(work)
    _write(work, TOKENS, "widgetco\n")
    assert _verify(work, snap, TOKENS).returncode == 0
    assert _verify(work, snap).returncode == 1


# requirement: cla-setup / Setup checks that its protected files were left alone
@pytest.mark.parametrize("rel", sorted(r for r, ok in PRESENT.items() if not ok))
def test_a_yes_does_not_cover_a_file_the_skill_never_changes(work: Path, rel: str) -> None:
    snap = _snap(work)
    _write(work, rel, "# rewritten\n")
    r = _verify(work, snap, rel)
    assert r.returncode == 1, r.stdout
    assert "so a yes does not cover it" in _problems(r)[0]


# requirement: cla-setup / Setup checks that its protected files were left alone
def test_an_approval_covers_only_the_path_it_names(work: Path) -> None:
    snap = _snap(work)
    _write(work, TERMS, "# reconciled\n")
    _write(work, OVERLAY, "# edited without a yes\n")
    r = _verify(work, snap, TERMS)
    assert r.returncode == 1, r.stdout
    assert _problems(r) == [f"PROBLEM changed: {OVERLAY} (an overlay; changed without the owner's yes)"]


# ---------------------------------------------------------------- could not check


# requirement: cla-setup / Setup checks that its protected files were left alone
def test_a_missing_snapshot_is_unchecked(work: Path) -> None:
    r = _verify(work, work.parent / "never-written.json")
    assert r.returncode == 2
    assert r.stdout.startswith("UNCHECKED snapshot:")


# requirement: cla-setup / Setup checks that its protected files were left alone
@pytest.mark.parametrize(
    "mangle",
    [
        lambda d: "{not json",
        lambda d: json.dumps([]),
        lambda d: json.dumps({**d, "version": 2}),
        lambda d: json.dumps({**d, "files": {}}),
        lambda d: json.dumps({**d, "files": {**d["files"], "CLAUDE.md": "abc"}}),
        lambda d: json.dumps({**d, "files": {k: v for k, v in d["files"].items() if k != "CLAUDE.md"}}),
        lambda d: json.dumps({**d, "files": {**d["files"], "src/app.py": None}}),
        lambda d: json.dumps({**d, "files": {**d["files"], ".claude/rules/cla-economy.md": None}}),
        lambda d: json.dumps({**d, "created": "yesterday"}),
        lambda d: json.dumps({**d, "created": True}),
        lambda d: json.dumps({**d, "head": "not-a-sha"}),
        lambda d: json.dumps({**d, "root": "/somewhere/else"}),
    ],
    ids=["not-json", "not-an-object", "version", "no-files", "bad-digest", "fixed-path-missing",
         "unprotected-path", "economy-rules-recorded", "bad-created", "bool-created", "bad-head", "other-root"],
)
def test_a_corrupt_snapshot_is_unchecked(work: Path, mangle) -> None:
    snap = _snap(work)
    snap.write_text(mangle(json.loads(snap.read_text(encoding="utf-8"))), encoding="utf-8")
    r = _verify(work, snap)
    assert r.returncode == 2, r.stdout
    assert r.stdout.startswith("UNCHECKED snapshot:")


# requirement: cla-setup / Setup checks that its protected files were left alone
def test_an_approval_outside_the_repo_is_unchecked(work: Path, tmp_path: Path) -> None:
    snap = _snap(work)
    r = _verify(work, snap, str(tmp_path / "outside.md"))
    assert r.returncode == 2 and r.stdout.startswith("UNCHECKED approved:")


# requirement: cla-setup / Setup checks that its protected files were left alone
def test_outside_a_git_repo_is_unchecked(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    r = _run("snapshot", "--root", str(plain), "--out", str(tmp_path / "s.json"))
    assert r.returncode == 2 and r.stdout.startswith("UNCHECKED repo:")
    assert not (tmp_path / "s.json").exists()


# requirement: cla-setup / Setup checks that its protected files were left alone
def test_the_snapshot_is_never_written_into_the_repo(work: Path) -> None:
    for rel in ("snap.json", TOKENS, "cla.io/overlays/snap.md"):
        before = (work / rel).read_bytes() if (work / rel).exists() else None
        r = _run("snapshot", "--root", str(work), "--out", str(work / rel))
        assert r.returncode == 2 and r.stdout.startswith("UNCHECKED out:"), (rel, r.stdout)
        after = (work / rel).read_bytes() if (work / rel).exists() else None
        assert before == after, rel
        why = "git does not ignore it" if rel == "snap.json" else "is a protected path"
        assert why in r.stdout, (rel, r.stdout)
    # A gitignored folder is allowed, and the file it writes there is not seen as a change.
    (work / "temp").mkdir()
    r = _run("snapshot", "--root", str(work), "--out", str(work / "temp" / "snap.json"))
    assert r.returncode == 0, r.stdout
    assert _verify(work, work / "temp" / "snap.json").returncode == 0


# ---------------------------------------------------------------- the skill calls it


# requirement: cla-setup / Setup checks that its protected files were left alone
def test_the_skill_snapshots_first_and_verifies_last() -> None:
    text = _SKILL.read_text(encoding="utf-8").replace("\r\n", "\n")
    snap = text.index('python3 "${CLAUDE_PLUGIN_ROOT}/skills/cla-setup/scripts/setup_guard.py" snapshot')
    verify = text.index('python3 "${CLAUDE_PLUGIN_ROOT}/skills/cla-setup/scripts/setup_guard.py" verify')
    assert snap < text.index("### 1. `cla.io/` directories")
    assert text.index("### 13. Confirm, write, check") < verify < text.index("## Report")
    tail = text[verify:text.index("## Report")]
    exit1 = tail[tail.index("- Exit 1:"):tail.index("- Exit 2:")]
    exit2 = tail[tail.index("- Exit 2:"):]
    assert "not clean" in exit1, "the exit-1 branch must refuse to call the run clean"
    assert "every line after it" in exit1 and "`UNCHECKED`" in exit1, \
        "the exit-1 report must carry the UNCHECKED lines as well as the PROBLEM lines"
    assert "could not run" in exit2 and "every line after it" in exit2
    assert "--approved" in tail
    assert "stop there" not in exit1, "the clean-up after the bullets must run on every exit"
    cleanup = tail[tail.index("- Exit 2:"):]
    assert "whatever the exit" in cleanup and 'rm -f -- "<snapshot file>"' in cleanup, \
        "the snapshot is deleted after verify, on every exit"
    assert 'rmdir -- "$d"' in cleanup, "the mktemp -d folder is removed too"
    report = text[text.index("## Report"):text.index("## Non-goals")]
    assert "post-run check's first line with every line after it" in report
    head = text[text.index("## Snapshot the protected files"):text.index("## Never-clobber contract")]
    assert 'd="$(mktemp -d' in head and '--out "$d/snapshot.json"' in head, \
        "the fallback is a new file in a fresh temp folder, never an existing file"
    assert ".git/" in head


# ---------------------------------------------------------------- more protected files


_NEVER_COVERED = [
    ".claude/settings.json", ".claude-plugin/plugin.json",
    ".claude/rules/house.md", "CLAUDE.local.md", ".claude/CLAUDE.local.md",
]


# requirement: cla-setup / Setup checks that its protected files were left alone
@pytest.mark.parametrize("rel", _NEVER_COVERED)
@pytest.mark.parametrize("action", ["changed", "deleted"])
def test_settings_rules_and_local_instruction_files_fail_even_when_approved(work: Path, rel: str, action: str) -> None:
    _write(work, rel, "{}\n" if rel.endswith(".json") else "# the owner's\n")
    snap = _snap(work)
    if action == "changed":
        _write(work, rel, '{"permissions": {}}\n' if rel.endswith(".json") else "# rewritten\n")
    else:
        (work / rel).unlink()
    r = _verify(work, snap, rel)
    assert r.returncode == 1, r.stdout
    assert len(_problems(r)) == 1 and _problems(r)[0].startswith(f"PROBLEM {action}: {rel} (")
    assert "so a yes does not cover it" in _problems(r)[0]


# requirement: cla-setup / Setup checks that its protected files were left alone
def test_claude_codes_own_permission_writes_pass(work: Path) -> None:
    # Claude Code writes settings.local.json when the user answers a permission prompt with
    # "Yes, don't ask again", which is routine during a setup run that is not in auto mode.
    snap = _snap(work)
    allow = {"permissions": {"allow": ["Bash(git status:*)"]}}
    _write(work, ".claude/settings.local.json", json.dumps(allow, indent=2) + "\n")
    assert _verify(work, snap).returncode == 0
    snap = _snap(work)
    allow["permissions"]["allow"].append("Bash(python3:*)")
    _write(work, ".claude/settings.local.json", json.dumps(allow, indent=2) + "\n")
    r = _verify(work, snap)
    assert r.returncode == 0, r.stdout


# requirement: cla-setup / Setup checks that its protected files were left alone
def test_gitignored_local_instruction_files_are_recorded(work: Path) -> None:
    _write(work, "CLAUDE.local.md", "# mine\n")
    _write(work, ".claude/CLAUDE.local.md", "# mine too\n")
    assert _git(work, "status", "--porcelain").stdout == ""  # both ignored by `*.local.md`
    snap = _snap(work)
    files = json.loads(snap.read_text(encoding="utf-8"))["files"]
    assert files["CLAUDE.local.md"] and files[".claude/CLAUDE.local.md"]
    _write(work, ".claude/CLAUDE.local.md", "# changed\n")
    r = _verify(work, snap)
    assert r.returncode == 1 and _problems(r)[0].startswith("PROBLEM changed: .claude/CLAUDE.local.md (")


# requirement: cla-setup / Setup checks that its protected files were left alone
def test_the_economy_rules_file_beside_a_protected_rules_file_is_not_protected(work: Path) -> None:
    _write(work, ".claude/rules/house.md", "# house rules\n")
    _write(work, ".claude/rules/cla-economy.md", "# old economy rules\n")
    snap = _snap(work)
    _write(work, ".claude/rules/cla-economy.md", "# new economy rules\n")
    assert _verify(work, snap).returncode == 0


def _case_sensitive(d: Path) -> bool:
    probe = d / "Case-Probe.tmp"
    probe.write_text("x", encoding="utf-8")
    try:
        return not (d / "case-probe.tmp").exists()
    finally:
        probe.unlink()


# requirement: cla-setup / Setup checks that its protected files were left alone
@pytest.mark.parametrize("rel", ["claude.md", "agents.md", ".claude/Claude.md"])
def test_an_instruction_file_in_another_letter_case_is_protected(work: Path, rel: str) -> None:
    if not _case_sensitive(work):
        pytest.skip("on a case-insensitive file system the variant is the fixed name itself")
    _write(work, rel, "# lower\n")
    snap = _snap(work)
    _write(work, rel, "# lower, edited\n")
    r = _verify(work, snap)
    assert r.returncode == 1 and _problems(r) == [
        f"PROBLEM changed: {rel} (an instruction file; cla-setup never touches it, so a yes does not cover it)"
    ]
    (work / rel).unlink()
    snap = _snap(work)
    _write(work, rel, "# made by the run\n")
    assert _problems(_verify(work, snap))[0].startswith(f"PROBLEM created: {rel} (")


# ---------------------------------------------------------------- what cannot be read


_symlinks = pytest.mark.skipif(os.name == "nt", reason="symlinks need privileges on Windows")


# requirement: cla-setup / Setup checks that its protected files were left alone
@_symlinks
def test_an_unreadable_protected_file_is_unchecked(work: Path) -> None:
    snap = _snap(work)
    (work / "CLAUDE.md").unlink()
    os.symlink("CLAUDE.md", work / "CLAUDE.md")  # a self-loop: present, never readable
    r = _verify(work, snap)
    assert r.returncode == 2, r.stdout
    assert r.stdout.startswith("UNCHECKED read: CLAUDE.md")


# requirement: cla-setup / Setup checks that its protected files were left alone
@_symlinks
def test_a_found_problem_wins_over_an_unreadable_file(work: Path) -> None:
    snap = _snap(work)
    (work / "CLAUDE.md").unlink()
    os.symlink("CLAUDE.md", work / "CLAUDE.md")
    _write(work, OVERLAY, "# edited without a yes\n")
    r = _verify(work, snap)
    assert r.returncode == 1, r.stdout
    lines = r.stdout.splitlines()
    assert lines[0] == "FAIL verify: 1 protected file problem(s)"
    assert lines[1].startswith(f"PROBLEM changed: {OVERLAY} (")
    assert lines[2].startswith("UNCHECKED read: CLAUDE.md")


# requirement: cla-setup / Setup checks that its protected files were left alone
def test_a_file_replaced_by_a_directory_is_changed(work: Path) -> None:
    snap = _snap(work)
    (work / "AGENTS.md").unlink()
    (work / "AGENTS.md").mkdir()
    r = _verify(work, snap)
    assert r.returncode == 1 and _problems(r)[0].startswith("PROBLEM changed: AGENTS.md (")


# requirement: cla-setup / Setup checks that its protected files were left alone
@_symlinks
def test_a_dangling_link_is_recorded_and_compared(work: Path) -> None:
    (work / "AGENTS.md").unlink()
    os.symlink("gone.md", work / "AGENTS.md")
    snap = _snap(work)
    assert json.loads(snap.read_text(encoding="utf-8"))["files"]["AGENTS.md"] == "not-a-file:dangling-link"
    assert _verify(work, snap).returncode == 0
    (work / "AGENTS.md").unlink()
    _write(work, "AGENTS.md", "# a real file now\n")
    r = _verify(work, snap)
    assert r.returncode == 1 and _problems(r)[0].startswith("PROBLEM changed: AGENTS.md (")


# ---------------------------------------------------------------- where the snapshot goes


# requirement: cla-setup / Setup checks that its protected files were left alone
def test_an_existing_file_is_never_overwritten_by_the_snapshot(work: Path, tmp_path: Path) -> None:
    (work / ".gitignore").write_text("*.local.md\ntemp/\n.env\n", encoding="utf-8")
    _write(work, ".env", "API_KEY=keep-me\n")
    outside = tmp_path / "user-notes.txt"
    outside.write_text("the user's own file\n", encoding="utf-8")
    for target in (work / ".env", outside):
        r = _run("snapshot", "--root", str(work), "--out", str(target))
        assert r.returncode == 2 and r.stdout.startswith("UNCHECKED out:"), r.stdout
        assert "it is not overwritten" in r.stdout
    assert (work / ".env").read_text(encoding="utf-8") == "API_KEY=keep-me\n"
    assert outside.read_text(encoding="utf-8") == "the user's own file\n"


# requirement: cla-setup / Setup checks that its protected files were left alone
def test_the_snapshot_never_clobbers_a_sibling_temp_file(work: Path, tmp_path: Path) -> None:
    sibling = tmp_path / "snap.json.tmp"
    sibling.write_text("someone else's\n", encoding="utf-8")
    _snap(work)
    assert sibling.read_text(encoding="utf-8") == "someone else's\n"
    assert sorted(p.name for p in tmp_path.iterdir() if p.name.startswith(".snap.json")) == []


# requirement: cla-setup / Setup checks that its protected files were left alone
def test_only_an_earlier_snapshot_may_be_replaced(work: Path, tmp_path: Path) -> None:
    out = tmp_path / "snap.json"
    assert _run("snapshot", "--root", str(work), "--out", str(out)).returncode == 0
    assert _run("snapshot", "--root", str(work), "--out", str(out)).returncode == 0  # a re-run
    assert _verify(work, out).returncode == 0


# requirement: cla-setup / Setup checks that its protected files were left alone
def test_an_empty_user_file_is_never_overwritten(work: Path, tmp_path: Path) -> None:
    (work / ".gitignore").write_text("*.local.md\ntemp/\n.env\n", encoding="utf-8")
    (work / ".env").write_bytes(b"")  # touch .env
    empty_outside = tmp_path / "empty.txt"
    empty_outside.write_bytes(b"")
    for target in (work / ".env", empty_outside):
        r = _run("snapshot", "--root", str(work), "--out", str(target))
        assert r.returncode == 2 and r.stdout.startswith("UNCHECKED out:") and "is empty" in r.stdout, r.stdout
        assert target.read_bytes() == b""


# requirement: cla-setup / Setup checks that its protected files were left alone
@_symlinks
@pytest.mark.parametrize("target_text", ["", '{"version": 1}'])
def test_a_symlink_at_out_is_never_written_through(work: Path, tmp_path: Path, target_text: str) -> None:
    target = tmp_path / "users-file"
    target.write_text(target_text, encoding="utf-8")
    link = tmp_path / "snap.json"
    os.symlink(target, link)
    r = _run("snapshot", "--root", str(work), "--out", str(link))
    assert r.returncode == 2 and r.stdout.startswith("UNCHECKED out:") and "is a symlink" in r.stdout, r.stdout
    assert target.read_text(encoding="utf-8") == target_text and os.path.islink(link)


# requirement: cla-setup / Setup checks that its protected files were left alone
def test_a_missing_folder_is_refused_and_not_created(work: Path, tmp_path: Path) -> None:
    r = _run("snapshot", "--root", str(work), "--out", str(tmp_path / "no" / "such" / "snap.json"))
    assert r.returncode == 2 and "does not exist" in r.stdout, r.stdout
    assert not (tmp_path / "no").exists()


# requirement: cla-setup / Setup checks that its protected files were left alone
def test_a_failed_write_leaves_no_file_behind(work: Path, tmp_path: Path, monkeypatch, capsys) -> None:
    spec = importlib.util.spec_from_file_location("setup_guard_failed_write", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    folder = tmp_path / "out"
    folder.mkdir()

    def refuse(src, dst):
        raise OSError("planted: disk full")

    monkeypatch.setattr(mod.os, "replace", refuse)
    assert mod.main(["snapshot", "--root", str(work), "--out", str(folder / "snap.json")]) == 2
    assert capsys.readouterr().out.startswith("UNCHECKED out: cannot write")
    assert list(folder.iterdir()) == []


# requirement: cla-setup / Setup checks that its protected files were left alone
def test_an_out_that_cannot_be_written_is_unchecked(work: Path, tmp_path: Path) -> None:
    (tmp_path / "a-dir").mkdir()
    r = _run("snapshot", "--root", str(work), "--out", str(tmp_path / "a-dir"))
    assert r.returncode == 2 and r.stdout.startswith("UNCHECKED out:") and "is a directory" in r.stdout
    (tmp_path / "a-file").write_text("x", encoding="utf-8")
    r = _run("snapshot", "--root", str(work), "--out", str(tmp_path / "a-file" / "snap.json"))
    assert r.returncode == 2 and "does not exist" in r.stdout, r.stdout
    r = _run("snapshot", "--root", str(work), "--out", str(work / ".git" / "snap.json"))
    assert r.returncode == 2 and "inside the git directory" in r.stdout, r.stdout
    assert not (work / ".git" / "snap.json").exists()


# requirement: cla-setup / Setup checks that its protected files were left alone
@pytest.mark.skipif(os.name == "nt", reason="the stand-in git is a shell script")
def test_a_failing_check_ignore_is_unchecked(work: Path, tmp_path: Path) -> None:
    real = shutil.which("git")
    fake = tmp_path / "fakebin"
    fake.mkdir()
    (fake / "git").write_text(
        "#!/bin/sh\n"
        'for a in "$@"; do [ "$a" = check-ignore ] && { echo "fatal: simulated" >&2; exit 128; }; done\n'
        f'exec "{real}" "$@"\n',
        encoding="utf-8",
    )
    (fake / "git").chmod(0o755)
    env = {**os.environ, "PATH": f"{fake}{os.pathsep}{os.environ['PATH']}"}
    (work / "temp").mkdir()
    r = _run("snapshot", "--root", str(work), "--out", str(work / "temp" / "snap.json"), env=env)
    assert r.returncode == 2 and r.stdout.startswith("UNCHECKED out: git check-ignore failed"), r.stdout


# requirement: cla-setup / Setup checks that its protected files were left alone
def test_a_crash_reads_as_unchecked(work: Path, tmp_path: Path, monkeypatch, capsys) -> None:
    spec = importlib.util.spec_from_file_location("setup_guard_under_test", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    snap = _snap(work)

    def boom(root):
        raise RuntimeError("planted")

    monkeypatch.setattr(mod, "protected_paths", boom)
    assert mod.main(["verify", "--root", str(work), "--snapshot", str(snap)]) == 2
    assert capsys.readouterr().out.startswith("UNCHECKED error: unexpected RuntimeError: planted")


# ---------------------------------------------------------------- stale snapshots


def _edit_snapshot(snap: Path, **fields) -> None:
    data = json.loads(snap.read_text(encoding="utf-8"))
    data.update(fields)
    snap.write_text(json.dumps(data), encoding="utf-8")


# requirement: cla-setup / Setup checks that its protected files were left alone
@pytest.mark.parametrize("offset, words", [(-25 * 3600, "h ago"), (+3600, "in the future")])
def test_a_snapshot_from_another_time_is_unchecked(work: Path, offset: int, words: str) -> None:
    snap = _snap(work)
    _edit_snapshot(snap, created=time.time() + offset)
    _write(work, "CLAUDE.md", "# even a real change is not trusted against it\n")
    r = _verify(work, snap)
    assert r.returncode == 2 and r.stdout.startswith("UNCHECKED snapshot:") and words in r.stdout, r.stdout


# requirement: cla-setup / Setup checks that its protected files were left alone
def test_a_snapshot_a_few_hours_old_still_counts(work: Path) -> None:
    snap = _snap(work)
    _edit_snapshot(snap, created=time.time() - 3 * 3600)
    assert _verify(work, snap).returncode == 0


# requirement: cla-setup / Setup checks that its protected files were left alone
def test_head_moving_off_the_snapshots_line_is_unchecked(work: Path) -> None:
    snap = _snap(work)
    _git(work, "commit", "-q", "--amend", "-m", "rewritten")  # not a descendant of the recorded HEAD
    r = _verify(work, snap)
    assert r.returncode == 2 and r.stdout.startswith("UNCHECKED snapshot: HEAD moved"), r.stdout


# requirement: cla-setup / Setup checks that its protected files were left alone
def test_a_commit_on_top_of_the_snapshot_passes(work: Path) -> None:
    snap = _snap(work)
    _write(work, "cla.io/project-facts.md", "# Facts\n- committed during the run\n")
    _git(work, "commit", "-q", "-am", "facts")
    assert _verify(work, snap).returncode == 0


# requirement: cla-setup / Setup checks that its protected files were left alone
def test_a_head_git_does_not_know_is_unchecked(work: Path) -> None:
    snap = _snap(work)
    _edit_snapshot(snap, head="0" * 40)
    r = _verify(work, snap)
    assert r.returncode == 2 and r.stdout.startswith("UNCHECKED snapshot: cannot relate"), r.stdout


# requirement: cla-setup / Setup checks that its protected files were left alone
def test_a_repo_with_no_commit_yet_is_checked(tmp_path: Path) -> None:
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    _git(fresh, "init", "-q", "-b", "main")
    out = tmp_path / "s.json"
    assert _run("snapshot", "--root", str(fresh), "--out", str(out)).returncode == 0
    assert json.loads(out.read_text(encoding="utf-8"))["head"] is None
    _write(fresh, "CLAUDE.md", "# made by the run\n")
    r = _verify(fresh, out)
    assert r.returncode == 1 and _problems(r)[0].startswith("PROBLEM created: CLAUDE.md (")
