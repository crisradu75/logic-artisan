"""Tests for the two PreToolUse dispatcher scripts (dispatch-bash-pretooluse.py,
dispatch-edit-write-pretooluse.py), which each replace 5 separate hook-process
spawns with 1 in-process run via `_dispatch_lib`. These exercise a representative
block / warn / allow case per dispatcher, end-to-end via subprocess, to confirm
the consolidation preserves each sibling hook's original semantics.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

_HOOKS_DIR = Path(__file__).resolve().parent.parent
_BASH_DISPATCH = _HOOKS_DIR / "dispatch-bash-pretooluse.py"
_EDIT_WRITE_DISPATCH = _HOOKS_DIR / "dispatch-edit-write-pretooluse.py"


def _run(
    script: Path,
    payload: dict,
    cwd: Path | None = None,
    extra_env: dict | None = None,
) -> subprocess.CompletedProcess:
    # The subprocess inherits this shell's environment, so a developer with
    # CLA_EXPECTED_GIT_EMAIL or either ALLOW_* override set would flip these
    # tests' results. Neutralise every switch the dispatched hooks read, and let
    # a test opt one back in explicitly.
    env = {
        **os.environ,
        "ALLOW_SHARED_CLONE_MUTATION": "",
        "ALLOW_WORKTREE_PATH_ESCAPE": "",
        "ALLOW_DESTRUCTIVE_GIT": "",
        "ALLOW_GIT_IDENTITY_MISMATCH": "",
        "CLA_EXPECTED_GIT_EMAIL": "",
    }
    env.update(extra_env or {})
    return subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload), capture_output=True, text=True,
        cwd=str(cwd) if cwd else None,
        env=env,
    )


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True)


def _hooks_copy(tmp_path: Path) -> Path:
    """Copy every hook script (dispatchers + _dispatch_lib + siblings) into a
    scratch directory so a test can corrupt one file's copy without touching
    the real hooks this whole test suite depends on."""
    dest = tmp_path / "hooks"
    dest.mkdir()
    for f in _HOOKS_DIR.glob("*.py"):
        shutil.copy(f, dest / f.name)
    return dest


# --------------------------------------------------------------------------- #
# Bash dispatcher
# --------------------------------------------------------------------------- #

def test_bash_dispatch_blocks_cd(tmp_path):
    r = _run(_BASH_DISPATCH, {"tool_input": {"command": "cd /tmp && ls"}, "cwd": str(tmp_path)})
    assert r.returncode == 2
    assert "block-cd-in-bash.py" in r.stderr


def test_bash_dispatch_blocks_unsafe_worktree_delete(tmp_path):
    target = tmp_path / ".claude" / "worktrees" / "some-change"
    target.mkdir(parents=True)
    r = _run(_BASH_DISPATCH, {"tool_input": {"command": f"rm -rf {target}"}, "cwd": str(tmp_path)})
    assert r.returncode == 2
    assert "block-unsafe-recursive-delete.py" in r.stderr


def test_bash_dispatch_warns_branch_base_off_non_master(tmp_path):
    _git(tmp_path, "init", "-b", "feature/base")
    _git(tmp_path, "config", "user.email", "t@t.t")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "f.txt").write_text("x", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "init")

    r = _run(
        _BASH_DISPATCH,
        {"tool_input": {"command": "git checkout -b feature/new-thing"}, "cwd": str(tmp_path)},
        cwd=tmp_path,
    )
    assert r.returncode == 0
    assert "warn-branch-base" in r.stderr
    assert "feature/base" in r.stderr


def test_bash_dispatch_allows_clean_command(tmp_path):
    r = _run(_BASH_DISPATCH, {"tool_input": {"command": "git status"}, "cwd": str(tmp_path)}, cwd=tmp_path)
    assert r.returncode == 0
    assert r.stderr.strip() == ""


def test_bash_dispatch_isolates_a_broken_sibling_hook(tmp_path):
    # A hook that fails to LOAD (position 1) must not prevent a LATER hook
    # (position 2) from still evaluating and blocking — the whole point of
    # run_hook_file's load-failure isolation.
    hooks_dir = _hooks_copy(tmp_path)
    (hooks_dir / "block-cd-in-bash.py").write_text("this is ) not ( valid python !!!", encoding="utf-8")

    r = subprocess.run(
        [sys.executable, str(hooks_dir / "dispatch-bash-pretooluse.py")],
        input=json.dumps({"tool_input": {"command": "git push origin main"}, "cwd": str(tmp_path)}),
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert r.returncode == 2
    assert "block-direct-push-to-main.py" in r.stderr  # the later hook still fired and blocked
    assert "block-cd-in-bash.py" in r.stderr           # the load failure is surfaced, not silent
    assert "failed to load" in r.stderr


def test_bash_dispatch_reports_a_crashed_hook_as_context(tmp_path):
    """A crashed hook must reach Claude — and exit 1 is the wrong way to do it.

    A non-zero exit discards stdout entirely and surfaces only the FIRST LINE of
    stderr, so it reports strictly less than additionalContext does. The failure
    therefore travels as context at exit 0, whole.
    """
    hooks_dir = _hooks_copy(tmp_path)
    (hooks_dir / "warn-branch-base.py").write_text(
        "def main():\n    raise RuntimeError('boom')\n", encoding="utf-8"
    )

    r = subprocess.run(
        [sys.executable, str(hooks_dir / "dispatch-bash-pretooluse.py")],
        input=json.dumps({"tool_input": {"command": "ls -la"}, "cwd": str(tmp_path)}),
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert r.returncode == 0
    context = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "warn-branch-base" in context
    assert "boom" in context
    # Still written to stderr as well, for `claude --debug`.
    assert "boom" in r.stderr


# --------------------------------------------------------------------------- #
# Edit|Write dispatcher
# --------------------------------------------------------------------------- #

def test_edit_write_dispatch_blocks_path_escape(tmp_path):
    primary = tmp_path / "primary"
    primary.mkdir()
    _git(primary, "init", "-b", "master")
    _git(primary, "config", "user.email", "t@t.t")
    _git(primary, "config", "user.name", "t")
    (primary / "f.txt").write_text("x", encoding="utf-8")
    _git(primary, "add", "-A")
    _git(primary, "commit", "-m", "init")
    wt = tmp_path / "wt"
    _git(primary, "worktree", "add", str(wt), "-b", "feature/x")

    escape_target = primary / "escaped.txt"
    r = subprocess.run(
        [sys.executable, str(_EDIT_WRITE_DISPATCH)],
        input=json.dumps({"tool_input": {"file_path": str(escape_target), "content": "x"}}),
        capture_output=True, text=True, cwd=str(wt),
        env={**os.environ, "ALLOW_WORKTREE_PATH_ESCAPE": ""},
    )
    assert r.returncode == 2
    assert "block-worktree-path-escape.py" in r.stderr


def test_edit_write_dispatch_warns_comment_date(tmp_path):
    target = tmp_path / "script.py"
    target.write_text("x = 1\n", encoding="utf-8")
    r = _run(
        _EDIT_WRITE_DISPATCH,
        {
            "tool_input": {
                "file_path": str(target),
                "old_string": "x = 1",
                "new_string": "x = 1  # confirmed 2026-07-12",
            },
            "cwd": str(tmp_path),
        },
        cwd=tmp_path,
    )
    assert r.returncode == 0
    out = json.loads(r.stdout)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "YYYY-MM-DD" in ctx


def test_edit_write_dispatch_allows_clean_edit(tmp_path):
    target = tmp_path / "notes.ts"
    r = _run(
        _EDIT_WRITE_DISPATCH,
        {"tool_input": {"file_path": str(target), "content": "export const x = 1;\n"}, "cwd": str(tmp_path)},
        cwd=tmp_path,
    )
    assert r.returncode == 0
    assert r.stdout.strip() == ""
    assert r.stderr.strip() == ""


def test_edit_write_dispatch_does_not_drop_earlier_warning_when_later_hook_blocks(tmp_path):
    # Regression: warn-smoke-test-drift.py (position 4) fires a non-blocking
    # stdout-JSON warning, then block-worktree-path-escape.py (position 5)
    # blocks on the same edit. The earlier warning must still reach the user
    # via stderr (the only channel fed back on a block) instead of vanishing.
    #
    # warn-smoke-test-drift.py is config-driven (a `smoke-test-drift.local.md`
    # overlay beside the hook — see its own module docstring), so this uses
    # `_hooks_copy` to drop that overlay into a SCRATCH hooks dir rather than
    # the real one: this repo ships no product code and deliberately carries
    # no such overlay.
    hooks_dir = _hooks_copy(tmp_path)
    (hooks_dir / "smoke-test-drift.local.md").write_text(
        "---\n"
        "component_path_substring: src/components/\n"
        "component_ext: .tsx\n"
        "i18n_path_substring: src/i18n/\n"
        "i18n_ext: .json\n"
        "smoke_test_relpath: test-app.mjs\n"
        "---\n",
        encoding="utf-8",
    )

    primary = tmp_path / "primary"
    primary.mkdir()
    _git(primary, "init", "-b", "master")
    _git(primary, "config", "user.email", "t@t.t")
    _git(primary, "config", "user.name", "t")
    (primary / "test-app.mjs").write_text(
        "page.waitForSelector('text=Total Media Budget (EUR)')\n", encoding="utf-8"
    )
    (primary / "f.txt").write_text("x", encoding="utf-8")
    _git(primary, "add", "-A")
    _git(primary, "commit", "-m", "init")
    wt = tmp_path / "wt"
    _git(primary, "worktree", "add", str(wt), "-b", "feature/x")

    # Escapes the worktree (blocks) AND removes a locator warn-smoke-test-drift.py
    # cares about (would otherwise only warn). Built with forward slashes
    # explicitly: warn-smoke-test-drift.py's scope check hardcodes
    # 'src/components/' (forward slashes), so a Windows-native backslash path
    # from Path/str() would never match its scope regardless of this fix.
    escape_target = (primary / "src" / "components" / "Thing.tsx").as_posix()
    payload = {
        "tool_input": {
            "file_path": escape_target,
            "old_string": "Total Media Budget (EUR)",
            "new_string": "Budget",
        },
    }
    r = subprocess.run(
        [sys.executable, str(hooks_dir / "dispatch-edit-write-pretooluse.py")],
        input=json.dumps(payload),
        capture_output=True, text=True, cwd=str(wt),
        env={**os.environ, "ALLOW_WORKTREE_PATH_ESCAPE": "", "CLAUDE_PROJECT_DIR": str(primary)},
    )
    assert r.returncode == 2
    assert "block-worktree-path-escape.py" in r.stderr
    assert "Total Media Budget (EUR)" in r.stderr  # the earlier warning survived


def test_edit_write_dispatch_isolates_a_broken_sibling_hook(tmp_path):
    hooks_dir = _hooks_copy(tmp_path)
    (hooks_dir / "warn-comment-dates.py").write_text("this is ) not ( valid python !!!", encoding="utf-8")

    target = tmp_path / "script.py"
    r = subprocess.run(
        [sys.executable, str(hooks_dir / "dispatch-edit-write-pretooluse.py")],
        input=json.dumps({"tool_input": {"file_path": str(target), "content": "x = 1\n"}}),
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    # Nothing else blocks this edit, but the load failure must still be visible —
    # as additionalContext, the only non-blocking channel Claude reads.
    assert r.returncode == 0
    context = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "warn-comment-dates.py" in context
    assert "failed to load" in context


# --------------------------------------------------------------------------- #
# Handler budget -- what a spent budget is allowed to drop, and what it is not
#
# Claude Code kills a handler at the hooks.json `timeout`, and a killed handler
# is enforcement that did not run. The dispatchers pre-empt that by skipping
# ADVISORY hooks once the budget is gone. These tests pin both halves: the
# warnings do get dropped (loudly), and the blocking guards never do.
# --------------------------------------------------------------------------- #


class _ExpiredDeadline:
    """Stands in for a budget already spent by earlier hooks in the same run."""

    def remaining(self) -> float:
        return -1.0

    def expired(self) -> bool:
        return True

    def has_room(self, cost_seconds: float) -> bool:
        # Nothing fits in a spent budget — not even a zero-cost hook, which the
        # real Deadline would admit. Overstating the pressure is right for a
        # stand-in whose job is to prove enforcement survives the worst case.
        return False


def _load_dispatcher(filename: str):
    """Import a dispatcher in-process so its `Deadline` can be monkeypatched.

    The subprocess helper used elsewhere in this file runs a fresh interpreter,
    which gives a test no way to reach that symbol.
    """
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    spec = importlib.util.spec_from_file_location(
        filename.replace("-", "_")[: -len(".py")], _HOOKS_DIR / filename
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_in_process(mod, payload: dict, monkeypatch) -> int:
    monkeypatch.setattr(mod, "Deadline", lambda *a, **k: _ExpiredDeadline())
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    return mod.main()


def test_bash_dispatch_skips_advisory_hooks_when_the_budget_is_spent(monkeypatch, capsys, tmp_path):
    mod = _load_dispatcher("dispatch-bash-pretooluse.py")
    rc = _run_in_process(mod, {"tool_input": {"command": "ls"}, "cwd": str(tmp_path)}, monkeypatch)
    captured = capsys.readouterr()

    assert rc == 0
    # Reported to the DEBUG LOG, naming every hook dropped — but deliberately
    # not to Claude's context. An advisory hook stepping aside under load is
    # this mechanism working, not a defect, and putting it in context on every
    # busy call is noise on the hottest path in the session.
    assert "skipped" in captured.err
    for advisory in mod._ADVISORY_HOOKS:
        assert advisory in captured.err, f"{advisory} was skipped without being named"
    assert captured.out.strip() == "", (
        "a routine advisory skip must not inject context into an ordinary call"
    )


def test_bash_dispatch_still_blocks_after_the_budget_is_spent(monkeypatch, capsys, tmp_path):
    mod = _load_dispatcher("dispatch-bash-pretooluse.py")
    rc = _run_in_process(
        mod, {"tool_input": {"command": "cd /tmp && ls"}, "cwd": str(tmp_path)}, monkeypatch
    )
    assert rc == 2, "an expired budget must never downgrade a block to an allow"
    assert "block-cd-in-bash.py" in capsys.readouterr().err


def test_edit_write_dispatch_still_blocks_after_the_budget_is_spent(monkeypatch, capsys, tmp_path):
    # Worth its own case: in this dispatcher a BLOCKING hook sits last in
    # _HOOK_FILES, so list order gives it none of the protection the Bash
    # dispatcher happens to get. Only its absence from _ADVISORY_HOOKS saves it.
    mod = _load_dispatcher("dispatch-edit-write-pretooluse.py")
    target = tmp_path / ".claude" / "notes.md"
    target.parent.mkdir(parents=True)
    rc = _run_in_process(
        mod,
        {"tool_input": {"file_path": str(target), "content": "(added 2026-01-01)"},
         "cwd": str(tmp_path)},
        monkeypatch,
    )
    assert rc == 2
    assert "block-dated-stamps-in-prose.py" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# `ask` escalation -- the middle tier between allow and block
#
# Only one process's stdout is read per PreToolUse call, so a child hook's
# permissionDecision has to be re-emitted by the dispatcher or it is silently
# downgraded to an allow. These pin that it survives, and that a real block
# still outranks it.
# --------------------------------------------------------------------------- #


def test_bash_dispatch_reemits_an_ask_escalation(tmp_path):
    r = _run(
        _BASH_DISPATCH,
        {"tool_input": {"command": "git push --force origin feature/x"}, "cwd": str(tmp_path)},
    )
    assert r.returncode == 0, "an ask must not block the call"
    payload = json.loads(r.stdout)
    nested = payload["hookSpecificOutput"]
    assert nested["permissionDecision"] == "ask"
    assert "force-push" in nested["permissionDecisionReason"]


def test_bash_dispatch_lets_a_block_outrank_an_ask(tmp_path):
    # `git push --force origin main` is BOTH a force-push (ask) and a push to
    # main (block). Deny > ask, so the call is refused outright and no
    # permission prompt is offered as an alternative.
    r = _run(
        _BASH_DISPATCH,
        {"tool_input": {"command": "git push --force origin main"}, "cwd": str(tmp_path)},
    )
    assert r.returncode == 2
    assert "block-direct-push-to-main.py" in r.stderr
    assert r.stdout.strip() == "", "a blocked call must not also emit an ask"


def test_bash_dispatch_stays_silent_on_a_guarded_force_push(tmp_path):
    # --force-with-lease is deliberately not escalated; see the hook's docstring.
    r = _run(
        _BASH_DISPATCH,
        {"tool_input": {"command": "git push --force-with-lease origin feature/x"},
         "cwd": str(tmp_path)},
    )
    assert r.returncode == 0
    assert r.stdout.strip() == ""


def test_an_ask_survives_an_unrelated_hook_crashing(tmp_path):
    """A permission decision is only honoured on exit 0.

    Reporting an unrelated hook's failure through the exit code discarded the
    escalation entirely: one sibling with a typo, and every force-push in the
    session ran unprompted. The failure notice rides in the prompt text instead.
    """
    hooks = _hooks_copy(tmp_path)
    (hooks / "warn-stacked-pr-merge.py").write_text(
        "this is not valid python(\n", encoding="utf-8"
    )
    r = _run(
        hooks / "dispatch-bash-pretooluse.py",
        {"tool_input": {"command": "git push --force origin feature/x"},
         "cwd": str(tmp_path)},
    )
    assert r.returncode == 0, "a crashed sibling must not discard the ask"
    nested = json.loads(r.stdout)["hookSpecificOutput"]
    assert nested["permissionDecision"] == "ask"
    assert "force-push" in nested["permissionDecisionReason"]
    # The failure travels alongside it as context, not in place of it: an ask
    # and advisory text coexist in one hookSpecificOutput object.
    assert "crashed" in nested["additionalContext"]


def test_an_ask_survives_a_spent_budget(monkeypatch, capsys, tmp_path):
    # The block case is covered above; an ask leaves no trace in the exit code,
    # so losing it to budget pressure would be invisible.
    mod = _load_dispatcher("dispatch-bash-pretooluse.py")
    monkeypatch.setenv("ALLOW_DESTRUCTIVE_GIT", "")
    rc = _run_in_process(
        mod,
        {"tool_input": {"command": "git push --force origin feature/x"},
         "cwd": str(tmp_path)},
        monkeypatch,
    )
    out = capsys.readouterr().out
    assert rc == 0
    nested = json.loads(out)["hookSpecificOutput"]
    assert nested["permissionDecision"] == "ask"


def test_advisory_warnings_travel_on_the_channel_claude_actually_reads(tmp_path):
    """The defect this closes: the whole Bash warn tier reached nobody.

    Per the hook contract, stderr from a hook exiting 0 goes to the debug log
    and Claude never sees it. Every warn-* hook on this matcher wrote there and
    exited 0, so they spawned subprocesses on every call and delivered nothing.
    Asserted end-to-end rather than in-process, because the bug was entirely
    about which stream the real process writes to.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    r = _run(_BASH_DISPATCH, {"tool_input": {"command": "git commit -m x"}, "cwd": str(repo)}, cwd=repo)

    assert r.returncode == 0
    assert r.stdout.strip(), (
        "a warning that exists only on stderr at exit 0 is delivered to nobody"
    )
    nested = json.loads(r.stdout)["hookSpecificOutput"]
    assert nested["additionalContext"].strip()


def test_edit_write_dispatch_also_keeps_skips_out_of_context(monkeypatch, capsys, tmp_path):
    """The twin of the Bash case, which had no coverage.

    This is the hotter of the two dispatchers, and reverting its
    `print(notice, file=sys.stderr)` back to `warnings.append(notice)` left the
    entire suite green — so the policy was pinned on one dispatcher only.
    """
    mod = _load_dispatcher("dispatch-edit-write-pretooluse.py")
    target = tmp_path / "notes.md"
    rc = _run_in_process(
        mod,
        {"tool_input": {"file_path": str(target), "content": "hello\n"},
         "cwd": str(tmp_path)},
        monkeypatch,
    )
    captured = capsys.readouterr()
    assert rc == 0
    assert "skipped" in captured.err, "the skip must still be diagnosable"
    for advisory in mod._ADVISORY_HOOKS:
        assert advisory in captured.err
    if captured.out.strip():
        assert "skipped" not in json.loads(captured.out)["hookSpecificOutput"].get(
            "additionalContext", ""
        ), "a routine advisory skip must not inject context on every Edit"
