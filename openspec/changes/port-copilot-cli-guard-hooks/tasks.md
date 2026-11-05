# Tasks

## 1. Copilot hook integration

- [x] 1.1 Verify the Copilot plugin-hook root and platform launch contract, then add Copilot-specific pre-tool and post-tool wiring for every applicable CLA guard; wiring tests prove scripts resolve and Claude hook configuration is unchanged.
- [x] 1.2 Add an adapter for Copilot hook payloads and native decision output; tests marked `requirement: guard-hooks / Copilot CLI enforces session guards` cover allow, deny with reason, interactive ask, and non-blocking warning outcomes.

## 2. Failure handling and validation

- [x] 2.1 Make malformed input, missing guard code, and dispatcher failures deny the affected call; tests marked `requirement: guard-hooks / Copilot hook failures have an explicit policy` prove failure cannot become approval.
- [x] 2.2 Test the configured timeout budget and autopilot ask denial; document Copilot's fail-open timeout behavior and record the live timeout probe result; run live allow, block, confirmation, and warning probes without editing project files.
- [x] 2.3 Test that missing Python and a missing interpreter probe make the launcher fail closed.

## 3. Documentation

- [x] 3.1 Update README.md, DEVELOPER-GUIDE.md, `.claude/plugins/cla/README.md`, and the OpenSpec distribution requirement with Copilot CLI coverage, timeout and autopilot limitations, and unchanged Claude and Git pre-push behavior.

## 4. Helper-agent model policy

- [x] 4.1 Generate Copilot profiles without account-specific model IDs and preserve session-model inheritance.
- [x] 4.2 Replace network-based model-table checks with local source-alias, profile-parity, and inheritance checks.

## 5. Skill compatibility

- [x] 5.1 Mark workflows requiring Claude-only delegation, skill chaining, model routing, or permission settings unsupported.
- [x] 5.2 Document conversational question handling and plugin-root reference resolution for Copilot CLI.
- [x] 5.3 Add tests for unsupported-workflow markers and Copilot-specific guidance.
- [x] 5.4 Invoke a representative interactive skill in Copilot CLI.

## 6. Instructions and user guidance

- [x] 6.1 Add a Copilot CLI response-style counterpart without changing the Claude output style.
- [x] 6.2 Document marketplace registration, install, update, and troubleshooting.
- [x] 6.3 Verify that Copilot CLI discovers the file at `.github/copilot-instructions.md`.
