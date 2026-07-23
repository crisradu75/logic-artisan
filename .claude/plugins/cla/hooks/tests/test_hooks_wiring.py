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
import json
import re
from pathlib import Path

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
