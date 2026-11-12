Detail for items 9 to 12 of `SKILL.md`. Moved verbatim from `SKILL.md`; the write-nothing-yet rule is repeated there.

### 9. Read the existing state

- `cla.io/project-facts.md`, if present (a **reconcile**, not a from-scratch write).
- Every `cla.io/overlays/*.md` except the `*.local.md` files (glob generically — never a hardcoded
  skill list). Sort each line into one of five kinds:
  - **fact** — a command, path, port, install step or env file (anything the list above covers),
    unless only a rule in this overlay uses it;
  - **rule** — what this one skill must do here, with any path or command only that rule uses;
  - **incident** — a dated story. Pull out every rule it states for this repo ("Rule here: …",
    "before trusting X, check Y", "always pass …") and sort that as a rule; the rest is story;
  - **duplicate** — a rule the plugin or the repo's instruction files (`CLAUDE.md`, `AGENTS.md`) already state (say where);
  - **scaffolding** — headings, HTML comments, and the old pointer that sent readers to the
    retired `sync-context` skill for repo-wide facts.

  When unsure whether a line is a rule, call it one: a rule moved to the log is lost to every skill
  that does not read it. In a repo that has not migrated yet, overlays may still sit at
  `${CLAUDE_PLUGIN_ROOT}/skills/*/references/project-context.md`; glob that too and say which you
  found.
- `cla.io/project-tokens.local.md`, if present, for the conformance guard's current token list.
- `cla.io/terminology.md`, if present — only for item 11.

### 10. Draft the changes

1. **The full proposed `cla.io/project-facts.md`.** Open with a heading and one line saying it is this
   repo's facts file, maintained by `/cla:cla-setup` and checked by
   `${CLAUDE_PLUGIN_ROOT}/skills/cla-setup/scripts/check_fact_paths.py`. Fold in every fact line
   item 9 found in an overlay, under its section.
2. **Each overlay's change.** Remove the facts just folded in; where a fact sits inside a sentence
   that also states a rule, rewrite the sentence to keep the rule and point at the facts file.
   Keep every rule as written, and each rule pulled out of an incident as one or two lines under
   a dated heading. Move the incident's story to `cla.io/lessons-learned/lessons-learned.md`,
   appended at the end under a heading naming the overlay it came from (the log is newest-first,
   and these predate it; then apply the log's 6,000-word rule from `codify-learnings` Step 5); name any that would happen in any repo as a candidate for
   `/cla:report-upstream`. Drop duplicates and scaffolding. An overlay left with no rule is
   proposed for **deletion**: an absent overlay and an empty one mean the same thing, and the
   empty one invites facts back in.
3. **Legacy-location overlays are never edited.** One at
   `${CLAUDE_PLUGIN_ROOT}/skills/*/references/project-context.md` sits in the read-only plugin
   cache, so an edit fails or is discarded by the next update. Record a one-line migration
   recommendation instead: its facts to `cla.io/project-facts.md`, its rules to
   `cla.io/overlays/<skill>.md`.
4. **Test proof granularity**, when `openspec/` exists and the facts file has no `## Test proof`
   line: draft `- Test proof granularity: requirement` under a `## Test proof` heading, unless the
   user chooses `scenario` at item 13.

### 11. Optionally reconcile `cla.io/terminology.md`

If the file exists, scan it for near-duplicate terms (two entries naming the same concept with
different words) or conflicting definitions (one term defined two ways), and draft a merge or reword
for each. Absent file or no issues: skip silently.

### 12. Propose new `project-tokens.local.md` entries

If item 8 surfaced a new, distinctive app/package/service name (or other compound repo-specific
token) not yet in `cla.io/project-tokens.local.md`, draft the addition — distinctive compound tokens
only, never generic words that legitimately appear in portable prose; grep the plugin tree for each
candidate before proposing it.
