## Why

`openspec validate --specs --strict` fails on every long requirement in the live spec. `change-review`
had five requirements over OpenSpec's 500-character limit, the largest at 6,299. #293 step 2, third
capability, following `compact-run-ledgers-spec` and `compact-annotate-spec`.

## What Changes

- Split the five long requirements into twenty-eight, one behaviour each, every requirement text ≤ 500
  characters; the twelve short requirements are untouched. SHALL sentences are kept verbatim wherever
  they fit; where one had to be compressed, the original is quoted in `rationale.md`.
- Each of the 48 scenarios moves byte-for-byte under the requirement it proves.
- Add four scenarios, one per split-out requirement that no existing scenario proved: producible-state
  resolution, precedent strictness and its floor, and the guarantee-class floor. Each restates text the
  requirement already carried and adds no behaviour; each is proved by a `manual:` line in `tasks.md`.
  They go straight into the live spec because this change carries no delta (`skip_specs`).
- Move the reasoning, measurements and the four claim shapes' original text to a new
  `openspec/specs/change-review/rationale.md`, under the same requirement headings.
- "cla-plugin review workflow" becomes "CLA review workflow": the capability the old name pointed at
  no longer exists.

## Impact

- `openspec/specs/change-review/` — `spec.md` compacted, `rationale.md` added.
- Every `scenario: change-review / <heading>` marker names a scenario under one of the twelve untouched
  requirements, so all still resolve.
- Known conflict, not changed here: the severity tie-break (implementation-level evidence wins; higher
  severity only as fallback) disagrees with `review-change/references/checklist.md` ("keep the higher
  severity, full stop") and `spec-to-pr/SKILL.md` SEV-MAX. It predates this change.
