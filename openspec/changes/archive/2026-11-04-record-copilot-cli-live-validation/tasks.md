# Tasks

## 1. Correct the Copilot validation contract

- [x] 1.1 Replace the obsolete “install is untested” assertions with regression coverage for the validated install, skill and agent invocations, Copilot CLI-only scope, Claude-only hooks, unported Claude-specific skill tools, and the agent model fallback; run the focused consistency tests.
- [x] 1.2 Update Copilot-facing docs and marketplace descriptions with the observed Copilot CLI 1.0.105 and release `cla--v2.2.3` results, preserving the unported-feature boundaries and disclosing the model fallback; verify the focused consistency tests pass.

## 2. Split the remaining implementation

- [x] 2.1 Create linked follow-up issues for Copilot hook porting, Claude-specific skill adaptation, Copilot instructions and install/update guidance, and valid helper-agent model mapping; verify each issue has acceptance criteria and link them from #302 before closing it.

## 3. Verify

- [x] 3.1 Run the affected plugin-distribution consistency tests and `openspec validate --specs --strict`; both commands must pass.
- [x] 3.2 docs and spec map: README.md, DEVELOPER-GUIDE.md, `.claude/plugins/cla/README.md`, and `.github/plugin/marketplace.json` updated with this change's verified Copilot status; `openspec/spec-map.md` unaffected because `plugin-distribution` is already linked under Install and release the plugin; `CLAUDE.md` unaffected because its release guidance does not describe the Copilot install.
