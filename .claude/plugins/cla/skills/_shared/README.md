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
| `conflict-resolution.md` | procedure for a mid-flight rebase/cherry-pick/merge — what `git_state.py` exit 2 hands you |
| `test-quality.md` | whether a test can fail at all — a couple of rules for any test, the rest for a gate; read at authoring time |
| `skill-authoring.md` | plugin-wide doctrine for writing a skill: progressive disclosure + completion criteria |

## `scripts/`

One script lives here on the same rule: `git_state.py` returns a single deterministic exit code for
"an in-progress rebase / cherry-pick / merge exists", and four skills check it at every commit
boundary. It is stdlib-only and imports nothing local.

Its tests do **not** sit beside it. The plugin ships only what a consuming repo can use, so every
test lives outside the published tree, in the canonical source repo's own development tree — this
script's are at `plugin-tests/tests/skills/_shared/test_git_state.py` there. The script moves alone;
there is no sibling `tests/` or `pyproject.toml` to move with it.

## How to reference one

Always with the explicit plugin-root path, never a bare relative one:

```
${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/model-routing.md
```

A bare `references/<file>` reads as "this skill's own reference" and resolves to
nothing from another skill. The source repo's
`plugin-tests/tests/conformance/test_skill_lint.py` fails the suite on both mistakes — a path that resolves nowhere, and a bare path that
actually means someone else's file.

## Scanning

Every `.md` under `references/` is scanned by the fact/procedure token guard with
no configuration, because the guard yields any `.md` beneath a `references/`
ancestor inside `skills/`. `required-permissions.json` is the exception — it is
not markdown, so no scanner reads it; it holds tool-permission patterns rather
than prose, but keep repo names out of it by hand. `scripts/git_state.py` is covered too, by the source
scanner's `.py` rule.

**This file is not scanned by either.** It is a `.md` directly under a skills
subdirectory, which matches neither rule — so the portability discipline below is
on you rather than on a guard. Keep everything here portable regardless: no repo
names, no absolute developer paths.
