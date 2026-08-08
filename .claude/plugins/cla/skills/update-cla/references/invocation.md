# invocation — full command reference, required environment, flags, portability, onboarding fallback

## Invocation

```
/cla:update-cla <source-repo> [asset-path]
```

- **`source-repo`** (required) — absolute path, `~`-prefixed path, or a short name resolved via `~/.claude/sync-config.json`'s `repos` map.
- **`asset-path`** (optional) — single file, directory, or glob under `.claude/plugins/cla/` to limit scope. Defaults to all of `.claude/plugins/cla/`. Examples:
  - `.claude/plugins/cla/skills/codify-learnings/`
  - `.claude/plugins/cla/skills/foo.md`
  - `.claude/plugins/cla/skills/*.md`

The script reads source from `<source-repo>` and writes to **CWD** (the local destination). For non-CWD destinations, pass `--local <path>` explicitly.

## Required environment

- **`git`** — always.
- **`gh` CLI** — only if you opt into `--mode pr`. `worktree` mode (the default) needs no `gh`.
- **`~/.claude/sync-config.json`** — optional. Used to resolve short-name source-repo arguments to absolute paths. Schema:
  ```json
  { "repos": {"claude-plugins": "~/OneDrive/Documents/Code/claude-plugins"} }
  ```
  If the user passes an absolute path as `<source-repo>`, no config is needed.

**`ANTHROPIC_API_KEY` is NOT required.**

## Flags

| Flag | Default | Purpose |
|---|---|---|
| `<source-repo>` (positional, `discover`) | required | Source repo path or short name. |
| `<asset-path>` (positional, `discover`) | none (= all of `.claude/plugins/cla/`) | Limit scope to a file, directory, or glob under `.claude/plugins/cla/`. |
| `--local <path>` | CWD | Destination repo path. Override when invoking from outside the destination. |
| `--mode worktree\|pr` | `worktree` | Phase 3 application mode. |
| `--run <RUN-ID>` (`apply`) | required | Selects which discover/adapt batch to apply. |

## Portability

The skill is **structurally portable**:
- Scripts are Python stdlib only — no `pip install`.
- No hardcoded repo paths; source and local repos are passed in.
- `~/.claude/sync-config.json` is user-global, shared across all copies.
- **`.claude/plugins/cla/.cla-sync-lock.json` is per-repo, not global** — unlike `sync-config.json`, it lives inside (and is committed with) each destination repo, since its content is specific to that repo's own sync history. Per-asset `source` provenance means the lockfile itself is also source-agnostic: it never assumes a single canonical upstream, so it works the same whether this repo pulls everything from one hub or different assets from different sibling repos.
- Two deployment styles work equally:
  - **Per-repo copy.** Drop `.claude/plugins/cla/skills/update-cla/` + `.claude/plugins/cla/skills/update-cla.md` into each repo. Invoke via slash command. (Caveat: N copies drift — same problem this skill solves, applied to itself. To sync the skill itself across repos, run it against itself from each destination: `/cla:update-cla <canonical-repo> .claude/plugins/cla/skills/update-cla/`.)
  - **Single canonical install.** Keep the skill in one repo. From any CWD, run `python3 /abs/path/to/scripts/orchestrate.py discover <source> --local <destination>` — no slash-command ergonomic, but zero drift.

## Onboarding-order fallback detail

**Onboarding order — `cla-init` → `/cla:sync-context` → `update-cla`.** `update-cla` syncs only the portable asset core and **never creates or populates project data**. When onboarding a fresh repo, run **`/cla:cla-init` first** to scaffold the `cla.io/` tree (retro ledgers, feedback inbox, lessons-learned log, decisions dir) and the per-skill `references/project-context.md` overlay stubs, **then `/cla:sync-context`** to populate the fact *content* — the consolidated `cla.io/project-facts.md` (repo-wide facts shared across skills: workspace members, commands, ports, the affected-file map, doc-sweep paths) plus the one-line pointers in per-skill overlays — **then `update-cla`** to sync/adapt the portable asset core. Skipping `cla-init` leaves the `cla.io/` tree and overlay stubs missing, so the retro/feedback/learnings skills degrade or fail on first use; skipping `/cla:sync-context` leaves `cla.io/project-facts.md` absent, so every skill that reads it gracefully falls back to its own per-skill overlay instead — `update-cla` will not create or populate either for you. `/cla:sync-context` is also self-sufficient (it creates `cla.io/` and `project-facts.md` if either is missing), so running it alone on a fresh repo works too — it just leaves the retro/feedback ledgers and skill-specific overlay stubs unscaffolded, which is still `cla-init`'s job.

## Scanned trees / manifest note

The scanned trees are the plugin core — `.claude/plugins/cla/skills`, `.claude/plugins/cla/agents`, `.claude/plugins/cla/hooks`, and `.claude/plugins/cla/output-styles` (`SCAN_DIRS` in `scripts/discover.py`). The `.claude-plugin/` manifest is synced by hand; the per-repo project overlay (`project-context.md` / `*.local.md`) is preserved, never synced (non-negotiable rule 5).

**Four repo-root files are also in scope, by name** (`SCAN_FILES`): the launchers `cla`, `cla.cmd`, `claw`, `claw.cmd`. Only those four — a general root scan would drag in the consuming repo's own `README.md`, `package.json` and everything else.

They were hand-carried for their whole life, and the bill arrived at once: `claw.cmd` shipped broken on Windows, three consuming repos each diagnosed and fixed it independently, and none of those fixes could flow anywhere. Two of the three still carried a separate bug that a fourth had already fixed. The objection to syncing them had been that they encode a per-repo choice (the `--model`/`--effort` a session launches with) — measured across all four repos, every one was `--model sonnet --effort medium` and the POSIX `claw` was byte-identical. The customization the argument protected did not exist, and rule 1 already covers a repo that later wants one: an edited launcher classifies `local-advanced` and is kept, like any other asset.

**One manual step, once per new adopter.** `apply.py` writes file *content*, not file *mode*, so a repo receiving `claw` or `cla` for the first time gets it non-executable and `./claw` fails on macOS/Linux:

```bash
git update-index --chmod=+x claw   # and cla, if new
```

A repo that already tracks the file keeps its existing mode when the content is overwritten, so this bites once and never again. It is documented rather than solved because reading and writing a git index mode from `apply.py` would mean shelling out to git in both the source and the destination — real machinery in the highest-blast-radius part of the sync, for a one-time step.

**Line endings need a second one-time step, in the DESTINATION.** Earlier wording here claimed they needed none, because "this repo's `.gitattributes`" pins them — true while you are reading it in the source, and false the moment it syncs, since "this repo" is then the consumer. One consuming repo had no `.gitattributes` at all: `git check-attr text eol` reported `unspecified` for all four launchers, `core.autocrlf=true` governed instead, and **both POSIX scripts were checked out CRLF-only** — exactly the CRLF-shebang shape the claim said was prevented. On macOS/Linux `#!/usr/bin/env bash\r` fails as `env: 'bash\r': No such file or directory`.

A repo receiving the launchers needs:

```gitattributes
cla        text eol=lf
claw       text eol=lf
cla.cmd    text eol=crlf
claw.cmd   text eol=crlf
```

`git add --renormalize` alone will not apply it: the index blobs are already LF, so it is a no-op and git's stat cache leaves the working copy untouched. Force the rewrite with `rm cla && git checkout -- cla` (and the same for `claw`).

## When NOT to use (full detail)

- *Other* installed plugins' internal assets (a third-party `{plugin}/commands/`, `{plugin}/skills/`) — those are that other plugin's published contract, not cla's; out of scope. This skill syncs only cla's own `skills`/`agents`/`hooks`/`output-styles` tree (`SCAN_DIRS` above), never a sibling plugin's.
- `.claude/settings.json` — project-level config, legitimately per-repo, out of scope. **Hook note:** the guard hooks live in `.claude/plugins/cla/hooks/` and are wired by the plugin's own `hooks/hooks.json` (auto-active when the plugin loads via `--plugin-dir`) — unlike the old `.claude/hooks/` model, there is NO manual `settings.json` wiring step to remember. The one exception is the project-specific operator-stack SessionStart hook, which stays wired in the destination's `.claude/settings.json` by hand.
