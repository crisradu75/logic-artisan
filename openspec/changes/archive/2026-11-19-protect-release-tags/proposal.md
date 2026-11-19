# Proposal

## Why

Two findings from an independent architecture review.

- "A published tag is never moved" is prose only. `git push --delete origin <tag>` and
  `git push origin :refs/tags/<tag>` pass every guard: the shipped `pre-push` hook matches only the
  default branch.
- The release window is detected, not prevented. The release commit is squash-merged first, so the
  default branch's catalogs name the new tag before it exists on the remote; that happened at 2.0.0
  and 2.4.0. `check_catalog_tags.py` only reports it after the fact.

## What Changes

- The shipped `pre-push` hook refuses a push that deletes a tag on the remote or moves a tag the
  remote already has, for any tag name, lightweight or annotated. Creating a new tag stays allowed.
  `ALLOW_TAG_REWRITE=1` lifts only this refusal, and `ALLOW_PUSH_TO_MAIN=1` now lifts only the
  default-branch refusal instead of disarming the whole hook.
- The repo-local `/release` skill tags the release PR's head commit, pushes the tag and proves it is
  on the remote with `check_catalog_tags.py --expect`, and only then merges the PR with
  `gh pr merge --merge --match-head-commit <tagged sha>`, never a squash or rebase merge. If the PR
  needs another commit after the tag push, the release restarts as the next version and the tag
  stays where it is.

## Capabilities

### Modified Capabilities

- `git-guards`: add a requirement that a push deleting or moving a remote tag is refused.
- `plugin-distribution`: add a requirement that a release is tagged before its catalogs name it.

## Impact

`hooks/git/pre-push` ships to every consuming repo; a consumer picks the change up by re-running the
install copy. `ask-destructive-git.py` does not yet ask before a command carrying
`ALLOW_TAG_REWRITE=1`; that change is handed to the PR refactoring the Python hooks. The repo-local
release skill, its checker's docstring, the hook's tests and mutation batch. No new dependency.
