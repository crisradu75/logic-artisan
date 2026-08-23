# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

`logic-artisan` is the canonical home of **CLA — Cris Logic Artisan**, a Claude Code dev-workflow
harness packaged as a plugin. It holds no product/application code — it's the *process* layer
(skills, guard hooks, helper agents) that carries a change from idea → spec → isolated
implementation → review → opened PR, and feeds learnings back into the next run. Other repos install
this plugin from the GitHub marketplace and adapt it to their own context via overlays.

Everything lives under `.claude/plugins/cla/`, which is exactly the directory the marketplace
catalog publishes as the plugin's source path.

**Distribution is GitHub, and only GitHub.** `.claude-plugin/marketplace.json` at the repo root
publishes one plugin, `cla`, from this subdirectory (`git-subdir` source, `url` + `path`, schema
verified against the live docs). It pins an **exact release tag**, not a moving major tag, so
publishing a release is a deliberate three-file edit: bump `version` in the plugin's own
`plugin.json`, the `ref` here, and the release line below — all in one commit. A test fails when they disagree. Consumers
pick the new release up on `/plugin marketplace update`.

Consumers add the marketplace from the repo, never from a path:

```bash
claude plugin marketplace add crisradu75/logic-artisan
claude plugin install cla@cris-logic-artisan --scope project
```

Cut the tag with **`claude plugin tag`** (shape `<name>--v<version>`); it refuses unless
`plugin.json` and the marketplace entry already agree. **Current release: `cla--v0.10.0`.** `0.9.x`
is the validation line; it becomes `1.0.0` once a real task has been run end-to-end through the
plugin in a consuming repo.

**A published tag is never moved** — cut it only from `main`, only after review. **Never publish
from a local-directory marketplace.** Background for both rules, and the deleted `claw` launcher:
DEVELOPER-GUIDE.md "Release and distribution history".

**Launching a session in THIS repo:** use the `cla` (POSIX) / `cla.cmd` (Windows) launcher at the
repo root rather than typing `claude` directly. It resolves its own absolute path, so it always
passes `--plugin-dir <repo>/.claude/plugins/cla` regardless of your cwd:

```bash
./cla   # claude --plugin-dir <repo>/.claude/plugins/cla --permission-mode auto --model opus --effort high
```

`--plugin-dir` loads the plugin live from this working tree, so you run the harness you are
editing. Without it the skills/hooks are inert files — no `/cla:*` commands, no guard hooks.
**Note:** `--permission-mode auto` bypasses per-action confirmation prompts; the guard hooks are
the safety layer.

**Starting work in a worktree.** Use `/cla:new-worktree` at any point — before starting, or once
you realise mid-flight that the work wants isolation. No penalty for deciding late.

## Commands

Run the full test suite:

```bash
pytest plugin-tests              # the whole suite: one scope, one command
pytest plugin-tests -q           # extra args go straight to pytest
pytest plugin-tests -k branch    # filter by name
```

Run part of it (e.g. while iterating on one skill):

```bash
pytest plugin-tests/tests/hooks
pytest plugin-tests/tests/skills/<name>
```

**The plugin's tests do not live in the plugin.** `.claude/plugins/cla/` is published whole to
consuming repos and carries only assets a consumer can use, so every test, every mutation batch,
the mutation runner, and the pytest configuration live in this repo's own `plugin-tests/` tree.
It is the repo's ONLY pytest scope — 1 in total, down from 12 — with a single `pyproject.toml`
(`testpaths = ["tests"]`, `norecursedirs = ["mutants", "node"]`, and a `pythonpath` of 10 entries
reaching out of the dev tree into the plugin, because the scripts under test stay shipped and only
their tests moved).

The twelve-scope split existed for exactly one reason — pytest's default import mode cannot hold
two test modules with the same basename — and the collision set is now empty. Measured with
`git ls-files '.claude/plugins/cla/**/tests/*.py' | xargs -n1 basename | sort | uniq -d`, the only
duplicate is `conftest.py`, which pytest special-cases per directory. (Note for anyone re-deriving
this: the split's usual justification named a second collision on `scripts/log_run.py`, which
`git ls-files | grep log_run` shows never existed — one module, one test. The measurement, not the
folklore.)

Inside `plugin-tests/tests/` the old scope names survive as area directories: `conformance/`,
`consistency/`, `launcher/`, `hooks/`, `lib/`, and `skills/<name>/` — 6 areas under `skills/`, one
per skill that ships tests, plus `_shared/`. `mutants/` is a SIBLING of `tests/`, mirroring its
subdirectory names, so the batches are never collected as tests and each guard maps to its batch by
a one-step name substitution.

**`lib/` is the odd one out in the plugin**: not a skill (no `SKILL.md`) and not a guard hook. It
holds `log_run.py`, the one ledger writer every retro-logging skill invokes as a program.

Of the four portable guards that police the fact/procedure split, **two reach consuming repos and
two do not, and the difference is where they live.** No project token in synced core
(`skills/_shared/scripts/check_no_project_tokens.py`) and no dead path in `cla.io/project-facts.md`
or an overlay (`skills/sync-context/scripts/check_fact_paths.py`) are skill scripts inside the
shipped tree, so a consumer gets them and can run them as programs. No hardcoded plugin path and no
SKILL.md with broken frontmatter or a dead reference are pytest guards in `plugin-tests/`; they
police the plugin's own source and do not reach a consumer at all, which is deliberate — a consuming
repo has no pytest gate over its plugin cache, so a guard filed as a test module is unreachable
there in practice.

Source-repo-only is now **structural rather than declared**. The whole dev tree exists only here, so
there is nothing to mark and nothing to skip; the `SOURCE-REPO-ONLY.md` marker mechanism and its
guard were deleted with the runner that read them. `plugin-tests/tests/launcher/` still tests the
repo-root `cla`/`cla.cmd` launchers, which live outside the plugin tree entirely (`claw`/`claw.cmd`
were deleted alongside the worktree-isolation guard, the hook they existed to dodge).

All scripts are stdlib-only Python (no third-party deps beyond pytest itself).

### Before shipping a change here, run four checks

The plugin's behaviour lives mostly in markdown, so a prose edit ships like code but
nothing compiles it. Every defect that reached review in this repo had one shape: the
artifact was checked, the system it lands in was not. These four checks are cheap and
each one comes from a real escape:

1. **Inserted a step into an ordered sequence?** Read the step immediately before and
   after **in the code**, not from memory of it. A phase added between two others
   inherits whatever the next one asserts on entry — a clean-tree check, a state file, a
   branch assumption.
2. **Rewrote a file rather than edited it?** Diff old against new and state what you
   dropped. A rewrite silently loses rules an edit would have preserved; "it reads better"
   is not evidence that nothing went missing.
3. **Asserting a diagnosis, a measurement, or a count?** Two halves, and the second is
   the one that keeps escaping. For a **diagnosis**, search the same source for
   counterexamples before shipping it, not just for supporting cases — a table of three
   examples proves nothing if three counterexamples sit in the same file. For a
   **measurement** — "measured", "verified", "zero violations", any number — name the
   command that produced it, in the same commit. If you cannot name one, you did not
   measure it: delete the claim or go run it. Reasoning that feels like measurement is the
   most expensive thing in this repo, because it ships with a measurement's authority.
   Recorded in `cla.io/lessons-learned/lessons-learned.md` (2026-08-14): review caught six
   such claims in one session, and in one of them the comment's own text contained the
   token it declared absent. Two more were invented blockers — "widening the scan roots
   fails on the test fixtures" survived until someone widened the scan roots and got zero
   violations. A seventh was caught by the merge check on the PR that added this very
   rule: a commit count nobody had run, in three files including the hook written to
   measure it.
4. **Fixing a defect a review found?** Break the fix and confirm a test fails —
   `python3 plugin-tests/mutate.py <batch.py>` runs a batch of those (a batch is a
   Python module defining `MUTANTS`; see the tool's docstring) and reports survivors. A
   fix is a change like any other and earns the same evidence the original code needed;
   "the reviewer's finding is now handled" is not that evidence. A fix also has a second
   branch nobody looks at: correcting one return path of a function commonly breaks
   another, which is how `lint_profile` traded a silent no-op on the default path for the
   identical no-op on the overlay path.

**A clean mutation run is not a licence to stop.** It is evidence about the mutants you
thought of, and nothing else. Measured on this repo: commits `1cf09da` and `0027bc7` each
recorded "three mutations checked, all caught" and each shipped a critical that a later
review found — the mutants covered the branch the author was reasoning about, not the
branch they got wrong. So mutate what the fix *touches*, not what it targets, and treat a
green run as one input to the ship decision rather than the decision itself.

**Match the checking to the change, and run each gate once.** The four checks above are
priced for a *fix* or a new component — the cases where being wrong is expensive and
invisible. An increment to something already built and already tested does not earn them,
and paying them anyway is not caution, it is waste with the shape of rigour. The defaults:

| | run |
|---|---|
| Editing one skill or area | `pytest plugin-tests/tests/<area>`, **once** |
| Fixing a defect a review found | that area, plus a mutation batch over what the fix touches |
| Adding a new script, skill, or hook | the four checks above, in full |
| Before opening a PR | `pytest plugin-tests`, once |

**A green run does not get more true by being repeated.** Re-running a suite to see whether
a failure recurs is the one case that justifies it — and then the finding is the flake, so
fix the mechanism rather than counting clean runs as evidence against it. Recorded
2026-08-22, after adding a navigation rail to `annotate` cost five full scope runs, a whole
sweep of the entire suite, and an unrelated change to a server, for an edit whose real gate
was one 13-second run over that one area and looking at the page. (The runner those runs
used is gone; the lesson is about the count, not the command.)

The one Node script in the plugin, `project-review/scripts/mechanical-checks.mjs`, has a
`node --test` suite, which lives in the dev tree with every other test. It is not a pytest scope
and **nothing runs it for you** — `pytest plugin-tests` does not reach it, so it is a second
command you run deliberately:

```bash
node --test plugin-tests/node/mechanical-checks.test.mjs
```

### No CI — verification is local, by design

This repo runs **no GitHub Actions and no CI of any kind**, deliberately. Two local commands are
the whole verification story: `pytest plugin-tests` for the suite, and `node --test` for the one
Node suite it does not reach. Run both once before opening a PR. **They are the shipping gate, not
the edit loop** — while iterating, run the one area you are changing; see the table above.

Do not add a workflow. If a change seems to need one, raise it rather than adding it.

Two consequences worth holding, since nothing else will catch them:

- **Platform-divergent code is only ever exercised on the machine you are on.** Several hooks shell
  out to real `git` and branch on Windows vs POSIX, and the three directory-alias tests take a
  junction path on Windows and a symlink path everywhere else (`make_dir_alias`). A green local
  run is evidence about that machine, not about the others.
- **Merging is unguarded.** Nothing blocks a merge on tests, so the local run before opening a PR
  is the only gate that exists.

## Recapping finished work

See `.claude/plugins/cla/output-styles/CLA.md`, "The one recap that stays". The rule lives there,
not here, so it ships to consuming repos with the plugin.

## Architecture — the fact/procedure split

CLA is portable across repos because it strictly separates *procedure* (generic, synced
everywhere) from *facts* (per-repo, never synced):

- **Synced core** — `.claude/plugins/cla/{skills,agents,hooks,output-styles}/`: portable procedure
  only. A conformance guard — `skills/_shared/scripts/check_no_project_tokens.py`, run as a program
  and, in this repo, also invoked as a subprocess by a `plugin-tests/tests/conformance/` test — fails
  if a distinctive project token, or a hardcoded absolute developer path, leaks into synced core — one
  scanner covers `SKILL.md`/`references/*.md` prose under `skills/`, a second covers every `.py` file
  plus `agents/*.md` and `output-styles/*.md` (frontmatter-exempt the same way `SKILL.md`'s own
  `description:` is). The source scanner covers **five** roots — the four synced dirs plus `lib/` —
  because the marketplace ships the whole directory. It was eight until the dev tree moved out; the
  three `*-checks/` entries then named directories that no longer exist, and a stale root is worse
  than a missing one, because the guard refuses to run at all rather than quietly scanning less.
  Two files still fall outside both TOKEN scanners and are watched by hand: the plugin's own
  `README.md` (its install commands legitimately name this repo) and `skills/_shared/README.md`.
  It was four — `run_tests.py` and `mutate.py` were the other two, and neither ships any more.
  The two scanner families do not have the same reach: the hardcoded-path one
  (`plugin-tests/tests/conformance/test_no_hardcoded_plugin_paths.py`) covers
  `.md`/`.py`/`.mjs`/`.json`, so `hooks/hooks.json` and a skill's `.mjs` **are** in scope; the
  project-token one is `.py`/`.md` only. Measured across both families:
  **101 files ship, 96 are reached by at least one scanner, 5 by none** —
  `.claude-plugin/plugin.json`, `.gitattributes` and the plugin `README.md` (all outside every scan
  root), plus `hooks/probe-python.sh` and `hooks/git/pre-push`, which sit inside a scan root but
  carry a suffix (`.sh`) and no suffix respectively that no scanner opens. Listed in TODO.md.
- **Overlays** — `cla.io/overlays/<skill>.md` plus any `*.local.md` files beside them: the
  destination repo's own facts and tuned checks. They live in the repo, not the plugin directory,
  so an install never reaches them. In *this* repo they are neutral stubs (this is the source, not
  a consumer).
- **`cla.io/`** (repo root) — all per-repo state: `decisions/`, `feedback/`, `retro/` run ledgers,
  `lessons-learned/`, `project-tokens.local.md` (the conformance guard's curated token list), and
  (in a consuming repo) a consolidated `project-facts.md` and `terminology.md` (internal naming
  disambiguation, format owned by `sync-context`, written inline by other skills as terms resolve).
  Never part of the synced core; a staleness guard
  (`skills/sync-context/scripts/check_fact_paths.py`) fails when a path named there no longer exists.

### Skill layout

The published plugin — everything here ships to a consuming repo:

```
.claude/plugins/cla/
  .claude-plugin/plugin.json   manifest
  agents/                      doc-sweeper, fact-gatherer (mechanical helpers other skills delegate to)
  hooks/                       guard hooks + hooks.json wiring
  lib/log_run.py               the one ledger writer, invoked as a program
  output-styles/               the project's writing convention (force-for-plugin: true)
  skills/_shared/references/   references two or more skills read as authority (no SKILL.md — not a skill)
  skills/<name>/
    SKILL.md                   the skill itself (portable procedure)
    references/                supporting docs (portable; overlays live in cla.io/overlays/)
    scripts/                   deterministic helpers (stdlib Python)
```

…and the two repo-root trees that do NOT ship, which is where the tests and the release workflow
went:

```
plugin-tests/                  the repo's ONE pytest scope
  pyproject.toml               testpaths, norecursedirs, and the 10-entry pythonpath
  mutate.py                    mutation checker: break a fix, confirm a test fails, restore
  tests/<area>/                conformance, consistency, launcher, hooks, lib, skills/<name>
  mutants/<area>/              mutation batches, mirroring tests/ — a sibling, never a child
  scripts/check_script_drift.py
  node/mechanical-checks.test.mjs
.claude/skills/release/        repo-local skill, invoked as /release (not /cla:release)
  SKILL.md
  scripts/check_shipped_tree.py
```

### Every script, and why it exists

A script earns its place only by doing something a direct command plus a sentence of prose
cannot do reliably. Seven that failed that bar were deleted; these are the survivors, and the
rule going in is the rule going out — **if a script here can't be justified in one line, it
isn't a survivor.** (Guard hooks are listed separately below.)

Shipped scripts are given relative to `.claude/plugins/cla/` and never repeat that prefix — a bare
top-level path (`lib/...`) for a script outside `skills/`, and a
skill-relative path (`<skill>/scripts/...`, no leading `skills/`) for a script that belongs to one,
matching every existing row (`_shared/scripts/git_state.py`, `codify-retro/scripts/codify_aggregate.py`,
`annotate/scripts/*.py`, and so on).

| Script | Why prose can't do it |
|---|---|
| `plugin-tests/mutate.py` *(dev tree)* | Breaks a fix, confirms a test fails, restores byte-exactly — a judgement no reading of the test can substitute for. |
| `lib/log_run.py` | The one ledger writer: validates the record, enforces the 4 KiB atomic-append ceiling, refuses a path-shaped ledger argument. |
| `plugin-tests/scripts/check_script_drift.py` *(dev tree)* | Compares the ledger-dir resolver across the writer and both readers. A divergence is silent — the retro reports zero runs, which reads as a cold start. |
| `sync-context/scripts/check_fact_paths.py` | Existence-checks every repo-relative path the facts file and overlays name, in the *consuming* repo — which has no pytest gate over the plugin cache, so a checker filed as a test is unreachable there. |
| `_shared/scripts/check_no_project_tokens.py` | Four scans in one run over the consuming repo's install (prose tokens, source tokens, absolute developer paths, readability); the readability check is what stops the other three passing vacuously. |
| `codify-retro/scripts/codify_aggregate.py`, `spec-to-pr-retro/scripts/spec_to_pr_aggregate.py` | Deterministic counting over 40–130 JSONL records, including malformed-shape and producer-drift buckets a reader would gloss. |
| `new-worktree/scripts/manual_worktree.py` | Routes around the Windows path-casing refusal, and refuses to remove a worktree holding uncommitted work — where a model slip destroys work. |
| `.claude/skills/release/scripts/check_shipped_tree.py` *(repo-local)* | Enumerates the tracked plugin tree against a 14-pattern allowlist before a tag is cut. `git-subdir` has no exclusion field, and the obvious denylist was measured to miss 7 of 72 dev-only files — including the two runners and the release skill itself. |
| `project-review/scripts/mechanical-checks.mjs` | Cross-file key-set parity from repo-supplied config; hand-grepping it is exactly what it replaces. Configured by 1 of 4 consuming repos today. |
| `annotate/scripts/annotations_store.py` | The annotation corpus: append-only merge rule, tombstones, and a refusal to read past a conflict marker rather than fabricate a corpus from both sides. |
| `annotate/scripts/render_doc.py` | Markdown → an annotatable page whose every block carries a source line, plus the anchor check that says which annotations the last edit orphaned. |
| `annotate/scripts/annotate_server.py` | Serves the page on loopback, validates each record before it reaches the file, and opens a chrome-less browser window. |
| `annotate/scripts/openspec_change.py` | Extracts a change's claims and the links between them, with thresholds measured over 355 real changes rather than reasoned about — the first cut left 83% of promises falsely uncovered. |
| `annotate/scripts/sweep_changes.py` | Runs the link detector over a corpus of real changes and reports the coverage split — the command behind every threshold in `openspec_change.py`, and how a consuming repo re-measures before trusting the coverage tab. |
| `annotate/scripts/render_change.py` | Lays a change's files into one annotatable page, binding each claim to its block one-match-or-none and keeping injected counterparts outside the blocks whose offsets they would corrupt. |
| `spec-to-pr/scripts/probe_state.py` | Resume detection across `openspec status`, `gh`, and `<base>..<branch>` ranges, with branch-resolution fallback. |
| `_shared/scripts/git_state.py` | One deterministic exit code for "an in-progress rebase/cherry-pick/merge exists", checked at every commit boundary across four skills. |
| `spec-to-pr/scripts/_git_common.py` | Repo root plus the `branch-prefix.local.md` overlay contract, for `probe_state.py`. |

### Skills by life-cycle phase

Every shipped skill is invocable as `/cla:<name>` or by natural language, and Claude Code already
surfaces each one's name and description — so the full phase table lives in
`.claude/plugins/cla/README.md` rather than being restated here. **One skill is not shipped and
carries no namespace:** `release` acts on the plugin's own *distribution* — it edits the repo-root
marketplace catalog and cuts `cla--v<version>` tags — so it is repo-local at
`.claude/skills/release/` and is invoked bare as `/release`. A consuming repo has nothing for it
to act on, which is why it does not ship rather than shipping and doing nothing. The arc it maps: bootstrap → discover & shape → specify & plan →
build & ship → review & assure → learn & improve, plus phase-agnostic utilities.

Typical flows: small change → `shape-decision` → `lite-pr`; larger → `shape-decision` →
`multi-spec` → `review-change` → `spec-to-pr`; a batch off one decisions doc → `multi-lite` or
`multi-pr`.

### Guard hooks (conventions enforced, not just advised)

Wired automatically by `hooks/hooks.json` when the plugin loads — these apply in this repo's own
sessions too. Two dispatchers run 7 leaf hooks between them; `warn-wholesale-rewrite` and
`log-commit-provenance` are wired directly on PostToolUse, making 9 leaf hook files in all. Three
severities: **blocks** stop the call, **asks** escalate to a permission prompt, **warns** let it
through with a caution. Full enumeration and the rationale per hook:
`.claude/plugins/cla/README.md` and DEVELOPER-GUIDE §8.

**No direct push to main/master** is enforced by `hooks/git/pre-push`, NOT a PreToolUse hook — git
hands it the already-resolved refspec, so no command spelling evades it and terminal/IDE pushes are
covered too. A plugin cannot write to `.git/hooks`, so **install it once per clone**:

```bash
cp .claude/plugins/cla/hooks/git/pre-push .git/hooks/pre-push && chmod +x .git/hooks/pre-push
```

### Portability

Distribution is the GitHub marketplace and nothing else. A consuming repo installs the plugin as a
versioned snapshot pinned to an exact release tag, and picks up newer releases with
`/plugin marketplace update` — there is no per-file reconcile, and the install never writes
anywhere in the consuming repo outside the plugin cache.

Portability is therefore carried entirely by the fact/procedure split rather than by a merge
algorithm: the whole plugin directory ships verbatim, and everything repo-specific lives in the
consuming repo's own `cla.io/` tree (overlays, `project-facts.md`, `project-tokens.local.md`,
ledgers), which no install touches. Onboarding a fresh consuming repo: install from the
marketplace → `cla-init` (scaffold `cla.io/`) → `sync-context` (populate the facts).

A local improvement worth having everywhere goes upstream as an issue via `/cla:report-upstream`
and comes back in the next release — the deleted `update-cla` engine's per-asset multi-sourcing has
no replacement, by design.
