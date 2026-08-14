# Base-branch resolution (hard rule)

`<base-branch>` means THIS repo's default branch, resolved — never assumed. Every command that
names it is a placeholder, not a literal: substitute the real name before running anything.
Resolve it once, at the start of the run, with `git symbolic-ref --quiet refs/remotes/origin/HEAD`
(take the segment after the last `/`); if that is unset, use whichever of `main` / `master`
actually exists. The harness used to hardcode `master`, which silently broke every `main`-default
repo — a `master..HEAD` range there fails outright with `unknown revision` rather than returning a
wrong answer, and `git checkout master` cannot succeed at all.

Shared verbatim by `multi-lite`, `multi-pr`, and `multi-spec` (all three chain per-change work
against `<base-branch>` in the primary clone) — previously copy-pasted identically into each
SKILL.md, so a fix to the resolution logic (like the master→main bug above) had to be
hand-reapplied to all three. Edit this file once; it's the single source of truth for all three.
