"""Mutant batch for `tests/hooks/test_ask_plugin_cache_edit.py` -- the enforcing ask
guard over an Edit or Write inside an installed plugin copy, in
`ask-plugin-cache-edit.py`.

Run:
    python3 plugin-tests/mutate.py plugin-tests/mutants/hooks/test_ask_plugin_cache_edit.py

Every mutant edits the hook, the Edit/Write dispatcher or `_dispatch_lib.py`,
never a test. The hook mutants re-break one line each: the subtree list, each
plugins-root candidate and its resolution, path containment and its
macOS/Windows case folding, the target's resolution, the empty-path and cwd
fallbacks, the fail-open catch and the ask payload. The dispatcher mutants
re-break the ask channel this change added (the hook's place in the list, ask
extraction, the joined reason) and the hook's enforcing tier and budget entry.

Deliberately absent, because no correct input can tell them from the real code:
- `_fold`'s `normcase` call: identity unless `os.path` is `ntpath`, so no test
  run on Linux or macOS could catch a planted bug there. Its
  `replace("\\\\", "/")` is the same on Windows; on POSIX it differs only for a
  file name holding a literal backslash, where a test would pin a quirk, not a
  rule. (The `sys.platform` lowercasing beside them is covered: the tests
  simulate the platform.)
- dropping `or not cwd` from the cwd fallback. An empty cwd joins to the bare
  path, which `realpath` resolves against the process cwd: the same directory
  the fallback picks.
- dropping `if not stdout_text: return None` in the dispatcher's `_extract_ask`.
  `json.loads("")` raises the `JSONDecodeError` the next line already maps to
  None.

Each anchor occurs once in its file; mutate.py's preflight refuses any that does not.

Dropped when re-anchored to the current hook: the eight `$CLAUDE_PLUGIN_ROOT`
mutants. That rule was removed from the hook (a copy synced from claude.ai is now
caught by the `synced/` subtree), so the code they broke no longer exists.

Paths resolve from this file's own location, never an absolute developer path.
"""

from pathlib import Path

DEV = Path(__file__).resolve().parents[2]          # <repo>/plugin-tests
PLUGIN = DEV.parent / ".claude" / "plugins" / "cla"
HOOK = PLUGIN / "hooks" / "ask-plugin-cache-edit.py"
GUARD = DEV / "tests" / "hooks" / "test_ask_plugin_cache_edit.py"
TARGETS = [GUARD]
DISPATCHER = PLUGIN / "hooks" / "dispatch-edit-write-pretooluse.py"
LIB = PLUGIN / "hooks" / "_dispatch_lib.py"
DISPATCH_TARGETS = [
    GUARD,
    DEV / "tests" / "hooks" / "test_dispatch.py",
    DEV / "tests" / "hooks" / "test_hooks_wiring.py",
]

MUTANTS = [
    # ---- which subtrees count -------------------------------------------
    (
        "cache/ is no longer an installed subtree",
        HOOK,
        '_INSTALLED_SUBTREES = ("cache", "marketplaces", "synced")',
        '_INSTALLED_SUBTREES = ("marketplaces", "synced")',
        TARGETS,
    ),
    (
        "marketplaces/ is no longer an installed subtree",
        HOOK,
        '_INSTALLED_SUBTREES = ("cache", "marketplaces", "synced")',
        '_INSTALLED_SUBTREES = ("cache", "synced")',
        TARGETS,
    ),
    (
        "synced/ is no longer an installed subtree",
        HOOK,
        '_INSTALLED_SUBTREES = ("cache", "marketplaces", "synced")',
        '_INSTALLED_SUBTREES = ("cache", "marketplaces")',
        TARGETS,
    ),
    (
        "the plugin data directory is treated as installed",
        HOOK,
        '_INSTALLED_SUBTREES = ("cache", "marketplaces", "synced")',
        '_INSTALLED_SUBTREES = ("cache", "marketplaces", "synced", "data")',
        TARGETS,
    ),
    # ---- the plugins roots ----------------------------------------------
    (
        "CLAUDE_CODE_PLUGIN_CACHE_DIR is ignored",
        HOOK,
        "        candidates.append(override)",
        "        pass",
        TARGETS,
    ),
    (
        "CLAUDE_CODE_PLUGIN_CACHE_DIR is read as the config dir, not the plugins root",
        HOOK,
        "        candidates.append(override)",
        '        candidates.append(os.path.join(override, "plugins"))',
        TARGETS,
    ),
    (
        "CLAUDE_CONFIG_DIR is taken as the plugins root itself",
        HOOK,
        '        candidates.append(os.path.join(config_dir, "plugins"))',
        "        candidates.append(config_dir)",
        TARGETS,
    ),
    (
        "CLAUDE_CONFIG_DIR is ignored",
        HOOK,
        "    if config_dir:",
        "    if False:",
        TARGETS,
    ),
    (
        "the default root is ~/.claude rather than ~/.claude/plugins",
        HOOK,
        '    candidates.append(os.path.join("~", ".claude", "plugins"))',
        '    candidates.append(os.path.join("~", ".claude"))',
        TARGETS,
    ),
    (
        "the plugins roots are not resolved through symlinks",
        HOOK,
        "    return [os.path.realpath(os.path.expanduser(c)) for c in candidates]",
        "    return [os.path.abspath(os.path.expanduser(c)) for c in candidates]",
        TARGETS,
    ),
    (
        "a ~ in a plugins root is not expanded",
        HOOK,
        "    return [os.path.realpath(os.path.expanduser(c)) for c in candidates]",
        "    return [os.path.realpath(c) for c in candidates]",
        TARGETS,
    ),
    # ---- containment -----------------------------------------------------
    (
        "containment by string prefix: cache-old/ counts as cache/",
        HOOK,
        "    return p[: len(r)] == r",
        "    return os.path.normcase(path).startswith(os.path.normcase(root))",
        TARGETS,
    ),
    (
        "containment answers yes for everything",
        HOOK,
        "    return p[: len(r)] == r",
        "    return True",
        TARGETS,
    ),
    (
        "case is never folded, so ~/.claude/PLUGINS/CACHE slips past on macOS and Windows",
        HOOK,
        '    if sys.platform == "darwin" or sys.platform.startswith("win"):',
        "    if False:",
        TARGETS,
    ),
    (
        "case is folded on every platform, Linux included",
        HOOK,
        '    if sys.platform == "darwin" or sys.platform.startswith("win"):',
        "    if True:",
        TARGETS,
    ),
    (
        "a subtree is the whole plugins root",
        HOOK,
        "            subtree = os.path.join(root, sub)",
        "            subtree = root",
        TARGETS,
    ),
    (
        "the subtree rule never asks",
        HOOK,
        "            if _is_inside(target, subtree):",
        "            if False:",
        TARGETS,
    ),
    # ---- the target ------------------------------------------------------
    (
        "an empty file_path is read as the cwd",
        HOOK,
        "        if not isinstance(file_path, str) or not file_path:",
        "        if not isinstance(file_path, str):",
        TARGETS,
    ),
    (
        "with no payload cwd, a relative path resolves against the filesystem root",
        HOOK,
        "            cwd = os.getcwd()",
        '            cwd = "/"',
        TARGETS,
    ),
    (
        "a non-string cwd is used as given",
        HOOK,
        "        if not isinstance(cwd, str) or not cwd:",
        "        if not cwd:",
        TARGETS,
    ),
    (
        "the target is not resolved through symlinks or ..",
        HOOK,
        "        target = os.path.realpath(os.path.join(cwd, os.path.expanduser(file_path)))",
        "        target = os.path.abspath(os.path.join(cwd, os.path.expanduser(file_path)))",
        TARGETS,
    ),
    (
        "a ~ in the target is not expanded",
        HOOK,
        "        target = os.path.realpath(os.path.join(cwd, os.path.expanduser(file_path)))",
        "        target = os.path.realpath(os.path.join(cwd, file_path))",
        TARGETS,
    ),
    (
        "a relative target ignores the payload cwd",
        HOOK,
        "        target = os.path.realpath(os.path.join(cwd, os.path.expanduser(file_path)))",
        "        target = os.path.realpath(os.path.expanduser(file_path))",
        TARGETS,
    ),
    (
        "only a parse error fails open; a missing key or wrong type crashes",
        HOOK,
        "    except Exception:  # noqa: BLE001 -- fail open: a guard does not break normal work",
        "    except ValueError:",
        TARGETS,
    ),
    # ---- the decision ----------------------------------------------------
    (
        "the hook asks about every path that is not installed",
        HOOK,
        "    if copy is None:",
        "    if copy is not None:",
        TARGETS,
    ),
    (
        "the hook blocks instead of asking",
        HOOK,
        '        "permissionDecision": "ask",',
        '        "permissionDecision": "deny",',
        TARGETS,
    ),
    (
        "the ask is labelled for the wrong hook event",
        HOOK,
        '        "hookEventName": "PreToolUse",',
        '        "hookEventName": "PostToolUse",',
        TARGETS,
    ),
    (
        "the reason stops saying the edit is lost",
        HOOK,
        '        "this edit would be lost without a word. A repo\'s own rules go in "',
        '        "this edit would vanish. A repo\'s own rules go in "',
        TARGETS,
    ),
    (
        "the reason stops naming where a repo's rules go",
        HOOK,
        '        "`cla.io/overlays/<skill>.md` or `cla.io/project-facts.md`; a fix to the "',
        '        "`cla.io/`; a fix to the "',
        TARGETS,
    ),
    (
        "the reason stops naming the target",
        HOOK,
        "        f\"'{target}' is inside an installed plugin copy ('{copy}'). Claude Code \"",
        "        f\"This file is inside an installed plugin copy ('{copy}'). Claude Code \"",
        TARGETS,
    ),
    # ---- the Edit/Write dispatcher ---------------------------------------
    (
        "the dispatcher no longer runs the hook",
        DISPATCHER,
        '    "ask-plugin-cache-edit.py",\n    "ask-secret-in-checkpoint.py",',
        '    "ask-secret-in-checkpoint.py",',
        DISPATCH_TARGETS,
    ),
    (
        "the hook is advisory, so a spent budget drops its ask",
        DISPATCHER,
        '_ADVISORY_HOOKS = frozenset({\n    "warn-comment-dates.py",\n})',
        '_ADVISORY_HOOKS = frozenset({\n    "warn-comment-dates.py",\n    "ask-plugin-cache-edit.py",\n})',
        DISPATCH_TARGETS,
    ),
    (
        "a hook's ask is dropped by the dispatcher",
        DISPATCHER,
        "        if ask:\n            asks.append(ask)",
        "        if ask:\n            pass",
        DISPATCH_TARGETS,
    ),
    (
        "the dispatcher re-emits every decision as an ask, allow included",
        DISPATCHER,
        '    if not isinstance(nested, dict) or nested.get("permissionDecision") != "ask":',
        "    if not isinstance(nested, dict):",
        DISPATCH_TARGETS,
    ),
    (
        "an ask with no reason gets an empty one",
        DISPATCHER,
        '    return str(nested.get("permissionDecisionReason") or "A guard requested confirmation.")',
        '    return str(nested.get("permissionDecisionReason") or "")',
        DISPATCH_TARGETS,
    ),
    (
        "a hook's stdout that is a JSON list crashes the extraction",
        DISPATCHER,
        "        return None\n    nested = payload.get(\"hookSpecificOutput\")\n    if not isinstance(nested, dict) or nested.get(\"permissionDecision\") != \"ask\":",
        "        pass\n    nested = payload.get(\"hookSpecificOutput\")\n    if not isinstance(nested, dict) or nested.get(\"permissionDecision\") != \"ask\":",
        DISPATCH_TARGETS,
    ),
    (
        "only the enforcing-guard escalation reaches the prompt, as before",
        DISPATCHER,
        "    if asks:\n        print(_ask_json(compose_output(asks), merged))",
        "    if errored_enforcing:\n        print(_ask_json(compose_output(asks), merged))",
        DISPATCH_TARGETS,
    ),
    (
        "only the first ask reaches the prompt",
        DISPATCHER,
        "        print(_ask_json(compose_output(asks), merged))",
        "        print(_ask_json(asks[0], merged))",
        DISPATCH_TARGETS,
    ),
    (
        "the enforcing-guard escalation no longer joins the asks",
        DISPATCHER,
        "        asks.append(\n            \"an ENFORCING guard could not run on this call — \"",
        "        [].append(\n            \"an ENFORCING guard could not run on this call — \"",
        DISPATCH_TARGETS,
    ),
    (
        "the hook's budget entry claims a subprocess it does not run",
        LIB,
        '    "ask-plugin-cache-edit.py": 0.0,',
        '    "ask-plugin-cache-edit.py": 3.0,',
        DISPATCH_TARGETS,
    ),
]
