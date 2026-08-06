#!/usr/bin/env python3
"""PreToolUse hook — warn when an Edit/Write on a config-defined "component" or
"i18n" file removes a literal string a config-defined smoke test locates by.

Generic by design (portable synced core, per CLAUDE.md's fact/procedure
split): this file holds no consuming repo's own paths or naming. Those are
per-repo FACTS, read from the overlay file `smoke-test-drift.local.md` in
this same directory — a `*.local.md` leaf name, the repo-neutral overlay
marker `update-cla` already recognizes and never syncs/overwrites (see
`update-cla/scripts/discover.py`'s `OVERLAY_LOCAL_SUFFIX`). No overlay file
on disk means this repo hasn't configured the check: no-op, exit 0.

Why this exists: a UI-driving smoke test (e.g. Playwright) that locates
elements by literal on-screen text breaks silently on a copy change or a
removed element — it only fails much later when someone runs the smoke test,
not at edit time. Observed once in a consuming repo: a UI element was removed
without updating its smoke test, and the break went unnoticed for a whole
session.

Overlay file format — flat `key: value` frontmatter between `---` lines,
followed by free-form prose (only the frontmatter is read):

    ---
    component_path_substring: src/components/
    component_ext: .tsx
    i18n_path_substring: src/i18n/
    i18n_ext: .json
    smoke_test_relpath: test-app.mjs
    ---

    Free-form notes for a human reader go here; the hook ignores this part.

All five keys are required; a missing key or an unparseable file is treated
like a missing file (no-op) rather than a guess — a guard should never rely
on partially-known facts about a repo it wasn't told about.

Non-blocking: prints an `additionalContext` warning when a locator string
looks like it's disappearing, and always exits 0.
"""
import sys
import json
import re
import os

_OVERLAY_LEAF = "smoke-test-drift.local.md"
_REQUIRED_KEYS = (
    "component_path_substring",
    "component_ext",
    "i18n_path_substring",
    "i18n_ext",
    "smoke_test_relpath",
)


def _load_config(hooks_dir: str) -> dict | None:
    """Parse the flat `key: value` frontmatter of the overlay file, or None if
    the file is absent, unreadable, malformed, or missing a required key."""
    path = os.path.join(hooks_dir, _OVERLAY_LEAF)
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return None

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    config: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        config[key.strip()] = value.strip()
    else:
        return None  # no closing "---" found

    if not all(k in config and config[k] for k in _REQUIRED_KEYS):
        return None
    return config


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    hooks_dir = os.path.dirname(os.path.abspath(__file__))
    config = _load_config(hooks_dir)
    if config is None:
        return 0

    tool_input = payload.get('tool_input', {})
    path = tool_input.get('file_path', '')
    if not (
        (config["component_path_substring"] in path and path.endswith(config["component_ext"]))
        or (config["i18n_path_substring"] in path and path.endswith(config["i18n_ext"]))
    ):
        return 0

    repo_root = os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd())
    smoke_test_path = os.path.join(repo_root, config["smoke_test_relpath"])
    try:
        with open(smoke_test_path, 'r', encoding='utf-8') as f:
            smoke_test = f.read()
    except OSError:
        return 0

    # Only plain literal `text=...` locators (not `text=/regex/`) are checkable.
    locators = re.findall(r"text=([^'\"]+)", smoke_test)
    locators = [loc for loc in locators if not loc.startswith('/')]

    # Edit supplies old_string/new_string; Write supplies content (compare against
    # the file's current on-disk content, since Write overwrites the whole file).
    if 'old_string' in tool_input:
        before = tool_input.get('old_string', '')
        after = tool_input.get('new_string', '')
    else:
        after = tool_input.get('content', '')
        try:
            with open(path, 'r', encoding='utf-8') as f:
                before = f.read()
        except OSError:
            before = ''

    disappearing = [loc for loc in locators if loc in before and loc not in after]

    if disappearing:
        msg = (
            f"Warning: this edit removes text that {config['smoke_test_relpath']}'s "
            "smoke test locates by literal string. Update it in the same change if "
            "this text/element is really going away. Affected locator(s): "
            + ' | '.join(disappearing[:3])
        )
        print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'additionalContext': msg}}))

    return 0


if __name__ == '__main__':
    sys.exit(main())
