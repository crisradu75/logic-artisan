# Proposal

## Why

CLA's guard logic and helper agents use Claude Code-specific interfaces. Copilot CLI supports its
own plugin hooks and agents, but explicit profile models can be unavailable to an account, and
several skills depend on Claude-only delegation or skill chaining. Copilot CLI also does not apply
plugin output styles automatically. This change records the Copilot CLI behavior and its limits
without changing Claude Code.

## What Changes

- Add Copilot CLI-specific hook configuration and an adapter for Copilot's event payloads and decision output.
- Enforce the applicable existing CLA guards for Copilot CLI tool calls, preserving block, confirmation, and warning behavior where Copilot supports it.
- Add tests for allow, deny, confirmation, warning, malformed or unavailable hook execution, and documented timeout behavior; verify with a live Copilot CLI session.
- Have generated Copilot helper-agent profiles inherit the session model and validate that policy locally before release.
- Mark skill workflows that require Claude-only agent delegation, skill chaining, model routing, or permission settings as unsupported; map interactive questions and plugin-path references for Copilot CLI.
- Add a Copilot CLI response-style counterpart, document copying it to `.github/copilot-instructions.md`, and explain install, update, and troubleshooting.
- Keep Claude Code wiring, settings, and output style plus the Git `pre-push` hook unchanged.
- Scope this change to Copilot CLI; Copilot cloud is not included.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `copilot-cli`: specify Copilot helper-agent model inheritance and the Copilot CLI compatibility, instruction, and support boundaries.

## Impact

Copilot-specific hook configuration, generated agent profiles, skill support notes, a response-style file, and focused tests and documentation. No new dependency is expected. Git-level `pre-push` remains independent of either agent's session hooks. This change covers the ordered Copilot validation follow-ups in #469–#472.
