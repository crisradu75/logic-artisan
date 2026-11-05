# Proposal

## Why

The Copilot CLI integration is no longer wholly untested: on Copilot CLI 1.0.105, marketplace registration and browsing, installation of the pinned `cla--v2.2.3` release, a `/cla:` skill invocation, and both helper agents succeeded. Current docs and tests still describe the entire install as untested, while the agent profiles also warn that their declared model is unavailable and falls back to `auto`.

## What Changes

- Replace the blanket “untested” disclosure with the verified CLI results and the remaining support boundaries.
- Preserve the explicit Copilot CLI-only scope and the statement that guard hooks remain Claude-only.
- Add regression coverage for accurate Copilot validation disclosures.
- Split the remaining hook, skill-portability, Copilot-instructions/update-docs, and helper-agent model-mapping work into follow-up issues; close #302 after linking them.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `plugin-distribution`: replace the outdated requirement that Copilot installation is untested with a requirement to document verified Copilot CLI capabilities and remaining limitations accurately.

## Impact

README, DEVELOPER-GUIDE, plugin README, Copilot marketplace descriptions, the `plugin-distribution` spec and its tests, plus GitHub issues linked to #302. No Copilot hooks or Claude skill text are ported by this change.
