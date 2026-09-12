"""Tests for the two PreToolUse dispatcher scripts (dispatch-bash-pretooluse.py,
dispatch-edit-write-pretooluse.py), which each replace 5 separate hook-process
spawns with 1 in-process run via `_dispatch_lib`. These exercise a representative
block / warn / allow case per dispatcher, end-to-end via subprocess, to confirm
the consolidation preserves each sibling hook's original semantics.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).resolve().parents[3] / ".claude" / "plugins" / "cla" / "hooks"
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
        input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(cwd) if cwd else None,
        env=env,
    )


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")


def _unsafe_delete_target(tmp_path: Path) -> Path:
    """A path whose `rm -rf` `block-unsafe-recursive-delete` refuses.

    That is a LINK to a directory. These dispatcher tests used a path under
    `.claude/worktrees/` while the hook carried a worktree-path trigger; that
    trigger was removed, and the tests went red because they assert on the
    dispatcher's routing, not on which shape the leaf hook happens to block.

    The alias is a real symlink where permitted and an NTFS junction otherwise,
    matching `test_block_unsafe_recursive_delete.make_dir_alias`. It is
    duplicated rather than imported because that module executes the hook at
    import time, which these tests must not depend on.
    """
    real = tmp_path / "far-side"
    real.mkdir()
    (real / "canary.txt").write_text("x", encoding="utf-8")
    link = tmp_path / "the-link"
    try:
        link.symlink_to(real, target_is_directory=True)
        return link
    except (OSError, NotImplementedError, AttributeError):
        pass
    if os.name != "nt":
        pytest.skip("symlink creation not permitted, and junctions are Windows-only")
    r = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(real)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if r.returncode != 0 or not link.exists():
        pytest.skip(f"neither symlink nor junction creation permitted here: {r.stderr}")
    return link


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


def test_bash_dispatch_blocks_an_unsafe_recursive_delete(tmp_path):
    target = _unsafe_delete_target(tmp_path)
    r = _run(_BASH_DISPATCH, {"tool_input": {"command": f"rm -rf {target}"}, "cwd": str(tmp_path)})
    assert r.returncode == 2
    assert "block-unsafe-recursive-delete.py" in r.stderr


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

    target = _unsafe_delete_target(tmp_path)
    r = subprocess.run(
        [sys.executable, str(hooks_dir / "dispatch-bash-pretooluse.py")],
        input=json.dumps({"tool_input": {"command": f"rm -rf {target}"}, "cwd": str(tmp_path)}),
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(tmp_path),
    )
    assert r.returncode == 2
    assert "block-unsafe-recursive-delete.py" in r.stderr  # the later hook still fired and blocked
    assert "block-cd-in-bash.py" in r.stderr               # the load failure is surfaced, not silent
    assert "failed to load" in r.stderr


def test_bash_dispatch_reports_a_crashed_hook_as_context(tmp_path):
    """A crashed hook must reach Claude — and exit 1 is the wrong way to do it.

    A non-zero exit discards stdout entirely and surfaces only the FIRST LINE of
    stderr, so it reports strictly less than additionalContext does. The failure
    therefore travels as context at exit 0, whole.
    """
    hooks_dir = _hooks_copy(tmp_path)
    (hooks_dir / "warn-stacked-pr-merge.py").write_text(
        "def main():\n    raise RuntimeError('boom')\n", encoding="utf-8"
    )

    r = subprocess.run(
        [sys.executable, str(hooks_dir / "dispatch-bash-pretooluse.py")],
        input=json.dumps({"tool_input": {"command": "ls -la"}, "cwd": str(tmp_path)}),
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(tmp_path),
    )
    assert r.returncode == 0
    context = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "warn-stacked-pr-merge" in context
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
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(wt),
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


def _primary_and_worktree(tmp_path):
    """A committed primary clone plus a linked worktree, for the escape guard."""
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
    return primary, wt


def test_edit_write_dispatch_does_not_drop_earlier_warning_when_later_hook_blocks(tmp_path):
    # Regression: warn-comment-dates.py (position 1) fires a non-blocking
    # stdout-JSON warning, then block-worktree-path-escape.py (position 2)
    # blocks on the same edit. The earlier warning must still reach the user
    # via stderr (the only channel fed back on a block) instead of vanishing.
    primary, wt = _primary_and_worktree(tmp_path)

    # Escapes the worktree (blocks) AND adds a dated code comment (would
    # otherwise only warn), so both hooks have something to say on one call.
    # `.py` with a `#` comment: warn-comment-dates is deliberately scoped to
    # .py/.sh so Markdown headings never trigger it.
    payload = {
        "tool_input": {
            "file_path": (primary / "src" / "thing.py").as_posix(),
            "old_string": "x = 1",
            "new_string": "# fixed on 2026-01-01\nx = 2",
        },
    }
    r = subprocess.run(
        [sys.executable, str(_EDIT_WRITE_DISPATCH)],
        input=json.dumps(payload),
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(wt),
        env={**os.environ, "ALLOW_WORKTREE_PATH_ESCAPE": "", "CLAUDE_PROJECT_DIR": str(primary)},
    )
    assert r.returncode == 2
    assert "block-worktree-path-escape.py" in r.stderr
    assert "2026-01-01" in r.stderr  # the earlier warning survived


def test_edit_write_dispatch_isolates_a_broken_sibling_hook(tmp_path):
    hooks_dir = _hooks_copy(tmp_path)
    (hooks_dir / "warn-comment-dates.py").write_text("this is ) not ( valid python !!!", encoding="utf-8")

    target = tmp_path / "script.py"
    r = subprocess.run(
        [sys.executable, str(hooks_dir / "dispatch-edit-write-pretooluse.py")],
        input=json.dumps({"tool_input": {"file_path": str(target), "content": "x = 1\n"}}),
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(tmp_path),
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
        # Nothing fits in a spent budget, which is what the real Deadline also
        # answers here: `remaining() >= cost_seconds` is False for every cost
        # once `remaining()` is negative, zero-cost included. An earlier version
        # of this comment claimed the real Deadline would ADMIT a zero-cost hook
        # — the misreading that `_dispatch_lib.Deadline.has_room`'s docstring
        # and `test_dispatch_lib.test_deadline_has_room_refuses_even_a_zero_cost_hook_once_overspent`
        # both exist to settle. The stub is a faithful stand-in, not an
        # exaggerated one.
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
    # Worth its own case: in this dispatcher the BLOCKING hook sits last in
    # _HOOK_FILES, so list order gives it none of the protection the Bash
    # dispatcher happens to get. Only its absence from _ADVISORY_HOOKS saves it.
    mod = _load_dispatcher("dispatch-edit-write-pretooluse.py")
    primary, wt = _primary_and_worktree(tmp_path)
    monkeypatch.chdir(wt)
    monkeypatch.setenv("ALLOW_WORKTREE_PATH_ESCAPE", "")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(primary))
    rc = _run_in_process(
        mod,
        {"tool_input": {"file_path": (primary / "src" / "thing.ts").as_posix(),
                        "content": "export const x = 1;\n"}},
        monkeypatch,
    )
    assert rc == 2
    assert "block-worktree-path-escape.py" in capsys.readouterr().err


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
    # A force-push (ask, position 2) chained with an unsafe recursive delete
    # (block, position 3): the ask is raised FIRST and must still lose. Deny >
    # ask, so the call is refused outright and no permission prompt is offered
    # as an alternative. Ordering matters here — a block that merely
    # short-circuits before the ask would pass this vacuously.
    target = _unsafe_delete_target(tmp_path)
    r = _run(
        _BASH_DISPATCH,
        {"tool_input": {"command": f"git push --force origin main && rm -rf {target}"},
         "cwd": str(tmp_path)},
    )
    assert r.returncode == 2
    assert "block-unsafe-recursive-delete.py" in r.stderr
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
    # An untracked, separator-free, scratch-named file at the repo root is what
    # warn-stray-scratch-artifact fires on before a `git commit`.
    (repo / "scratchpad-dump.txt").write_text("x", encoding="utf-8")
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


# --------------------------------------------------------------------------- #
# MD-10 — an errored ENFORCING hook read as `allow`
#
# `_dispatch_lib`'s docstring told callers to exit non-zero-non-2 when any hook
# errored. Neither dispatcher did, and neither should: a non-zero exit makes
# Claude Code discard stdout, DOWNGRADING a pending `ask` to an allow and
# surfacing only the first line of merged stderr. The contract was stated one
# way and implemented another, and the implementation was right.
#
# But the consequence it warned about was real. An enforcing guard that failed
# to load did not run its check, and from the outside that is indistinguishable
# from one that ran and allowed -- reported only through stderr, which for an
# exit-0 hook reaches the debug log alone.
# --------------------------------------------------------------------------- #


def _dispatch_with_errored(monkeypatch, dispatcher, target, payload):
    """Run `dispatcher.main()` with exactly one hook reporting errored=True."""
    import _dispatch_lib as lib

    def one(filename, stdin_text, argv=None):
        return lib.HookResult(0, "", "", filename == target)

    monkeypatch.setattr(dispatcher, "run_hook_file", one)
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = dispatcher.main()
    out = buf.getvalue().strip()
    return rc, (json.loads(out)["hookSpecificOutput"] if out else {})


def test_an_errored_enforcing_hook_escalates_to_ask(monkeypatch):
    """`ask` is the one channel that reaches the user and cannot be ignored,
    and it costs nothing when the call was legitimate."""
    mod = _load_dispatcher("dispatch-bash-pretooluse.py")
    rc, nested = _dispatch_with_errored(
        monkeypatch, mod, "block-unsafe-recursive-delete.py",
        {"tool_name": "Bash", "tool_input": {"command": "echo hi"}},
    )
    assert rc == 0, "must stay fail-open — a non-zero exit discards this payload"
    assert nested.get("permissionDecision") == "ask"
    assert "ENFORCING" in nested.get("permissionDecisionReason", "")
    assert "block-unsafe-recursive-delete.py" in nested.get("permissionDecisionReason", "")


def test_an_errored_advisory_hook_stays_a_warning(monkeypatch):
    """Losing a warning is the acceptable half of the trade this dispatcher
    already makes for budget. Escalating those too would train the user to
    dismiss the prompt, which costs the enforcing case its only channel."""
    mod = _load_dispatcher("dispatch-bash-pretooluse.py")
    rc, nested = _dispatch_with_errored(
        monkeypatch, mod, "warn-stacked-pr-merge.py",
        {"tool_name": "Bash", "tool_input": {"command": "echo hi"}},
    )
    assert rc == 0
    assert "permissionDecision" not in nested
    assert "additionalContext" in nested


def test_no_errored_hook_produces_no_prompt(monkeypatch):
    """Non-vacuity partner: the escalation must not fire on a healthy run."""
    mod = _load_dispatcher("dispatch-bash-pretooluse.py")
    rc, nested = _dispatch_with_errored(
        monkeypatch, mod, None,
        {"tool_name": "Bash", "tool_input": {"command": "echo hi"}},
    )
    assert rc == 0
    assert nested.get("permissionDecision") is None


def test_the_edit_write_dispatcher_also_escalates_without_crashing(monkeypatch):
    """CRITICAL regression. The escalation was applied to BOTH dispatchers, but
    the edit/write one has no `asks` variable — it died with
    `NameError: name 'asks' is not defined` on EVERY Edit/Write whenever an
    enforcing hook errored, discarding every other hook's output on that call.
    Strictly worse than the silent-allow it replaced.

    It also had no ask CHANNEL at all (`_context_json` emits only
    `additionalContext`), so even a defined variable would have been dropped.
    Both new escalation tests loaded only the Bash dispatcher, so nothing saw it."""
    mod = _load_dispatcher("dispatch-edit-write-pretooluse.py")
    rc, nested = _dispatch_with_errored(
        monkeypatch, mod, "block-worktree-path-escape.py",
        {"tool_name": "Write", "tool_input": {"file_path": "x.md", "content": "y"}},
    )
    assert rc == 0
    assert nested.get("permissionDecision") == "ask"
    assert "ENFORCING" in nested.get("permissionDecisionReason", "")


def test_the_edit_write_dispatcher_leaves_advisory_errors_as_context(monkeypatch):
    """Non-vacuity partner for the dispatcher that had no coverage at all."""
    mod = _load_dispatcher("dispatch-edit-write-pretooluse.py")
    rc, nested = _dispatch_with_errored(
        monkeypatch, mod, "warn-comment-dates.py",
        {"tool_name": "Write", "tool_input": {"file_path": "x.md", "content": "y"}},
    )
    assert rc == 0
    assert "permissionDecision" not in nested
