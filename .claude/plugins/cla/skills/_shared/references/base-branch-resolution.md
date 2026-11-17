# Base-branch resolution (hard rule)

`<base-branch>` means THIS repo's default branch, resolved — never assumed. Every command that
names it is a placeholder, not a literal: substitute the real name before running anything.
Resolve it once, at the start of the run, with `git symbolic-ref --quiet refs/remotes/origin/HEAD`
(take the segment after the last `/`); if that is unset, use whichever of `main` / `master`
actually exists. Never hardcode `master`: in a `main`-default repo a `master..HEAD` range fails
with `unknown revision`, and `git checkout master` cannot succeed.

Shared by `multi-lite`, `multi-pr`, and `multi-spec`, which all chain per-change work against
`<base-branch>` in the primary clone. Edit this file once; it is the single source of truth.
