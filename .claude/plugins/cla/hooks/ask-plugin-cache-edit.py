#!/usr/bin/env python3
"""PreToolUse hook: ask before an Edit or Write lands inside an installed plugin copy.

Problem this solves
--------------------
A plugin installed from a marketplace is a copy that Claude Code owns. It sits in
the plugins root, which is `~/.claude/plugins` by default (Claude Code's plugin
loading reference, "Find plugins on disk"):

    cache/<marketplace>/<plugin>/<version>/   one directory per installed version
    marketplaces/<name>/                      the clone of a marketplace's catalog

An update writes a new version directory and orphans the old one, and a
marketplace refresh re-clones its catalog, so an edit in either place is lost
without a word. The plugin's README says so ("Never edit it: it is a
version-keyed cache") and several skills repeat it, but nothing enforced it. A
repo's own rules belong in its `cla.io/overlays/<skill>.md` or
`cla.io/project-facts.md`; a fix to the plugin itself goes upstream.

Detection
---------
The target `file_path` (relative paths against the payload's `cwd`, `~`
expanded) is resolved through symlinks and `..`, then asked about when it lies
inside

the `cache/`, `marketplaces/` or `synced/` subtree of a plugins root (`synced/` holds
  other plugins' copies synced from claude.ai). The roots are
  `$CLAUDE_CODE_PLUGIN_CACHE_DIR` (despite its name, the whole plugins root),
  `$CLAUDE_CONFIG_DIR/plugins` and `~/.claude/plugins`, each one checked when
  it applies. Only those subtrees: `data/<id>/` is `${CLAUDE_PLUGIN_DATA}`,
  which a plugin is meant to write.

Path components compare case-insensitively on macOS and Windows, whose file systems
fold case. A plugin loaded with `--plugin-dir` runs from a working tree outside every
plugins root, so it matches none of these subtrees, and the repo
that develops it can edit it freely.

Decision: `ask`, never a block, so a person who means it can say yes.

Failure: bad input (a parse error, a missing or mistyped field, a path that
cannot be resolved) fails open, exiting 0 with no output. If this file itself
fails to load or crashes, the Edit/Write dispatcher counts it as an enforcing
guard that did not run and asks on every Edit and Write until it is fixed. It
runs no subprocess; its only I/O is resolving paths.
"""

from __future__ import annotations

import json
import os
import sys

# The parts of a plugins root that hold copies Claude Code replaces.
_INSTALLED_SUBTREES = ("cache", "marketplaces", "synced")


def _plugins_roots() -> list[str]:
    """Every plugins root that may hold an installed copy, resolved."""
    candidates = []
    override = os.environ.get("CLAUDE_CODE_PLUGIN_CACHE_DIR")
    if override:
        candidates.append(override)
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    if config_dir:
        candidates.append(os.path.join(config_dir, "plugins"))
    candidates.append(os.path.join("~", ".claude", "plugins"))
    return [os.path.realpath(os.path.expanduser(c)) for c in candidates]


def _fold(path: str) -> list[str]:
    """Path components, lowercased where the file system ignores case."""
    if sys.platform == "darwin" or sys.platform.startswith("win"):
        path = path.lower()
    return os.path.normcase(path).replace("\\", "/").split("/")


def _is_inside(path: str, root: str) -> bool:
    """True when `path` is `root` or below it. Both are already resolved."""
    p, r = _fold(path), _fold(root)
    return p[: len(r)] == r


def _installed_copy(target: str) -> str | None:
    """The installed-copy directory `target` lies in, or None."""
    for root in _plugins_roots():
        for sub in _INSTALLED_SUBTREES:
            subtree = os.path.join(root, sub)
            if _is_inside(target, subtree):
                return subtree
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        file_path = payload["tool_input"]["file_path"]
        if not isinstance(file_path, str) or not file_path:
            return 0
        cwd = payload.get("cwd")
        if not isinstance(cwd, str) or not cwd:
            cwd = os.getcwd()
        target = os.path.realpath(os.path.join(cwd, os.path.expanduser(file_path)))
        copy = _installed_copy(target)
    except Exception:  # noqa: BLE001 -- fail open: a guard does not break normal work
        return 0
    if copy is None:
        return 0

    reason = (
        f"'{target}' is inside an installed plugin copy ('{copy}'). Claude Code "
        "replaces that copy on the next plugin update or marketplace refresh, so "
        "this edit would be lost without a word. A repo's own rules go in "
        "`cla.io/overlays/<skill>.md` or `cla.io/project-facts.md`; a fix to the "
        "plugin goes upstream (`/cla:report-upstream`), or into the plugin's own "
        "working tree run with `--plugin-dir`. Confirm only if you mean to edit "
        "the installed copy. (hook: ask-plugin-cache-edit.py)"
    )
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": reason,
    }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
