# Tasks

## 1. Guard hook

- [x] 1.1 Add `ask-secret-in-checkpoint`: a Write or Edit under one of the four briefing directories whose new text holds a listed secret shape asks, naming kind and line without the value; tests marked `requirement: guard-hooks / A secret written into a committed briefing asks first` cover each shape both ways.
- [x] 1.2 Placeholders, ordinary prose (a commit sha, a UUID, `sk-` inside a word, a URL without a password) and paths outside the scope stay silent; malformed input fails open; a 1 MB payload scans in linear time; tests cover each.
- [x] 1.3 Run it from the Edit/Write dispatcher as an enforcing hook at no budget cost; dispatcher, wiring and Copilot tests cover the ask, a spent budget and a load failure.
- [x] 1.4 Write a mutation batch for the hook's lines and the changed dispatcher lines under `plugin-tests/mutants/hooks/`.

## 2. Docs

- [x] 2.1 docs and spec map: `.claude/plugins/cla/README.md`, `DEVELOPER-GUIDE.md` and `CHANGELOG.md` updated; root `CLAUDE.md`, `README.md` and `openspec/spec-map.md` none affected: they name no individual guard and the spec map already links guard-hooks.
