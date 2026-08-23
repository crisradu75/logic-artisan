"""probe_state.py tests.

Patches REPO_ROOT to the tmp repo so subprocess invocations of `git`/`openspec`/`gh`
operate against the test fixture. `gh` is mocked via monkeypatched _run.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

import probe_state

# Loaded by PATH, not as `from conftest import ...`. The dev tree is one pytest
# scope holding five sibling `conftest.py` files, so a bare conftest import
# resolves to whichever one reached `sys.modules` first. That is import-order
# dependent, and the identical import in `tests/hooks/` resolved to the wrong
# module the first time this scope was collapsed into one.
_spec = importlib.util.spec_from_file_location(
    "_ut_spec_to_pr_conftest", Path(__file__).resolve().parent / "conftest.py"
)
_conftest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_conftest)
commit_on_branch = _conftest.commit_on_branch
make_change = _conftest.make_change


REPO_VIEW_KEY = ("gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner")
REPO_VIEW_OK = subprocess.CompletedProcess([], 0, "owner/some-repo\n", "")
REPO_VIEW_FAIL = subprocess.CompletedProcess([], 1, "", "not authenticated")


@pytest.fixture(autouse=True)
def _repo_root(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(probe_state, "REPO_ROOT", tmp_repo)


@pytest.fixture(autouse=True)
def _reset_module_state() -> None:
    """`_base_branch_cache` and the two degradation lists are module globals, so
    one test's resolution would otherwise decide the next one's — and now that
    `probe()` reports the base branch, every test resolves it.

    `_resolved_branch_cache` joins them for the same reason: all three probes
    key off one resolution per change name, so without this a test that resolves
    a fallback branch answers for the next test's fresh repo."""
    probe_state._base_branch_cache = None
    probe_state._resolved_branch_cache.clear()
    probe_state._missing_tools.clear()
    probe_state._environment_errors.clear()
    yield
    probe_state._base_branch_cache = None
    probe_state._resolved_branch_cache.clear()
    probe_state._missing_tools.clear()
    probe_state._environment_errors.clear()


def _stub_run(returns: dict[tuple[str, ...], subprocess.CompletedProcess[str]]):
    def fake(cmd, cwd=None, check=False):
        key = tuple(cmd)
        if key in returns:
            return returns[key]
        # Default to subprocess.run for git commands
        return subprocess.run(cmd, cwd=cwd, check=check, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return fake


def _gh_closed_stubs(branch: str) -> dict:
    """Stubs that make _pr_state return {open: False, url: None} via repo-view failure."""
    return {REPO_VIEW_KEY: REPO_VIEW_FAIL}


def test_no_artifacts(tmp_repo: Path, monkeypatch):
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "missing", "--json"):
            subprocess.CompletedProcess([], 1, "", "no such change"),
        REPO_VIEW_KEY: REPO_VIEW_FAIL,
    }))
    result = probe_state.probe("missing")
    assert result["propose"] is False
    assert result["implement"] is False
    assert result["branch"] is False
    assert result["pr"] == {"open": False, "url": None}
    assert result["fix_rounds_applied"] == 0
    assert result["archived"] is False


def test_archived_detection(tmp_repo: Path, monkeypatch):
    archive_dir = tmp_repo / "openspec" / "changes" / "archive" / "2026-05-03-demo"
    archive_dir.mkdir(parents=True)
    (archive_dir / "proposal.md").write_text("## Why\n", encoding="utf-8")
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "demo", "--json"):
            subprocess.CompletedProcess([], 1, "", ""),
        REPO_VIEW_KEY: REPO_VIEW_FAIL,
    }))
    result = probe_state.probe("demo")
    assert result["archived"] is True
    assert result["propose"] is False


def test_archived_no_suffix_collision(tmp_repo: Path, monkeypatch):
    """Change `bar` must NOT match archive dir `2026-05-03-add-foo-bar`."""
    archive_dir = tmp_repo / "openspec" / "changes" / "archive" / "2026-05-03-add-foo-bar"
    archive_dir.mkdir(parents=True)
    (archive_dir / "proposal.md").write_text("## Why\n", encoding="utf-8")
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "bar", "--json"):
            subprocess.CompletedProcess([], 1, "", ""),
        REPO_VIEW_KEY: REPO_VIEW_FAIL,
    }))
    result = probe_state.probe("bar")
    assert result["archived"] is False, "suffix collision: 'bar' wrongly matched 'add-foo-bar'"


def test_archived_no_match_when_archive_dir_present_but_different_name(tmp_repo: Path, monkeypatch):
    archive_dir = tmp_repo / "openspec" / "changes" / "archive" / "2026-05-03-other-change"
    archive_dir.mkdir(parents=True)
    (archive_dir / "proposal.md").write_text("## Why\n", encoding="utf-8")
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "demo", "--json"):
            subprocess.CompletedProcess([], 1, "", ""),
        REPO_VIEW_KEY: REPO_VIEW_FAIL,
    }))
    result = probe_state.probe("demo")
    assert result["archived"] is False


def test_archived_ignores_non_date_prefixed_dirs(tmp_repo: Path, monkeypatch):
    bad = tmp_repo / "openspec" / "changes" / "archive" / "demo"
    bad.mkdir(parents=True)
    (bad / "proposal.md").write_text("## Why\n", encoding="utf-8")
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "demo", "--json"):
            subprocess.CompletedProcess([], 1, "", ""),
        REPO_VIEW_KEY: REPO_VIEW_FAIL,
    }))
    result = probe_state.probe("demo")
    assert result["archived"] is False


def test_proposal_exists(tmp_repo: Path, monkeypatch):
    make_change(tmp_repo, "demo")
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "demo", "--json"):
            subprocess.CompletedProcess([], 1, "", ""),
        REPO_VIEW_KEY: REPO_VIEW_FAIL,
    }))
    result = probe_state.probe("demo")
    assert result["propose"] is True
    assert result["implement"] is False


def test_implement_complete(tmp_repo: Path, monkeypatch):
    make_change(tmp_repo, "demo")
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "demo", "--json"):
            subprocess.CompletedProcess([], 0, json.dumps({"isComplete": True}), ""),
        REPO_VIEW_KEY: REPO_VIEW_FAIL,
    }))
    result = probe_state.probe("demo")
    assert result["implement"] is True


def test_branch_present_and_ahead(tmp_repo: Path, monkeypatch):
    commit_on_branch(tmp_repo, "feature/demo", "first feature commit")
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "demo", "--json"):
            subprocess.CompletedProcess([], 1, "", ""),
        REPO_VIEW_KEY: REPO_VIEW_FAIL,
    }))
    result = probe_state.probe("demo")
    assert result["branch"] is True


def test_pr_open(tmp_repo: Path, monkeypatch):
    make_change(tmp_repo, "demo")
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "demo", "--json"):
            subprocess.CompletedProcess([], 1, "", ""),
        REPO_VIEW_KEY: REPO_VIEW_OK,
        ("gh", "pr", "view", "feature/demo", "--repo", "owner/some-repo", "--json", "url,state"):
            subprocess.CompletedProcess([], 0,
                json.dumps({"url": "https://example.com/pr/42", "state": "OPEN"}), ""),
    }))
    result = probe_state.probe("demo")
    assert result["pr"] == {"open": True, "url": "https://example.com/pr/42"}


def test_pr_probe_scoped_to_current_repo(tmp_repo: Path, monkeypatch):
    """Regression: _pr_state must scope `gh pr view` by --repo so a fork or
    multiple-PR-on-same-branch context cannot resolve to the wrong PR.

    Mocks: `gh repo view` returns `owner/some-repo`. The unscoped form
    (`gh pr view feature/demo --json url,state`) is intentionally NOT in the
    stub map — if _pr_state ever reverts to that shape, the test fixture's
    fallback subprocess will run real `gh` and the assertion still fails (no
    matching open PR for this tmp repo).
    """
    make_change(tmp_repo, "demo")
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "demo", "--json"):
            subprocess.CompletedProcess([], 1, "", ""),
        REPO_VIEW_KEY: REPO_VIEW_OK,
        # Only the SCOPED form is wired to a successful response. Unscoped form
        # would 404 / hit the wrong repo.
        ("gh", "pr", "view", "feature/demo", "--repo", "owner/some-repo", "--json", "url,state"):
            subprocess.CompletedProcess([], 0,
                json.dumps({"url": "https://example.com/owner/some-repo/pr/7", "state": "OPEN"}), ""),
    }))
    result = probe_state.probe("demo")
    assert result["pr"]["open"] is True
    assert result["pr"]["url"] == "https://example.com/owner/some-repo/pr/7"


def test_pr_state_degrades_when_repo_view_returns_empty_stdout(tmp_repo: Path, monkeypatch):
    """`gh repo view` exits 0 but emits nothing (or whitespace only). _pr_state
    must NOT then call `gh pr view --repo "" ...` — it must short-circuit to
    closed/None."""
    make_change(tmp_repo, "demo")
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "demo", "--json"):
            subprocess.CompletedProcess([], 1, "", ""),
        REPO_VIEW_KEY: subprocess.CompletedProcess([], 0, "\n", ""),
    }))
    result = probe_state.probe("demo")
    assert result["pr"] == {"open": False, "url": None}


def test_pr_state_strips_repo_view_trailing_newline(tmp_repo: Path, monkeypatch):
    """Real `gh repo view` returns stdout with a trailing newline; the helper
    must strip it before forming the --repo argument."""
    make_change(tmp_repo, "demo")
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "demo", "--json"):
            subprocess.CompletedProcess([], 1, "", ""),
        REPO_VIEW_KEY: subprocess.CompletedProcess([], 0, "owner/some-repo\n", ""),
        # If strip is dropped, the lookup key would carry the newline and miss this stub.
        ("gh", "pr", "view", "feature/demo", "--repo", "owner/some-repo", "--json", "url,state"):
            subprocess.CompletedProcess([], 0,
                json.dumps({"url": "https://example.com/pr/9", "state": "OPEN"}), ""),
    }))
    result = probe_state.probe("demo")
    assert result["pr"]["open"] is True


def test_pr_state_degrades_when_repo_view_fails(tmp_repo: Path, monkeypatch):
    """If `gh repo view` itself fails (unauthenticated, no remote), _pr_state
    must degrade to {open: False, url: None} rather than raise."""
    make_change(tmp_repo, "demo")
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "demo", "--json"):
            subprocess.CompletedProcess([], 1, "", ""),
        REPO_VIEW_KEY: REPO_VIEW_FAIL,
    }))
    result = probe_state.probe("demo")
    assert result["pr"] == {"open": False, "url": None}


def test_fix_rounds_counted(tmp_repo: Path, monkeypatch):
    commit_on_branch(tmp_repo, "feature/demo", "feat: demo")
    commit_on_branch(tmp_repo, "feature/demo", "fix: review round 1")
    commit_on_branch(tmp_repo, "feature/demo", "fix: review round 2")
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "demo", "--json"):
            subprocess.CompletedProcess([], 1, "", ""),
        REPO_VIEW_KEY: REPO_VIEW_FAIL,
    }))
    result = probe_state.probe("demo")
    assert result["fix_rounds_applied"] == 2


def test_fix_rounds_uses_distinct_count_not_max(tmp_repo: Path, monkeypatch):
    """Regression: _fix_rounds_applied counts DISTINCT round numbers, not max(N).

    A manual squash that drops round 2 but keeps rounds 1 and 3 must report 2
    (distinct rounds present), not 3 (max number). The round counter is
    consumed downstream as 'next round to apply' and a wrong count silently
    breaks Revise's diff-scoping.
    """
    commit_on_branch(tmp_repo, "feature/demo", "feat: demo")
    commit_on_branch(tmp_repo, "feature/demo", "fix: review round 1")
    commit_on_branch(tmp_repo, "feature/demo", "fix: review round 3")
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "demo", "--json"):
            subprocess.CompletedProcess([], 1, "", ""),
        REPO_VIEW_KEY: REPO_VIEW_FAIL,
    }))
    result = probe_state.probe("demo")
    assert result["fix_rounds_applied"] == 2, (
        "must count distinct round numbers (1 and 3 present, round 2 squashed) "
        "and not max(N)"
    )


def test_fix_rounds_dedupes_repeated_round_numbers(tmp_repo: Path, monkeypatch):
    """Two commits both labeled `fix: review round 1` (e.g. round 1 was squashed
    and re-applied) must collapse to 1, not 2. Pins the dedup behavior so a
    refactor from `set` to `list` would be caught."""
    commit_on_branch(tmp_repo, "feature/demo", "feat: demo")
    commit_on_branch(tmp_repo, "feature/demo", "fix: review round 1")
    commit_on_branch(tmp_repo, "feature/demo", "fix: review round 1")
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "demo", "--json"):
            subprocess.CompletedProcess([], 1, "", ""),
        REPO_VIEW_KEY: REPO_VIEW_FAIL,
    }))
    result = probe_state.probe("demo")
    assert result["fix_rounds_applied"] == 1, (
        "duplicate round numbers must dedupe — len(set(rounds)), not len(rounds)"
    )


def test_tools_missing_surfaces_in_result(tmp_repo: Path, monkeypatch):
    """Regression: when openspec.cmd or gh is not on PATH, _run catches the
    FileNotFoundError and records the tool as missing. probe() must surface
    `tools_missing` in the JSON so the orchestrator distinguishes "phase
    not done" from "tool unavailable" — the documented Windows-degradation
    contract. Without this, missing tools look identical to incomplete
    workflows and resume picks the wrong phase."""
    def fake_run(cmd, cwd=None, check=False):
        # Simulate openspec.cmd missing on PATH (the typical Windows path).
        if cmd and cmd[0] == "openspec":
            if cmd[0] not in probe_state._missing_tools:
                probe_state._missing_tools.append(cmd[0])
            return subprocess.CompletedProcess(
                cmd, returncode=probe_state._TOOL_MISSING_RC, stdout="",
                stderr=f"executable not found: {cmd[0]}")
        # Other commands fall through to a generic non-zero so the rest of
        # probe() can complete without exploding.
        return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="")

    monkeypatch.setattr(probe_state, "_run", fake_run)
    result = probe_state.probe("demo")
    assert "tools_missing" in result, (
        "tools_missing must appear in result whenever any required tool is unavailable"
    )
    assert "openspec" in result["tools_missing"]
    assert result["implement"] is False  # not "complete" — we couldn't tell


# --------------------------------------------------------------------------- #
# Degradation must be reported, never mistaken for a legitimate negative
# --------------------------------------------------------------------------- #


def test_run_survives_an_unusable_working_directory(tmp_repo: Path, monkeypatch):
    """`cwd=` raises `NotADirectoryError`/`PermissionError` — both `OSError`,
    neither `FileNotFoundError`. Catching only the latter meant the script died
    with an uncaught traceback and emitted NO JSON at all, which is strictly
    worse for a caller that parses stdout than any reported failure. Uses a
    real FILE as cwd (not merely a nonexistent path) — the actual "cwd is not
    a directory" trigger the surrounding code comment describes."""
    not_a_directory = tmp_repo / "README.md"
    assert not_a_directory.is_file(), "fixture must provide a real file, not a missing path"

    def raise_not_a_directory(*args, **kwargs):
        raise NotADirectoryError(20, "Not a directory")

    monkeypatch.setattr(probe_state, "REPO_ROOT", not_a_directory)
    monkeypatch.setattr(probe_state.subprocess, "run", raise_not_a_directory)
    result = probe_state._run(["git", "status"])
    assert result.returncode == probe_state._ENVIRONMENT_RC
    assert "working directory unusable" in result.stderr


def test_run_survives_a_permission_denied_working_directory(tmp_repo: Path, monkeypatch):
    """`Path.is_dir()` does NOT swallow every `OSError` — `EACCES` is not in its
    ignored-errno set, so it RE-RAISES a `PermissionError` from `.stat()`. Since
    the classifier here calls `Path(target_cwd).is_dir()` from inside the
    `except (OSError, ...)` handling a `PermissionError` from `subprocess.run`,
    an unguarded call would let that second `PermissionError` escape `_run`
    entirely — a raise during exception handling, and precisely the "no JSON
    at all" failure this function's own docstring says must never happen."""
    def raise_permission_denied(*args, **kwargs):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(probe_state.subprocess, "run", raise_permission_denied)
    monkeypatch.setattr(
        probe_state.Path, "is_dir",
        lambda self: (_ for _ in ()).throw(PermissionError(13, "Permission denied")),
    )
    result = probe_state._run(["git", "status"], cwd=tmp_repo)
    assert result.returncode == probe_state._ENVIRONMENT_RC
    assert "working directory unusable" in result.stderr


def test_a_bad_cwd_is_not_reported_as_a_missing_tool(tmp_repo: Path, monkeypatch):
    """A bad cwd that raises `FileNotFoundError` was recorded as
    `tools_missing: ["git"]` — a false diagnostic pointing at PATH for a
    problem PATH has nothing to do with."""
    probe_state._missing_tools.clear()
    probe_state._environment_errors.clear()

    def raise_not_found(*args, **kwargs):
        raise FileNotFoundError(2, "No such file or directory")

    monkeypatch.setattr(probe_state, "REPO_ROOT", tmp_repo / "definitely-not-here")
    monkeypatch.setattr(probe_state.subprocess, "run", raise_not_found)
    result = probe_state._run(["git", "status"])
    assert result.returncode == probe_state._ENVIRONMENT_RC
    assert probe_state._missing_tools == []
    assert probe_state._environment_errors, "the environment failure must be recorded"


def test_a_genuinely_missing_executable_is_still_reported_as_such(tmp_repo: Path, monkeypatch):
    probe_state._missing_tools.clear()
    probe_state._environment_errors.clear()

    def raise_not_found(*args, **kwargs):
        raise FileNotFoundError(2, "No such file or directory")

    monkeypatch.setattr(probe_state.subprocess, "run", raise_not_found)
    result = probe_state._run(["openspec", "status"])
    assert result.returncode == probe_state._TOOL_MISSING_RC
    assert probe_state._missing_tools == ["openspec"]
    assert probe_state._environment_errors == []


def test_run_passes_a_timeout_and_survives_expiry(tmp_repo: Path, monkeypatch):
    """Unbounded, every `gh` call could hang on a credential prompt — the one
    failure an orchestrator waiting on stdout can never recover from."""
    captured = {}

    def fake_run(cmd, **kwargs):
        captured.update(kwargs)
        raise subprocess.TimeoutExpired(cmd, 30)

    monkeypatch.setattr(probe_state.subprocess, "run", fake_run)
    probe_state._environment_errors.clear()
    result = probe_state._run(["gh", "pr", "view"])
    assert captured.get("timeout"), "_run must pass a subprocess timeout"
    assert result.returncode == probe_state._ENVIRONMENT_RC
    assert probe_state._environment_errors


def test_environment_errors_surface_in_the_probe_result(tmp_repo: Path, monkeypatch):
    def fake_run(cmd, cwd=None, check=False):
        probe_state._environment_errors.append("working directory unusable: /nope")
        return subprocess.CompletedProcess(cmd, returncode=probe_state._ENVIRONMENT_RC,
                                           stdout="", stderr="working directory unusable")

    monkeypatch.setattr(probe_state, "_run", fake_run)
    result = probe_state.probe("demo")
    assert "environment_errors" in result
    assert "tools_missing" not in result


def test_probe_resets_the_base_branch_cache_between_calls(tmp_repo: Path, monkeypatch):
    # `probe()` clears `_missing_tools`/`_environment_errors` between calls;
    # `_base_branch_cache` must reset alongside them, or a second `probe()` in
    # the same process reports a `base_branch` resolved under the PREVIOUS
    # call's conditions with no re-warning.
    probe_state._base_branch_cache = "stale-from-a-previous-call"
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "demo", "--json"):
            subprocess.CompletedProcess([], 1, "", "no such change"),
        REPO_VIEW_KEY: REPO_VIEW_FAIL,
        ("git", "rev-parse", "--verify", "--quiet", "refs/heads/main"):
            subprocess.CompletedProcess([], 0, "abc123\n", ""),
    }))
    result = probe_state.probe("demo")
    assert result["base_branch"] != "stale-from-a-previous-call"


def test_probe_reports_the_resolved_base_branch(tmp_repo: Path, monkeypatch):
    """`branch` and `fix_rounds_applied` are both computed from a
    `<base>..<branch>` range, so a wrongly-resolved base turns them into
    plausible-looking negatives. Report the value rather than making the reader
    infer it from work being redone."""
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("openspec", "status", "--change", "demo", "--json"):
            subprocess.CompletedProcess([], 1, "", "no such change"),
        REPO_VIEW_KEY: REPO_VIEW_FAIL,
    }))
    result = probe_state.probe("demo")
    assert result["base_branch"] == probe_state._base_branch()
    assert result["base_branch"], "a base branch is always resolved to something"


def test_base_branch_ignores_a_dangling_origin_head(tmp_repo: Path, monkeypatch):
    """`refs/remotes/origin/HEAD` is a clone-time cache git never refreshes and
    `symbolic-ref` exits 0 on a dangling symref, so after an upstream
    `master`→`main` rename it names a ref that is gone. Trusting it unverified
    returned `master` in a `main` repo — and the caller's `master..HEAD` then
    died with `unknown revision`, the exact failure this resolver prevents."""
    def fake_run(cmd, cwd=None, check=False):
        if cmd[:2] == ["git", "symbolic-ref"]:
            return subprocess.CompletedProcess(cmd, 0, "refs/remotes/origin/master\n", "")
        if cmd[:4] == ["git", "rev-parse", "--verify", "--quiet"]:
            ref = cmd[4]
            ok = ref == "refs/heads/main"
            return subprocess.CompletedProcess(cmd, 0 if ok else 1, "abc123\n" if ok else "", "")
        return subprocess.CompletedProcess(cmd, 1, "", "")

    monkeypatch.setattr(probe_state, "_run", fake_run)
    assert probe_state._base_branch() == "main"


def test_base_branch_announces_the_master_guess(tmp_repo: Path, monkeypatch, capsys):
    monkeypatch.setattr(probe_state, "_run",
                        lambda cmd, cwd=None, check=False:
                        subprocess.CompletedProcess(cmd, 1, "", ""))
    assert probe_state._base_branch() == "master"
    assert "could not resolve the base branch" in capsys.readouterr().err


def test_base_branch_handles_a_slash_containing_default_branch(tmp_repo: Path, monkeypatch):
    # Mirrors the identical fix in `_dispatch_lib.default_base_branch`:
    # `rsplit("/", 1)[-1]` would truncate `release/main` to `main`, and
    # `rev-parse --verify` on the FULL target succeeds regardless of what
    # candidate name was derived from it — so the truncated name passed every
    # check and resolved to a branch that doesn't exist.
    def fake_run(cmd, cwd=None, check=False):
        if cmd[:2] == ["git", "symbolic-ref"]:
            return subprocess.CompletedProcess(cmd, 0, "refs/remotes/origin/release/main\n", "")
        if cmd[:4] == ["git", "rev-parse", "--verify", "--quiet"] and cmd[4] == "refs/remotes/origin/release/main":
            return subprocess.CompletedProcess(cmd, 0, "abc123\n", "")
        return subprocess.CompletedProcess(cmd, 1, "", "")

    monkeypatch.setattr(probe_state, "_run", fake_run)
    assert probe_state._base_branch() == "release/main"


def test_base_branch_is_silent_on_success(tmp_repo: Path, monkeypatch, capsys):
    # Mirrors `_dispatch_lib`'s `test_a_successful_resolution_is_silent`: the
    # stderr note belongs to the GUESS, not to every call.
    monkeypatch.setattr(probe_state, "_run", _stub_run({
        ("git", "rev-parse", "--verify", "--quiet", "refs/heads/main"):
            subprocess.CompletedProcess([], 0, "abc123\n", ""),
    }))
    assert probe_state._base_branch() == "main"
    assert capsys.readouterr().err == ""


def test_branch_state_reports_a_failed_range(tmp_repo: Path, monkeypatch, capsys):
    """`False` reads as "no feature branch yet" and the orchestrator re-runs
    completed work — so an `unknown revision` from a wrong base must say so."""
    def fake_run(cmd, cwd=None, check=False):
        if cmd[:3] == ["git", "rev-parse", "--verify"] and cmd[-1].startswith("feature/"):
            return subprocess.CompletedProcess(cmd, 0, "abc123\n", "")
        if cmd[:2] == ["git", "rev-list"]:
            return subprocess.CompletedProcess(cmd, 128, "", "fatal: unknown revision")
        return subprocess.CompletedProcess(cmd, 1, "", "")

    monkeypatch.setattr(probe_state, "_run", fake_run)
    assert probe_state._branch_state("demo") is False
    assert "unknown revision" in capsys.readouterr().err


def test_fix_rounds_reports_a_failed_range(tmp_repo: Path, monkeypatch, capsys):
    """Same hazard: `0` reads as "no fix rounds applied yet"."""
    def fake_run(cmd, cwd=None, check=False):
        if cmd[:2] == ["git", "log"]:
            return subprocess.CompletedProcess(cmd, 128, "", "fatal: unknown revision")
        return subprocess.CompletedProcess(cmd, 1, "", "")

    monkeypatch.setattr(probe_state, "_run", fake_run)
    assert probe_state._fix_rounds_applied("demo") == 0
    assert "unknown revision" in capsys.readouterr().err


def test_branch_state_suppresses_the_diagnostic_when_the_tool_is_already_reported_missing(
    tmp_repo: Path, monkeypatch, capsys,
):
    # A missing tool is already surfaced via `tools_missing` — printing a
    # SECOND "range failed" diagnostic for the same root cause would be
    # confusing noise, not a new fact.
    def fake_run(cmd, cwd=None, check=False):
        if cmd[:3] == ["git", "rev-parse", "--verify"] and cmd[-1].startswith("feature/"):
            return subprocess.CompletedProcess(cmd, 0, "abc123\n", "")
        if cmd[:4] == ["git", "rev-parse", "--verify", "--quiet"] and cmd[4] == "refs/heads/main":
            return subprocess.CompletedProcess(cmd, 0, "abc123\n", "")  # base branch resolves silently
        if cmd[:2] == ["git", "rev-list"]:
            return subprocess.CompletedProcess(
                cmd, probe_state._TOOL_MISSING_RC, "", "executable not found: git")
        return subprocess.CompletedProcess(cmd, 1, "", "")

    monkeypatch.setattr(probe_state, "_run", fake_run)
    assert probe_state._branch_state("demo") is False
    assert capsys.readouterr().err == ""


def test_fix_rounds_suppresses_the_diagnostic_when_the_tool_is_already_reported_missing(
    tmp_repo: Path, monkeypatch, capsys,
):
    def fake_run(cmd, cwd=None, check=False):
        if cmd[:4] == ["git", "rev-parse", "--verify", "--quiet"] and cmd[4] == "refs/heads/main":
            return subprocess.CompletedProcess(cmd, 0, "abc123\n", "")  # base branch resolves silently
        if cmd[:2] == ["git", "log"]:
            return subprocess.CompletedProcess(
                cmd, probe_state._TOOL_MISSING_RC, "", "executable not found: git")
        return subprocess.CompletedProcess(cmd, 1, "", "")

    monkeypatch.setattr(probe_state, "_run", fake_run)
    assert probe_state._fix_rounds_applied("demo") == 0
    assert capsys.readouterr().err == ""


# --------------------------------------------------------------------------- #
# _resolve_branch -- the clean false negative that made the orchestrator
# redo finished work
# --------------------------------------------------------------------------- #


def test_the_configured_branch_is_used_when_it_exists(tmp_repo: Path):
    """Non-vacuity partner, and it must come first: if the fallback ran even
    when the configured name resolves, every repo would pay a `for-each-ref`
    and the suffix search could adopt a DIFFERENT branch than the one the run
    actually created."""
    commit_on_branch(tmp_repo, "feature/add-auth", "work")
    assert probe_state._resolve_branch("add-auth") == "feature/add-auth"


def test_a_branch_on_another_convention_is_found_and_announced(tmp_repo, capsys):
    """The reported bug. `references/ship.md` permits shortening a change name,
    and a convention varying its MIDDLE segment (`claude/fix/x`) cannot be
    expressed by any single prefix — so all three probes missed, `rev-parse
    --verify --quiet` exited 1 with empty stderr, and the orchestrator read
    `branch: false, pr: {open: false}, fix_rounds_applied: 0` as "nothing done
    yet". It then redoes finished work and can open a duplicate branch and PR.
    """
    commit_on_branch(tmp_repo, "claude/fix/add-auth", "work")
    assert probe_state._resolve_branch("add-auth") == "claude/fix/add-auth"
    err = capsys.readouterr().err
    assert "claude/fix/add-auth" in err, "adopting a different branch must be announced"


def test_an_ambiguous_match_refuses_to_guess(tmp_repo, capsys):
    """Committing onto the wrong one of several same-named branches is worse
    than reporting nothing, so ambiguity falls back to the configured name."""
    commit_on_branch(tmp_repo, "claude/fix/add-auth", "a")
    commit_on_branch(tmp_repo, "claude/feature/add-auth", "b")
    assert probe_state._resolve_branch("add-auth") == "feature/add-auth"
    err = capsys.readouterr().err
    assert "refusing to guess" in err


def test_a_partial_name_match_is_not_accepted(tmp_repo):
    """Matching the final path SEGMENT, not a bare `endswith`: otherwise
    `feature/hotfix-add-auth` answers for change `add-auth` and the probe
    reports against a branch belonging to different work."""
    commit_on_branch(tmp_repo, "feature/hotfix-add-auth", "unrelated")
    assert probe_state._resolve_branch("add-auth") == "feature/add-auth"


def test_no_match_at_all_is_silent_and_keeps_the_configured_name(tmp_repo, capsys):
    """The ordinary "not started yet" case must stay quiet — a note here would
    fire on every first run of every change."""
    assert probe_state._resolve_branch("add-auth") == "feature/add-auth"
    assert capsys.readouterr().err == ""
