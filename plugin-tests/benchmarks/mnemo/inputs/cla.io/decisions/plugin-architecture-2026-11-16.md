# Decision 2026-11-16: mnemo plugin architecture and technology

Topic: architecture and technology for the `mnemo` plugin (packaging of skills, shared conventions, hooks and checks; runtime; testing; release). Made with `/cla:shape-decision` on 2026-11-15/16.

Grounded in: this repo's `CLAUDE.md`, `.claude/rules/cla-economy.md`, `cla.io/project-facts.md`, `README.md`, `marketplace.json`, `plugin.json`; and in `crisradu75/research`: `cla.io/decisions/2026-11-15-mnemo-design.md` and `mnemo/build-guide/build-guide-report.md`. This decision changes parts of that report (see Follow-ups).

## Questions and choices

| Q | Question | Chosen | Why |
|---|---|---|---|
| Q1 | Where do the checks (links, schema, deletions, secrets; there is no `index.md`, see structure decision Q11) live and run? | Inside `plugins/mnemo/`. They run only in the Claude Code session on the repo, never on GitHub machines. No `mnemo-core` repo. (Location replaced by Q12–Q14: the source is `mnemo-plugin/mnemo/scripts/` in `mnemo`, and each domain repo runs its copy at `.claude/mnemo/scripts/`. Still never on GitHub.) | The plugin packages everything required; nothing runs on GitHub |
| Q2 | What makes sure checks run before a push? | Skills run them, plus a plugin hook on `git commit` / `git push`. (Replaced by Q12: the hook is wired in each domain repo's `.claude/settings.json`, written by `mnemo-setup`, not in a plugin's `hooks/hooks.json`.) | Catches commits made outside a skill |
| Q3 | What happens when a check fails before a capture commit? | Block; Claude fixes and retries once; then saves to `inbox/` and says so | `main` stays valid and no capture is lost |
| Q4 | Language for hooks and checks? | Python 3, standard library only, reading a simple YAML subset (`key: value`, inline lists). Schema files use two-level block style (no inline maps), so the report's inline-map example does not apply. The spec lists the exact grammar, and `unittest` cases cover values containing `:` and quotes | Nothing to install; runs on Mac, Windows and the cloud VM |
| Q5 | Chat support and shared-file packaging? | Claude Code only, not chat. Shared files exist once in the plugin; skills point to them. Each skill starts with a guard: no `mnemo.schema.yml` in the repo → say so and stop. (Packaging replaced by Q12–Q14: one source in `mnemo`'s `mnemo-plugin/`; domain copies are generated and refreshed only by `mnemo-setup`, never hand-edited. The guard stays.) | Chat can't save or search; the guard covers non-Mnemo cloud sessions where the account plugin also loads. (Reason replaced by Q11: there is no account plugin. The guard stays as a cheap safety net: a skill copy can run while the session's working folder is another repo, such as a second attached repo or a scratch clone, or in a repo whose schema was removed.) |
| Q6 | How does a session get the schema and conventions? | `@mnemo.schema.yml` and `@_meta/conventions.md` in each domain `CLAUDE.md`, written by `mnemo-setup` (renamed by the structure decision, Q2). No SessionStart hook | Built-in feature, no hook. If `@` doesn't import `.yml`, rename the schema to `.md` |
| Q7 | How is nothing lost before push? | Skills commit their own writes (recall only appends its query-log line, and the Stop hook commits and pushes it; changed by the self-improvement decision, Q9); an end-of-turn (Stop) hook is the backup, no-op outside Mnemo repos, loop-safe. Clarification made after review: the Stop hook calls `mnemo_check.py save` (structure decision Q13), which runs every check on changed files, `secrets` included, before committing; if a check fails it commits nothing and prints why; on success it pulls with rebase, commits and pushes right away (structure Q12) | Same pattern as Q2; a reclaimed VM loses uncommitted files and unpushed commits |
| Q8 | Improvement loop (rule location, loop PRs) | Out of scope for this decision | User's call |
| Q9 | Testing before merge? | Python `unittest` for hooks and checks; 20 trigger prompts via `claude plugin eval`, pass mark 18 of 20; `claude plugin validate`. All local. (Tools replaced by Q14: `claude plugin validate` becomes a `unittest` that checks the layout of `mnemo-plugin/`; `claude plugin eval` becomes trigger tests that run `claude -p` against a scratch domain repo holding the copied skills. The 20 prompts and the 18-of-20 pass mark stay.) | Enforces the decided pass mark |
| Q10 | How does a change reach sessions? | Release tags: `marketplace.json` points at a tag; release = tag, then move the pointer. (Pointer replaced by Q12–Q14: a release is still a tag on `mnemo`, now `v<semver>`, with the same version in a root `VERSION` file. `mnemo-setup` copies the shared files in `mnemo-plugin/` from a named tag into a domain repo, and records that tag in the domain's stamp file, `.claude/mnemo/stamp.json`. A refresh reaches a domain through a PR that shows the old and new version. There is no pointer and no `marketplace.json`.) | User chooses when sessions get a change. The review proposed "a version bump is the release"; the owner kept tags. Still true: a domain gets a release only when the owner merges its refresh PR |

## Changed 2026-11-16: project-level install, copied into each repo

Owner decisions made after the first pass, once the cloud docs were read. They replace every earlier text that assumed an account-level or plugin install; that text is marked "(replaced by Q11–Q14)" in this file, in `plugin-structure-2026-11-16.md` and in `recursive-self-improvement-2026-11-16.md`.

Repo rename (owner, 2026-11-16): the GitHub repo `crisradu75/mnemo-plugin` is now `crisradu75/mnemo`. In these records `mnemo` names the repo, and `mnemo-plugin/` (with the slash) names the shipped folder at its root. The local clone folder may keep its old name.

Evidence (Claude Code docs, code.claude.com, fetched 2026-11-16):
- cloud-environments: "A cloud session doesn't install the plugins a repository turns on under `enabledPlugins`, including ones from the marketplaces it lists under `extraKnownMarketplaces`."
- plugins/loading: adding them "requires the workspace trust dialog, which a cloud session never shows".
- Locally, a project plugin loads only after the folder is trusted plus `claude plugin install <name>@<marketplace> --scope project` once per clone.
- Skills committed to `.claude/skills/`, and hooks and permissions in `.claude/settings.json`, do load in cloud sessions ("Part of the clone").

| Q | Question | Chosen | Why |
|---|---|---|---|
| Q11 | At what level is Mnemo installed? | Only at project (repo) level, never at user or account level. No account plugin and no `@synced` plugin | Cloud sessions do not install repo-enabled plugins, and an account plugin also loads in every non-Mnemo session |
| Q12 | How does a domain repo get Mnemo? | Copy into each repo. `mnemo` is the single source. Each domain repo carries a copy of the shared files: the skills (`.claude/skills/mnemo-*`), and the check script, conventions and probe (`.claude/mnemo/`). Setup also generates the per-domain files: the hook wiring in the domain's `.claude/settings.json`, and a stamp file, `.claude/mnemo/stamp.json`, that records the tag the copy came from, a hash per copied file, and the issue target (`repository`). Refreshing a copy after a release goes through a PR in the domain repo, as structure Q5's no-overwrite rule requires | It works in cloud, on the phone and locally, with no plugin install or trust step for the plugin. The research report's fallback, "commit capture and recall to each repo's `.claude/skills/`", is now the main path |
| Q13 | Where does `mnemo-setup` run? | From a session on `mnemo`. It lives in `mnemo`'s own `.claude/skills/mnemo-setup/`, not in `mnemo-plugin/`, so it is never copied. It targets one domain repo, attached to the session (cloud) or given as a clone path (laptop). It does the first install (the shared files from `mnemo-plugin/`, plus the per-domain files it generates) and later refreshes (by PR). This revises structure Q2's "works on the repo it runs in" | `mnemo` holds no notes, so no domains mix. A setup session is not a domain session, so it needs no exception to the domain wall (self-improvement Q10) |
| Q14 | How is `mnemo` packaged? | No plugin or marketplace packaging. `mnemo` is a plain source repo, holding three things: `mnemo-plugin/`, `mnemo-setup` in its own `.claude/skills/`, and tests and evals at the root. `mnemo-plugin/` is one shared set of files (the Mnemo skills, the check script, the base schema in `conventions/`, the Python probe and the guard dispatcher `guard_git.py`), identical for every domain, which `mnemo-setup` copies into each domain repo's `.claude/`. Its folder shape matches the destination path (`mnemo-plugin/skills/...` → `.claude/skills/...`, `mnemo-plugin/mnemo/...` → `.claude/mnemo/...`). The folder is `mnemo-plugin/` at the root of the `mnemo` repo. The name is the owner's choice, even though it is not a Claude Code plugin; nothing installs it as one. Per-domain files never live in `mnemo-plugin/`; setup generates them: `CLAUDE.md`, `mnemo.schema.yml`, the folders, the hook wiring in `.claude/settings.json`, and the version stamp. `.claude-plugin/marketplace.json` and `plugins/mnemo/.claude-plugin/plugin.json` are removed by the first implementation change (`add-check-scripts`). The version is the git tag `v<semver>`, with the same version in a root `VERSION` file that every PR changing `mnemo-plugin/` or `mnemo-setup` bumps. `claude plugin validate` becomes a shipped-layout `unittest`; `claude plugin eval` becomes trigger tests that run `claude -p` against a scratch domain repo with the copied skills | Nothing installs Mnemo as a plugin any more, so the packaging has no reader. A version file and tags are enough for the stamp and the release tests |

## Noted, not asked

- **Reversibility:** one user, private repos, all in git. Skill names and base-schema fields are already fixed by the design.
- **Outside service:** not applicable; the plugin adds no vendor call.
- **Loop rule location; loop PRs vs OpenSpec and version-bump rules:** declined (Q8).
- **Release tags are created from the Mac or GitHub's web page:** Anthropic's proxy blocks tags in cloud sessions (build-guide report, Skills section).
- **Unverified, to confirm in the spec step:** `@` import of a `.yml` file; ~~`claude plugin eval` fits the trigger tests~~ (dropped: replaced by Q14, the trigger tests run `claude -p`); Python 3 present in the cloud VM; ~~claude.ai plugin sync follows a tagged `ref` in `marketplace.json`~~ (dropped: replaced by Q11–Q14, there is no plugin sync or pointer).
- **Checks to run before the scaffold spec (device test 2, extended):** PreToolUse and Stop plugin hooks run in cloud sessions (the only source covers SessionStart); `git push` runs without a prompt in Accept-edits or Auto mode. If plugin hooks don't run in cloud sessions, the fallback is decided after that test. The report's fallbacks (an Actions fast-forward, repo-level skills) are both ruled out by this decision. (Replaced by Q11–Q14. The checks are now: repo-committed hooks in a domain repo's `.claude/settings.json` run in a cloud session and block a bad commit (device test 2); skills in `.claude/skills/` load in cloud sessions (the docs say yes, so the device test only confirms); a cloud session with `mnemo` and a domain repo attached can write and push to the domain repo, for setup (Q13); local Windows hooks run through Git Bash; Python 3 is present in the cloud VM; `git push` runs without a prompt in Accept-edits or Auto mode. The repo-level-skills fallback is now the main path (Q12); the Actions fast-forward stays ruled out.)

## Invariants

- No check or workflow runs on GitHub.
- A commit Claude makes through Bash, in a session where the plugin loaded, never lands on `main` with failing checks; the capture lands in `inbox/` instead. Commits from GitHub's web editor, a clone without the plugin, or GitHub API tools are not covered; `mnemo-review` checks after the fact. (Replaced by Q12: "in a session on a domain repo that carries the Mnemo copy". Not covered: GitHub's web editor, GitHub API tools, a clone without the copy, and sessions on another repo, such as a setup session on `mnemo`.)
- Every skill stops when the repo has no `mnemo.schema.yml`.
- Hook and check scripts import only the Python standard library.
- Shared files (base schema, scripts) exist once in the plugin. (Replaced by Q12–Q14: one source, `mnemo-plugin/` in `mnemo`. Domain copies are generated and refreshed only by `mnemo-setup`, never hand-edited, and a check detects drift: a copied file that differs from its stamped hash.)
- Every plugin PR bumps `version`; a tagged commit's `version` equals the tag. (Replaced by Q14: every PR that changes `mnemo-plugin/` or `mnemo-setup` bumps `VERSION`; `VERSION` at a tag equals the tag; a domain copy's stamp equals the tag it was copied from.)
- No note content in this repo.

## Final axes

All Clear: reversibility (Noted), downstream consumers (Q1, Q5), release (Q10), smaller option (Q1, Q6), edge cases (Q4, Q5, Q7, Noted), design elegance (Q5, Q6, Noted), invariants (Noted), check location (Q1), conventions packaging (Q5), runtime (Q4), enforcement (Q2, Q3), loop PRs (Noted), test technology (Q9).

## Follow-ups

- Reword device test 2 (research issue #72) to "a bad commit in a cloud session is blocked"; the SessionStart line it checked no longer exists. (Since Q12 the hooks it watches are the repo-committed ones in a domain repo's `.claude/settings.json`.)
- ~~`CLAUDE.md`: remove the "skills must also load in claude.ai chat" rule.~~ Done in PR #3.
- ~~`README.md`: replace the pinning note with the release-tag flow.~~ Done in PR #4, with the copy-and-refresh flow of Q12–Q14.
- Research design file: record that GitHub CI, `mnemo-core` and the SessionStart hook are dropped, and chat is out.
- Research design file and report: record Q11–Q14 (project-level copy, setup run from `mnemo`, no plugin packaging), and that the report's `.claude/skills/` fallback is now the main path.
- Q14's file moves and removals (`mnemo-plugin/`, `VERSION`, deleting `marketplace.json` and `plugin.json`) and the matching `CLAUDE.md` and `cla.io/project-facts.md` updates: an early task group in `add-check-scripts`, not this docs PR.

## Why it matters, and next step

It fixes the plugin's shape before the first skill is written: one self-contained source, checks enforced locally by hooks, Python stdlib, local tests and tagged releases. Since Q11–Q14, each domain repo carries a stamped copy that `mnemo-setup` installs and refreshes. Next: `/opsx:propose` a scaffold change (hooks, check scripts, test harness, guard line, ~~release-tag `marketplace.json`~~ the `mnemo-plugin/` move and `VERSION`), then `/cla:spec-to-pr`, or `/cla:multi-spec` on this file to split it into several changes.
