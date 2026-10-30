# Project facts

This repo's facts file, maintained by `/cla:cla-setup` and checked by
`.claude/plugins/cla/skills/cla-setup/scripts/check_fact_paths.py`. This is the plugin's source
repo: it has no product code.

## Workspace shape

- `.claude/plugins/cla/` — the shipped plugin: skills, agents, hooks, output styles, `lib/`, and `com.github.copilot/agents/` (Copilot copies of the agents).
- `.claude-plugin/marketplace.json` — the Claude Code catalog; `.github/plugin/marketplace.json` — the Copilot CLI catalog.
- `plugin-tests/` — every test, mutation batch, `mutate.py` and the pytest config; never ships.
- `.claude/skills/release/` — the repo-local `/release` skill; never ships.
- `.claude/skills/openspec-*/`, `.claude/commands/opsx/` — OpenSpec's generated skills and commands; never ship.
- `openspec/` — live specs and active changes; `cla.io/` — this repo's facts, decisions, retros and overlays.
- `cla`, `cla.cmd` — launchers that load the plugin from the working tree.

## Dev / build / test commands

- Install: `pip install pytest-xdist` (optional browser suite: `pip install playwright && playwright install chromium`).
- No build or lint step, and no CI.
- Gate: `pytest plugin-tests -q -n auto --dist loadfile` — always `--dist loadfile`, never plain `-n auto`.
- Serial fallback: `pytest plugin-tests`; trust a parallel run only when its pass and skip counts match a serial run of the same tree.
- One area while iterating: `pytest plugin-tests/tests/<area> -n auto --dist loadfile`.
- Live specs: `openspec validate --specs --strict`.
- Mutation batch (opt-in: only when the owner asks or a guard hook is rewritten; serial only): `python3 plugin-tests/mutate.py <batch.py>`.

## Test proof

- Test proof granularity: requirement

## Spec map

- `openspec/spec-map.md`

## Test-file locations

- `plugin-tests/tests/<area>/` — areas `conformance`, `consistency`, `launcher`, `hooks`, `lib`, and `skills/<name>`.
- `plugin-tests/mutants/<area>/` — mutation batches, never collected; a skill's batches sit at `mutants/<skill>/`, with no `skills/` level.

## Doc-sweep paths

- Root `CLAUDE.md`, `README.md` and `DEVELOPER-GUIDE.md`.
- `.claude/plugins/cla/README.md` — the plugin's own readme and phase table.
- `openspec/spec-map.md` — the spec map (capabilities, workflows, the specs each step links).

## Cross-file lockstep doc sets

- Root `CLAUDE.md` — the commands, the release line, and the sentence naming the `disable-model-invocation: true` skills (also in `DEVELOPER-GUIDE.md` and the phase table; `test_doc_facts.py`).
- A release — both plugin manifests' `version`, both catalogs' `ref`, and the CLAUDE.md release line (`test_marketplace_manifest.py`, `test_doc_facts.py`).
- `DEVELOPER-GUIDE.md` §11 — the script table.
- `.claude/plugins/cla/README.md` — the phase table.
- `.claude/plugins/cla/hooks/_dispatch_lib.py` — `HOOK_WORST_CASE_SECONDS` must match each hook's real (call sites × timeout); `plugin-tests/tests/hooks/test_hooks_wiring.py` checks every entry exists; only `ask-destructive-git.py`'s value is tested.
