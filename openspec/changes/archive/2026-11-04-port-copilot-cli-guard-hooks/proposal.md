# Proposal

## Why

CLA's guard logic currently runs through Claude Code hook wiring only. Copilot CLI supports plugin-provided hooks, but a live check showed that installing CLA there does not enforce its guards: `cd .` ran despite the existing Claude dispatcher blocking the equivalent payload. Porting the hook integration would extend CLA's safety checks to Copilot CLI users without replacing the Claude integration.

## What Changes

- Add Copilot CLI-specific hook configuration and an adapter for Copilot's event payloads and decision output.
- Enforce the applicable existing CLA guards for Copilot CLI tool calls, preserving block, confirmation, and warning behavior where Copilot supports it.
- Add tests for allow, deny, confirmation, warning, malformed or unavailable hook execution, and documented timeout behavior; verify with a live Copilot CLI session.
- Update Copilot-facing documentation to state the supported coverage and limitations. Keep Claude Code wiring and the Git `pre-push` hook unchanged.
- Scope this change to Copilot CLI; Copilot cloud is not included.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `guard-hooks`: specify that applicable CLA guard behavior is available in Copilot CLI sessions as well as Claude Code sessions.

## Impact

Copilot-specific plugin hook configuration and adapter code under `.claude/plugins/cla/`, hook tests under `plugin-tests/`, and Copilot support documentation. No new dependency is expected. Git-level `pre-push` remains independent of either agent's session hooks. Track implementation under issue #469.
