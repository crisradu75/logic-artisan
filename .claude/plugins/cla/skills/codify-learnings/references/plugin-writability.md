# Is the plugin writable here? — the check, and what each answer means

Shared reference. Cited by `codify-learnings`, `codify-retro`, `spec-to-pr-retro`
and `sync-context` — every skill that might otherwise propose an edit to a file
inside the plugin.

## Why this needs a check rather than an assumption

The plugin lives in one of two places, and they behave oppositely:

- **Loaded from a working tree** (`--plugin-dir`, how the harness's own source
  repo runs) — inside the repo, tracked by git, writable, and an edit is a real
  change you can commit.
- **Installed from a marketplace** (how every other repo runs it) — a
  **read-only, version-keyed cache** outside the repo entirely. An edit there
  either fails, or lands in a directory the next `/plugin update` discards.

The second case is the dangerous one, because a failed edit is not obviously a
failure: the suggestion reports as applied, the user believes the lesson landed,
and it is gone at the next update with nothing to show it ever existed.

## The check

The two cases differ in one stable, observable way: **a working-tree plugin sits
INSIDE the repo; an installed one does not.** Nothing else about the layout is
guaranteed — cache paths are an implementation detail and may change.

1. Resolve the repo root: `git rev-parse --show-toplevel`.
2. Resolve the plugin root — take the absolute path of any file you have already
   read from the plugin (a `SKILL.md`, or a `references/` file such as this one)
   and cut it at the `.../plugins/cla` segment.
3. **Is the plugin root inside the repo root?**
   - **Yes → writable.** You are in the harness's own source repo.
   - **No → read-only.** The plugin is installed; treat every file under it as
     unmodifiable.

If you cannot establish either path, treat it as **read-only**. That is the safe
default: the cost of wrongly assuming read-only is one unnecessary upstream
issue; the cost of wrongly assuming writable is a silently discarded edit.

## What each answer permits

| Target | Writable | Read-only |
|---|---|---|
| `cla.io/**` (overlays, facts, ledgers, decisions) | edit | **edit** — repo content either way |
| Repo `CLAUDE.md`, `.claude/settings*.json` | edit | **edit** — repo content either way |
| User memory | edit | **edit** — outside both |
| `skills/**/SKILL.md`, `references/**` | edit | **`/cla:report-upstream`** |
| `hooks/**`, `lib/**`, any plugin script | edit | **`/cla:report-upstream`** |

**Read-only does not mean "drop the lesson".** It means the lesson goes where it
can actually take effect. A fix to portable core, written into a local overlay to
make it stick, reaches no other repo and does not change the prose that produced
the miss — so the same lesson is re-learned here next run, and independently in
every other repo. Route it to `/cla:report-upstream` and say in the routing line
that it is going upstream rather than being applied here.

A lesson that is genuinely about **this repo** is not affected by any of this:
`cla.io/overlays/<skill>.md` is the right home for it, and is writable in both
cases.
