# Proposal

## Why

Both marketplace catalogs pin the plugin to a `cla--v<version>` tag and are read from the default
branch. The release commit that moves those refs is merged first and the tag is pushed after, so
when the tag push fails or never happens every consuming repo's `marketplace update` fetches a ref
that does not exist. It happened at 2.0.0, and the catalogs on the default branch name
`cla--v2.4.0` while the remote has no such tag. Reordering cannot close the window:
`claude plugin tag` refuses until the manifest and the catalog agree, and a tag cut on the release
branch is not on the default branch after a squash merge.

## What Changes

- Add a repo-local, stdlib-only script, `check_catalog_tags.py`, beside the other release checks.
  It asks the remote for its tags once and exits 1 naming every catalog `ref` the remote lacks,
  0 when every one is there, and 2 when it could not read a catalog or ask the remote.
- `/release` runs it as a precondition, so an earlier dangling ref stops the next release, and as
  the postcondition after the tag push: the release is not reported done until it exits 0.

## Capabilities

### Modified Capabilities

- `plugin-distribution`: add a requirement that a release never ends with a catalog naming a tag
  the remote lacks.

## Impact

The new script and its tests, the repo-local release skill, the developer guide's script table and
the changelog. Nothing ships to consuming repos. No new dependency.
