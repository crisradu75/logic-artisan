# Proposal

## Why

Part of #302 (make CLA installable from GitHub Copilot CLI). This is item 5 of the draft split in
`cla.io/decisions/copilot-cli-port-2026-10-16.md`: port the five helper agents. Copilot CLI only;
skills, hooks, the output style and instructions are other items.

## What Changes

- Add `com.github.copilot/agents/<name>.agent.md` to the plugin, one per helper agent. GitHub's
  plugin reference says an Agent Plugins 1.0 plugin keeps Copilot custom agents in that directory and
  that the location is fixed, so Copilot cannot read the Claude files in `agents/`, and the copies
  are generated, not written.
- A dev script, `plugin-tests/scripts/sync_copilot_agents.py`, writes each copy: the body, `name` and
  `description` are copied unchanged; `tools: ["Read","Grep","Glob"]` becomes `["read","search"]`;
  `model: haiku|sonnet|opus` becomes the Copilot model ID the CLI reference lists; `color` is dropped.
  It refuses a tool, model or field it has no documented mapping for.
- A consistency test fails when a Copilot copy's instructions, description, tools or model differ from
  its Claude agent, when a copy is missing or orphaned, or when a copy is not read-only.
- No manifest entry: the docs list no fields for the root manifest's `com.github.copilot` extension,
  and the directory alone is what Copilot reads. The root manifest's description now says agents are
  offered.
- `check_shipped_tree.py` allows `com.github.copilot/agents/<name>.agent.md` (a sixteenth pattern,
  cap raised), or `/release` would refuse the new files.
- The decisions file records the owner's 2026-10-16 decisions to wait for a live test on hooks and
  skill text, and the README and DEVELOPER-GUIDE say the guard hooks do not run in Copilot.
- The README, plugin README and DEVELOPER-GUIDE say the agents are offered to Copilot and are
  **untested in a live Copilot CLI** (not installed on the owner's machine).

## Capabilities

### Modified Capabilities

- `plugin-distribution`: one requirement added (Helper agents in GitHub Copilot CLI).

## Impact

`.claude/plugins/cla/com.github.copilot/agents/` (5 files), `plugin.json` (description),
`check_shipped_tree.py`, `plugin-tests/`, README, plugin README, DEVELOPER-GUIDE. The Claude install
is unchanged: `claude plugin validate` passes before and after and a `claude -p` run lists the same
five `cla:` agents. The copies reach Copilot only from the next release, because the catalog pins
`cla--v2.1.0`, cut before the root manifest existed.
