# TODO

Leftover review suggestions. The inbox is emptied by regular sweep PRs.

- The seeded ~400-word proposal rule leaves little room for the authoring brief's new `## Open questions` and `## Risks noted` sections.
- Cap `## Risks noted` in the authoring brief at about 5 lines.
- The seed's `_BUDGET_LINE` matches only lowercase "at most"; a config that capitalises it is listed as missing the budget.
- The seed's `budget_held` counts commented-out lines in a config as carrying the budget.
- `check_change_budget` checks every active change, whatever the `--base` or path filter.
- `change_totals` reads `.md` files as `utf-8`, not `utf-8-sig`, so a byte-order mark adds a stray character to the first word.
- `Budget: protected` inside a code fence in `proposal.md` still selects the override (`_BUDGET_LINE` in `check_spec_proof.py` reads every line).
- Rule ledger: about 70 `keep` entries use the area "shipped to other repos" as a catch-all; at the next ledger review, keep that area only where breaking the rule makes the plugin misbehave in a consumer repo.
- Rule ledger: "never `git show HEAD:<path>`" is `keep` in `spec-to-pr/references/revise.md` and `multi-spec/references/review-gate.md` but softened to "Avoid" in `_shared/references/review-sweeps.md`; make the three agree.
- `test_rule_ledger.py`'s keyword regex misses "mustn't", and it scans only `.md` files.
- `codify-learnings/SKILL.md`: "not a made-up slug no file has" reads awkwardly.
- `test_autonomy_gate_exceptions.py` passes rewordings like "no exceptions authorize a pause"; pin the exact clause if the gate is reworded again.
- Rule ledger: a few `not-a-rule` fragments also span a real rule's keyword (`agents/doc-sweeper.md` and its Copilot copy, `cla-setup/SKILL.md` "never-clobber. ALWAYS guard"); narrow them so deleting the rule's own `keep` entry would fail the test.

## From the ask-broad-git-add review (Suggestions, not fixed)

- `git add */` is classed broad, but the probe passes a literal `*/` to git, so it stays silent while the shell stages every directory.
- Not detected: `..`, `sub/..`, `"$PWD"`, `$(pwd)`, `:(glob)**`, a quoted `"git"` and `--config-env`.
- A `GIT_DIR=` anywhere in the command silences every add in it, e.g. `GIT_DIR=x git status; git add -A`.
- The rename skip checks only `code[0]`, so a worktree rename shown as `" R"` is missed.
- The bare `except Exception` hides parser bugs even under `--debug`.
- Untracked file names go verbatim into the ask reason, so a file named "…did not run…" makes the Copilot adapter turn the ask into a deny.

## From the ask-plugin-cache-edit review (Suggestions, not fixed)

- Other plugins' copies under `synced/` are not covered. Adding `"synced"` to `_INSTALLED_SUBTREES` and dropping rule 2 (the `$CLAUDE_PLUGIN_ROOT` rule) would close that gap and stop a false ask when a dev tree sits under a broad `CLAUDE_CODE_PLUGIN_CACHE_DIR`.
- On macOS, `normcase` does nothing, so `~/.claude/Plugins/Cache/x` is not caught.
- The `Edit|Write` matcher misses NotebookEdit, and Bash writes (`sed -i`, `cp`) into the cache are not checked.
- The Edit/Write dispatcher's docstring says "deny > ask > allow", but a child's stdout `permissionDecision: "deny"` at exit 0 is dropped (no hook does that today).
- `test_a_plugin_root_in_the_cache_asks` does not exercise rule 2 (the subtree rule already asks); the `synced/` tests do.

## From the ship_check review (Suggestions, not fixed)

- `multi-spec/references/phases.md` Phase 2 finds an existing branch with `git ls-remote --heads origin docs/propose-<batch-slug>`, which also matches a longer branch name ending in it.
- Rule ledger: the `ship.md` rows for "must be EMPTY" and "They must be equal" are gone; those obligations remain in the text, held by `ship_check.py`, without absolute wording.
- `ship_check.py`: the "no remote" branch of `_upstream_config`'s callers is untested; a `merge` set with no `remote` makes `preflight` exit 2, not 1.
- `ship_check.py`: `branch.X.merge = X` (the short form) is reported as `upstream-elsewhere`. It fails safe.

## From the chain_check review (Suggestions, not fixed)

- "Opened by this chain" is branch match plus not-a-fork. A teammate's or bot's PR on the chain's branch at the same head would pass. An `author.login` check needs `gh api user`, which fails under some tokens.
- A fork workflow (gh resolving to an `upstream` remote) now blocks every merge as `not opened by this chain`. It fails closed, but it is new.
- Untested: `after-merge` on a not-found PR, the crash path, and a 64-hex head.
