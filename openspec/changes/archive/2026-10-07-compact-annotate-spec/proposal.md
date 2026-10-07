## Why

`openspec validate --specs --strict` fails on every long requirement in the live spec. `annotate`
had six of its seven requirements over OpenSpec's 500-character limit, mixing SHALL statements with
the measurements and reasoning behind them. #293 step 2, second capability, following the pattern
set by `compact-run-ledgers-spec`.

## What Changes

- Split the seven requirements into fifteen, one behaviour each, every requirement text ≤ 500
  characters. SHALL sentences are kept verbatim wherever they fit. Each of the 15 scenarios moves
  byte-for-byte under the requirement it proves.
- Add one scenario, for the layer's own appended presentation, which no scenario proved before; two
  existing tests in `test_render_html.py` now carry its marker.
- Move the reasoning and measurements to a new `openspec/specs/annotate/rationale.md`, under the
  same requirement headings, edited only so each section reads on its own. The Purpose paragraph
  points to it.
- The seven original headings are kept; eight new headings name the split-out behaviours.

No behaviour changes, so this change carries no spec delta (`skip_specs`).

## Impact

- `openspec/specs/annotate/` — `spec.md` compacted, `rationale.md` added.
- `plugin-tests/tests/skills/annotate/test_render_html.py` — two scenario markers.
- No shipped file names a requirement heading.
- Known gap, not changed here: `render_doc.py --out` and `render_html.py --out` do not refuse a path
  naming the source document, so "never written to" is not enforced against a caller who passes one.
