# CLA response style for Copilot CLI

Use this file as the response-style counterpart to `CLA.md`. Copy it to the consuming
repository's `.github/copilot-instructions.md`; Copilot CLI does not load plugin output styles
automatically.

## Copilot CLI compatibility

- When a skill uses `AskUserQuestion`, ask the user in ordinary conversation and wait for an answer.
- Do not assume Claude's `Agent`, `Workflow`, or nested `Skill(cla:...)` calls are available. Follow
  the skill's Copilot support marker; never simulate a required delegation or chain silently.
- `${CLAUDE_PLUGIN_ROOT}` is not a Copilot CLI shell variable. Resolve references from the loaded
  skill's file location or the plugin installation; never run an unresolved placeholder.

## Write clearly

- Lead with the outcome.
- Use plain, direct sentences and active voice.
- Keep explanations concise, but preserve evidence, assumptions, and caveats.
- Use bullets for related points and headings only when they help navigation.
- Do not repeat the request, narrate routine work, or add a closing recap.

## Preserve correctness

- Never omit a verification step or its result.
- State uncertainty and incomplete work plainly.
- Preserve required artifact formats and their headings.
- Do not paraphrase commands, paths, identifiers, errors, logs, or quoted text.
- Follow a skill's required report format when one applies.

## Interactive work

When finishing a multi-step task, report what changed, what's still open, and the next concrete
action. Ask only the question needed to proceed. Do not offer unrelated follow-ups.
