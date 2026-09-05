# fleet — the repos whose cla ledgers this machine can read

Read as data by `_fleet_roots()`, which has THREE copies — both retro aggregators and
`.claude/plugins/cla/lib/ledger_summary.py`, the reader the per-skill ledger sections point
at. All three are byte-identical and pinned together by
`plugin-tests/scripts/check_script_drift.py`. (The list said two for one commit, while the
third copy sat unpinned — a fix landing in the aggregators and not the summariser would
have left the guard green and the two tools reading different fleets from this one file.) One repo ROOT per `- ` bullet; an inline
`# comment` and surrounding backticks are stripped. This is a `*.local.md` overlay in the
repo's own `cla.io/` tree, outside the distributed plugin — **each machine curates its
own, and it is never synced.**

## Why this file exists

Any single repo's ledger is thin enough to mislead. The measured case: this repo's 8
spec-to-pr records put round-cap exhaustion at 4 of 5, where the fleet's 156 put it at 6
of 129. So a retro that reads one repo answers a different question than it appears to.

Reading several was already possible — `--log` has taken many paths for a while — but the
list lived nowhere. It had to be retyped from memory every time, and a path that resolves
to nothing contributes silently, which is the *same* sample-size error the fleet mode
exists to remove. `--fleet` reads this file instead.

Roots, not ledger paths, so one list serves both aggregators and both of codify's ledger
kinds. Each caller appends the ledger filename it already knows.

## Not every repo listed here has data

That is expected and worth keeping visible rather than pruning. A root with no ledger
shows up in the output's `ledgers` array as `found: false` with `records: 0`, which is how
a four-repo aggregate is prevented from being mistaken for a six-repo one. Removing a
quiet repo from this list would hide exactly that.

## Roots

- C:/Code/logic-artisan
- C:/Code/claude-plugins
- C:/Code/agentic-air
- C:/Code/interoga-ro
- C:/Code/market-distiller-mcp
- C:/Code/future-champs   # scaffolded, ledgers still empty
- C:/Code/verto-ai        # has a cla.io tree, no ledger rows yet
