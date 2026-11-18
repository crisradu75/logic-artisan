# Proposal

Budget: protected

## Why

`/cla:checkpoint` writes a briefing to `cla.io/checkpoints/` that gets committed, and its rule says
"Never copy a token, key, connection string, or the contents of a `.env`. Name the file, not its
value." Nothing enforces it (check 11 of
`cla.io/audits/rule-enforcement-2026-11-18.md`, principle 3). A secret written there lands in git
history. The same holds for the other committed briefings an agent fills from the session:
decisions, feedback findings and the lessons log.

## What Changes

- Add an enforcing guard hook, `ask-secret-in-checkpoint`, to the Edit/Write dispatcher. It reads
  a Write's content or an Edit's new text when the target lies under `cla.io/checkpoints/`,
  `cla.io/decisions/`, `cla.io/feedback/` or `cla.io/lessons-learned/`.
- It asks when the text holds a high-signal secret shape: a well-known API key format (AWS, GitHub,
  Anthropic, OpenAI, Slack, Google, Stripe live), a private-key header, a JWT, or a
  `scheme://user:password@host` URL whose password is not a placeholder.
- The ask names each kind and its line and leaves the value out; it points at the rule. It is
  silent for placeholders and ordinary prose, and on malformed input.
- The scan is linear in the size of the text.

## Capabilities

### Modified Capabilities

- `guard-hooks`: add a requirement that a secret written into a committed briefing asks first.

## Impact

The new hook file, the Edit/Write dispatcher list, the budget table in `_dispatch_lib.py`, tests
and a mutation batch under `plugin-tests/`, and the guard tables in the plugin README and the
developer guide. Copilot CLI picks the guard up through the same dispatcher. No new dependency.
