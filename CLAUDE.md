# CLAUDE.md

Rules for working in this repo. Reference material (layout, the script table) is in
DEVELOPER-GUIDE §11. Where a rule came from an incident, a measurement or a decision, §12 tells
that story under a heading naming the rule. Read it before you question or change a rule.

## What this repo is

The source of **CLA — Cris Logic Artisan**, a Claude Code dev-workflow plugin. No product code:
skills, guard hooks and helper agents under `.claude/plugins/cla/`, which ships whole, through the
GitHub marketplace, to every repo that installs it. Tests and dev tools live in `plugin-tests/`,
which never ships.

- **Start sessions with `./cla`** (`cla.cmd` on Windows). It runs `claude --plugin-dir
  <repo>/.claude/plugins/cla --permission-mode auto --model opus --effort medium`, so you run the
  plugin you are editing. Plain `claude` gives you no `/cla:*` skills and no guard hooks.
  `--permission-mode auto` skips confirmations; the guard hooks are what stop a dangerous command.
- **Install the push guard once per clone.** Direct pushes to main are blocked by a git hook, not a
  Claude Code hook, and a plugin cannot install it:

  ```bash
  cp .claude/plugins/cla/hooks/git/pre-push .git/hooks/pre-push && chmod +x .git/hooks/pre-push
  ```

- Use `/cla:new-worktree` whenever work needs its own copy of the repo, before starting or partway
  through.
- Every shipped skill is invocable as `/cla:<name>`, and all but `cla-setup`, `codify-learnings`,
  `multi-lite`, `multi-pr`, `right-model`, `save-permissions` and `spec-to-pr-retro` — which set
  `disable-model-invocation: true` — can also be triggered by natural language.

## Releasing

- Use `/release` (it lives in this repo at `.claude/skills/release/` and does not ship). Cut a
  release only from `main`, only after the work is reviewed and merged.
- **A release is a three-file edit in one commit:** `version` in
  `.claude/plugins/cla/.claude-plugin/plugin.json`, the `ref` in `.claude-plugin/marketplace.json`,
  and the release line below. A test fails when they disagree.
- Cut the tag with **`claude plugin tag .claude/plugins/cla`**. The path is required: without it the
  command looks for `plugin.json` at the repo root, where this repo keeps `marketplace.json`. The
  tag is `cla--v<version>`, and the command refuses unless `plugin.json` and `marketplace.json`
  agree.
- **A published tag is never moved.** A fix after a release is a new version.
- **Never publish from a marketplace added from a local folder.** Other repos add the marketplace
  from the GitHub repo, never from a path.
- Versioning: a change that breaks how another repo uses the plugin is a major version; adding or
  removing a skill or guard is a minor; fixes and doc corrections are a patch.

**Current release: `cla--v2.0.0`.**

## Running the tests

```bash
pytest plugin-tests -q -n auto --dist loadfile   # the gate
pytest plugin-tests                              # serial
pytest plugin-tests/tests/<area> -n auto --dist loadfile    # one area while iterating
openspec validate --specs --strict
```

### The parallel gate

- **Always pass `--dist loadfile`; plain `-n auto` is the trap.** Each annotate browser test file
  starts its own local server port and Chromium. Plain `-n auto` can split one file across workers,
  and they fight over the port. That suite skips without Playwright, so a green plain `-n auto` can
  mean it never ran.
- **Trust a parallel run only when its pass AND skip counts match a serial run of the same code.**
  Some test folders skip themselves entirely, so the only sign one didn't run is a higher skip
  count. Re-check whenever you change which tests the command runs.
- `pytest-xdist` is the one test-only dependency. Without it, use the serial form.
- **`mutate.py` stays serial.** It reads pytest's exit code to tell whether a planted bug was
  caught. Put speed flags like `-n` on the command line, never in pytest's `addopts` setting, which
  every run picks up, `mutate.py`'s included.
- **Never run `mutate.py` while a review agent reads the same tree.** It edits real files and puts
  them back afterwards; an agent reading mid-run sees a broken file while `git status` shows
  nothing. Run one after the other, or run `mutate.py` in a copy.

## Where things go

- **Tests never go in the plugin.** Every test, mutation batch, `mutate.py` and the pytest config
  live in `plugin-tests/`. A skill's tests go in `plugin-tests/tests/skills/<name>/`. A guard's
  mutation batch (its list of planted bugs) is named after the guard and lives under
  `plugin-tests/mutants/<area>/`, outside `tests/` so pytest never runs it as a test.
- **Shipped scripts are stdlib-only Python.** A shipped import outside the standard library is a
  defect: a repo installs the plugin, not a requirements file. pytest, pytest-xdist and the opt-in
  Playwright suite stay in `plugin-tests/`, which does not ship.
- **A browser test covers only what reading the page source cannot answer** — where things sit on
  the page, what covers what, what changes at a screen width, and whether a save-and-reload leaves
  the page as it claims. Anything readable from the generated source goes in `test_render_doc.py`.
- **A script earns its place only if a command plus one sentence of prose cannot do the job
  reliably.** Add a new one to the script table in DEVELOPER-GUIDE §11 with its one-line reason.
- **A check another repo must run ships as a script, not a test.** A repo that installs the plugin
  never runs the plugin's tests.
- **Keep facts out of the shipped plugin.** `skills/`, `agents/`, `hooks/`, `output-styles/` and
  `lib/` hold only steps that work in any repo. No project-specific word and no absolute path from
  a developer's machine: `skills/_shared/scripts/check_no_project_tokens.py` fails on either. A
  repo's own facts go in its own `cla.io/project-facts.md`; a rule for one skill in that repo goes
  in an optional `cla.io/overlays/<skill>.md`. A skill reads an overlay only if it is present, and
  nothing ships or seeds one.
- **Do not copy the checkers' lists of file types into any doc.** Read them in the code. A new kind
  of shipped file stays unchecked until someone adds it to a checker.

## Before shipping a change: five checks

A prose edit here ships like code, and nothing compiles it. Each check comes from a real escape.

1. **Inserted a step into an ordered sequence?** Read the steps before and after it in the code.
   The step after yours may check things when it starts (a clean tree, a state file, the branch).
   Make sure your step leaves them true.
2. **Rewrote a file rather than edited it?** Diff old against new and state what you dropped.
3. **Asserting a diagnosis, a measurement or a count?** For a diagnosis, look in the same place for
   cases that contradict it, not only ones that support it. For a measurement, name the command
   that produced it, in the same commit, or delete the claim. A number holds only for the code,
   platform and shell it ran on. "Unchanged" must compare two runs on the same code. "Faster" must
   name both versions. Don't repeat an old number as if it were current.
4. **Fixing a defect a review found?** Break the fix and confirm a test fails, then restore it. Do
   this by hand, once per fix. In a guard hook or a checker, also run a mutation batch:
   `python3 plugin-tests/mutate.py <batch.py>` (a batch is a Python file whose `MUTANTS` list holds
   small deliberate bugs). Run it once per PR, over the guard or checker lines the PR changed,
   after the last fix. A broken guard fails silently, so this is the only cheap sign. Guard hooks
   are the files under `.claude/plugins/cla/hooks/`. Checkers are the `check_*.py` scripts under
   `.claude/plugins/cla/skills/` and `.claude/skills/release/scripts/`. Checkers also include the
   guard tests in `plugin-tests/tests/conformance/` and `plugin-tests/tests/consistency/`. Check
   the function's other return paths too: fixing one often breaks another.
5. **Changed a function's signature?** Grep for its callers across the whole repo and fix them in
   the same edit. The folder you are working in is not the whole blast radius.

- **A clean mutation run (every planted bug caught) is not a reason to stop.** Plant bugs in
  every guard or checker line the PR changed, not only the line a fix meant to fix.
- **A KILLED mutant is not a pass until you read the test that killed it.** A test built on a wrong
  belief catches planted bugs just as reliably. Worst when the planted bug is a simpler form of the
  code. If the simpler code is actually right, the test is protecting the bug. Rule:
  `.claude/plugins/cla/skills/_shared/references/test-quality-gates.md`, "How planting goes
  wrong".
- **A SURVIVOR is not automatically a finding.** Some planted bugs make no visible difference while
  the files are correct. If no correct file can tell the real check from the broken one, add a bad
  input file instead of breaking the check. Never leave a planted bug no test can catch in a batch.
- **A green run is not more true for being repeated.** Re-run only to test for a flake, and then fix
  the flake.

**Match the checking to the change, and run each gate once.** The five checks are sized for a fix
or a new component. A small addition to something already built and tested does not need them.

| | run |
|---|---|
| Editing one skill or area | `pytest plugin-tests/tests/<area> -n auto --dist loadfile`, **once** |
| Fixing a defect a review found | that area; for a guard hook or checker, also one mutation batch over the PR's changed lines, run once after the last fix |
| Adding a new script, skill, or hook | the five checks above, in full |
| Before opening a PR | `pytest plugin-tests -q -n auto --dist loadfile` and `openspec validate --specs --strict`, each once |

## No CI — verification is local

- **This repo runs no CI, by design. Do not add a workflow;** if a change seems to need one, raise
  it. The two commands in the last table row are the whole shipping gate.
- **Merging is unguarded.** Your local run before opening a PR is the only gate.
- **A green run is evidence about your machine only.** Several hooks behave differently on Windows
  and on Linux/macOS; do not claim the other platform passed.
- **After merging a change, run `ls openspec/changes/`.** Archiving is a step of `/cla:spec-to-pr`;
  merging does not do it. Anything listed there that is not still in progress needs archiving.
- **Deferred work goes in GitHub issues.** A root `TODO.md` holds leftover suggestions written by
  spec-to-pr's last step, not a backlog.
