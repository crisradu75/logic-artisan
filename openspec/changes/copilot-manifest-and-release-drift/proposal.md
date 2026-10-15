# Proposal

## Why

Part of #302 (make CLA installable from GitHub Copilot CLI). The owner's decisions
(`cla.io/decisions/copilot-cli-port-2026-10-16.md`) are Copilot CLI only, and a new Agent Plugins 1.0
root `plugin.json` beside the Claude manifest. This change is items 2 and 3 of that draft split: the
catalog and manifest, and the drift check that keeps them in step. Skills, agents, hooks and
output-style ports are out of scope.

## What Changes

- Add `.github/plugin/marketplace.json`, a Copilot catalog whose `cla` entry is a `github` source
  (repo, plugin path, `ref` = the current release tag).
- Add the Agent Plugins 1.0 `plugin.json` at the plugin root, beside `.claude-plugin/plugin.json`.
  Per GitHub's docs it takes precedence for Copilot and offers only skills and MCP servers from its
  fixed locations; Claude Code does not read it (shown by a run, see the tasks).
- `/release` (and CLAUDE.md's release section) edit five files in one commit instead of three, and
  its shipped-tree check allows the new root manifest, which it would otherwise refuse.
- The existing version-agreement test checks the Claude manifest, the Copilot manifest, both catalogs'
  refs and the CLAUDE.md release line together. New structure tests pin the two new files.
- The README states the Copilot install lines, that it is Copilot CLI only, and that it is
  **untested in a live Copilot CLI** (not installed on the owner's machine).

## Capabilities

### Modified Capabilities

- `plugin-distribution`: one requirement added (Installing from GitHub Copilot CLI); two modified
  (Publishing a release names the new files; What a release contains says manifests).

## Impact

`.claude/plugins/cla/plugin.json`, `.github/plugin/marketplace.json`, `check_shipped_tree.py` (a
fifteenth allowlist pattern, cap raised), the release skill, CLAUDE.md, README, DEVELOPER-GUIDE and
the tests under `plugin-tests/`. The Claude install is unchanged. `check_no_project_tokens.py` does
not scan any manifest (both are outside its scan roots), so the new one is covered by the shipped-tree
allowlist and the structure tests only.
