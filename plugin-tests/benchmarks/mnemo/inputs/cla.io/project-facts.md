# Project facts

This repo's facts file. `/cla:cla-setup` maintains it, and `check_fact_paths.py` checks its paths.

## Workspace shape
- A plain source repo with no plugin packaging (architecture Q14)
- Shared files copied into each domain repo's `.claude/`: `mnemo-plugin/`. The check script is `mnemo-plugin/mnemo/scripts/mnemo_check.py`, the base schema `mnemo-plugin/mnemo/conventions/base-schema.yml`
- Release version: `VERSION`, one semver line; a release is the tag `v<VERSION>`

## Dev / build / test commands
- Install: none, Python 3 standard library only
- Build: none
- Test: `python -m unittest discover -s tests`
- Check the shipped layout: `python -m unittest tests.test_shipped_layout`
- Trigger evals (cost model calls, not part of the tests): `python evals/run_triggers.py`

## Doc-sweep paths
- `README.md`
- `CLAUDE.md`
- `mnemo-plugin/skills/README.md`

## Test-file locations
- Tests: `tests/` (`test_*.py`; shared harness in `tests/helpers.py`)
- Hook tests: `tests/test_hooks_*.py` (probe, wiring, exit codes, guard, Stop); the guard's form table `tests/fixtures/guard_forms.json`; the real-command run `tests/guard_real_run.py` (run by hand, not discovered)
- Trigger evals: `evals/` (`evals/run_triggers.py`, `evals/triggers.jsonl`)

## Test proof
- Test proof granularity: scenario
