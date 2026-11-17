# TODO

Leftover review suggestions. The inbox is emptied by regular sweep PRs.

- The seed's `_BUDGET_LINE` matches only lowercase "at most"; a config that capitalises it is listed as missing the budget.
- The seed's `budget_held` counts commented-out lines in a config as carrying the budget.
- `check_change_budget` checks every active change, whatever the `--base` or path filter.
- `change_totals` reads `.md` files as `utf-8`, not `utf-8-sig`, so a byte-order mark adds a stray character to the first word.
- `Budget: protected` inside a code fence in `proposal.md` still selects the override (`_BUDGET_LINE` in `check_spec_proof.py` reads every line).
