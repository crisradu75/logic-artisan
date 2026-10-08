# Project facts

This repo's facts file, maintained by `/cla:cla-setup` and checked by
`.claude/plugins/cla/skills/cla-setup/scripts/check_fact_paths.py`. This is the plugin's source
repo: it has no product code.

## Workspace shape

- `.claude/plugins/cla/` — the shipped plugin: skills, agents, hooks, output styles, `lib/`.
- `plugin-tests/` — every test, mutation batch, `mutate.py` and the pytest config; never ships.
- `.claude/skills/release/` — the repo-local `/release` skill; never ships.

## Dev / build / test commands

- Install: `pip install pytest-xdist` (optional browser suite: `pip install playwright && playwright install chromium`).
- No build or lint step, and no CI.
- Gate: `pytest plugin-tests -q -n auto --dist loadfile` — always `--dist loadfile`, never plain `-n auto`.
- Serial fallback: `pytest plugin-tests`; trust a parallel run only when its pass and skip counts match a serial run of the same tree.
- One area while iterating: `pytest plugin-tests/tests/<area> -n auto --dist loadfile`.
- Node suite, which pytest does not reach: `node --test plugin-tests/node/mechanical-checks.test.mjs`.
- Live specs: `openspec validate --specs --strict`.
- Mutation batch (serial only): `python3 plugin-tests/mutate.py <batch.py>`.

## Test-file locations

- `plugin-tests/tests/<area>/` — areas `conformance`, `consistency`, `launcher`, `hooks`, `lib`, and `skills/<name>`.
- `plugin-tests/mutants/<area>/` — mutation batches, mirroring `tests/`, never collected.

## Cross-file lockstep doc sets

- Root `CLAUDE.md` — the commands, the release line, and the sentence naming the skills with `disable-model-invocation: true`.
- `DEVELOPER-GUIDE.md` §11 — the script table.
- `.claude/plugins/cla/README.md` — the phase table.
- `.claude/plugins/cla/hooks/_dispatch_lib.py` — `HOOK_WORST_CASE_SECONDS` must match each hook's real (call sites × timeout); `plugin-tests/tests/hooks/test_hooks_wiring.py` checks that every entry exists, not that its value is right.
