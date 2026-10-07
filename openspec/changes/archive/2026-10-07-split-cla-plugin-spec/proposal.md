## Why

The live spec was one catch-all capability, `cla-plugin`: 77 requirements and 284 scenarios in a
single file. Every lookup reads all of it, and OpenSpec's overview-first read
(`openspec show <id> --type spec --no-scenarios`) only helps when there are several capabilities.
This is step 1 of #293.

## What Changes

- Split `openspec/specs/cla-plugin/spec.md` into six capabilities named for lasting behaviour:
  `plugin-architecture`, `change-authoring`, `change-review`, `orchestration`, `run-ledgers`,
  `annotate`. Each requirement block moves verbatim; order within a capability is preserved.
  "The live specification set is validated where it is written" goes to `orchestration`, where
  its archive and merge write sites live.
- Each new spec gets its own Purpose paragraph.
- Scenario markers in `plugin-tests` (`scenario: cla-plugin / <heading>`) and the four shipped
  files naming the old capability now name the new one.

No requirement or scenario text changes, so this change carries no spec delta (`skip_specs`).
Requirement prose that says "cla-plugin" is left as written, since this change edits no text.
`openspec validate --specs --strict` fails before and after this change on the same over-long
requirements; compacting them is the next change in #293.

## Impact

- `openspec/specs/` — one directory becomes six.
- `plugin-tests/` — 16 scenario markers, five docstring pointers in four files, one test that read
  the old path, and a new guard that every scenario marker names a live scenario.
- Shipped prose: `multi-spec/references/authoring-brief.md`, `review-change/references/checklist.md`,
  `_shared/references/runtime-rules.md`, `cla-init/SKILL.md`.
