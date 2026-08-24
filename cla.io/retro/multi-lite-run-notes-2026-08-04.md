# multi-lite run notes — cla-upstream port from claude-plugins

**Source doc:** `cla.io/decisions/cla-upstream-port-from-claude-plugins.md` — deleted 2026-08-24;
recover with `git show eaa579b:cla.io/decisions/cla-upstream-port-from-claude-plugins.md`.
**Base branch:** `main` (primary clone)
**Plan confirmed:** yes — run as derived, dependency-first, PRs 1–3 merged as dependencies, #4 left open.

| id | status | branch | pr_number |
|---|---|---|---|
| push-guard-bypasses | merged | fix/push-guard-bypasses | 12 |
| hook-crash-and-base-branch | merged | fix/hook-crash-and-base-branch | 13 |
| update-cla-apply-hardening | merged | fix/update-cla-apply-hardening | 14 |
| docs-accuracy-and-guard-determinism | open | fix/docs-accuracy-and-guard-determinism | 15 |

## Out of scope for multi-lite

- Ledger item 11 (adapt-phase local-line accounting) — design change to the adapt contract, route to `/cla:spec-to-pr`.
- `discover_tests.py`'s `package.json` premise — real here, but a separate change from the port.
- `python3` vs `python` across the plugin — needs a stated convention, not a token swap.
- Ledger item 15 — not applicable to this repo (no such text in `codify-learnings/references/routing.md`).

## Notes

All 4 candidates ran; all 4 shipped a PR; all 4 had at least one Critical/Important
review finding surfaced and fixed in a single enforcement round (0 deferred to a
second round, 0 left unresolved). Sequence held exactly as confirmed — no reordering,
no fusing, no drops. Run completed clean: no failures, no quarantines, no reactive
worktree pivot.

- **#12 push-guard-bypasses** — review found two regressions the first commit itself
  introduced (relative `-C` resolving against the wrong cwd; silent `None` on git
  exit 128) plus a pre-existing `-o ci.skip` bypass. Fixed in one round, merged.
- **#13 hook-crash-and-base-branch** — review found a real slash-in-branch-name
  truncation bug reintroduced in both resolver copies, and a `Path.is_dir()` call
  that could itself raise and escape the function it was meant to harden. Fixed,
  merged.
- **#14 update-cla-apply-hardening** — review found the ratio threshold was
  literally inverted (set below the corruption signature's own floor rather than
  above it), which would have silently refused a real, uncorrupted file in this
  repo's own synced core (`design-tradeoffs.md`) on the very next real sync. Also
  found the new `skipped_malformed` status had no bucket in either summary printer,
  making the refusal invisible. Both fixed, merged.
- **#15 docs-accuracy-and-guard-determinism** — review found a corrected comment in
  block-direct-push-to-main.py that was itself still inaccurate (fixed), and a
  design-level gap in the new git-based top-level-name resolution (keyed off `HEAD`
  instead of the index, silently missing a staged-but-uncommitted top-level
  directory). Switched to `git ls-files --cached` with env scrubbing. Left **open**
  per the confirmed plan — nothing in this batch depends on it.
