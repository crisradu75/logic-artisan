# Tasks

## 1. Guards

- [x] 1.1 Every Bash guard but the `cd` guard checks each shell wrapper's body as typed bare; a wrapped write outside the checkout asks, a wrapped `Measured-by: none` commit is blocked, and harmless wrapped commands stay silent; tests marked `requirement: guard-hooks / A command run through a shell wrapper is checked as typed bare`.
- [x] 1.2 `ALLOW_TAG_REWRITE=1` typed into a push asks in each value form `ALLOW_PUSH_TO_MAIN=1` takes; tests marked `requirement: git-guards / A push that skips the pre-push guard asks first`.
- [x] 1.3 `git push --mirror` asks with its own reason, wrapped or bare, and `git clone --mirror` stays silent; tests marked `requirement: git-guards / A mirror push asks first`.

## 2. Structure and budget (no spec change)

- [x] 2.1 The shell reader moves to a shared hooks module; the old and new dispatchers give the same decision and reason on every command string in the hook tests, the review reproducers and the plugin's docs as heredocs, apart from the wrapped forms in 1.1.
- [x] 2.2 `ask-destructive-git` splits into its decision, its rule tables and its probes, no file over about 1,000 lines, every name its tests import still importable from it.
- [x] 2.3 Its git probes share one deadline; the worst-case table entry drops from 12 s to 6 s and the budget tests pin it.
- [x] 2.4 Mutation batches retargeted and run once after the last change, with a mutant per new dispatcher and reader line that carries logic.

## 3. Docs

- [x] 3.1 docs and spec map: none affected in this change: `.claude/plugins/cla/README.md`, `DEVELOPER-GUIDE.md`, `README.md` and `CHANGELOG.md` get their lines from the orchestrator's docs pull request; `openspec/spec-map.md` already links both specs.
