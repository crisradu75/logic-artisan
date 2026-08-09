# Adaptation guide

Reasoning rubric for Phase 2. You (conversation Claude) read `divergences.json`
and for each file produce an entry in `adaptations.json`. You are running
**inside the local destination repo** — its `CLAUDE.md`, plugins, skills, and
conventions are natively available; read whatever you need.

## Inputs per file

From `divergences.json`:
- `source_content` — the canonical version from the source repo.
- `local_content` — the existing local version (or `null` for new files).
- `status` — the file's provenance classification: `divergent` (local exists, differs, no lockfile ancestor), `adapted` (neither side moved since the last sync — they differ only because the adoption was adapted → keep local, nothing upstream to pull), `source-advanced` (local untouched AND source genuinely moved → adopt, re-applying the local adaptation rather than taking raw source verbatim), `local-advanced` (source unmoved since last sync but local advanced → keep local; source would regress), `both-diverged` (both changed → careful manual reconcile), or `new` (local missing). Handle each per the Phase-2 classification guidance in `references/phases.md`.

From the local repo (read directly):
- Top-level `CLAUDE.md` and any plugin/skill-local `CLAUDE.md` along the asset's path.
- Existing sibling skills/commands for naming and structural conventions.
- `plugin.json` / `pyproject.toml` / `package.json` if relevant.

## The non-negotiables

**1. Preserve local strengths.**

When the local version has content the source lacks — a workflow step source
doesn't cover, a local-specific reference, a refinement the local author made,
a workaround for a local quirk — *keep it*. Default merge stance is **additive,
not overwrite**. Only drop local content when the source explicitly supersedes
it:

- Source has a new section that replaces the local one's purpose entirely.
- Source deliberately removes a feature/flag the local version still has (this
  is rare — when in doubt, keep the local feature and flag it in your summary).

**2. Adapt for local context.**

- Swap plugin names, paths, and example references to match the destination.
- Swap tool references when the local stack differs (e.g., pytest vs jest).
- Preserve local heading style and terminology where they diverge from source
  cosmetically (the source's "## Steps" stays "## Workflow" if that's what
  this repo uses elsewhere).
- Apply the additive-merge rule to frontmatter too: preserve any local
  frontmatter field the source lacks (local `argument-hint` stays if source
  omits it), and adopt source frontmatter improvements (richer `description`,
  new `argument-hint`) only when they don't drop a local field. Rewrite the
  prose body to match local conventions.

**3. When local is a re-specialized fork, cherry-pick — don't adopt.**

If the local file and the source both descend from a common asset but each was
re-specialized to its own repo, the source is a *sibling fork*, not an upstream
baseline. Symptoms in the diff:

- It's dominated by convention swaps that REVERSE local choices — branch
  prefixes (`claude/feature/` ↔ `feature/`), directory scopes (`src/` ↔
  `<plugin>/`), plugin names, permission-pattern style (`Bash(git:*)` ↔
  `Bash(git *)`), version-bump targets.
- Source *deletes* content that is a deliberate local strength (a
  platform-specific fix, an extra verification step).

When you see it, do NOT overwrite. Treat source as a **menu of portable
improvements to cherry-pick**: take only genuinely new general-purpose content
(a real bug fix, a section covering a case local lacks), **re-adapt it to local
conventions** before writing, and keep everything else local. A file whose diff
is *all* convention-reversal has nothing to pull — leave it untouched and say so
in the `change_summary`. Overwriting a fork with its sibling is the failure
mode, not the goal.

**4. A synced SCRIPT's environmental premise must be checked, not assumed.**

Applies only to executable scripts (Python/JS/shell under a skill's `scripts/`
or `hooks/`), not prose/docs. A script often assumes something about the
destination repo's environment — a root `package.json`, an interpreter name, a
particular directory shape — and that assumption can be quietly wrong here even
though the script itself adapts cleanly (no local content to preserve, no
syntax problem, every test green). Check: would this script's discovery/gate
actually produce output in *this* repo, or would it silently return empty? A
script whose premise fails locally still needs to land (removing a portable
capability outright is its own regression), but the failure must be **reported
in `change_summary`**, not adopted silently — the same "trust but verify"
standard applied to every other adapted file, extended to a script's runtime
behavior rather than only its text.

This is a recurrence, not a hypothetical: `discover_tests.py` arrived assuming
a root `package.json`. In a repo with none, both its discovery tiers return
empty forever, and the Test phase reports `skip` with a *wrong* reason — a
silent gate rather than an honest "this check doesn't apply here". The same
script's premise had already failed once before (then it assumed a root
`pyproject.toml`), so this is the second occurrence of the identical failure
shape arriving through the same file.

## Do not

- Rename symbols/variables/functions unless forced by local context.
- Add scope or features not present in source OR local.
- Strip sections from source unless they reference something genuinely absent
  in local (e.g., a skill that doesn't exist here).

## Output

Append one entry per file to `adaptations.json` — **every file in `divergences.json`'s `files[]`, without exception**. A file you are deliberately NOT rewriting (a `local-advanced` or `adapted` you are keeping) still needs an entry: give it `"keep_local": true` and omit `adapted_content`. `apply` diffs the two lists and reports anything discovered-but-absent under `NOT ADAPTED`, then exits 1 — because a silently dropped entry is written nowhere, surfaces nowhere, and leaves the file at its pre-sync content.

Entry shape:

```json
{
  "asset_path": ".claude/plugins/cla/skills/foo/SKILL.md",
  "adapted_content": "<full final file content, exactly as it should be written>",
  "change_summary": "Ported source's new Phase 3 section; kept local's Linear-ticket reference."
}
```

The `change_summary` is one line, two at most, and **explicit about what local
content was preserved**. Examples:

- `Adopted source's new --dry-run flag; kept local's Romanian-locale handling.`
- `Renamed paths to match local plugin name; no local content dropped.`
- `Adopted verbatim — NOTE: assumes a root package.json, which this repo doesn't have; discovery will silently return empty here (see rule 4).`
- `New file — adapted source examples to use local IBKR ports instead of mock ones.`

If a file needs no adaptation (the source applies cleanly with no local
strengths worth preserving), write the source verbatim as `adapted_content`
and set `change_summary` to `Adopted source verbatim — no local-specific
adjustments needed.`
