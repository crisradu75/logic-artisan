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

**Then validate, because this remediation is the same class of edit as the one that has bitten.**
A live spec is a **parsed document, not a prose file**, and the flow treats an edit to one as if it
were a comment.

The measured failure was a hand-edit filling a **TBD `## Purpose`** — a heading that was present,
not missing — whose replacement text ended with a `## Requirements` heading while the original line
survived, leaving a **duplicate**. A second `## Requirements` *closes* the section, so every
requirement below it becomes invisible to `validate`, `list` and `archive`, and the file still reads
correctly to a human.

That was **not** this remediation, and the distinction is worth keeping straight: check (a) fires on
an *absent* heading, and adding one that is genuinely absent cannot duplicate it. What makes the two
the same class is the edit, not the cause — hand-writing canonical headings into a parsed document,
where the failure is silent and reads fine. Note also that the instruction above says "the canonical
headings", plural and unconditional, while the greps report them individually: **add only the
heading the grep actually reported missing.** Re-adding one that is already there is how the
duplicate gets made.

So: **any hand-edit under `openspec/specs/` is followed by**

```
openspec validate --specs --strict
```

**before the commit** — not `openspec validate <change> --strict`, which validates the change and
never looks at the live set. It needs no database and no build and takes seconds.

Measured in a six-change chain in a repo consuming this plugin, and reported here rather than
re-derived: two live specs were broken this way while working change 1, and nothing caught them —
the change's own archive had already run, and the repo's verify command never looks at live specs.
Both merged broken and surfaced one whole change later, as an aborted archive far from its cause.

## (b) Per-requirement `### Requirement:` prefix

Legacy specs use plain `### <Name>` headings; the materialization step matches MODIFIED blocks by
`### Requirement: <Name>` and aborts with `MODIFIED failed for header "### Requirement: X" - not
found` when the prefix is missing. Run:

```
grep -n '^### ' openspec/specs/<capability>/spec.md | grep -v '^.*:### Requirement: '
```

Each match is a legacy heading — rewrite it to `### Requirement: <Name>` before archiving. This is a hand-edit under `openspec/specs/` — the validate rule in check (a) applies to it too.

## (c) MODIFIED-block heading existence, and scenario retention under it

For every `## MODIFIED Requirements` block in the change's delta
(`openspec/changes/<name>/specs/<capability>/spec.md`), confirm the `### Requirement: <Name>` heading
exists *verbatim* in the active spec. If the delta **renames** a requirement (new name on the
heading, broader scope in the body), the active spec still has the **old** name and the
materialization aborts. Rename the active heading to the new name first, in the same archive commit. This is a hand-edit under `openspec/specs/` — the validate rule in check (a) applies to it too.
Quick check:

```
# for each MODIFIED heading in the delta
grep -n '^### Requirement: ' openspec/changes/<name>/specs/<capability>/spec.md
# for each result, confirm an exact-string hit in the active spec
grep -F '### Requirement: <Name>' openspec/specs/<capability>/spec.md
```

**A heading match is not retention.** The loop above has already located the live requirement, which
is the expensive half; stopping there leaves the scenario set unexamined, and a MODIFIED block
*replaces* its requirement rather than patching it — so a live scenario absent from the block is
deleted the moment `openspec archive` runs, with the block reading complete on its own face. So for
each heading confirmed present, compare the scenario sets before moving on, per
`${CLAUDE_PLUGIN_ROOT}/skills/_shared/references/modified-block-retention.md`.

**Why here as well as at review time.** This is the last point before materialization deletes
anything, and it is the only one that sees the window *after* review closes — a Revise-round edit to
the delta, a hand-resolved conflict in it. Review-time cannot look at either.

**On a current `openspec` the tool itself refuses, and this check still earns its place.**
`buildUpdatedSpec` in `core/specs-apply` calls `findMissingCurrentScenarios` and throws
`"<spec> MODIFIED failed ... current spec contains scenario(s) not present in the modified block"`,
so `openspec archive` aborts rather than dropping the scenario. Verified by reading the installed
package. **Do not restate a version boundary here** — not the release the guard landed in, and not
how far back it goes. An earlier draft asserted "from 1.11.0, and nothing before it refuses", which
was simply wrong for the versions in between; its replacement then quantified the correction
("predates 1.11.0 by several releases") with nothing behind the quantifier, which is the same defect
one size smaller. Both are the stale-fact-as-current-fact failure this whole reference exists to
catch, and a boundary written here decays the moment upstream cuts a release. Run
`openspec --version` and read `findMissingCurrentScenarios` in your own install if you need the
answer for a specific repo.

Where the tool does refuse, this check runs *before* it, which is the value: you get a named scenario
and an adjudication instead of a failed archive mid-commit. Where it does not, this check is the only
thing between the delta and a silently deleted `SHALL`.

**The comparison itself never halts, on either version.** Raise a `dropped` verdict as a **Critical
against the change** and carry it into the run's Issues so the PR shows it. Do not add a halt of your
own: a scenario renamed in place is indistinguishable from a deleted one, so a halt would fire on
legitimate renames — which is the complaint against the upstream refusal, not a shape to copy.

## Retired-path cross-reference cleanup

**If the change retired any script/file:** before archiving, grep the active materialized spec
(`openspec/specs/<capability>/spec.md`) for cross-references to the retired path. The change's
spec-delta only replaces modified-requirement *blocks*; cross-refs in traceability matrices,
"Implementation" tables, or other non-modified requirements remain stale unless explicitly cleaned in
this PR. Add the cleanup edits to the active spec — another hand-edit, so check (a)'s validate rule applies —
before running `openspec archive` so they ship with
the archive commit.

## Failure modes these checks catch

- A change can abort on (a) when the delta's target capability heading is missing from the active spec.
- A change with several legacy `### X` headings aborts on (b) until each is rewritten to
  `### Requirement: <Name>`, and can then abort again on (c) when a requirement was **renamed** in the
  delta while the active spec still carries the old heading name.
