# Tasks

## 1. Guard hooks

- [x] 1.1 Add `warn-agent-dispatch`: warns on an Agent call with no model, a prompt line starting `diff --git `, and `(none recorded)` in the protected-areas slot; silent on a named model, a diff path, a filled slot and bad input. Tests carry the three `guard-warnings` requirement lines.
- [x] 1.2 Add `warn-agent-reply-format`: warns when a completed `doc-sweeper` reply has no `Scanned:` line, and when a brief naming `Fact corrections:` gets a reply without it; silent on a background launch, a reply holding the line and bad input. Tests carry the two requirement lines.
- [x] 1.3 Wire both on the `Agent` matcher in `hooks.json` with the shared probe prologue; a wiring test runs each through its real command. A multi-megabyte prompt or reply finishes within seconds.
- [x] 1.4 Write a mutation batch for each hook under `plugin-tests/mutants/hooks/`, each mutant checked by hand.

## 2. Docs

- [x] 2.1 docs and spec map: `.claude/plugins/cla/README.md`, `DEVELOPER-GUIDE.md`, `CHANGELOG.md` and `docs/rule-ledger.md` updated; `openspec/spec-map.md` none affected: it already links guard-warnings.
