# Proposal

## Why

Several shipped rules govern how a skill dispatches a subagent and what the subagent must send
back, and nothing checks them (check 10 of `cla.io/audits/rule-enforcement-2026-11-18.md`, items
M10 and M11):

- "Pass `model:` on EVERY dispatch": a dispatch without one runs on an unplanned model, a silent cost.
- "Write the diff to a file; pass its path, never the text."
- A review brief's protected-areas slot is never `(none recorded)`.
- A `doc-sweeper` reply always ends with a `Scanned:` footer line.
- A fix reply whose brief asks for `Fact corrections:` never omits the field.

## What Changes

- A new warn hook, `warn-agent-dispatch`, runs before every Agent call. It warns when the call
  names no model, when the prompt holds a line starting `diff --git `, and when the prompt fills
  the protected-areas slot with `(none recorded)`.
- A new warn hook, `warn-agent-reply-format`, runs after every completed Agent call. It warns when
  a `doc-sweeper` reply has no `Scanned:` line, and when the brief named `Fact corrections:` and
  the reply has no such field. It checks presence only, never whether the content is true.
- Both only warn: the owner's own ad-hoc dispatch on the session model is legitimate. Both are
  silent on bad input and run no subprocess.
- Copilot CLI's adapter handles only shell and file tools, so these two hooks do not run there.

## Capabilities

### Modified Capabilities

- `guard-warnings`: five requirements, one per warning.

## Impact

Two hook files and their `hooks.json` wiring; tests and two mutation batches under
`plugin-tests/`; the guard tables in the plugin README and the developer guide; the rule ledger's
origin field for the five rules; the changelog. No new dependency.
