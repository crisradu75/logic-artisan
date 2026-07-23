# spec-to-pr — Archive main-spec heading sanity (pre-archive checks)

Older main spec files (`openspec/specs/<capability>/spec.md`) predating various OpenSpec heading
conventions block the archive's materialization step. Before invoking `openspec archive`, run all
three checks below plus the retired-path grep. Apply all remediations in the **same PR** so the
heading fixes ship with the archive commit.

## (a) Section headers present

Missing `## Purpose` or `## Requirements` aborts with "Requirement header appears outside the main
`## Requirements` section":

```
grep -L '^## Requirements' openspec/specs/<capability>/spec.md
grep -L '^## Purpose' openspec/specs/<capability>/spec.md
```

If either returns the file path, edit the main spec to add the canonical headings (Purpose: one-line
capability description; Requirements: the section directly above the first `### Requirement:`).

## (b) Per-requirement `### Requirement:` prefix

Legacy specs use plain `### <Name>` headings; the materialization step matches MODIFIED blocks by
`### Requirement: <Name>` and aborts with `MODIFIED failed for header "### Requirement: X" - not
found` when the prefix is missing. Run:

```
grep -n '^### ' openspec/specs/<capability>/spec.md | grep -v '^.*:### Requirement: '
```

Each match is a legacy heading — rewrite it to `### Requirement: <Name>` before archiving.

## (c) MODIFIED-block heading existence

For every `## MODIFIED Requirements` block in the change's delta
(`openspec/changes/<name>/specs/<capability>/spec.md`), confirm the `### Requirement: <Name>` heading
exists *verbatim* in the active spec. If the delta **renames** a requirement (new name on the
heading, broader scope in the body), the active spec still has the **old** name and the
materialization aborts. Rename the active heading to the new name first, in the same archive commit.
Quick check:

```
# for each MODIFIED heading in the delta
grep -n '^### Requirement: ' openspec/changes/<name>/specs/<capability>/spec.md
# for each result, confirm an exact-string hit in the active spec
grep -F '### Requirement: <Name>' openspec/specs/<capability>/spec.md
```

## Retired-path cross-reference cleanup

**If the change retired any script/file:** before archiving, grep the active materialized spec
(`openspec/specs/<capability>/spec.md`) for cross-references to the retired path. The change's
spec-delta only replaces modified-requirement *blocks*; cross-refs in traceability matrices,
"Implementation" tables, or other non-modified requirements remain stale unless explicitly cleaned in
this PR. Add the cleanup edits to the active spec before running `openspec archive` so they ship with
the archive commit.

## Failure modes these checks catch

- A change can abort on (a) when the delta's target capability heading is missing from the active spec.
- A change with several legacy `### X` headings aborts on (b) until each is rewritten to
  `### Requirement: <Name>`, and can then abort again on (c) when a requirement was **renamed** in the
  delta while the active spec still carries the old heading name.
