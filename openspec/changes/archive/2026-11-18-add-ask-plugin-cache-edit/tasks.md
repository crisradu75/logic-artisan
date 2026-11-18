# Tasks

## 1. Guard hook

- [x] 1.1 Add `ask-plugin-cache-edit`: a write in `cache/` or `marketplaces/` under a plugins root, or inside a `$CLAUDE_PLUGIN_ROOT` below one, asks; `data/`, a `--plugin-dir` tree and ordinary files are silent; tests marked `requirement: guard-hooks / A write into an installed plugin copy asks first` cover each rule both ways.
- [x] 1.2 Resolve symlinks, `..`, relative paths and `~`, honour `CLAUDE_CONFIG_DIR` and `CLAUDE_CODE_PLUGIN_CACHE_DIR`, and fail open silently on malformed input; tests cover each.
- [x] 1.3 Run it from the Edit/Write dispatcher as an enforcing hook, with the dispatcher re-emitting a hook's ask; dispatcher, wiring and Copilot tests cover the ask, a spent budget, deny over ask and a load failure.
- [x] 1.4 Write a mutation batch for the hook's lines and the changed dispatcher lines under `plugin-tests/mutants/hooks/`.

## 2. Docs

- [x] 2.1 docs and spec map: `.claude/plugins/cla/README.md`, `DEVELOPER-GUIDE.md` and `CHANGELOG.md` updated; root `CLAUDE.md`, `README.md` and `openspec/spec-map.md` none affected: they name no individual guard and the spec map already links guard-hooks.
