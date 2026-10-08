# fleet — the repos whose cla ledgers this machine can read

Read as data by `_fleet_roots()` in the spec-to-pr retro aggregator, which reads this file
by default — its one reader since the generic ledger reader was deleted. One repo ROOT per
`- ` bullet; an inline `# comment` and surrounding backticks are stripped. This is a `*.local.md` overlay in the
repo's own `cla.io/` tree, outside the distributed plugin — **each machine curates its
own, and it is never synced.**

## Why this file exists

Any single repo's ledger is thin enough to mislead. The measured case (2026-10-08,
`spec_to_pr_aggregate.py --limit 0`, consumer ledgers migrated): this repo's 11 spec-to-pr
records put Revise cap exhaustion at 5 of 9, where the 137 records of the four repos with
ledgers below put it at 43 of 119. So a retro that reads one repo answers a different
question than it appears to.

Reading several was already possible — `--log` has taken many paths for a while — but the
list lived nowhere. It had to be retyped from memory every time, and a path that resolves
to nothing contributes silently, which is the *same* sample-size error the fleet mode
exists to remove. The retro aggregator reads this file by default, and falls back to this
repo's own ledger, saying so, when none of the roots below exists on the machine it runs on.

Roots, not ledger paths: the reader appends the ledger filename it already knows.

## Not every repo listed here has data

That is expected and worth keeping visible rather than pruning. A root with no ledger
shows up in the output's `ledgers` array as `found: false` with `records: 0`, which is how
a four-repo aggregate is prevented from being mistaken for a six-repo one. Removing a
quiet repo from this list would hide exactly that.

A *frozen* repo is different: one that stopped running cla but still holds old rows keeps
stale data in every aggregate. `agentic-air` was removed on 2026-10-08 for that reason — it
vendors plugin 0.0.1, does not enable the marketplace plugin, and its last ledger row is
from 2026-07-22, yet its 64 spec-to-pr rows were about a third of the sample. Re-add it
only after it is re-onboarded (marketplace install, then `cla-init` and `sync-context` —
`cla-setup` once those merge).

## Roots

- C:/Code/logic-artisan
- C:/Code/claude-plugins
- C:/Code/interoga-ro
- C:/Code/market-distiller-mcp
- C:/Code/future-champs   # scaffolded, ledgers still empty
- C:/Code/verto-ai        # has a cla.io tree, no ledger rows yet
