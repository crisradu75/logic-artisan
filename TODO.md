# TODO

Leftover review suggestions. The inbox is emptied by regular sweep PRs.

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
