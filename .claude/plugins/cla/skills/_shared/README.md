# `skills/_shared/` — references used by more than one skill

Not a skill. There is no `SKILL.md` here on purpose: Claude Code defines a skill as
a directory whose entrypoint is `SKILL.md`, so a directory without one is not
loaded, not registered, and not invocable. `_shared/` is a plain content
directory that other skills point into.

## Why it exists

These files were previously under `skills/spec-to-pr/references/`, where up to
nine other skills reached for them. That made one skill's directory the plugin's
de-facto common library: `spec-to-pr` could not be reorganised, renamed, or
version-bumped without moving files half the plugin depends on, and a reader had
no way to tell which of its references were its own and which were everyone's.

## What belongs here

A reference earns a place here when **two or more skills read it as authority**.
One skill's own procedure stays in that skill's `references/`, however long it is.

| File | Read by |
|---|---|
| `model-routing.md` | the single routing table — which model each dispatched agent runs at |
| `runtime-rules.md` | the thin-orchestrator disciplines (delegation, I/O hygiene, batching) |
| `bash-discipline.md` | hard rules for emitted bash shape |
| `base-branch-resolution.md` | how to resolve this repo's default branch, never assume it |
| `required-permissions.json` | the bootstrap permission set the ship skills check |
| `run-log-schema.md` | the per-run JSONL contract the retro skills consume |
| `past-offenses.md` | the generic enforcement-tier vocabulary behind the guardrails |
| `retro-skeleton.md` | the workflow every `*-retro` skill follows, minus its own heuristics |

## `scripts/`

One script lives here on the same rule: `git_state.py` returns a single deterministic exit code for
"an in-progress rebase / cherry-pick / merge exists", and four skills check it at every commit
boundary. It is stdlib-only and imports nothing local. Its test and this scope's `pyproject.toml`
sit beside it — `run_tests.py` fails the whole run as a "near-miss" if a directory has a
pytest-configured `pyproject.toml` without a `tests/`, or the reverse, so the three move together
or not at all.

## How to reference one

Always with the explicit plugin-root path, never a bare relative one:

```
${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md
```

A bare `references/<file>` reads as "this skill's own reference" and resolves to
nothing from another skill. `conformance-checks/tests/test_skill_lint.py` fails
the suite on both mistakes — a path that resolves nowhere, and a bare path that
actually means someone else's file.

## Scanning

Everything here is under a `references/` ancestor inside `skills/`, so the
fact/procedure token guard picks it up with no configuration. Keep it portable:
no repo names, no absolute developer paths.
