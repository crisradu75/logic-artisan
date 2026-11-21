## Why

A plugin analysis found three contradictions or dangling pointers in the chain skills and
`right-model`, and the turn-liveness rule written out three times with incident anecdotes.

## What Changes

- `multi-lite` said a change that is not protected belongs on `spec-to-pr`; it now says a protected
  change does.
- `right-model` said `multi-pr` never dispatches an `Agent`; it now says `multi-pr` runs whole
  `spec-to-pr` runs and its own helper dispatches are not routed per the routing reference.
- `multi-spec` pointed at a "noted above" posture that did not exist; the clause and a run-ledger
  history are deleted.
- The turn-liveness rule moves once into `_shared/references/turn-liveness.md`; each of
  `multi-lite`, `multi-pr` and `multi-spec` keeps a short bullet carrying the three markers the
  consistency test pins, plus a pointer. Anecdotes are dropped.
- `multi-pr`: the closed blocker list moves to `change-loop.md`; the carried-obligation and cite
  recheck bullets shrink to one-line invariants; the cite script joins the reference list.
- `multi-lite`: quarantine and ledger bullets shrink to what the loop reference does not state.
- `spec-to-pr-retro`: the round-2 rule reads as "if X, propose Y; otherwise report counts".
- Overlay sentences in `multi-pr` and `multi-spec` point at the shared overlay rules.

No rule's behaviour changes, so there is no spec delta (`skip_specs`).

**Dropped (CLAUDE.md check 2).** Anecdotes ("lost about 4.5 hours", the deleted-ledger history, the
"deleted unread" note) and the `multi-pr`/`multi-lite` copies of text that `change-loop.md` and
`candidate-loop.md` already hold. Two `not-a-rule` ledger entries went with their lines.
