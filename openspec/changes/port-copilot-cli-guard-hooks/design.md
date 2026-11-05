# Design

## Context

See proposal.md for motivation and specs/guard-hooks/spec.md for required behavior. CLA currently has two Claude `PreToolUse` dispatchers, one `PostToolUse` rewrite warning, and a separate Git `pre-push` hook. Its Python guards accept Claude-shaped `tool_input` payloads; the dispatchers emit Claude's nested decision format. Copilot CLI supports hooks in Agent Plugins 1.0 under `com.github.copilot/hooks/hooks.json`, but uses its own decision output and documents fail-open hook timeouts.

## Goals / Non-Goals

**Goals:**
- Keep the Claude hook configuration and dispatcher contracts unchanged.
- Reuse existing guard checks where their inputs and behavior match; translate Copilot hook inputs/results at a separate boundary.
- Make Copilot CLI block, ask, and advisory-warning outcomes observable and testable.

**Non-Goals:**
- Copilot cloud, other Copilot clients, or changing the Git `pre-push` hook.
- Claiming timeout-safe enforcement beyond Copilot CLI's documented behavior.

## Decisions

### Keep Copilot wiring and translation separate

Add a Copilot-specific hook file under `com.github.copilot/hooks/` and a small adapter rather than editing Claude's `hooks.json` or its dispatchers. Keeping the surface-specific configuration separate prevents Copilot's required versioned envelope and native output format from changing Claude behavior.

Alternative: share and rewrite the existing dispatchers. Rejected because their exit codes and `hookSpecificOutput` JSON are Claude contracts; changing them risks silently weakening existing enforcement.

### Translate decisions at the adapter boundary

Use Copilot's `PreToolUse` event with the Claude-compatible tool names and payload shape where supported, then translate dispatcher results into Copilot-native `permissionDecision`, reason, and warning fields. Blocking results must become explicit denies; confirmation results become asks in interactive mode; warnings remain non-blocking context. Use `PostToolUse` for the existing after-write warning.

Alternative: rely only on nonzero exits. Rejected because it cannot preserve the distinction between deny, ask, and allow-with-warning or provide the guard's specific reason consistently.

### Treat missing checks as denial, with timeout as a documented exception

Validate required input and surface launcher, import, and dispatcher failures as denies rather than allowing a call that was never checked. Set a bounded Copilot timeout based on measured guard runtime and keep each guard's behavior covered by tests. Copilot CLI timeouts are documented to fail open, so no adapter can convert a killed timed-out hook into a deny; disclose that residual risk and test the timeout path.

The live timeout probe confirmed this behavior: Copilot killed the timed-out hook, then proceeded with the tool call. Launcher tests also confirm that missing Python or the interpreter probe exits with an explicit failure before dispatch.

Alternative: silently accept Copilot's timeout behavior. Rejected because it would overstate the protection offered by the guards.

### Resolve plugin paths from Copilot's supported hook environment

Use only a plugin-root mechanism supported by Copilot CLI hook commands, verified on the minimum supported CLI version and a locally mounted plugin. Keep shell launchers platform-specific where needed and invoke the existing stdlib-only Python guard code without adding a shipped dependency.

Alternative: use checkout-specific or installation-cache absolute paths. Rejected because plugin consumers install CLA at different paths and platforms.

### Inherit the Copilot session model

Generated Copilot agent profiles omit the `model` field. An account may not support an otherwise
valid model ID, and silent fallback to Auto is less predictable than honoring the user's session.
The local release check validates source aliases, generated-copy parity, and absence of explicit
Copilot model pins.

### Mark runtime-dependent workflows explicitly

Keep neutral skill instructions shared. Mark complete workflows unsupported when Claude Code agent
delegation, explicit model routing, permission settings, or nested skill invocation cannot be
guaranteed in Copilot CLI. The Copilot instruction counterpart maps user-question steps to ordinary
conversation and warns against running an unresolved `${CLAUDE_PLUGIN_ROOT}` placeholder.

### Install response style as repository instructions

Copilot CLI discovers `.github/copilot-instructions.md` for the current repository, not a plugin's
output-style directory. Ship a counterpart beside the Claude style and document manual copying;
do not change Claude Code's style loading.

## Risks / Trade-offs

- [Copilot changes hook payloads or output handling] -> Pin schema expectations in tests and run live allow/deny/ask/warning probes on the supported CLI.
- [Hook timeouts permit the normal permission flow to continue] -> Keep guards bounded, test and document the fail-open boundary; retain Git `pre-push` as an independent defense for pushes to protected branch names.
- [Autopilot cannot interactively resolve an ask] -> Verify it is denied rather than executed and document the difference from an interactive session.
- [Plugin hook path or sandbox access differs by platform] -> Test macOS, Linux and Windows launch configuration before claiming platform support.

## Migration Plan

Ship Copilot hook configuration alongside, not in place of, Claude wiring. Enable only the guards whose Copilot adapter and tests pass. Validate the installed plugin with harmless allowed and denied calls before updating support documentation. Rollback by removing the Copilot-specific hook configuration; Claude hooks remain operational.
