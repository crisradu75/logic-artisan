# Tasks

## 1. Copilot hook integration

- [x] 1.1 Verify the Copilot plugin-hook root and platform launch contract, then add Copilot-specific pre-tool and post-tool wiring for every applicable CLA guard; wiring tests prove scripts resolve and Claude hook configuration is unchanged.
- [x] 1.2 Add an adapter for Copilot hook payloads and native decision output; tests marked `requirement: guard-hooks / Copilot CLI enforces session guards` cover allow, deny with reason, interactive ask, and non-blocking warning outcomes.

## 2. Failure handling and validation

- [x] 2.1 Make malformed input, missing guard code, and dispatcher failures deny the affected call; tests marked `requirement: guard-hooks / Copilot hook failures have an explicit policy` prove failure cannot become approval.
- [x] 2.2 Test the configured timeout budget and autopilot ask denial; document Copilot's fail-open timeout behavior and record that the live timeout probe was inconclusive; run live allow, block, confirmation, and warning probes without editing project files.

## 3. Documentation

- [x] 3.1 docs and spec map: README.md, DEVELOPER-GUIDE.md, `.claude/plugins/cla/README.md`, or none affected: `openspec/spec-map.md` already links `guard-hooks` and `plugin-distribution`; document Copilot CLI coverage, timeout and autopilot limitations, and the unchanged Claude and Git pre-push behavior.
