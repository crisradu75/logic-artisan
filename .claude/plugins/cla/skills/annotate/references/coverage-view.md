# Reading the coverage view

The change page derives a coverage view — which promises a task implements, and
which nothing does. **Report it as what it is: what the detector found.** Four
groups, and only the first is a finding:

- **Uncovered** — the bullet names a file or an identifier and no task names it
  back. Worth raising.
- **Not checkable** — the bullet names neither, so there was nothing to match on.
  Design and product bullets are prose, and prose is not a link, so
  many proposal bullets land here. Never present these as gaps.
- **Covered** — a task names the same file, or cites the bullet outright.
- **Not done** — a task whose box holds anything but `x` or `X`. Its own group, never added to
  Uncovered: an unstarted change has every task open, and reporting that as
  "18 uncovered" is the overclaim the whole tab exists to prevent.

The share of bullets in each group depends on how a repo writes its proposals:
prose-heavy proposals land mostly in *not checkable*. **Run
`python3 "${CLAUDE_PLUGIN_ROOT}/skills/annotate/scripts/sweep_changes.py" <changes folder>`
before relying on the tab, and quote the figures it prints for this repo, not a
figure from another one.**

**A page reporting `Nothing to check` means no `## What Changes` bullets were
parsed**, not that the change is clean. Say which it is.

A spec delta counts as named when the proposal mentions its capability anywhere,
under `## Impact` as much as `## Capabilities`; only a delta the proposal never
mentions is flagged.

**Never restate a coverage row as a defect in the change.** Say "no task names
this bullet's file", which is what was measured, rather than "this is not
implemented", which was not. The page states the same distinction; the reply must
not quietly upgrade it.
