# Proposal

## Why

`/cla:cla-setup` promises, in prose only, to leave certain files of a repo alone: the instruction
files stay byte-identical, an existing feedback `notes.md` is always skipped, machine-read
`*.local.md` files are never reshaped, and the terminology file and overlays are never created and
change only on the owner's yes. About seven rules state these promises and nothing checks them
(check 5 of `cla.io/audits/rule-enforcement-2026-11-18.md`, principle 3 of the foundation decision).
The harm is to the user's own files, a protected area.

## What Changes

- Add a shipped, stdlib-only script, `setup_guard.py`, with two subcommands: `snapshot` (the first
  step of a run: the SHA-256 or absence of each protected file, and the list of overlays, in a JSON
  file outside the repo) and `verify` (the last step: each protected file changed, created or deleted
  without an `--approved` yes, and each overlay or terminology file created). Exit 0 passes, 1 is a
  problem, 2 means it could not check and is never a pass.
- `cla-setup/SKILL.md` runs the snapshot before item 1 and the check after item 13, passes each
  yes-confirmed protected file as `--approved`, and on exit 1 reports what changed and does not call
  the run clean.

## Capabilities

### Modified Capabilities

- `cla-setup`: add requirements that the run checks its protected files and creates no overlay or
  terminology file.

## Impact

The new script and its tests, `cla-setup/SKILL.md`, the rule ledger, the developer guide's script
table and the changelog. No new dependency.
