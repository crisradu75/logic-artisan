## Why

`openspec validate --specs --strict` fails on every long requirement in the live spec. `annotate`
had six of its seven requirements over OpenSpec's 500-character limit, mixing SHALL statements with
the measurements and reasoning behind them. #293 step 2, second capability, following the pattern
set by `compact-run-ledgers-spec`.

## What Changes

- Split the seven requirements into fourteen, one behaviour each, every requirement text ≤ 500
  characters. Each of the 15 scenarios moves byte-for-byte under the requirement it proves.
- Move the reasoning and measurements to a new `openspec/specs/annotate/rationale.md`, under the
  same requirement headings, edited only so each section reads on its own. The Purpose paragraph
  points to it.
- The seven original headings are kept; seven new headings name the split-out behaviours.

No behaviour changes, so this change carries no spec delta (`skip_specs`).

## Impact

- `openspec/specs/annotate/` — `spec.md` compacted, `rationale.md` added.
- No test marker names an `annotate` scenario, and no shipped file names a requirement heading.
