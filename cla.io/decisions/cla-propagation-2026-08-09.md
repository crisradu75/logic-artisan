# Decision — CLA propagation

**Topic:** how the CLA plugin core gets from `logic-artisan` into consuming repos, and how
fixes get back.

Scoped deliberately: guard-hook design and the retro-loop budget were named in the same
assessment but are **not** decided here.

## Where this came from

Session `84e7fdce` (2026-08-09) assessed the current approach and measured it: 18,371 →
35,555 plugin lines in 18 days (+94%), 49 commits, buying 1 skill and 3 hooks — the rest
hardening and fixes-to-fixes. `cla.io/inbound-findings.md` records 29 verified consumer-reported
defects in one triage. Root cause named there and accepted here: **synced core is writable in
consumers**, so five editable forks require permanent N-way reconciliation by construction.

That session also found a global `alias cla="claude --permission-mode auto"` in `~/.bashrc`
shadowing the repo launcher, meaning the guard layer had largely been off across repos. Alias
removed. Relevant here only as context: the guard layer's value is **unmeasured**, not disproven.

## Grounding facts checked during this session

- Real consumer set is **market-distiller-mcp, claude-plugins, agentic-air, interoga-ro** (4).
  `sync-config.json` also lists `sitekit` and `legal-docs`, which were never onboarded — the
  config is stale.
- The CLAUDE.md claim that a cached marketplace install "can't" read/write repo-local state is
  **wrong as written**. Hooks and skills run against the session cwd, so `cla.io/` and git state
  are reachable; `hooks.json` already uses `${CLAUDE_PLUGIN_ROOT}`. The one real blocker is that
  overlays live *inside* the plugin tree (9 `references/project-context.md` + `branch-prefix.local.md`,
  `project-tokens.local.md`, `smoke-test-drift.local.md`), and one shared per-user cache cannot hold
  four repos' different facts.
- Overlay sizes, measured: market-distiller-mcp 50,578 B across 10 overlays + 9,834 B
  `project-facts.md`; claude-plugins 66,303 B across 9 + 6,755 B. Per-skill spread 2.9 KB
  (`new-worktree`) → 8.6 KB (`spec-to-pr`).
- `update-cla` is 6,224 lines incl. tests. `SCAN_FILES` = the repo-root launchers.
- `logic-artisan` has a GitHub remote (`crisradu75/logic-artisan`). Both active consumers still
  carry a `cla-upstream.md`.

## Decisions

| # | Question | Chosen | Rationale |
|---|---|---|---|
| 1 | Is synced core writable in consumers? | **Read-only core; all changes originate in logic-artisan** | Converts N-way reconcile into an ordinary dependency — the one change that stops the cycle at its source |
| 2 | How is core distributed? | **Publish as a marketplace plugin; overlays move to `cla.io/`** | Makes the read-only boundary structural rather than aspirational, and deletes the machinery instead of policing it |
| 3 | Where do overlays live? | **Hybrid — repo facts in `cla.io/project-facts.md`, skill tuning in `cla.io/overlays/<skill>.md`** | Measured split supports it: ~10 KB shared facts vs 50–66 KB of single-consumer tuning; consolidating all of it would cost every skill ~15–18k tokens per read |
| 4 | Fate of `update-cla` (6,224 lines)? | **Retire it — one-shot migration script, then delete** | A second propagation path means the boundary isn't structural; the code's job disappears once core is read-only |
| 5 | How do downstream defects reach the source? | **Consumer opens a GitHub issue/PR against `logic-artisan`** | The only option where the source finds out without someone remembering to look; replaces the sync-moment trigger that dies with `update-cla` |
| 6 | Where does harness development happen? | **In logic-artisan, as now** | Everything in one place — edit, test, commit, release, with no cross-repo mechanics |
| 7 | What exercises a change before five repos get it? | **Pre-release exercise pass: install candidate in one consumer, run one real task, then tag** | Closes the author-can't-exercise gap without moving development, which Q6 fixed in place |
| 8 | What earns a release? | **Deliberate release when warranted, gated by the exercise pass, with release notes** | The only option where the gate stays affordable enough to actually run every time |
| 9 | How do the four consumers migrate? | **Pilot one repo end-to-end, then the rest** | Four untested links in the chain — a flaw found in the pilot is a fix, not a rollback |

## Open questions

Both need a real install to settle — do not design around an assumed answer:

1. **Can a marketplace plugin be pinned to a different version per repo?** `installed_plugins.json`
   entries carry a `scope: "user"` field, are array-valued, and key `installPath` by version, which
   suggests project-scoped installs at differing versions are representable. Suggestive, not proof.
   If the answer is no, all repos move together and Q9's pilot still works but Q8's staged holding
   of a risky release does not.
2. **Where does `claw` live** once the launcher sync goes away with `update-cla`? `cla`/`cla.cmd`
   lose their reason to exist under a marketplace install (no `--plugin-dir` to pass); `claw` keeps
   its job but is a repo-root file no plugin can install.

## Why this matters, and what's next

This is the decision that ends the correction treadmill: one writer, N readers, with the boundary
enforced by the install mechanism rather than by discipline. It also removes the single largest
body of code in the plugin.

Natural next step: a `/cla:multi-spec` batch off this file, since the work spans several
independently-shippable changes — overlay relocation and the `project-facts.md`/`overlays/` split,
the marketplace manifest and publishing setup, the upstream-reporting skill replacing `update-cla`
Phase 4, the one-shot migration script, and the `update-cla` removal. Sequence the pilot repo (Q9)
before the remaining three, and settle both open questions during the pilot.
