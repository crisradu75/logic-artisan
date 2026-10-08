## Why

Run notes are local (`run-notes-stay-local`). A `/cla:multi-pr` resume without them could not read
the obligations an earlier change recorded for a later one, yet still ran the later change, which
`change-chains` forbids: a later change is not ready while an obligation is ignored.

## What Changes

- A `multi-pr` resume with no run notes stops before any not-yet-shipped change that has an earlier
  change in the chain, says why, and names the ways on: resume on the machine holding the notes, or
  run the remaining changes one at a time with `/cla:spec-to-pr`.

## Impact

- `change-chains`: the obligations requirement gains the stop and a scenario for it.
