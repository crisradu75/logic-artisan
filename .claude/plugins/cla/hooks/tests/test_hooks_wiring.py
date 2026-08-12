"""Wiring-integrity tests for the cla plugin's hook layer.

The whole point of the extract-cla-plugin move was relocating the hook scripts,
so the failure mode most worth guarding is a *dangling wire*: a `hooks.json`
command (or a dispatcher's `_HOOK_FILES` entry) that names a script which no
longer exists at that path. At runtime such a break is near-silent -- the
`PYEXE ... || exit 0` guards swallow a missing interpreter, and a missing script
just errors into stderr -- so nothing else in the suite would catch it. These
tests assert every referenced hook script resolves to a real file, and are
deliberately non-vacuous (they fail if the extraction found *no* references,
which would mean the regex/parse silently matched nothing).
"""

from __future__ import annotations

import ast
import importlib.util
import json
import re
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).resolve().parent.parent
_PLUGIN_ROOT = _HOOKS_DIR.parent  # ${CLAUDE_PLUGIN_ROOT} == the plugin dir
_HOOKS_JSON = _HOOKS_DIR / "hooks.json"

# Captures the path after ${CLAUDE_PLUGIN_ROOT}/ in a hook command string,
# stopping at the closing quote / whitespace, e.g.
#   "${CLAUDE_PLUGIN_ROOT}/hooks/guard-worktree-isolation.py" -> hooks/guard-worktree-isolation.py
_PLUGIN_ROOT_REF = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\"'\s]+)")

_DISPATCHERS = (
    "dispatch-bash-pretooluse.py",
    "dispatch-edit-write-pretooluse.py",
)


def _load_hooks_json() -> dict:
    return json.loads(_HOOKS_JSON.read_text(encoding="utf-8"))


def _iter_hook_commands(hooks_json: dict):
    """Yield every `command` string across all events/matchers in hooks.json."""
    for _event, groups in hooks_json.get("hooks", {}).items():
        for group in groups:
            for hook in group.get("hooks", []):
                command = hook.get("command")
                if command:
                    yield command


def _hook_files_list(dispatcher_path: Path) -> list[str]:
    """Extract the `_HOOK_FILES = [...]` string list from a dispatcher, via AST.

    Parsing (not importing) keeps this side-effect-free and independent of
    sys.path -- the dispatcher's own `from _dispatch_lib import ...` never runs.
    """
    tree = ast.parse(dispatcher_path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "_HOOK_FILES" for t in node.targets
        ):
            return [ast.literal_eval(elt) for elt in node.value.elts]
    raise AssertionError(f"_HOOK_FILES not found in {dispatcher_path.name}")


def test_hooks_json_is_valid_json_with_expected_shape():
    data = _load_hooks_json()
    assert isinstance(data.get("hooks"), dict) and data["hooks"], "hooks.json has no hooks"
    for event, groups in data["hooks"].items():
        assert isinstance(groups, list) and groups, f"{event} has no hook groups"
        for group in groups:
            assert isinstance(group.get("hooks"), list) and group["hooks"], (
                f"{event} group missing hooks"
            )


def test_every_plugin_root_command_reference_resolves():
    """Every ${CLAUDE_PLUGIN_ROOT}/... path named in hooks.json exists on disk."""
    refs = [
        rel
        for command in _iter_hook_commands(_load_hooks_json())
        for rel in _PLUGIN_ROOT_REF.findall(command)
    ]
    # Non-vacuous: the current wiring references guard + both dispatchers.
    assert len(refs) >= 3, f"expected >=3 ${{CLAUDE_PLUGIN_ROOT}} references, found {refs}"
    missing = [rel for rel in refs if not (_PLUGIN_ROOT / rel).is_file()]
    assert not missing, f"hooks.json references non-existent scripts: {missing}"


def test_no_bare_repo_relative_hook_paths_remain():
    """No command still points at the pre-extraction $REPO/.claude/hooks/... path."""
    stale = [
        command
        for command in _iter_hook_commands(_load_hooks_json())
        if ".claude/hooks/" in command
    ]
    assert not stale, f"hooks.json still has pre-extraction .claude/hooks/ paths: {stale}"


def test_every_dispatcher_sibling_hook_exists():
    """Each script in a dispatcher's _HOOK_FILES resolves as a sibling on disk."""
    for dispatcher in _DISPATCHERS:
        dispatcher_path = _HOOKS_DIR / dispatcher
        assert dispatcher_path.is_file(), f"dispatcher missing: {dispatcher}"
        hook_files = _hook_files_list(dispatcher_path)
        assert hook_files, f"{dispatcher} has an empty _HOOK_FILES"
        missing = [name for name in hook_files if not (_HOOKS_DIR / name).is_file()]
        assert not missing, f"{dispatcher} references non-existent siblings: {missing}"


# --------------------------------------------------------------------------- #
# Handler budget -- hooks.json's `timeout` is the ceiling every hook must fit
# under, so the value and the constant the dispatchers reason about must agree.
# --------------------------------------------------------------------------- #


def _load_dispatch_lib():
    spec = importlib.util.spec_from_file_location(
        "dispatch_lib_for_wiring", _HOOKS_DIR / "_dispatch_lib.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _named_collection(dispatcher_path: Path, name: str) -> set[str]:
    """Extract a `NAME = frozenset({...})` / `NAME = [...]` literal via AST."""
    tree = ast.parse(dispatcher_path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            value = node.value
            # `frozenset({...})` — unwrap the call to reach the set literal.
            if isinstance(value, ast.Call):
                value = value.args[0]
            return set(ast.literal_eval(value))
    raise AssertionError(f"{name} not found in {dispatcher_path.name}")


def test_hooks_json_timeouts_match_the_dispatcher_budget_constant():
    # `_dispatch_lib.Deadline` sizes itself from HANDLER_TIMEOUT_SECONDS, and
    # every hook's own subprocess timeouts were chosen to fit under it. Raising
    # the JSON without the constant (or vice versa) silently invalidates both,
    # so pin them together rather than leaving the correspondence in a comment.
    lib = _load_dispatch_lib()
    declared = {
        hook.get("timeout")
        for _event, groups in _load_hooks_json()["hooks"].items()
        for group in groups
        for hook in group.get("hooks", [])
    }
    assert declared, "no timeouts declared in hooks.json"
    assert declared == {lib.HANDLER_TIMEOUT_SECONDS}, (
        f"hooks.json declares timeouts {declared} but _dispatch_lib."
        f"HANDLER_TIMEOUT_SECONDS is {lib.HANDLER_TIMEOUT_SECONDS}"
    )


@pytest.mark.parametrize("dispatcher", _DISPATCHERS)
def test_enforcing_hooks_fit_inside_the_handler_budget(dispatcher):
    """The sum that actually matters, and the one nobody was checking.

    Enforcing hooks are never skipped, so if their combined worst case exceeds
    the handler timeout then no admission policy can save them — Claude Code
    kills the handler mid-run and whichever hook had not run yet is silently
    skipped. That is indistinguishable from a guard that ran and allowed the
    call, which is the worst failure this layer has.

    Before this was asserted, the Bash dispatcher's enforcing hooks summed to
    17s and the Edit/Write dispatcher's to 21s, both against a 10s handler.
    """
    lib = _load_dispatch_lib()
    dispatcher_path = _HOOKS_DIR / dispatcher
    advisory = _named_collection(dispatcher_path, "_ADVISORY_HOOKS")
    hook_files = _hook_files_list(dispatcher_path)

    missing = [n for n in hook_files if n not in lib.HOOK_WORST_CASE_SECONDS]
    assert not missing, (
        f"{dispatcher} runs hook(s) with no HOOK_WORST_CASE_SECONDS entry: "
        f"{missing}. Add the (call sites x timeout) product so the budget can "
        "be checked."
    )

    enforcing = [n for n in hook_files if n not in advisory]
    total = sum(lib.HOOK_WORST_CASE_SECONDS[n] for n in enforcing)
    budget = lib.HANDLER_TIMEOUT_SECONDS - lib._BUDGET_RESERVE_SECONDS
    assert total <= budget, (
        f"{dispatcher}'s enforcing hooks can spend {total}s but only {budget}s "
        f"of the {lib.HANDLER_TIMEOUT_SECONDS}s handler is usable. These are "
        "never skipped, so the only fixes are fewer subprocess calls or shorter "
        f"per-hook timeouts. Enforcing: {enforcing}"
    )


@pytest.mark.parametrize("dispatcher", _DISPATCHERS)
def test_every_advisory_hook_is_admissible_on_an_idle_budget(dispatcher):
    """No advisory hook may be structurally impossible to run.

    Routine skips are reported to the debug log only — deliberately, because a
    skip is designed degradation and context noise on the hottest path in the
    session trains the channel to be ignored. The cost of that choice is that
    a hook which NEVER runs looks exactly like one that always does.

    This is the missing counterweight: if some hook's worst case exceeds the
    whole budget, it can never be admitted no matter how idle the handler, and
    it has quietly stopped being a guard. That is a defect, and it fails here
    rather than going unnoticed until someone wonders why a warning stopped
    appearing.
    """
    lib = _load_dispatch_lib()
    dispatcher_path = _HOOKS_DIR / dispatcher
    advisory = _named_collection(dispatcher_path, "_ADVISORY_HOOKS")
    budget = lib.HANDLER_TIMEOUT_SECONDS - lib._BUDGET_RESERVE_SECONDS

    unrunnable = {
        name: lib.HOOK_WORST_CASE_SECONDS[name]
        for name in advisory
        if lib.HOOK_WORST_CASE_SECONDS[name] > budget
    }
    assert not unrunnable, (
        f"{dispatcher}: these advisory hooks cost more than the entire {budget}s "
        f"budget, so they can never be admitted and have silently stopped "
        f"guarding: {unrunnable}"
    )


def test_the_budget_table_covers_every_dispatched_hook():
    """A table entry silently defaulting to 0.0 would make the sum meaningless."""
    lib = _load_dispatch_lib()
    dispatched = {
        name
        for dispatcher in _DISPATCHERS
        for name in _hook_files_list(_HOOKS_DIR / dispatcher)
    }
    assert dispatched <= set(lib.HOOK_WORST_CASE_SECONDS)
    # And the table must not accumulate entries for hooks nobody runs.
    stale = set(lib.HOOK_WORST_CASE_SECONDS) - dispatched
    assert not stale, f"HOOK_WORST_CASE_SECONDS has stale entries: {sorted(stale)}"


def test_powershell_runs_the_same_git_guards_as_bash():
    """PowerShell is the primary shell on Windows and ran one hook, not nine.

    Every hook on the Bash matcher reads `tool_input.command` and matches the
    command SHAPE, so `git push --force` is the same text either way. Wiring
    PowerShell to only `block-unsafe-recursive-delete.py` meant a force-push, a
    push straight to main, or a wrong-identity commit issued through it bypassed
    every git guard in the tree.
    """
    groups = {
        group.get("matcher"): group
        for group in _load_hooks_json()["hooks"]["PreToolUse"]
    }
    assert "PowerShell" in groups, "PowerShell has no PreToolUse wiring"
    commands = " ".join(h.get("command", "") for h in groups["PowerShell"]["hooks"])
    assert "dispatch-bash-pretooluse.py" in commands, (
        "PowerShell must route through the shared shell dispatcher, or its git "
        "guards silently do not apply"
    )


def _changes_the_outcome(hook_source: str) -> bool:
    """True iff a hook can alter whether/how the tool call proceeds.

    Two shapes qualify, and the second is why an exit-code check alone is not
    enough: a hook can return 2 (block), or exit 0 while emitting
    `permissionDecision` (escalate to a prompt). The latter leaves no trace in
    the exit code, so a scan for `return 2` would happily call it advisory and
    let budget pressure silently downgrade an ask to an allow.
    """
    return bool(
        re.search(r"^\s*return 2\b", hook_source, re.M)
        or "permissionDecision" in hook_source
    )


@pytest.mark.parametrize("dispatcher", _DISPATCHERS)
def test_no_outcome_changing_hook_is_marked_advisory(dispatcher):
    """A hook that can block or escalate must never be skippable.

    Advisory hooks get dropped when the handler budget is spent. Losing a
    warning is acceptable; losing a BLOCK or an ASK is a silent enforcement
    failure, and is the exact outcome the budget logic exists to prevent.
    Asserted structurally so that adding a block or ask path to a currently
    advisory hook fails here rather than quietly widening what budget pressure
    can drop.
    """
    dispatcher_path = _HOOKS_DIR / dispatcher
    advisory = _named_collection(dispatcher_path, "_ADVISORY_HOOKS")
    hook_files = set(_hook_files_list(dispatcher_path))

    assert advisory, f"{dispatcher} has an empty _ADVISORY_HOOKS"
    assert advisory <= hook_files, (
        f"{dispatcher} marks hooks advisory that it never runs: {advisory - hook_files}"
    )

    enforcing = {
        name for name in advisory
        if _changes_the_outcome((_HOOKS_DIR / name).read_text(encoding="utf-8"))
    }
    assert not enforcing, (
        f"{dispatcher} marks outcome-changing hook(s) as advisory, so budget "
        f"pressure could silently drop enforcement: {sorted(enforcing)}"
    )


def test_the_outcome_detector_is_not_vacuous():
    # A structural guard that matches nothing passes forever. Pin that the
    # detector actually recognizes both shapes it claims to cover, so a future
    # refactor of the hooks cannot quietly turn the test above into a no-op.
    assert _changes_the_outcome((_HOOKS_DIR / "block-cd-in-bash.py").read_text(encoding="utf-8"))
    assert _changes_the_outcome((_HOOKS_DIR / "ask-destructive-git.py").read_text(encoding="utf-8"))
    assert not _changes_the_outcome(
        (_HOOKS_DIR / "warn-stacked-pr-merge.py").read_text(encoding="utf-8")
    )


@pytest.mark.parametrize("dispatcher", _DISPATCHERS)
def test_dispatcher_caps_its_output(dispatcher):
    # The 10,000-char cap applies to what the PROCESS prints, and only the
    # dispatcher sees the concatenation of every hook's output, so this is the
    # one place it can be enforced. Structural: a dispatcher that stops routing
    # through the shared helpers has re-opened the gap.
    source = (_HOOKS_DIR / dispatcher).read_text(encoding="utf-8")
    assert "compose_output" in source, (
        f"{dispatcher} must route stderr through compose_output so the block "
        "reason is budgeted ahead of advisory text"
    )


# --------------------------------------------------------------------------- #
# The interpreter probe in hooks.json
#
# The previous form was `command -v python3 || command -v py || command -v
# python`. On Windows `python3` commonly resolves to the Store alias stub, which
# EXISTS and is executable — so `command -v` succeeds, the fallbacks never fire,
# and every dispatched hook is invoked through an interpreter that cannot run
# it. The hook then exits non-zero with no output, which for a PreToolUse hook
# is indistinguishable from "ran and allowed": the whole guard set silently does
# nothing. Reproduced with a non-functional `python3` first on PATH.
# --------------------------------------------------------------------------- #


def _wiring_commands() -> list[str]:
    import json
    data = json.loads((_HOOKS_DIR / "hooks.json").read_text(encoding="utf-8"))
    return [h["command"] for ev in data["hooks"].values() for m in ev for h in m["hooks"]]


def test_every_wiring_runs_each_interpreter_candidate_before_accepting_it():
    """`command -v` only proves a name resolves, not that it works.

    Asserting the VERSION via stdout, not merely running `-c "import sys"`: that
    weaker check succeeds on Python 2.7 and on any wrapper that swallows `-c`,
    so a stub exiting 0 for everything was still accepted. A silent stub prints
    nothing and a Python 2 prints `0`, so both now fail the comparison.
    """
    for cmd in _wiring_commands():
        assert "sys.version_info" in cmd, (
            "a wiring accepts an interpreter without asserting its version:\n" + cmd[:200]
        )
        assert 'print(1 if sys.version_info' in cmd, (
            "version must be asserted via STDOUT, not an exit code:\n" + cmd[:200]
        )


def test_every_wiring_clears_pyexe_before_probing():
    """REGRESSION guard. The loop only assigns on success, so without an explicit
    clear `${PYEXE:-}` reads whatever the parent exported and the probe hands
    every hook to it. Both launchers already clear their equivalents."""
    for cmd in _wiring_commands():
        assert cmd.startswith("PYEXE=;"), (
            "a wiring can inherit a stale PYEXE from the environment:\n" + cmd[:120]
        )


def test_every_wiring_exits_non_zero_when_no_interpreter_works():
    """Still fail-open -- only exit 2 blocks a tool call -- but stderr from an
    exit-0 hook reaches the debug log only. `_dispatch_lib` documents that
    contract and both dispatchers follow it; the probe was the one place that
    regressed to stderr + exit 0, so its own "announced rather than silent"
    comment was false."""
    for cmd in _wiring_commands():
        assert "NOT running\" >&2; exit 1;" in cmd, (
            "a wiring announces failure only to the debug log:\n" + cmd[:200]
        )


def test_no_wiring_uses_the_bare_command_v_chain():
    """The exact shape that shipped broken. Pinned by text because the failure
    is invisible at runtime on a machine where `python3` happens to work."""
    for cmd in _wiring_commands():
        assert "command -v python3 2>/dev/null || command -v py" not in cmd, (
            "a wiring reverted to the trust-the-first-name probe:\n" + cmd[:160]
        )


def test_every_wiring_announces_when_no_interpreter_works():
    """Fail-open is right for a guard, but fail-open-and-silent means the user
    believes they are protected when nothing is running."""
    for cmd in _wiring_commands():
        assert "NOT running" in cmd, (
            "a wiring degrades silently when no interpreter is usable:\n" + cmd[:160]
        )


def test_every_wiring_probes_the_same_candidates_in_the_same_order():
    """The candidate ORDER is the load-bearing part of the probe.

    `python3` first matters on Windows, where it commonly resolves to the Store
    alias stub: the probe RUNS each candidate rather than trusting the first
    name that resolves, so a stub that cannot execute is skipped instead of
    silently disabling every dispatched hook.

    This used to be a parity check against `claw`, which carried the probe
    first. `claw` is gone (its reason to exist went with
    `guard-worktree-isolation.py`) and `cla` never had a probe at all, so
    hooks.json is now the sole holder and this pins it directly.
    """
    for cmd in _wiring_commands():
        assert "for c in python3 py python" in cmd


# --------------------------------------------------------------------------- #
# No synced-core hook may prescribe a branch NAMING CONVENTION
#
# `guard-worktree-isolation.py` told the user to run
# `git worktree add ... -b feature/<task>`. These hooks are synced core, so a
# consuming repo whose convention is e.g. `claude/fix/...` had an ENFORCING hook
# instructing it to create a branch its own rules forbid — and no way to correct
# that downstream. It did not even match this plugin's own tooling, which uses
# `manual_worktree.DEFAULT_BRANCH_PREFIX` (`worktree-`).
#
# Reported by a consumer, which also noted the existing test would not have
# caught it: it asserted only `returncode == 2` and `"worktree" in stderr`,
# leaving the remediation command itself unpinned.
# --------------------------------------------------------------------------- #


def _runtime_string_constants(path):
    """Every string literal in the module EXCEPT docstrings.

    Docstrings are prose for a maintainer and may legitimately use a concrete
    example; a runtime string is what the user is actually told to run.
    """
    import ast
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                if isinstance(body[0].value.value, str):
                    docstrings.add(id(body[0].value))
    return [
        n.value for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings
    ]


def test_no_hook_prescribes_a_branch_naming_convention_at_runtime():
    import re
    # Scoped to what follows the BRANCH flag. An earlier, broader form also
    # flagged `.claude/worktrees/<task>` — a directory this plugin owns and is
    # entitled to name (`manual_worktree.DEFAULT_WORKTREE_DIR`), not a
    # convention imposed on the consuming repo. The defect is specifically
    # telling someone what to call their BRANCH.
    prescriptive = re.compile(r"-b\s+(?!<)[\w.-]+/?[\w.-]*")
    offenders = []
    for hook in sorted(_HOOKS_DIR.glob("*.py")):
        for s in _runtime_string_constants(hook):
            for m in prescriptive.finditer(s):
                offenders.append(f"{hook.name}: {m.group(0)!r} in {s[:60]!r}")
    assert not offenders, (
        "a synced-core hook prescribes a branch naming convention the consuming "
        "repo may forbid; say `<branch>` or point at /cla:new-worktree instead:\n"
        + "\n".join(offenders)
    )


# --------------------------------------------------------------------------- #
# The interpreter probe -- EXECUTED, not substring-asserted
#
# Every prior test of this probe checked that hooks.json CONTAINS certain text.
# A probe with an unbalanced quote, a `break` in the wrong scope, or a stale
# variable passes all of those. A consuming repo measured three real defects in
# it that substring assertions could not see.
# --------------------------------------------------------------------------- #

import shutil
import subprocess as _sp


def _probe_prefix() -> str:
    """The probe half of a wiring's command, up to the interpreter invocation."""
    cfg = json.loads((_HOOKS_DIR / "hooks.json").read_text(encoding="utf-8"))
    cmd = cfg["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    return cmd.split('; "$PYEXE"')[0]


_BASH = shutil.which("bash")


@pytest.mark.skipif(_BASH is None, reason="no POSIX shell available")
def test_probe_rejects_a_stale_exported_pyexe(tmp_path):
    """REGRESSION. The loop only assigns on success, so without an explicit
    clear `${PYEXE:-}` reads whatever the parent exported -- and the probe then
    hands every hook to it. The form this replaced (`PYEXE=$(command -v ...)`)
    always overwrote, so this was a regression, and it drifts from both
    launchers, which do clear it.

    PATH must therefore contain no USABLE interpreter, which is why it points at
    an empty directory. Not `PATH=""` -- some shells read an empty PATH as the
    cwd, which is not the state this needs. And not a real system directory: the
    refusal fires whenever the loop ends with `PYEXE` unset, which includes an
    interpreter that was found but failed the >=3.8 check (the case the next test
    covers), but a directory holding a WORKING python defeats this test
    specifically, because the loop's `PYEXE=$p` then overwrites the stale value
    and the missing-clear regression becomes invisible. `/usr/bin` is exactly
    such a directory on macOS, where `/usr/bin/python3` is a working interpreter.

    An empty directory needs nothing on PATH to work: on the refusal path the
    probe runs only `command -v`, `[` and `echo`, all builtins in bash and in
    every POSIX sh, and never reaches the `"$p" -c ...` liveness call."""
    empty = tmp_path / "empty-path"
    empty.mkdir()
    env = {"PATH": str(empty), "PYEXE": "/definitely/not/a/python"}
    r = _sp.run([_BASH, "-c", _probe_prefix() + '; echo "SELECTED:$PYEXE"'],
                capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    assert "SELECTED:/definitely/not/a/python" not in r.stdout
    assert r.returncode == 1, "must refuse, and non-zero so the notice reaches the transcript"
    assert "NOT running" in r.stderr


@pytest.mark.skipif(_BASH is None, reason="no POSIX shell available")
def test_probe_rejects_an_interpreter_that_exits_zero_for_everything(tmp_path):
    """A liveness check of `-c "import sys"` succeeds on Python 2.7 and on any
    wrapper that swallows `-c`. Asserting the version VIA STDOUT rejects both:
    a silent stub prints nothing, a Python 2 prints 0.

    PATH is the stub dir ALONE. It previously also held `/usr/bin`, which the
    probe reaches: the loop falls through the rejected `python3` stub to `py`,
    then to `python`, and `/usr/bin/python` is a working 3.8+ interpreter on any
    distro with `python-is-python3` -- the probe then exits 0 and both asserts
    below fail. That never fired on macOS only because `/usr/bin/python` was
    removed in 12.3. Nothing here needs `/usr/bin`: the stub carries its own
    `#!/bin/sh`, which the kernel resolves absolutely."""
    stub_dir = tmp_path / "stub"
    stub_dir.mkdir()
    stub = stub_dir / "python3"
    stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    stub.chmod(0o755)
    env = {"PATH": str(stub_dir)}
    r = _sp.run([_BASH, "-c", _probe_prefix() + '; echo "SELECTED:$PYEXE"'],
                capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    assert "SELECTED:" not in r.stdout or "SELECTED:\n" in r.stdout
    assert r.returncode == 1


@pytest.mark.skipif(_BASH is None, reason="no POSIX shell available")
def test_probe_still_selects_a_working_interpreter():
    """Non-vacuity partner: the two tests above pass trivially if the probe
    rejects everything."""
    r = _sp.run([_BASH, "-c", _probe_prefix() + '; echo "SELECTED:$PYEXE"'],
                capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0
    assert re.search(r"SELECTED:\S+", r.stdout), r.stdout


def test_every_wiring_shares_one_probe():
    """Seven inlined copies drifted from the `_pyexe` reference once already."""
    cfg = json.loads((_HOOKS_DIR / "hooks.json").read_text(encoding="utf-8"))
    probes = {
        h["command"].split('; "$PYEXE"')[0]
        for arr in cfg["hooks"].values() for m in arr for h in m["hooks"]
    }
    assert len(probes) == 1, f"{len(probes)} distinct probes across the wirings"
    # `_pyexe` carries the trailing `;` that joins it to the interpreter call;
    # splitting the live command on `; "$PYEXE"` consumes that separator.
    assert probes.pop() == cfg["_pyexe"].rstrip("; "), (
        "_pyexe drifted from the live wirings"
    )
