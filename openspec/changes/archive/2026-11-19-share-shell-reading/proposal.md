# Proposal

## Why

An independent review found that only `ask-destructive-git` read the body of a shell wrapper. Every
other Bash guard read the command's text outside quotes, so `bash -c "echo hi > ../../x"`,
`eval "..."` and `bash -c 'git commit -m x -m "Measured-by: none"'` ran with no prompt and no block
while their bare forms were stopped. The reader lived inside that one 2,474-line hook, whose git
probes also spent the whole handler budget, leaving no room for another enforcing guard.

Two smaller gaps in the same hook came from parallel reviews: the pre-push guard gained an
`ALLOW_TAG_REWRITE=1` override that a command can carry like `ALLOW_PUSH_TO_MAIN=1`, and
`git push --mirror` can delete every remote branch and tag without the pre-push guard seeing it.

## What Changes

- Every Bash guard except the `cd` guard checks each body a shell wrapper hands on, as if typed bare.
  A `cd` inside a wrapper's own shell stays allowed; heredoc prose that names a wrapper is data.
- `ALLOW_TAG_REWRITE=1` typed into a push asks, like the other pre-push overrides.
- `git push --mirror` asks, with its own reason, wrapped or bare.
- Not in the specs, because no user sees them: the shell reader moves to a shared module the
  dispatcher reads once per call; the hook splits into its decision, its rule tables and its probes;
  its git probes share one deadline of half the old worst case.

## Capabilities

### Modified Capabilities

- `guard-hooks`: one requirement, for wrapped commands across the guards.
- `git-guards`: the pre-push skip requirement gains the tag override; one requirement for a mirror push.

## Impact

The hooks directory (three new shared modules, the Bash dispatcher, the dispatch library and
`ask-destructive-git`), their tests and mutation batches. No new dependency.
