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
        (_HOOKS_DIR / "warn-branch-base.py").read_text(encoding="utf-8")
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
