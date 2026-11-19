"""`check_catalog_tags.py` fails while a catalog `ref` names a tag the remote lacks.

Every test builds a real repo with a local bare `origin` (`<tmp>/origin.git`, no
network) and two catalogs shaped like this repo's. The tag set on the REMOTE is
what varies, so each exit path is reached by the state it describes rather than
by a mocked call. Asserting the exit code alone would pass against a check that
had stopped reading the catalogs, so the failing paths also assert what is named.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

import check_catalog_tags as cct

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SCRIPT = _REPO_ROOT / ".claude" / "skills" / "release" / "scripts" / "check_catalog_tags.py"
_SKILL_MD = _REPO_ROOT / ".claude" / "skills" / "release" / "SKILL.md"

_CLAUDE = ".claude-plugin/marketplace.json"
_COPILOT = ".github/plugin/marketplace.json"


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True,
        text=True, encoding="utf-8", errors="replace",
    )


def _write_catalogs(work: Path, claude_ref: str, copilot_ref: str) -> None:
    for rel, ref in ((_CLAUDE, claude_ref), (_COPILOT, copilot_ref)):
        path = work / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "name": "placeholder-market",
            "plugins": [{"name": "cla", "source": {"path": "p", "ref": ref}}],
        }), encoding="utf-8")


@pytest.fixture
def work(tmp_path: Path) -> Path:
    """A checkout pushed to a bare `origin` that holds the tag `cla--v1.0.0` (annotated)."""
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", "origin.git")
    work = tmp_path / "work"
    work.mkdir()
    _git(work, "init", "-q", "-b", "main")
    _git(work, "config", "user.email", "test@example.com")
    _git(work, "config", "user.name", "Test")
    _write_catalogs(work, "cla--v1.0.0", "cla--v1.0.0")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "initial")
    _git(work, "remote", "add", "origin", "../origin.git")
    _git(work, "tag", "-a", "-m", "release", "cla--v1.0.0")
    _git(work, "push", "-q", "origin", "main", "cla--v1.0.0")
    return work


def _run(work: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    # A neutral cwd: the script must check --root, not wherever it was started.
    return subprocess.run(
        [sys.executable, str(_SCRIPT), "--root", str(work), *extra],
        cwd=Path(__file__).parent, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120,
    )


# requirement: plugin-distribution / A catalog never names a missing tag
def test_passes_when_every_ref_names_a_tag_on_the_remote(work: Path):
    r = _run(work)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "2 catalog ref(s)" in r.stdout


# requirement: plugin-distribution / A catalog never names a missing tag
def test_a_ref_with_no_tag_fails_and_is_named(work: Path):
    """The 2.0.0 and 2.4.0 shape: the bump is merged, the tag never pushed."""
    _write_catalogs(work, "cla--v1.1.0", "cla--v1.1.0")
    r = _run(work)
    assert r.returncode == 1, r.stdout + r.stderr
    assert f"{_CLAUDE}: plugin `cla` pins `cla--v1.1.0`, missing on origin" in r.stdout
    assert f"{_COPILOT}: plugin `cla` pins `cla--v1.1.0`, missing on origin" in r.stdout


# requirement: plugin-distribution / A catalog never names a missing tag
def test_one_stale_catalog_is_caught_even_when_the_other_is_tagged(work: Path):
    _write_catalogs(work, "cla--v1.0.0", "cla--v9.9.9")
    r = _run(work)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "1 of 2" in r.stdout
    assert f"{_COPILOT}: plugin `cla` pins `cla--v9.9.9`" in r.stdout
    assert _CLAUDE not in r.stdout


# requirement: plugin-distribution / A catalog never names a missing tag
def test_a_tag_only_in_the_local_clone_counts_as_missing(work: Path):
    """The cloud-session shape: `claude plugin tag` created the tag, the push got 403."""
    _git(work, "tag", "cla--v1.1.0")
    _write_catalogs(work, "cla--v1.1.0", "cla--v1.1.0")
    r = _run(work)
    assert r.returncode == 1, r.stdout + r.stderr
    _git(work, "push", "-q", "origin", "cla--v1.1.0")
    assert _run(work).returncode == 0


def test_a_branch_named_like_the_tag_is_not_a_tag(work: Path):
    _git(work, "push", "-q", "origin", "main:refs/heads/cla--v1.1.0")
    _write_catalogs(work, "cla--v1.1.0", "cla--v1.1.0")
    assert _run(work).returncode == 1


# requirement: plugin-distribution / A catalog never names a missing tag
def test_an_unreachable_remote_is_not_checked_never_a_pass(work: Path):
    _git(work, "remote", "set-url", "origin", "../no-such-remote.git")
    r = _run(work)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "NOT CHECKED" in r.stdout


@pytest.mark.parametrize("broken", [
    pytest.param("missing", id="catalog-missing"),
    pytest.param("not json {", id="catalog-not-json"),
    pytest.param(json.dumps({"plugins": [{"name": "cla", "source": {"path": "p"}}]}),
                 id="catalog-pins-no-ref"),
    pytest.param(json.dumps({"plugins": []}), id="catalog-lists-no-plugin"),
])
def test_a_catalog_that_cannot_be_read_is_not_checked(work: Path, broken: str):
    """Reading no ref must not read as "nothing dangling"."""
    path = work / _COPILOT
    if broken == "missing":
        path.unlink()
    else:
        path.write_text(broken, encoding="utf-8")
    r = _run(work)
    assert r.returncode == 2, r.stdout + r.stderr
    assert _COPILOT in r.stdout


def test_the_real_catalogs_each_pin_a_release_tag():
    """Read-only, no network: the script reads this repo's two catalogs, one ref each."""
    refs = cct.catalog_refs(_REPO_ROOT)
    assert [rel for rel, _, _ in refs] == [_CLAUDE, _COPILOT]
    assert all(ref.startswith("cla--v") for _, _, ref in refs)


def _step(body: str, start: str, end: str) -> str:
    assert start in body and end in body, f"release/SKILL.md lost {start!r} or {end!r}"
    return body.split(start, 1)[1].split(end, 1)[0]


# requirement: plugin-distribution / A catalog never names a missing tag
def test_the_skill_runs_the_check_before_and_after_the_tag():
    """The precondition and the postcondition are both commands, in fenced blocks:
    a mention in a table cell or a sentence is not a run."""
    body = _SKILL_MD.read_text(encoding="utf-8")
    command = "python3 .claude/skills/release/scripts/check_catalog_tags.py"
    for start, end in (("## Step 1", "## Step 2"), ("## Step 4", "## Step 5")):
        blocks = "\n".join(re.findall(r"```bash\n(.*?)```", _step(body, start, end), re.S))
        assert command in blocks, f"release/SKILL.md {start} no longer runs {command}"
    step_5 = _step(body, "## Step 5", "## When NOT to use")
    assert "only after Step 4's `check_catalog_tags.py` exited 0" in step_5

