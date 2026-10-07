## Why

`openspec validate --specs --strict` fails on every long requirement in the live spec: OpenSpec wants
one behaviour per requirement in 500 characters or fewer. `run-ledgers` had three requirements, all
over the limit, mixing SHALL statements with the measurements and reasoning behind them. This is
#293 step 2, first capability; the other four follow one PR each.

## What Changes

- Split the three requirements into twelve, one behaviour each, every requirement text ≤ 500
  characters. Each of the 13 scenarios moves byte-for-byte under the requirement it proves.
- Move the reasoning and measurements to a new `openspec/specs/run-ledgers/rationale.md`, under the
  same requirement headings. The Purpose paragraph points to it.
- Reword one requirement heading to match its narrower scope; nothing references it.

No behaviour changes, so this change carries no spec delta (`skip_specs`), as in step 1.

## Impact

- `openspec/specs/run-ledgers/` — `spec.md` compacted, `rationale.md` added.
- No test marker names a `run-ledgers` scenario, and no shipped file names a requirement heading.
