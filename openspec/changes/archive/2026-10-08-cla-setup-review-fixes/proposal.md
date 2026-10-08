## Why

Review of `cla-setup-and-optional-overlays` found that cla-setup's overlay migration moved whole
dated incidents to the lessons log, rules inside them included, though most skills never read that
log; counted every path as a fact, so the memory location only codify-learnings reads would leave
its overlay; and accepted a pattern in `.git/info/exclude` as the repo's run-notes line, though that
file belongs to one clone.

## What Changes

- A rule stated inside an incident stays in the overlay as one or two lines; only the story moves.
  A path or command only one rule uses stays with that rule. The old `/cla:sync-context` pointer is
  scaffolding, so an overlay left with it alone is proposed for deletion.
- The run-notes check accepts only a match from a `.gitignore` in the repo. The chains' own check
  still accepts any source, since a run only needs git to ignore the notes locally.
- Each skill that reads a fact from the facts file says what to do when an old overlay may still
  hold it: run `/cla:cla-setup` to move it.
- The terminology entry format moves to a shared reference read by cla-setup and shape-decision.
- This repo: its three overlays migrated by hand; two are deleted.

## Impact

- `repo-context`: two requirements replaced (REMOVED and ADDED under new headings), one modified;
  still eight.
- `cla-setup`, `codify-learnings`, `lite-pr`, `multi-lite`, `multi-pr`, `new-worktree`,
  `project-review`, `review-change`, `shape-decision`, `spec-to-pr`, and their tests.
