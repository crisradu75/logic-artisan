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

All five keys are required. A missing key or an unparseable file still no-ops
rather than guessing — a guard should never rely on partially-known facts —
but unlike an ABSENT overlay it warns on stderr first: the repo stated intent,
so a typo that silently disables the check forever is the worse outcome.

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


def _warn(msg: str) -> None:
    """Surface a degraded condition. Goes to the debug log (this hook always
    exits 0), which is where a misconfiguration is looked for — the point is
    that it is discoverable at all, rather than the check vanishing in silence."""
    print(f"[warn-smoke-test-drift] warn: {msg}", file=sys.stderr)


def _load_config(hooks_dir: str) -> dict | None:
    """Parse the flat `key: value` frontmatter of the overlay file, or None.

    Silence is reserved for ONE case: the file does not exist, meaning this repo
    never opted into the check. Every other None — unreadable, malformed, a
    missing or blank required key — means the repo DID state intent and the
    check still isn't running, so it warns on stderr first. Without that split,
    a typo in the overlay was indistinguishable from not having one, and the
    check silently never ran again.
    """
    path = os.path.join(hooks_dir, _OVERLAY_LEAF)
    if not os.path.isfile(path):
        return None  # not configured; the only silent no-op
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        _warn(f"{_OVERLAY_LEAF} exists but could not be read ({e})")
        return None

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        _warn(f"{_OVERLAY_LEAF} does not start with a `---` frontmatter line")
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
        _warn(f"{_OVERLAY_LEAF} frontmatter has no closing `---` line")
        return None

    missing = [k for k in _REQUIRED_KEYS if not config.get(k)]
    if missing:
        _warn(f"{_OVERLAY_LEAF} is missing or has a blank value for: {', '.join(missing)}")
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
