## Why

`multi-lite` and `multi-pr` each carried their own copy of how a chain merges a pull request.
Only `multi-lite`'s checked the remote checks, the recorded head and `--match-head-commit`, so
`multi-pr` could merge a head its review and tests never covered. `multi-pr`'s `stacked` and
`open all` policies were never used (`cla.io/decisions/plugin-surface-simplification-2026-10-08.md`,
P7 and P7a).

## What Changes

- One shared file, `skills/_shared/references/chain-merge.md`, holds the merge steps both chains
  run: bootstrap, the autonomy override's limits on merging, recording the head, the pre-merge
  checks, the merge command, confirming the merge, a host refusal, and a fix after a merge. Both
  skills point to it and drop their own copies.
- `multi-pr` records each PR's head and merges only through those checks, with
  `--match-head-commit`. A needed merge that cannot happen halts the chain.
- `multi-pr`'s `stacked` and `open all` policies are deleted. It merges each change a later change
  needs, and leaves every other PR open.

## Impact

- `change-chains`: "What an OpenSpec change chain merges" is rewritten under a new heading to say
  `multi-pr` merges only a prerequisite, and only on the head it checked.
- `small-change-chains`: no change; `multi-lite`'s behaviour is unchanged.
