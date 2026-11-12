Detail for the start of Part 2 of `SKILL.md`: where a fact goes, what `cla.io/project-facts.md` holds, and the terminology file. Moved verbatim from `SKILL.md`.

### Where a fact goes

- **`cla.io/project-facts.md` holds the repo's facts** — every command (install, dev, build, lint,
  test), path, port, workspace member, file map and env file the skills read. A skill looks there
  for them and nowhere else.
- **`cla.io/overlays/<skill>.md`, when present, holds only that skill's own rules** — a check, a
  limit or a preference for one skill in this repo — **with any path or command only that rule
  uses** (where codify-learnings finds memory, the files a review-change check opens). Optional; a
  skill without one runs on its generic procedure.
- **A dated incident's story goes to `cla.io/lessons-learned/`, and any rule it states stays in the
  overlay** as one or two lines, since most skills never read the lessons log. One that would
  happen in any repo goes upstream through `/cla:report-upstream`.
- **Machine-read `*.local.md` files stay where they are and are never reshaped here:**
  `cla.io/overlays/branch-prefix.local.md` (spec-to-pr's branch prefix),
  `cla.io/project-tokens.local.md` (the token guard's list) and `cla.io/fleet.local.md` (this
  machine's list of repos for `/cla:spec-to-pr-retro`).

`cla.io/project-facts.md` holds, under headed sections (omit one that does not apply; add one for any
other repo-wide fact you find):

- **Workspace shape** — the workspace member list (apps/packages/services and their one-line roles),
  derived from the repo's own workspace manifest (e.g. `pnpm-workspace.yaml` + each `package.json`
  name, a Cargo workspace's `Cargo.toml`, a Go module's `go.work`, or whatever this repo actually uses
  — read the real manifest, never assume a stack).
- **Dev / build / test commands** — the repo's dependency-install command, and its dev/build/lint/test
  invocations (from its root manifest's scripts/tasks), including any workspace-wide fan-out and any
  suite deliberately excluded from the default aggregate (and why, and what it needs to run).
- **Ports** — every fixed local-dev port tied to a specific process, and what runs on it.
- **Affected-file map** — the per-change-type file lists reviewers use to identify what a change of a
  given shape touches.
- **Doc-sweep paths** — the fixed list of docs outside `openspec/` that any change should keep in
  sync (root guidance doc, per-subapp guidance docs, README, docs tree). A change's docs task and
  the Review and Revise docs checks read it.
- **Cross-file lockstep doc sets** — any set of files that must be updated together whenever a specific
  piece of core logic changes.
- **Test-file locations** — unit/integration/e2e/smoke test locations, including any excluded from the
  default aggregate.
- **The i18n layers** (if the repo has translated user-facing text) — each layer's file paths and
  whether they are independent of one another.
- **Env files** — gitignored env files tied to a specific local process, and which var(s) they carry
  that matter to a caller (never the secret VALUES — only paths/names).
- **Infrastructure** — local services a gate needs (a database stack, a container engine), the
  command that reports whether they are up, and whether the dev environment is shared across branches.
- **Dataset / data locations** — any committed mock/reference dataset a core computation loads from.
- **Test proof granularity** (a repo with `openspec/` only) — whether its tests prove each
  requirement (the default) or each scenario. Ask the user once, with the default recommended, and
  write exactly one line under a `## Test proof` heading: `- Test proof granularity: requirement`
  or `- Test proof granularity: scenario`.
  `${CLAUDE_PLUGIN_ROOT}/skills/_shared/scripts/check_spec_proof.py` reads that line and exits 2 on
  any other form, so never reword or merge it. A reconcile keeps an existing line as written.
- **Full gate** (optional, only for a repo whose full gate is slow) — never proposed by default.
  When the user asks for one full run on the final commit, write the line
  `- Full gate: final-commit-only`; `/cla:spec-to-pr` Test then runs smoke and touched tests only, and the one full gate runs after Archive.
  A reconcile keeps an existing line as written.
- **Spec map** (a repo with `openspec/` only, and only if the user takes the offer in "The spec map
  scaffold") — the path or glob of the file that maps the repo's capabilities and workflows to its
  specs, one bullet per path under a `## Spec map` heading, any layout. `check_spec_proof.py` reads
  it and exits 2 on a heading with no bullet, a line that is not a bullet, or a heading that reads as this one in another form (`### Spec map`). Never write the
  heading when there is no map, and never invent a path: a reconcile keeps an existing section as
  written.
- **Worktree convention** — where this repo puts worktrees, if it has a rule.

**Keep it terse: one fact per line, under its `##` section.** Skills that cite a section read the
whole file, so every line is paid on each read. A list-valued fact (an affected-file map) stays a
list.

### The terminology file (`cla.io/terminology.md`)

What it holds and its entry format are in
`${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/terminology-format.md`. Other skills write it
inline as terms resolve; this skill never creates it and only reconciles it (item 11).
