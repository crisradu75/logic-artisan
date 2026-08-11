# multi-spec — change-plan file schema

Phase 1 derives the grouping this file records; **Phase 2 writes and commits it once, on the batch branch, before any change is authored** — its own small commit ahead of any proposal work, so the grouping/sequencing judgment itself is protected by the same durability discipline as everything downstream. (It's written in Phase 2 rather than Phase 1 because two of its required fields — `batch_slug` and `branch` — are only derived once the branch is set up in Phase 2, and because a Phase-1 commit would land on `<base-branch>`, which this skill may never push, so a "durability" commit there couldn't actually be pushed to survive a dead disk. See SKILL.md Phase 2's "Persist the plan now, on the branch.")

## Location

```
cla.io/decisions/<stem>.multi-spec-plan.json
```

Colocated with the source decisions file (`cla.io/decisions/<stem>.md`) — same directory, same stem, `.multi-spec-plan.json` suffix instead of `.md`. This keeps the plan discoverable next to the thing it was derived from, and matches this repo's existing convention that `cla.io/decisions/*` is committed, not gitignored — a convention learned the hard way, when an *untracked* decisions doc destroyed in an `rm -rf` worktree-junction incident had to be reconstructed by hand and only then committed (see memory `feedback-worktree-rmrf-junction-risk`).

## Shape

```json
{
  "decisions_file": "cla.io/decisions/<stem>.md",
  "batch_slug": "<batch-slug>",
  "branch": "docs/propose-<batch-slug>",
  "sequence_source": "file-sequencing-section | derived-judgment",
  "changes": [
    {
      "name": "<kebab-case-change-name>",
      "decisions_covered": [1, 2],
      "one_line_scope": "<what this change does, one line>",
      "depends_on": ["<other-change-name-in-this-batch>"]
    }
  ]
}
```

## Field intent

- `decisions_file` — repo-relative path to the source decisions file, so a resumed run (or a human) can re-open the exact input this plan was derived from.
- `batch_slug` / `branch` — echoed here rather than re-derived on resume, so a resumed run doesn't have to re-run the filename-stripping logic and risk a different slug than the one already used for the branch and commit messages.
- `sequence_source` — `file-sequencing-section` when Phase 1 found and trusted the decisions file's own "Sequencing" section; `derived-judgment` when no such section existed and the grouping came from the skill's own reasoning (or an escalated `opus` `Agent` call on a sub-Opus session). This is a transparency field, not a behavior switch — it tells a human (or a future resumed run) how much to trust the grouping versus re-checking it.
- `changes[].decisions_covered` — the numbered decisions (from the source file's "Decisions" section) this change implements. Lets a human trace a change back to its shaping rationale without re-reading the whole decisions file.
- `changes[].depends_on` — other change names **in this same batch** that must be authored (not necessarily merged — this batch lands in one PR, so "authored before" is the only ordering that matters here) before this one, so cross-references are accurate. This drives Phase 3's authoring order; it is not a build/merge dependency in the `multi-pr` sense.

## What this file is NOT

**Not a live status ledger.** It does not track which changes are authored/committed/reviewed — that would create a second source of truth that could drift from the actual git-tracked state of `openspec/changes/<name>/`. Resume always re-derives "is this change done" from the repository itself (Phase 3 step 1's tracked-file check), never from a status field in this plan. This mirrors `/cla:spec-to-pr`'s own resume philosophy: `probe_state.py` reads repo state, not a log file, specifically because a log can go stale or get lost in exactly the kind of local-machine incident this skill exists to survive — a plan file that also tried to be a status ledger would be exactly as fragile as the problem it's meant to solve.

**Not append-only / not a ledger of runs.** Unlike `spec-to-pr`'s `cla.io/retro/spec-to-pr-runs.jsonl` (one line appended per completed run, consumed by `/cla:spec-to-pr-retro`), this file is written once per batch and never appended to again. There is no retro tooling over it and none is planned — see `multi-spec`'s own "What this skill deliberately does not do."

## Resume read path

On re-invocation with the same (or the same auto-resolved-latest) decisions file:

1. Compute `<stem>` from the decisions file path. Check whether `cla.io/decisions/<stem>.multi-spec-plan.json` exists (tracked or not — either way it's cheap to read).
2. If it exists, parse it and skip Phase 1's grouping entirely — the plan is already decided. Use its `batch_slug`/`branch` values directly in Phase 2 rather than re-deriving them.
3. If it does not exist, this is a fresh run (or the very first attempt crashed before Phase 2 finished writing it) — run Phase 1's grouping in full, then Phase 2 writes the plan.

A plan file that exists but is **untracked** (a crash landed between Phase 2's Write and its commit) is still safe to read and trust — re-deriving the grouping is wasted work the file already did; just commit + push it (`git add -- <the plan file>` then `git commit`, as Phase 2 does) before proceeding to Phase 3.
