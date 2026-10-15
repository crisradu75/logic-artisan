# Proposal

## Why

Review suggestions left in `TODO.md` after the Purpose note shipped in `check_spec_proof.py`: the
note repeats on every run for old specs in a repo that installs the plugin, a hard-wrapped `**Serves:**`
line draws a false note, one stray backtick can hide a sentence break, a live spec with several
scenario-less requirements is told only the generic line, and the final print crashes on a cp1252
console. The spec-proof spec also never said the `NOTE purpose:` behaviour exists.

## What Changes

- `purpose_notes` runs only over the live specs the branch touches: a live spec file the branch
  changed, or a spec named by a changed or untracked delta of any change. It reuses the changed-path
  list the checker already builds for the changed-requirement rule. With no default branch to compare
  with, every live spec is noted, and the output says which.
- A Serves line may be hard-wrapped: when a blank line follows the first Purpose paragraph, that
  whole paragraph is the Serves line. A Purpose with no blank line keeps the old reading (first line
  is the Serves line).
- A backtick left unpaired no longer hides a sentence break: code spans pair backtick runs of equal
  length, and when any backtick stays unpaired no span is masked.
- In scenario mode, a live spec with no scenario at all also names each requirement heading that has
  none, after the generic line.
- Reading a file at the base commit uses `git cat-file blob` instead of `git show`. On Windows `git show
  <sha>:<path>` fails with "Filename too long" when the working directory plus the argument pass 260
  characters, and the checker read that failure as "new file", so every archived unit counted as
  changed and drew a false `uncovered`. Now only a path git confirms is absent counts as new; any other
  failure exits 2.
- The final print replaces a character the console cannot encode, and is unchanged on UTF-8.
- Spec delta: `spec-proof` gains one requirement for the `NOTE purpose:` behaviour (6 in all).

Out of scope: the `manual: <heading>` line format, which needs a tasks-rule change.

## Capabilities

### Modified Capabilities

- `spec-proof`: one requirement added.

## Impact

`check_spec_proof.py`, its tests, `TODO.md` (the fixed lines removed).
