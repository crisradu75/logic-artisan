# Proposal

## Why

About seven shipped rules say not to edit the installed plugin: the plugin README's "Never edit it:
it is a version-keyed cache", cla-setup's "never under the plugin tree", and "Legacy-location
overlays are never edited". An edit inside an installed copy is lost without a word on the next
plugin update or marketplace refresh, and a repo's own rules belong in its `cla.io/overlays/` or
`cla.io/project-facts.md`. Nothing enforces the rules today (check 4 of
`cla.io/audits/rule-enforcement-2026-11-18.md`).

## What Changes

- Add an enforcing guard hook, `ask-plugin-cache-edit`, to the Edit/Write dispatcher. It resolves
  the target through symlinks and `..` and asks when it lies in the `cache/` or `marketplaces/`
  subtree of a plugins root (`$CLAUDE_CODE_PLUGIN_CACHE_DIR`, `$CLAUDE_CONFIG_DIR/plugins`,
  `~/.claude/plugins`), or inside `$CLAUDE_PLUGIN_ROOT` when that root lies below a plugins root.
- It asks rather than blocks, so a person who means it can say yes, and it is silent on any error.
- A plugin run from a working tree with `--plugin-dir` matches neither rule, so the repo that
  develops it can edit it. The plugin's `data/` directory is not checked.
- The Edit/Write dispatcher learns to pass a hook's `ask` through, as the Bash dispatcher does.

## Capabilities

### Modified Capabilities

- `guard-hooks`: add a requirement that a write into an installed plugin copy asks first.

## Impact

The new hook file, the Edit/Write dispatcher, the budget table in `_dispatch_lib.py`, tests and a
mutation batch under `plugin-tests/`, and the guard tables in the plugin README and the developer
guide. Copilot CLI picks the guard up through the same dispatcher. No new dependency.
