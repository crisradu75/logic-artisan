# CLAUDE.md

Rules for working in this repo. Reference material (layout, the script table) is in
DEVELOPER-GUIDE §11; the incident or measurement behind each rule is in §12, under a heading naming
the rule. Read §12 before you question or revise a rule.

## What this repo is

The source of **CLA — Cris Logic Artisan**, a Claude Code dev-workflow plugin. No product code:
skills, guard hooks and helper agents under `.claude/plugins/cla/`, which ships whole to consuming
repos through the GitHub marketplace. Tests and dev tools live in `plugin-tests/`, which never ships.

- **Start sessions with `./cla`** (`cla.cmd` on Windows). It runs `claude --plugin-dir
  <repo>/.claude/plugins/cla --permission-mode auto --model opus --effort medium`, so you run the
  harness you are editing. Plain `claude` gives you no `/cla:*` skills and no guard hooks.
  `--permission-mode auto` skips confirmations; the guard hooks are the safety layer.
- **Install the push guard once per clone.** Direct pushes to main are blocked by a git hook, not a
  PreToolUse hook, and a plugin cannot install it:

  ```bash
  cp .claude/plugins/cla/hooks/git/pre-push .git/hooks/pre-push && chmod +x .git/hooks/pre-push
  ```

- Use `/cla:new-worktree` whenever work wants isolation, before starting or mid-flight.
- Every shipped skill is invocable as `/cla:<name>`, and all but `cla-init`, `codify-learnings`,
  `multi-lite`, `multi-pr`, `right-model`, `save-permissions` and `spec-to-pr-retro` — which set
  `disable-model-invocation: true` — can also be triggered by natural language.

## Releasing

- Use `/release` (repo-local at `.claude/skills/release/`; it does not ship). Cut a release only
  from `main`, only after the work is reviewed and merged.
- **A release is a three-file edit in one commit:** `version` in
  `.claude/plugins/cla/.claude-plugin/plugin.json`, the `ref` in `.claude-plugin/marketplace.json`,
  and the release line below. A test fails when they disagree.
- Cut the tag with **`claude plugin tag .claude/plugins/cla`**. The path is required: the bare form
  looks for a manifest at the repo root, where this repo keeps `marketplace.json`. The tag is
  `cla--v<version>`, and the command refuses unless the manifest and catalog agree.
- **A published tag is never moved.** A fix after a release is a new version.
- **Never publish from a local-directory marketplace.** Consumers add the marketplace from the
  GitHub repo, never from a path.
- Versioning: a breaking change to how a consuming repo uses the plugin is a major; a skill or
  guard added or removed is a minor; fixes and doc corrections are a patch.

**Current release: `cla--v1.2.4`.**

## Running the tests

```bash
pytest plugin-tests -q -n auto --dist loadfile   # the gate
pytest plugin-tests                              # serial
pytest plugin-tests/tests/<area> -n auto --dist loadfile    # one area while iterating
node --test plugin-tests/node/mechanical-checks.test.mjs     # pytest does not reach this
openspec validate --specs --strict
```

### The parallel gate

- **Always pass `--dist loadfile`; plain `-n auto` is the trap.** The annotate browser suite
  builds a loopback port and a Chromium process per module, and splitting a module across workers
  races them. That suite skips without Playwright, so a green plain `-n auto` can mean it never ran.
- **Trust a parallel run only when its pass AND skip counts match a serial run of the same tree.**
  Whole scopes skip conditionally, so a dropped scope shows only as a skip-count change. Re-check
  when the invocation's scope changes.
- `pytest-xdist` is the one test-only dependency. Without it, use the serial form.
- **`mutate.py` stays serial.** It reads pytest's exit code to decide killed vs survived. Keep speed
  flags on the command line, never in `addopts`.
- **Never run `mutate.py` while a review agent reads the same tree.** It rewrites real files in
  place; a reader mid-run sees a mutated file and a clean `git status`. Serialise, or use a copy.

## Where things go

- **Tests never go in the plugin.** Every test, mutation batch, `mutate.py` and the pytest config
  live in `plugin-tests/`. A skill's tests go in `plugin-tests/tests/skills/<name>/`. A guard's
  mutation batch carries the guard's name under `plugin-tests/mutants/<area>/`, a sibling of
  `tests/` so it is never collected.
- **Shipped scripts are stdlib-only Python.** A shipped import outside the stdlib is a defect: a
  consumer installs the plugin, not a requirements file. pytest, pytest-xdist and the opt-in
  Playwright suite stay in the dev tree.
- **A browser test covers only what a string cannot answer** — geometry, stacking, breakpoints,
  round-trip state. Anything readable from the generated source goes in `test_render_doc.py`.
- **A script earns its place only if a command plus one sentence of prose cannot do the job
  reliably.** Add a new one to the script table in DEVELOPER-GUIDE §11 with its one-line reason.
- **A check a consuming repo must run is a shipped script, not a test.** A consumer has no pytest
  gate over its plugin cache.
- **Keep facts out of the synced core.** `skills/`, `agents/`, `hooks/`, `output-styles/` and `lib/`
  hold portable procedure only. No project token and no absolute developer path:
  `skills/_shared/scripts/check_no_project_tokens.py` fails on either. A repo's facts go in its own
  `cla.io/` (overlays, `project-facts.md`). Here the overlays stay neutral stubs: this is the
  source, not a consumer.
- **Do not restate the scanners' file-type lists in any doc.** Read them in the code. A new kind of
  shipped file stays unscanned until someone widens a scanner to it.

## Before shipping a change: five checks

A prose edit here ships like code, and nothing compiles it. Each check comes from a real escape.

1. **Inserted a step into an ordered sequence?** Read the steps before and after it in the code. A
   new phase inherits whatever the next one asserts on entry.
2. **Rewrote a file rather than edited it?** Diff old against new and state what you dropped.
3. **Asserting a diagnosis, a measurement or a count?** For a diagnosis, search the same source for
   counterexamples. For a measurement, name the command that produced it, in the same commit, or
   delete the claim. It holds only for the tree, platform and shell it ran on: a sameness claim
   comes from one tree, a before/after delta names both, and an old number is not current.
4. **Fixing a defect a review found?** Break the fix and confirm a test fails:
   `python3 plugin-tests/mutate.py <batch.py>` (a batch is a module defining `MUTANTS`). Check the
   function's other return paths too: fixing one often breaks another.
5. **Changed a function's signature?** Grep for its callers across the whole repo and fix them in
   the same edit. The scope you are working in is not the blast radius.

- **A clean mutation run is not a licence to stop.** Mutate what the fix touches, not only what it
  targets.
- **A KILLED mutant is not a pass until you read the test that killed it.** A test built on a wrong
  belief kills mutants just as reliably. Worst when the mutant is the simpler form of the code.
  Rule: `.claude/plugins/cla/skills/_shared/references/test-quality-gates.md`, "How planting goes
  wrong".
- **A SURVIVOR is not automatically a finding.** Some edits cannot be observed in a correct tree.
  Where two candidate rules agree on every correct input, mutate the input, not the guard. Never
  leave an unkillable mutant in a batch.
- **A green run is not more true for being repeated.** Re-run only to test for a flake, and then fix
  the flake.

**Match the checking to the change, and run each gate once.** The five checks are priced for a fix
or a new component. An increment to something already built and tested does not earn them.

| | run |
|---|---|
| Editing one skill or area | `pytest plugin-tests/tests/<area> -n auto --dist loadfile`, **once** |
| Fixing a defect a review found | that area, plus a mutation batch over what the fix touches |
| Adding a new script, skill, or hook | the five checks above, in full |
| Before opening a PR | `pytest plugin-tests -q -n auto --dist loadfile`, `node --test plugin-tests/node/mechanical-checks.test.mjs` and `openspec validate --specs --strict`, each once |

## No CI — verification is local

- **This repo runs no CI, by design. Do not add a workflow;** if a change seems to need one, raise
  it. The three commands in the last table row are the whole shipping gate.
- **Merging is unguarded.** Your local run before opening a PR is the only gate.
- **A green run is evidence about your machine only.** Several hooks branch on Windows vs POSIX;
  do not claim the other platform passed.
- **After merging a change, run `ls openspec/changes/`.** Archive is a phase of `/cla:spec-to-pr`,
  not a result of merging; anything there that is not in flight needs archiving.
- **Deferred work goes in GitHub issues.** A root `TODO.md` is spec-to-pr's Handoff residue, not a
  backlog.
