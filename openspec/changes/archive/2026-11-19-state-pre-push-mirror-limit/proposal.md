# Proposal

## Why

Review of PR #556 found that the git-guards requirements overstate the `pre-push` hook. git writes
no line on the hook's stdin for a deletion `git push --mirror` makes, so a mirror push from a clone
that lacks a tag or a protected branch deletes it on the remote without the hook being asked.
Verified: `git clone --no-tags <remote>` then `git push --mirror origin` deleted every remote tag.
A `--prune` push, `--delete` and `:<ref>` do reach the hook and are refused. A hook cannot close
this gap, so the requirements state it instead of claiming more than the hook does.

## What Changes

- The three push requirements in `git-guards` (main and master, the remote's default branch, tags)
  each say that a deletion git does not report to the hook, as in a mirror push, is outside what it
  can refuse. Every scenario is kept.
- The hook's header names the limit, and two tests pin it: a mirror push deletes a remote tag and a
  protected branch without the hook seeing either line, while `--prune` and `--delete` stay refused.
- The tag refusal message also suggests `git fetch --tags --force` for stale local tags, since a
  non-forced `git push --tags` carrying one stale tag is now refused whole.

## Capabilities

### Modified Capabilities

- `git-guards`: three push requirements gain the mirror-push exception.

## Impact

`hooks/git/pre-push` (comments and one message line, no decision logic) and its tests. No new
dependency.
