#!/usr/bin/env python3
"""PreToolUse hook — warn when an Edit/Write on a component or i18n file removes
a literal string that test-app.mjs's Playwright smoke test depends on.

test-app.mjs drives a UI flow using literal English UI text (e.g.
`page.waitForSelector('text=Some Screen Label')`). A copy change or a removed
UI element can silently break the smoke script — it only fails much later when
someone runs `node test-app.mjs`, not at edit time. This has happened before (a
named UI element was removed without updating test-app.mjs, and the break went
unnoticed for a whole session).

Non-blocking: prints an `additionalContext` warning when a locator string
looks like it's disappearing, and always exits 0. Scoped to component .tsx
files and the i18n JSON dictionaries.
"""
import sys
import json
import re
import os


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool_input = payload.get('tool_input', {})
    path = tool_input.get('file_path', '')
    if not (
        ('src/components/' in path and path.endswith('.tsx'))
        or ('src/i18n/' in path and path.endswith('.json'))
    ):
        return 0

    repo_root = os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd())
    smoke_test_path = os.path.join(repo_root, 'test-app.mjs')
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
            "Warning: this edit removes text that test-app.mjs's Playwright smoke "
            "test locates by literal string. Update test-app.mjs in the same "
            "change if this text/element is really going away. Affected locator(s): "
            + ' | '.join(disappearing[:3])
        )
        print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'additionalContext': msg}}))

    return 0


if __name__ == '__main__':
    sys.exit(main())
