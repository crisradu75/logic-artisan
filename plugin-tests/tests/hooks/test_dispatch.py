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


def _unsafe_delete_target(tmp_path: Path, make_dir_alias) -> Path:
    """A path whose `rm -rf` `block-unsafe-recursive-delete` refuses.

    That is a LINK to a directory. These dispatcher tests used a path under
    `.claude/worktrees/` while the hook carried a worktree-path trigger; that
    trigger was removed, and the tests went red because they assert on the
    dispatcher's routing, not on which shape the leaf hook happens to block.

    The alias comes from the shared `make_dir_alias` fixture in
    `tests/conftest.py`: a real symlink where permitted, an NTFS junction
    otherwise.
    """
    real = tmp_path / "far-side"
    real.mkdir()
    (real / "canary.txt").write_text("x", encoding="utf-8")
    link = tmp_path / "the-link"
    make_dir_alias(link, real)
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


def test_bash_dispatch_blocks_an_unsafe_recursive_delete(tmp_path, make_dir_alias):
    target = _unsafe_delete_target(tmp_path, make_dir_alias)
    r = _run(_BASH_DISPATCH, {"tool_input": {"command": f"rm -rf {target}"}, "cwd": str(tmp_path)})
    assert r.returncode == 2
    assert "block-unsafe-recursive-delete.py" in r.stderr


def test_bash_dispatch_allows_clean_command(tmp_path):
    r = _run(_BASH_DISPATCH, {"tool_input": {"command": "git status"}, "cwd": str(tmp_path)}, cwd=tmp_path)
    assert r.returncode == 0
    assert r.stderr.strip() == ""


def test_bash_dispatch_isolates_a_broken_sibling_hook(tmp_path, make_dir_alias):
    # A hook that fails to LOAD (position 1) must not prevent a LATER hook
    # (position 2) from still evaluating and blocking — the whole point of
    # run_hook_file's load-failure isolation.
    hooks_dir = _hooks_copy(tmp_path)
    (hooks_dir / "block-cd-in-bash.py").write_text("this is ) not ( valid python !!!", encoding="utf-8")

    target = _unsafe_delete_target(tmp_path, make_dir_alias)
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


def _run_copy(hooks_dir: Path, name: str, payload: dict, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(hooks_dir / name)], input=json.dumps(payload),
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(cwd),
    )


@pytest.mark.parametrize("name", ["dispatch-bash-pretooluse.py", "dispatch-edit-write-pretooluse.py"])
def test_a_dispatcher_whose_library_fails_to_load_asks_instead_of_allowing(tmp_path, name):
    """Every guard runs through `_dispatch_lib`. Left uncaught, its import failure exits 1, a
    non-blocking error, so every block and ask would silently become an allow."""
    hooks_dir = _hooks_copy(tmp_path)
    (hooks_dir / "_dispatch_lib.py").write_text("raise ImportError('planted')\n", encoding="utf-8")
    payload = {"tool_input": {"command": "ls", "file_path": str(tmp_path / "x.py"), "content": "x"},
               "cwd": str(tmp_path)}
    r = _run_copy(hooks_dir, name, payload, tmp_path)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "ask"
    assert "_dispatch_lib failed to load" in out["permissionDecisionReason"]
    assert "Traceback (most recent call last)" in r.stderr and "planted" in r.stderr


def test_a_block_survives_a_failure_to_format_its_message(tmp_path):
    """A guard that already blocked stays a block: the crash path's ask must not replace it."""
    hooks_dir = _hooks_copy(tmp_path)
    with (hooks_dir / "_dispatch_lib.py").open("a", encoding="utf-8") as lib:
        lib.write("\n\ndef compose_output(*args, **kwargs):  # planted\n    raise RuntimeError('planted')\n")
    r = _run_copy(hooks_dir, "dispatch-bash-pretooluse.py",
                  {"tool_input": {"command": "cd /tmp && ls"}, "cwd": str(tmp_path)}, tmp_path)
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert "block-cd-in-bash" in r.stderr


def test_a_dispatcher_that_crashes_in_main_asks_instead_of_allowing(tmp_path):
    hooks_dir = _hooks_copy(tmp_path)
    with (hooks_dir / "_dispatch_lib.py").open("a", encoding="utf-8") as lib:
        lib.write("\n\nclass Deadline:  # planted: main() crashes on its first use\n"
                  "    def __init__(self):\n        raise RuntimeError('planted crash')\n")
    r = _run_copy(hooks_dir, "dispatch-bash-pretooluse.py",
                  {"tool_input": {"command": "ls"}, "cwd": str(tmp_path)}, tmp_path)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)["hookSpecificOutput"]
    assert out["permissionDecision"] == "ask"
    assert "the dispatcher crashed: RuntimeError: planted crash" in out["permissionDecisionReason"]


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


def test_override_notice_reaches_claude_through_the_edit_write_dispatcher(tmp_path):
    primary, wt = _primary_and_worktree(tmp_path)
    payload = {"tool_input": {"file_path": (primary / "src" / "thing.py").as_posix(),
                              "content": "x = 1\n"}}
    r = subprocess.run(
        [sys.executable, str(_EDIT_WRITE_DISPATCH)],
        input=json.dumps(payload),
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(wt),
        env={**os.environ, "ALLOW_WORKTREE_PATH_ESCAPE": "1", "CLAUDE_PROJECT_DIR": str(primary)},
    )
    assert r.returncode == 0
    context = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "DISABLED by ALLOW_WORKTREE_PATH_ESCAPE=1" in context


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


def test_bash_dispatch_lets_a_block_outrank_an_ask(tmp_path, make_dir_alias):
    # A force-push (ask, position 2) chained with an unsafe recursive delete
    # (block, position 3): the ask is raised FIRST and must still lose. Deny >
    # ask, so the call is refused outright and no permission prompt is offered
    # as an alternative. Ordering matters here — a block that merely
    # short-circuits before the ask would pass this vacuously.
    target = _unsafe_delete_target(tmp_path, make_dir_alias)
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


def test_bash_dispatch_stays_well_inside_the_hook_timeout_on_a_hostile_command(tmp_path):
    """Per-operator work once made 199 message heredocs plus 36000 plain lines take
    23 s against a 15 s hook timeout, and a killed hook lets the command through."""
    import time

    message = "git commit -m \"$(cat <<'EOF'\nfix: x\nEOF\n)\"\n"
    command = message * 199 + "git status\n" * 36000 + "git reset --hard HEAD~1"
    started = time.perf_counter()
    r = _run(_BASH_DISPATCH, {"tool_input": {"command": command}, "cwd": str(tmp_path)})
    assert time.perf_counter() - started < 8.0
    assert json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_the_edit_write_dispatcher_leaves_advisory_errors_as_context(monkeypatch):
    """Non-vacuity partner for the dispatcher that had no coverage at all."""
    mod = _load_dispatcher("dispatch-edit-write-pretooluse.py")
    rc, nested = _dispatch_with_errored(
        monkeypatch, mod, "warn-comment-dates.py",
        {"tool_name": "Write", "tool_input": {"file_path": "x.md", "content": "y"}},
    )
    assert rc == 0
    assert "permissionDecision" not in nested


# --------------------------------------------------------------------------- #
# Command substitution inside double quotes / backticks EXECUTES, so the guards
# must see its body; single-quoted text and plain prose must stay hidden.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "command, reason_word",
    [
        ('echo "$(git reset --hard HEAD~1)"', "reset --hard"),
        ("echo `git push --force origin feat`", "force-push"),
        ('echo "`git push --force origin feat`"', "force-push"),
        ('echo "x $(echo y; git push --force origin feat) z"', "force-push"),
        ('git commit -m "$(git reset --hard HEAD~1)"', "reset --hard"),
        # the flag is the LAST thing before the substitution closes
        ('echo "$(git reset --hard)"', "reset --hard"),
        ('echo "$(git push -f)"', "force-push"),
        ('echo "$(git push --force)"', "force-push"),
        ("x=`git reset --hard`", "reset --hard"),
        # an UNQUOTED heredoc is expanded, so its substitutions run
        ("cat <<EOF\nnow $(git reset --hard HEAD)\nEOF", "reset --hard"),
        # a heredoc fed to a shell executes its body, however the shell is spelled
        ("bash <<'EOF'\ngit reset --hard HEAD\nEOF", "reset --hard"),
        ("/bin/bash <<'EOF'\ngit reset --hard HEAD\nEOF", "reset --hard"),
        ("bash.exe <<'EOF'\ngit reset --hard HEAD\nEOF", "reset --hard"),
        ("cat <<'EOF' | bash\ngit reset --hard HEAD~1\nEOF", "reset --hard"),
        ("cat <<'EOF' | sh -s\ngit reset --hard HEAD~1\nEOF", "reset --hard"),
        ("cat <<EOF | bash\ngit reset --hard HEAD~1\nEOF", "reset --hard"),
        ("tee x.sh <<'EOF' | bash\ngit reset --hard HEAD~1\nEOF", "reset --hard"),
        ("ssh host <<'EOF'\ngit reset --hard HEAD\nEOF", "reset --hard"),
        # the interpreter is the only thing on an otherwise data-looking line
        ("/bin/bash -c \"$(cat <<'EOF'\ngit reset --hard HEAD\nEOF\n)\"", "reset --hard"),
        ("bash.exe -c \"$(cat <<'EOF'\ngit reset --hard HEAD\nEOF\n)\"", "reset --hard"),
        ("C:\\\\Git\\\\bin\\\\bash.exe -c \"$(cat <<'EOF'\ngit reset --hard HEAD\nEOF\n)\"", "reset --hard"),
        ("source /dev/stdin <<'EOF'\ngit reset --hard HEAD\nEOF", "reset --hard"),
        (". /dev/stdin <<'EOF'\ngit reset --hard HEAD\nEOF", "reset --hard"),
        ("fish <<'EOF'\ngit reset --hard HEAD\nEOF", "reset --hard"),
        ("pwsh -Command - <<'EOF'\ngit reset --hard HEAD\nEOF", "reset --hard"),
        ("source <(cat <<'EOF'\ngit reset --hard HEAD\nEOF\n)", "reset --hard"),
        ("eval \"$(cat <<'EOF'\ngit reset --hard HEAD\nEOF\n)\"", "reset --hard"),
        # a script written and then run, or written to a name that may be run
        ("cat > x.sh <<'EOF'\ngit reset --hard HEAD\nEOF\nbash x.sh", "reset --hard"),
        ("cat > x.sh <<'EOF'\ngit reset --hard HEAD\nEOF", "reset --hard"),
        ("cat > runme <<'EOF'\ngit reset --hard HEAD\nEOF", "reset --hard"),
        # only a plain quoted word is a delimiter we trust
        ("cat <<-'EOF' > n.md\n\tgit reset --hard HEAD\n\tEOF", "reset --hard"),
        ("cat > n.md <<EOF\nplain git reset --hard prose\nEOF", "reset --hard"),
        ('cat <<E"O"F\nhello\nEOF\ngit reset --hard\nE', "reset --hard"),
        ("cat <<'END-OF-FILE'\nx\nEND-OF-FILE\ngit reset --hard HEAD\nEND", "reset --hard"),
        # an operator that is not a real heredoc must not hide the lines after it
        ('echo "<<EOF"\ngit reset --hard HEAD\nEOF', "reset --hard"),
        ("# cat <<'EOF'\ngit reset --hard HEAD\nEOF", "reset --hard"),
        # a heredoc body written inside another heredoc body is data; what follows is not
        ("cat <<'A'\ncat <<'B'\nA\ngit reset --hard\nB", "reset --hard"),
        # an unquoted body is expanded, so quotes and case do not hide the command
        ('cat <<EOF\n$(echo ")"; git reset --hard)\nEOF', "reset --hard"),
        ("cat <<EOF\n$(case x in x) git reset --hard;; esac)\nEOF", "reset --hard"),
        # CRLF line endings: the body is data but what follows is not
        ("cat <<'EOF'\r\nx\r\nEOF\r\ngit reset --hard HEAD\r\n", "reset --hard"),
        # the "operator" is not one the shell sees: comment, single quotes, another body
        ("git commit -m x # \"x \"$(cat <<'EOF'\ngit reset --hard HEAD~1\nEOF\n)\"", "reset --hard"),
        ("git status; # \"x \"$(cat <<'EOF'\ngit reset --hard HEAD~1\nEOF\n)\"", "reset --hard"),
        ("git commit -m 'a \"$(cat <<'EOF'\n'; git reset --hard HEAD~1\nEOF\n)\"", "reset --hard"),
        ("git commit -F - <<X\ngit commit -m \"$(cat <<'EOF'\nX\n: \\\"\ngit reset --hard HEAD~1\nEOF\n)\"", "reset --hard"),
        ("git commit -F - <<<'EOF'\ngit reset --hard HEAD~1\nEOF\n)\"", "reset --hard"),
        ("git commit -m \"$(cat <<'EOF'\nmsg\nEOF\n)\" ; git reset --hard HEAD~1", "reset --hard"),
        # inside $( ), bash also ends a heredoc at a line that only STARTS with the word
        ("git commit --allow-empty -m \"$(cat <<'EOF'\nEOF)\"; git reset --hard HEAD~1; : \"\nEOF\n)\"", "reset --hard"),
        ("git commit --allow-empty -m \"$(cat <<'EOF'\nEOF )\"; git reset --hard HEAD~1; : \"\nEOF\n)\"", "reset --hard"),
        ("git commit --allow-empty -m \"$(cat <<'EOF'\nEOF\t)\"; git reset --hard HEAD~1; : \"\nEOF\n)\"", "reset --hard"),
        ("git commit --allow-empty -m \"$(cat <<'EOF'\nEOFx)\"; git reset --hard HEAD~1; : \"\nEOF\n)\"", "reset --hard"),
        # a backtick inside a quote must not pair across real commands
        ("cat > x.sh <<'EOF'\n echo ' ` '; git reset --hard HEAD~1; echo ' ` '\nEOF\nchmod +x x.sh && ./x.sh", "reset --hard"),
        ("cat > Makefile <<'EOF'\nall:\n\t@echo ' ` '; git reset --hard HEAD~1; echo ' ` '\nEOF\nmake", "reset --hard"),
        # backtick spans are not blanked when the heredoc is not plainly data
        ("# `cat <<'EOF'\n`git reset --hard HEAD~1`\nEOF", "reset --hard"),
        ("bash <<'EOF' # `\n`git reset --hard HEAD~1`\nEOF", "reset --hard"),
        ("sh <<'EOF'\n`git reset --hard HEAD~1`\nEOF", "reset --hard"),
        ("$SHELL <<'EOF'\n`git reset --hard HEAD~1`\nEOF", "reset --hard"),
        ("$0 <<'EOF'\n`git reset --hard HEAD~1`\nEOF", "reset --hard"),
        ("/bin/bash <<'EOF'\n`git reset --hard HEAD~1`\nEOF", "reset --hard"),
        ("bash.exe <<'EOF'\n`git reset --hard HEAD~1`\nEOF", "reset --hard"),
        ("ls # cat <<'EOF'\n`git reset --hard HEAD~1`\nEOF", "reset --hard"),
        # an earlier unquoted heredoc may make the quoted "operator" a body line
        ("cat <<X\ncat > f <<'EOF'\nX\n`git reset --hard HEAD~1`\nEOF", "reset --hard"),
        # `.` runs a script: an alias or a sourced stdin reads the message back
        ("git commit --allow-empty -m \"$(cat <<'EOF'\n: \\\"\ngit reset --hard HEAD~1\nEOF\n)\" && git -c alias.r='!. /dev/stdin <<< \"$(git log -1 --format=%B)\"' r", "reset --hard"),
        # a `<<<` here-string is never a heredoc operator
        ("bash <<<'EOF'\n`git reset --hard HEAD`\nEOF", "reset --hard"),
        # the substitution's OUTPUT is run: the command that runs it may sit elsewhere
        ("$(cat <<'EOF'\ngit reset --hard HEAD~1\nEOF\n)", "reset --hard"),
        ("x=$(cat <<'EOF'\ngit reset --hard HEAD~1\nEOF\n)\n$x", "reset --hard"),
        ("x=$(cat <<'EOF'\ngit reset --hard HEAD~1\nEOF\n)\nbash -c \"$x\"", "reset --hard"),
        ("eval \\\n$(cat <<'EOF'\ngit reset --hard HEAD~1\nEOF\n)", "reset --hard"),
        ("eval $(\ncat <<'EOF'\ngit reset --hard HEAD~1\nEOF\n)", "reset --hard"),
        ("bash <(\ncat <<'EOF'\ngit reset --hard HEAD~1\nEOF\n)", "reset --hard"),
        ("source <(\ncat <<'EOF'\ngit reset --hard HEAD~1\nEOF\n)", "reset --hard"),
        ("$SHELL <<< $(cat <<'EOF'\ngit reset --hard HEAD~1\nEOF\n)", "reset --hard"),
        ("$0 <<< $(cat <<'EOF'\ngit reset --hard HEAD~1\nEOF\n)", "reset --hard"),
        ("{\ncat <<'EOF'\ngit reset --hard HEAD~1\nEOF\n} | bash", "reset --hard"),
        ("(\ncat <<'EOF'\ngit reset --hard HEAD~1\nEOF\n) | bash", "reset --hard"),
        ("f() {\ncat <<'EOF'\ngit reset --hard HEAD~1\nEOF\n}\nf | bash", "reset --hard"),
        ("for i in 1; do\ncat <<'EOF'\ngit reset --hard HEAD~1\nEOF\ndone | sh", "reset --hard"),
        ("if true; then\ncat <<'EOF'\ngit reset --hard HEAD~1\nEOF\nfi | bash", "reset --hard"),
        ("while true; do\ncat <<'EOF'\ngit reset --hard HEAD~1\nEOF\ndone | bash", "reset --hard"),
        ("cat <<'EOF' > out.md\ngit reset --hard HEAD~1\nEOF\nbash out.md", "reset --hard"),
        ("cat > out.txt <<'EOF'\ngit reset --hard HEAD~1\nEOF\nsource out.txt", "reset --hard"),
        # a consumer on a LATER line (or after `;`/`&&`) keeps even a message body visible
        ("git commit -m \"$(cat <<'EOF'\ngit reset --hard HEAD~1\nEOF\n)\" && bash x.sh", "reset --hard"),
        ("git commit -m \"$(cat <<'EOF'\ngit reset --hard HEAD~1\nEOF\n)\"; eval \"$x\"", "reset --hard"),
        ("git commit -m \"$(cat <<'EOF'\ngit reset --hard HEAD~1\nEOF\n)\"\nbash x.sh", "reset --hard"),
        ("git commit -m \"$(cat <<'EOF'\ngit reset --hard HEAD~1\nEOF\n)\" | bash", "reset --hard"),
        ("echo \"$(cat <<'EOF'\ngit reset --hard HEAD~1\nEOF\n)\"", "reset --hard"),
        ("git commit -m $(cat <<'EOF'\ngit reset --hard HEAD~1\nEOF\n)", "reset --hard"),
        ("git commit \\\n-m \"$(cat <<'EOF'\ngit reset --hard HEAD~1\nEOF\n)\"", "reset --hard"),
        ("git commit -m \"$(cat <<'EOF'\ngit reset --hard HEAD~1\nEOF\n)\" && ./run.sh", "reset --hard"),
        # the message text itself is not blanked unless it is a plain quoted delimiter
        ("git commit -m \"$(cat <<EOF\ngit reset --hard HEAD~1\nEOF\n)\"", "reset --hard"),
        ("git commit -m \"$(cat <<'END-X'\ngit reset --hard HEAD~1\nEND-X\n)\"", "reset --hard"),
    ],
)
def test_bash_dispatch_asks_on_a_destructive_command_inside_a_substitution(
    tmp_path, command, reason_word
):
    r = _run(_BASH_DISPATCH, {"tool_input": {"command": command}, "cwd": str(tmp_path)})
    assert r.returncode == 0
    nested = json.loads(r.stdout)["hookSpecificOutput"]
    assert nested["permissionDecision"] == "ask"
    assert reason_word in nested["permissionDecisionReason"]


@pytest.mark.parametrize(
    "command",
    [
        'git commit -m "reset --hard docs"',
        "echo 'literal $(git reset --hard HEAD~1) text'",
        "echo '`git push --force origin feat`'",
        'echo "escaped \\$(git reset --hard HEAD~1) text"',
        'echo "git push --force origin feat"',
        # text AFTER a closed substitution is still prose
        'echo "$(date) then git reset --hard HEAD~1"',
        'echo "`date` then git push --force origin feat"',
        # heredoc bodies with a QUOTED delimiter are data, in every wrapper
        'git commit -m "$(cat <<\'EOF\'\nfix: now asks on git reset --hard in a substitution\nEOF\n)"',
        'git commit -m "$(cat <<\'EOF\'\nfix: do not git push -f; it\'s a git branch -D thing\nEOF\n)"',
        'gh pr create --title t --body "$(cat <<\'EOF\'\nuse `gh pr merge 12` or Bash(gh pr merge:*)\nEOF\n)"',
        'git commit -m "$(cat <<"EOF"\nreset --hard (see git reset --hard HEAD)\nEOF\n)"',
        "cat > notes.md <<'EOF'\nRun `git push --force origin x` to fix.\nEOF",
        "cat > notes.md <<'EOF'\n```bash\ngit reset --hard HEAD\n```\nEOF",
        "gh pr comment 5 --body-file - <<'EOF'\nuse `git branch -D old` after\nEOF",
        'git tag -a v1 -m "$(cat <<\'EOF\'\nrelease: git reset --hard docs\nEOF\n)"',
        'git add . && git commit -m "$(cat <<\'EOF\'\nfix: git reset --hard docs\nEOF\n)" && git status',
        'gh issue comment 5 --body "$(cat <<\'EOF\'\nwe run gh pr merge 12 next\nEOF\n)"',
        # any other body keeps main's behaviour for Markdown code spans: blanked
        'cat > "$body" <<\'EOF\'\nuse `git reset --hard` to undo\n```\ngit push -f\n```\nEOF',
    ],
)
def test_bash_dispatch_stays_silent_when_the_shell_would_not_run_the_text(tmp_path, command):
    r = _run(_BASH_DISPATCH, {"tool_input": {"command": command}, "cwd": str(tmp_path)})
    assert r.returncode == 0
    assert "permissionDecision" not in r.stdout


# --------------------------------------------------------------------------- #
# Oversize command: asked about, never scanned, never allowed
#
# Guard cost grows linearly with the command, and a hook killed at the 15 s
# timeout lets the call through. The dispatcher caps what it scans.
# --------------------------------------------------------------------------- #

_CAP = _load_dispatcher("dispatch-bash-pretooluse.py").MAX_SCANNED_COMMAND_CHARS


def _padded(prefix: str, length: int) -> str:
    return prefix + "a" * (length - len(prefix))


def _bash(tmp_path, command: str):
    return _run(_BASH_DISPATCH, {"tool_input": {"command": command}, "cwd": str(tmp_path)})


def test_the_scan_cap_sits_between_real_commands_and_the_timeout():
    # Longest real command measured: 25,270 characters. Worst hostile shape: ~7.5 us per
    # character through the dispatcher: ~5 s at 650,000 characters, and 15 s (the timeout) near
    # 2,000,000. The cap keeps a 3x slower machine under the timeout.
    assert 100_000 <= _CAP <= 600_000


# requirement: guard-hooks / A command too large to scan asks first
@pytest.mark.parametrize("length", [_CAP + 1, _CAP * 6])
def test_an_oversize_command_gets_one_ask_naming_its_size_and_the_cap(tmp_path, length):
    r = _bash(tmp_path, _padded("echo ", length))
    assert r.returncode == 0
    assert r.stderr.strip() == ""
    nested = json.loads(r.stdout)["hookSpecificOutput"]
    reason = nested["permissionDecisionReason"]
    assert nested == {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": reason,
    }
    assert f"{length:,} characters" in reason
    assert f"{_CAP:,}-character" in reason
    assert "NO guard checked" in reason


# requirement: guard-hooks / A command too large to scan asks first
def test_an_oversize_command_runs_no_guard_not_even_the_first(tmp_path):
    # `cd` is blocked (exit 2) and a force-push asked about by their own hooks;
    # past the cap neither runs, and the one ask is the size ask.
    for prefix in ("cd /tmp && ", "git push --force origin x; "):
        r = _bash(tmp_path, _padded(prefix, _CAP + 1))
        assert r.returncode == 0, prefix
        reason = json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        assert "NO guard checked" in reason and "force-push" not in reason, prefix


# requirement: guard-hooks / A command too large to scan asks first
def test_a_command_at_or_below_the_cap_is_still_scanned(tmp_path):
    for length in (_CAP - 1, _CAP):
        clean = _bash(tmp_path, _padded("echo ", length))
        assert (clean.returncode, clean.stdout.strip()) == (0, ""), length
        cd = _bash(tmp_path, _padded("cd /tmp && ", length))
        assert cd.returncode == 2 and "block-cd-in-bash.py" in cd.stderr, length
        push = _bash(tmp_path, _padded("git push --force origin x; ", length))
        assert "force-push" in json.loads(push.stdout)["hookSpecificOutput"]["permissionDecisionReason"], length


@pytest.mark.parametrize(
    "stdin_text",
    ["not json {", "[]", '{"tool_input": null}', '{"tool_input": []}', '{"tool_input": {}}',
     '{"tool_input": {"command": 5}}'],
)
def test_input_without_a_command_string_goes_to_the_guards_unchanged(tmp_path, stdin_text):
    # The size check reads only `tool_input.command`; anything else is not its business.
    r = subprocess.run([sys.executable, str(_BASH_DISPATCH)], input=stdin_text, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", cwd=str(tmp_path))
    assert (r.returncode, r.stdout.strip()) == (0, "")


def test_the_cap_counts_characters_not_bytes(tmp_path):
    # Multi-byte text at the cap is still scanned: guard cost follows characters.
    command = "echo " + "é" * (_CAP - 5)
    assert len(command.encode("utf-8")) > _CAP
    r = _bash(tmp_path, command)
    assert (r.returncode, r.stdout.strip()) == (0, "")


# requirement: guard-hooks / A command too large to scan asks first
def test_a_three_megabyte_command_answers_well_inside_the_hook_timeout(tmp_path):
    import time

    started = time.perf_counter()
    r = _bash(tmp_path, ";" * 3_000_000)
    assert time.perf_counter() - started < 10.0
    assert json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "ask"
