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
# The interpreter probe -- hooks/probe-python.sh
#
# The previous form was `command -v python3 || command -v py || command -v
# python`. On Windows `python3` commonly resolves to the Store alias stub, which
# EXISTS and is executable — so `command -v` succeeds, the fallbacks never fire,
# and every dispatched hook is invoked through an interpreter that cannot run
# it. The hook then exits non-zero with no output, which for a PreToolUse hook
# is indistinguishable from "ran and allowed": the whole guard set silently does
# nothing. Reproduced with a non-functional `python3` first on PATH.
#
# The probe was inlined into all five commands (plus a `_pyexe` reference copy)
# until it moved into its own file. These tests therefore split in two: the
# WIRINGS are checked for reaching the script, and the SCRIPT is checked for the
# properties that used to be substring-asserted five times over.
# --------------------------------------------------------------------------- #

_PROBE_SH = _HOOKS_DIR / "probe-python.sh"


def _wiring_commands() -> list[str]:
    import json
    data = json.loads((_HOOKS_DIR / "hooks.json").read_text(encoding="utf-8"))
    return [h["command"] for ev in data["hooks"].values() for m in ev for h in m["hooks"]]


def _probe_source() -> str:
    return _PROBE_SH.read_text(encoding="utf-8")


def test_every_wiring_sources_the_shared_probe():
    """Replaces `test_every_wiring_shares_one_probe`, which held five inlined
    copies equal to a sixth reference copy -- they had drifted from it once
    already. One file cannot drift from itself; what can still break is a wiring
    that stops reaching it, or reaches a different path."""
    for cmd in _wiring_commands():
        assert cmd.startswith('. "${CLAUDE_PLUGIN_ROOT}/hooks/probe-python.sh"'), (
            "a wiring does not source the shared probe first:\n" + cmd[:160]
        )
        assert '"$PYEXE" "${CLAUDE_PLUGIN_ROOT}/hooks/' in cmd, (
            "a wiring does not run its hook through the probed interpreter:\n" + cmd[:160]
        )


def test_every_wiring_refuses_when_the_probe_file_is_missing():
    """The one failure sourcing adds, and the shells disagree about it: bash
    prints its own error and CONTINUES -- which would run the hook with $PYEXE
    empty -- while sh exits 1 on its own. Both verified. An `exit` inside a probe
    that IS present exits the shell before this clause is reached, so it cannot
    mask a refusal."""
    for cmd in _wiring_commands():
        assert "|| { echo" in cmd and "NOT running" in cmd, (
            "a wiring proceeds with an empty $PYEXE when the probe file is gone:\n"
            + cmd[:200]
        )


def test_the_probe_has_no_carriage_returns():
    """A CRLF checkout disables every guard hook in the plugin.

    A shell reads `\\r` as content, not as a line ending, so a CRLF probe fails on
    its first statement with `$'\\r': command not found`, leaves $PYEXE unset, and
    every wiring stops working -- the silent degradation the probe exists to
    prevent, reintroduced by a checkout setting. This repo has
    `core.autocrlf=true`; `.gitattributes` pins `hooks/*.sh` to LF because of it.

    This test is the half that ships: `.gitattributes` lives at the SOURCE repo
    root and does not govern a consuming repo's checkout, but the plugin's own
    test scope travels with the plugin.
    """
    assert b"\r" not in _PROBE_SH.read_bytes(), (
        f"{_PROBE_SH.name} has CRLF line endings; no shell can source it, so "
        "every guard hook is silently disabled. Check .gitattributes and re-checkout."
    )


def test_probe_runs_each_interpreter_candidate_before_accepting_it():
    """`command -v` only proves a name resolves, not that it works.

    Asserting the VERSION via stdout, not merely running `-c "import sys"`: that
    weaker check succeeds on Python 2.7 and on any wrapper that swallows `-c`,
    so a stub exiting 0 for everything was still accepted. A silent stub prints
    nothing and a Python 2 prints `0`, so both now fail the comparison.
    """
    src = _probe_source()
    assert "sys.version_info" in src, "the probe accepts an interpreter unversioned"
    assert "print(1 if sys.version_info" in src, (
        "version must be asserted via STDOUT, not an exit code"
    )


def test_probe_clears_pyexe_before_probing():
    """REGRESSION guard. The loop only assigns on success, so without an explicit
    clear `$PYEXE` reads whatever the parent exported and the probe hands every
    hook to it. Executed counterpart: `test_probe_rejects_a_stale_exported_pyexe`."""
    body = [
        line for line in _probe_source().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert body and body[0] == "PYEXE=", (
        "the probe can inherit a stale PYEXE from the environment; first "
        f"non-comment line is {body[0] if body else '<empty>'!r}"
    )


def test_probe_announces_failure_and_exits_non_zero():
    """Still fail-open -- only exit 2 blocks a tool call -- but stderr from an
    exit-0 hook reaches the debug log only. `_dispatch_lib` documents that
    contract and both dispatchers follow it; the probe was the one place that
    regressed to stderr + exit 0, so its own "announced rather than silent"
    comment was false."""
    src = _probe_source()
    assert "NOT running" in src, "the probe degrades silently when nothing is usable"
    assert ">&2" in src and "exit 1" in src, (
        "refusal must reach stderr AND exit non-zero, or it lands in the debug log only"
    )


def test_the_refusal_message_names_the_escape_hatch():
    """A user whose interpreter is somewhere stages 2 and 3 do not look needs to
    be told what to do about it, in the message they actually see."""
    src = _probe_source()
    assert "Set CLA_PYTHON" in src, (
        "the refusal message does not tell the user how to fix it"
    )


def test_probe_does_not_use_the_bare_command_v_chain():
    """The exact shape that shipped broken. Pinned by text because the failure
    is invisible at runtime on a machine where `python3` happens to work."""
    assert "command -v python3 2>/dev/null || command -v py" not in _probe_source(), (
        "the probe reverted to the trust-the-first-name form"
    )


def test_probe_tries_the_candidate_names_in_the_same_order():
    """The candidate ORDER is the load-bearing part of stage 2.

    `python3` first matters on Windows, where it commonly resolves to the Store
    alias stub: the probe RUNS each candidate rather than trusting the first
    name that resolves, so a stub that cannot execute is skipped instead of
    silently disabling every dispatched hook.
    """
    assert "for _c in python3 py python" in _probe_source()


def test_probe_searches_install_locations_off_path():
    """The three NAMES are not enough, and the failure is invisible from pytest.

    Measured on one Windows machine: the hook's PATH and the PATH a tool call
    sees are different, and the real interpreter is on the second but not the
    first. Under the hook's PATH `python3` is a wrapper delegating to `python`,
    which there is the Store alias stub; `py` is absent; `python` is the same
    stub. All three fail the version assertion, the probe reports that nothing
    is usable, and every dispatched hook stops running.

    `test_probe_still_selects_a_working_interpreter` cannot catch this -- it runs
    the probe under the TEST process's PATH, which has a real python on it.

    Both families are asserted because the defect is not Windows-specific: a hook
    PATH missing `/usr/local/bin` fails the same way. An unmatched glob stays
    literal, `-x` is then false, and the entry is skipped -- so each family is
    inert on the other's platform.

    EVERY location is pinned individually, and the list is deliberately brittle.
    An earlier form asserted `"Python3*/python.exe" in src` once; a mutation run
    then deleted the per-user Windows install path -- the single location that
    fixed the machine this whole defect came from -- and the test still passed,
    because the all-users path two lines down matches the same substring.
    Dropping a location should cost a second edit here, on purpose.
    """
    src = _probe_source()
    expected = (
        '"$HOME"/AppData/Local/Programs/Python/Python3*/python.exe',  # per-user installer
        "/c/Program\\ Files/Python3*/python.exe",                     # all-users installer
        "/c/Python3*/python.exe",                                     # legacy root install
        "/opt/homebrew/bin/python3",                                  # Apple Silicon Homebrew
        "/usr/local/bin/python3",                                     # Intel Homebrew, /usr/local
        "/usr/bin/python3",                                           # system python
    )
    missing = [p for p in expected if p not in src]
    assert not missing, f"stage 3 no longer searches: {missing}"


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
    """The probe half of a wiring's command, up to the interpreter invocation.

    Taken from the LIVE wiring rather than hand-written, so these executed tests
    exercise the same `. <script> || {...}` text a hook actually runs.
    """
    cfg = json.loads((_HOOKS_DIR / "hooks.json").read_text(encoding="utf-8"))
    cmd = cfg["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    return cmd.split('; "$PYEXE"')[0]


# The wiring expands ${CLAUDE_PLUGIN_ROOT}; these tests pass a restricted env, so
# they must supply it. Forward slashes because a POSIX shell reads `C:\...`
# backslashes as escapes -- `C:/...` it resolves.
_PLUGIN_ROOT_SH = str(_PLUGIN_ROOT).replace("\\", "/")

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
    # CLA_PY_SEARCH empty suppresses stage 3, the install-location search.
    # Without it the probe finds the real interpreter off PATH entirely and the
    # refusal path -- the only path this test examines -- is never reached.
    # Clearing the env does not do it: bash supplies HOME from the passwd entry
    # when it is absent.
    env = {
        "PATH": str(empty),
        "PYEXE": "/definitely/not/a/python",
        "CLA_PY_SEARCH": "",
        "CLAUDE_PLUGIN_ROOT": _PLUGIN_ROOT_SH,
    }
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
    # See the note in the previous test: empty CLA_PY_SEARCH suppresses stage 3,
    # which would otherwise satisfy the probe off PATH and hide the stub
    # rejection this test exists to prove.
    env = {
        "PATH": str(stub_dir),
        "CLA_PY_SEARCH": "",
        "CLAUDE_PLUGIN_ROOT": _PLUGIN_ROOT_SH,
    }
    r = _sp.run([_BASH, "-c", _probe_prefix() + '; echo "SELECTED:$PYEXE"'],
                capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    assert "SELECTED:" not in r.stdout or "SELECTED:\n" in r.stdout
    assert r.returncode == 1


def _real_interpreter() -> str:
    """An absolute path to a KNOWN-GOOD interpreter, in a form a POSIX shell
    resolves.

    `sys.executable`, deliberately, and not `command -v python3`: on the machine
    that produced this whole defect the first `python3` on PATH is a wrapper that
    delegates to `python`, so it fails the version check the moment PATH is
    poisoned -- and these tests poison PATH on purpose. The process running
    pytest is by definition a real Python.
    """
    import sys
    return sys.executable.replace("\\", "/")


def _inherited_env(**overrides) -> dict:
    """The real environment plus CLAUDE_PLUGIN_ROOT, for the tests that want a
    normal PATH rather than a poisoned one."""
    import os
    env = dict(os.environ)
    env["CLAUDE_PLUGIN_ROOT"] = _PLUGIN_ROOT_SH
    env.update(overrides)
    return env


@pytest.mark.skipif(_BASH is None, reason="no POSIX shell available")
def test_probe_still_selects_a_working_interpreter():
    """Non-vacuity partner: the two tests above pass trivially if the probe
    rejects everything.

    Weaker evidence than it looks, and the comment is the point: this runs under
    the TEST process's PATH. The defect that produced stage 3 was a hook PATH on
    which every name failed while this test stayed green.
    """
    r = _sp.run([_BASH, "-c", _probe_prefix() + '; echo "SELECTED:$PYEXE"'],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                env=_inherited_env())
    assert r.returncode == 0, r.stderr
    assert re.search(r"SELECTED:\S+", r.stdout), r.stdout


@pytest.mark.skipif(_BASH is None, reason="no POSIX shell available")
def test_stage_three_finds_an_interpreter_that_is_not_on_path(tmp_path):
    """The whole reason stage 3 exists, exercised rather than asserted by text.

    PATH holds nothing usable, so stages 1 and 2 must fail; CLA_PY_SEARCH then
    points stage 3 at a real interpreter by absolute path. Without a stage 3 this
    refuses -- which is exactly what shipped, and what killed every guard hook on
    a machine whose hook PATH differed from its tool PATH.
    """
    interpreter = _real_interpreter()
    empty = tmp_path / "empty-path"
    empty.mkdir()
    env = {
        "PATH": str(empty),
        "CLA_PY_SEARCH": interpreter,
        "CLAUDE_PLUGIN_ROOT": _PLUGIN_ROOT_SH,
    }
    r = _sp.run([_BASH, "-c", _probe_prefix() + '; echo "SELECTED:$PYEXE"'],
                capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    assert r.returncode == 0, r.stderr
    assert f"SELECTED:{interpreter}" in r.stdout, r.stdout


@pytest.mark.skipif(_BASH is None, reason="no POSIX shell available")
def test_cla_python_overrides_a_working_path_interpreter():
    """The escape hatch has to WIN, or it is not an escape hatch. PATH here is
    the normal one, so stage 2 would succeed; CLA_PYTHON must be taken first."""
    interpreter = _real_interpreter()
    r = _sp.run([_BASH, "-c", _probe_prefix() + '; echo "SELECTED:$PYEXE"'],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                env=_inherited_env(CLA_PYTHON=interpreter))
    assert r.returncode == 0, r.stderr
    assert f"SELECTED:{interpreter}" in r.stdout, r.stdout


@pytest.mark.skipif(_BASH is None, reason="no POSIX shell available")
def test_cla_python_is_still_version_checked(tmp_path):
    """An override is not a bypass. A CLA_PYTHON naming a stub must fall through
    to the later stages, not be handed every hook on the user's say-so."""
    stub = tmp_path / "fake-python"
    stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    stub.chmod(0o755)
    r = _sp.run([_BASH, "-c", _probe_prefix() + '; echo "SELECTED:$PYEXE"'],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                env=_inherited_env(CLA_PYTHON=str(stub)))
    assert str(stub) not in r.stdout, "a stub named by CLA_PYTHON was accepted"


@pytest.mark.skipif(_BASH is None, reason="no POSIX shell available")
def test_wiring_refuses_when_the_probe_file_is_absent(tmp_path):
    """Executed counterpart to the text assertion. bash does NOT stop on a failed
    `.` -- it prints and continues -- so without the `||` clause the wiring would
    run the hook with $PYEXE empty."""
    r = _sp.run([_BASH, "-c", _probe_prefix() + '; echo "SELECTED:$PYEXE"'],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                env=_inherited_env(CLAUDE_PLUGIN_ROOT=str(tmp_path).replace("\\", "/")))
    assert r.returncode != 0, "a missing probe let the wiring proceed"
    assert "SELECTED:" not in r.stdout
    assert "NOT running" in r.stderr
