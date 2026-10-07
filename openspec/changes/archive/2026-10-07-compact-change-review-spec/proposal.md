## Why

`openspec validate --specs --strict` fails on every long requirement in the live spec. `change-review`
had five requirements over OpenSpec's 500-character limit, the largest at 6,299. #293 step 2, third
capability, following `compact-run-ledgers-spec` and `compact-annotate-spec`.

## What Changes

- Split the five long requirements into twenty-six, one behaviour each, every requirement text ≤ 500
  characters; the twelve short requirements are untouched. SHALL sentences are kept verbatim wherever
  they fit; where one had to be compressed, the original sits in `rationale.md`.
- Each of the 48 scenarios moves byte-for-byte under the requirement it proves.
- Add one scenario, for precedent strictness, the only claim shape no scenario proved. Its proof is a
  `manual:` line in `tasks.md`.
- Move the reasoning, measurements and the four claim shapes' original text to a new
  `openspec/specs/change-review/rationale.md`, under the same requirement headings.
- "cla-plugin review workflow" becomes "CLA review workflow": the capability the old name pointed at
  no longer exists.

No behaviour changes, so this change carries no spec delta (`skip_specs`).

## Impact

- `openspec/specs/change-review/` — `spec.md` compacted, `rationale.md` added.
- The five original headings are kept, so every `scenario: change-review / <heading>` marker still
  resolves.
